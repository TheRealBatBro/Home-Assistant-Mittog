"""Config flow.

The config entry is just the "Mittog" hub. Every station is a subentry, so one
install can watch any number of stations, and the same station can be added once
per direction.

Adding a station takes three steps:
1. station: one searchable list of every board ("Vinge (S-tog)", "København H (Tog)").
2. direction: the directions trains actually leave in, read from the live board and
   labelled by where they go ("Towards Klampenborg, Svanemøllen · next stop Ølstykke").
3. filters: stops, lines and tracks, offering only what runs in that direction.
"""

from __future__ import annotations

from collections import Counter
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import stations
from .api import Board, Departure, MittogError, async_fetch_board
from .const import (
    BOTH_DIRECTIONS,
    CONF_DELAY_THRESHOLD,
    CONF_DIRECTION,
    CONF_HIDE_CANCELLED,
    CONF_LINES,
    CONF_MAX_DEPARTURES,
    CONF_SERVICE,
    CONF_STATION,
    CONF_TOWARDS,
    CONF_TRACKS,
    DEFAULT_DELAY_THRESHOLD,
    DEFAULT_MAX_DEPARTURES,
    DIRECTIONS,
    DOMAIN,
    S_TRAIN_LINES,
    SERVICE_STOG,
    SERVICES,
    SUBENTRY_STATION,
)
from .coordinator import parse_filter

_LOGGER = logging.getLogger(__name__)

HUB_TITLE = "Mittog"
BOARD_LABEL = {SERVICE_STOG: "S-tog", "tog": "Tog"}
HUB = "KH"

# Labels built from live data can't come from translation files.
TEXT = {
    "en": {
        "towards": "Towards {dest}",
        "next_stop": "next stop {stop}",
        "via": "via {stop}",
        "both": "Both directions",
        "generic": "Direction {n}",
    },
    "da": {
        "towards": "Mod {dest}",
        "next_stop": "næste stop {stop}",
        "via": "via {stop}",
        "both": "Begge retninger",
        "generic": "Retning {n}",
    },
}


def _number(lo: int, hi: int, unit: str | None = None) -> NumberSelector:
    config = NumberSelectorConfig(min=lo, max=hi, step=1, mode=NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


def board_label(service: str, code: str) -> str:
    return f"{stations.name(code)} ({BOARD_LABEL[service]})"


def station_choices() -> dict[str, tuple[str, str]]:
    """Picker label -> (service, code) for every board mittog.dk has.

    The label doubles as the option value: HA shows a searchable picker's raw value
    once something is picked, so the value has to be readable.
    """
    choices = {
        board_label(service, s.code): (service, s.code)
        for service in SERVICES
        for s in stations.for_service(service)
    }
    return dict(sorted(choices.items(), key=lambda item: item[0].casefold()))


def resolve_station(value: str) -> tuple[str, str] | None:
    """A picked label, or a typed station code (as in the mittog.dk URL) or exact name."""
    choices = station_choices()
    value = value.strip()
    if value in choices:
        return choices[value]
    folded = value.casefold()
    for label, choice in choices.items():
        if label.casefold() == folded:
            return choice
    code = stations.normalize(value.upper())
    matches = [c for c in choices.values() if c[1] == code]
    if not matches:
        matches = [c for c in choices.values() if stations.name(c[1]).casefold() == folded]
    # A name or code shared by both boards (e.g. KH) is ambiguous: prefer S-tog.
    matches.sort(key=lambda c: c[0] != SERVICE_STOG)
    return matches[0] if matches else None


def _in_direction(board: Board | None, direction: str) -> list[Departure]:
    if board is None:
        return []
    if direction == BOTH_DIRECTIONS:
        return list(board.departures)
    return [d for d in board.departures if d.direction == direction]


def _destinations(departures: list[Departure]) -> list[str]:
    """Destinations, farthest (longest remaining route) first."""
    reach: dict[str, int] = {}
    for dep in departures:
        for dest in dep.destinations:
            reach[dest] = max(reach.get(dest, 0), len(dep.stops))
    return sorted(reach, key=lambda code: -reach[code])


def direction_options(board: Board | None, language: str) -> list[SelectOptionDict]:
    text = TEXT["da" if language.startswith("da") else "en"]
    options = []
    for n, direction in enumerate(DIRECTIONS, start=1):
        deps = _in_direction(board, direction)
        if deps:
            dests = _destinations(deps)[:3]
            label = text["towards"].format(dest=", ".join(stations.name(c) for c in dests))
            # Everyone knows where København H is; say so when this way passes it.
            if HUB not in dests and any(HUB in d.stops for d in deps):
                label += f" · {text['via'].format(stop=stations.name(HUB))}"
            next_stops = Counter(d.stops[0] for d in deps if d.stops)
            if next_stops and (stop := next_stops.most_common(1)[0][0]) not in dests:
                label += f" · {text['next_stop'].format(stop=stations.name(stop))}"
            options.append(SelectOptionDict(value=direction, label=label))
    if not options:
        # Empty board (night, or feed down): nothing to name the directions by.
        options = [
            SelectOptionDict(value=d, label=text["generic"].format(n=n))
            for n, d in enumerate(DIRECTIONS, start=1)
        ]
    options.append(SelectOptionDict(value=BOTH_DIRECTIONS, label=text["both"]))
    return options


def direction_destinations(board: Board | None, direction: str) -> list[str]:
    return _destinations(_in_direction(board, direction))


def title_for(service: str, code: str, destinations: list[str]) -> str:
    station = stations.get(code)
    title = stations.name(code)
    if station and len(station.services) > 1:
        title += f" ({BOARD_LABEL[service]})"
    if destinations:
        title += " → " + ", ".join(stations.name(c) for c in destinations[:2])
    return title


def unique_id_for(data: dict[str, Any]) -> str:
    def part(key: str) -> str:
        return ",".join(sorted(v.casefold() for v in parse_filter(data.get(key))))

    return "|".join(
        (
            data[CONF_SERVICE],
            data[CONF_STATION],
            data.get(CONF_DIRECTION) or BOTH_DIRECTIONS,
            part(CONF_TOWARDS),
            part(CONF_LINES),
            part(CONF_TRACKS),
        )
    )


def _multi(options: list[SelectOptionDict] | list[str], custom: bool = False) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            multiple=True,
            mode=SelectSelectorMode.DROPDOWN,
            custom_value=custom,
            sort=False,
        )
    )


class _StationSteps:
    """Steps shared by the first setup and the add-station subentry flow."""

    hass: Any

    def _station_steps_init(self) -> None:
        self._service = SERVICE_STOG
        self._station = ""
        self._board: Board | None = None
        self._direction = BOTH_DIRECTIONS
        self._defaults: dict[str, Any] = {}

    # Step 1: station ------------------------------------------------------------

    def _station_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(CONF_STATION): SelectSelector(
                    SelectSelectorConfig(
                        options=list(station_choices()),
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                        sort=False,
                    )
                )
            }
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        if (abort := self._abort_before_start()) is not None:
            return abort
        await self.hass.async_add_executor_job(stations.load_catalogue)
        errors: dict[str, str] = {}
        if user_input is not None:
            choice = resolve_station(user_input.get(CONF_STATION) or "")
            if choice is None:
                errors[CONF_STATION] = "unknown_station"
            else:
                self._service, self._station = choice
                if await self._load_board():
                    return await self.async_step_direction()
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="user", data_schema=self._station_schema(), errors=errors)

    def _abort_before_start(self) -> Any:
        return None

    async def _load_board(self) -> bool:
        try:
            self._board = await async_fetch_board(
                async_get_clientsession(self.hass), self._service, self._station, timeout=20
            )
        except MittogError as err:
            _LOGGER.debug("Could not read %s/%s: %s", self._service, self._station, err)
            self._board = None
            return False
        return True

    def _placeholders(self) -> dict[str, str]:
        count = len(self._board.departures) if self._board else 0
        return {"station": board_label(self._service, self._station), "count": str(count)}

    # Step 2: direction ----------------------------------------------------------

    async def async_step_direction(self, user_input: dict[str, Any] | None = None) -> Any:
        if user_input is not None:
            self._direction = user_input[CONF_DIRECTION]
            return await self.async_step_filters()
        options = direction_options(self._board, self.hass.config.language or "en")
        default = self._defaults.get(CONF_DIRECTION) or options[0]["value"]
        return self.async_show_form(
            step_id="direction",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DIRECTION, default=default): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST, sort=False)
                    )
                }
            ),
            description_placeholders=self._placeholders(),
        )

    # Step 3: filters ------------------------------------------------------------

    def _filters_schema(self) -> vol.Schema:
        deps = _in_direction(self._board, self._direction)
        here = self._station
        reach: dict[str, int] = {}
        for dep in deps:
            for i, code in enumerate(dep.stops + dep.destinations):
                if code != here:
                    reach[code] = min(reach.get(code, 999), i)
        # Stations in route order: the nearest stops first.
        stops = [SelectOptionDict(value=c, label=stations.name(c)) for c in sorted(reach, key=reach.get)]
        lines = sorted({d.line for d in deps}) or (
            list(S_TRAIN_LINES) if self._service == SERVICE_STOG else []
        )
        tracks = sorted({d.track for d in deps if d.track}, key=lambda t: (len(t), t))
        d = self._defaults
        return vol.Schema(
            {
                vol.Optional(CONF_TOWARDS, default=list(d.get(CONF_TOWARDS) or [])): _multi(stops, custom=not stops),
                vol.Optional(CONF_LINES, default=list(d.get(CONF_LINES) or [])): _multi(lines, custom=True),
                vol.Optional(CONF_TRACKS, default=sorted(parse_filter(d.get(CONF_TRACKS)))): _multi(tracks, custom=True),
                vol.Required(
                    CONF_MAX_DEPARTURES, default=d.get(CONF_MAX_DEPARTURES, DEFAULT_MAX_DEPARTURES)
                ): _number(1, 30),
                vol.Required(
                    CONF_DELAY_THRESHOLD, default=d.get(CONF_DELAY_THRESHOLD, DEFAULT_DELAY_THRESHOLD)
                ): _number(1, 60, "min"),
                vol.Required(
                    CONF_HIDE_CANCELLED, default=d.get(CONF_HIDE_CANCELLED, False)
                ): BooleanSelector(),
            }
        )

    def _filters_data(self, user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        errors: dict[str, str] = {}
        towards: list[str] = []
        for value in user_input.get(CONF_TOWARDS) or []:
            code = stations.normalize(value.strip())
            if stations.get(code) is None:
                code = next(
                    (s.code for s in stations.for_service(self._service)
                     if s.name.casefold() == value.strip().casefold()),
                    "",
                )
            if not code:
                errors[CONF_TOWARDS] = "unknown_station"
            elif code == self._station:
                errors[CONF_TOWARDS] = "towards_self"
            elif code not in towards:
                towards.append(code)
        data = {
            CONF_SERVICE: self._service,
            CONF_STATION: self._station,
            CONF_DIRECTION: self._direction,
            CONF_TOWARDS: towards,
            CONF_LINES: [v.strip() for v in user_input.get(CONF_LINES) or [] if v.strip()],
            CONF_TRACKS: sorted(parse_filter(user_input.get(CONF_TRACKS))),
            CONF_MAX_DEPARTURES: int(user_input[CONF_MAX_DEPARTURES]),
            CONF_DELAY_THRESHOLD: int(user_input[CONF_DELAY_THRESHOLD]),
            CONF_HIDE_CANCELLED: bool(user_input[CONF_HIDE_CANCELLED]),
        }
        return data, errors

    def _title(self, data: dict[str, Any]) -> str:
        if data[CONF_TOWARDS]:
            return title_for(self._service, self._station, data[CONF_TOWARDS])
        if self._direction == BOTH_DIRECTIONS:
            return title_for(self._service, self._station, [])
        deps = _in_direction(self._board, self._direction)
        if self._station != HUB and any(HUB in d.stops for d in deps):
            # "Vinge → København H" stays right when trains turn back early at night.
            return title_for(self._service, self._station, [HUB])
        dests = direction_destinations(self._board, self._direction)
        if not dests:
            # Nothing on the board to name it by; keep a readable, unique title.
            return title_for(self._service, self._station, []) + f" ({self._direction.lower()})"
        return title_for(self._service, self._station, dests)

    async def async_step_filters(self, user_input: dict[str, Any] | None = None) -> Any:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = self._filters_data(user_input)
            if not errors:
                return self._finish(data)
            self._defaults = {**self._defaults, **user_input}
        return self.async_show_form(
            step_id="filters",
            data_schema=self._filters_schema(),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    def _finish(self, data: dict[str, Any]) -> Any:
        raise NotImplementedError


class MittogConfigFlow(_StationSteps, ConfigFlow, domain=DOMAIN):
    """Create the hub together with its first station."""

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._station_steps_init()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_STATION: StationSubentryFlow}

    def _abort_before_start(self) -> ConfigFlowResult | None:
        if self._async_current_entries():
            return self.async_abort(reason="already_configured_hub")
        return None

    def _finish(self, data: dict[str, Any]) -> ConfigFlowResult:
        return self.async_create_entry(
            title=HUB_TITLE,
            data={},
            subentries=[
                ConfigSubentryData(
                    subentry_type=SUBENTRY_STATION,
                    title=self._title(data),
                    unique_id=unique_id_for(data),
                    data=data,
                )
            ],
        )


class StationSubentryFlow(_StationSteps, ConfigSubentryFlow):
    """Add another station (or another direction for a station), or edit one."""

    def __init__(self) -> None:
        super().__init__()
        self._station_steps_init()
        self._reconfiguring = False

    def _duplicate(self, unique_id: str, ignore: str | None = None) -> bool:
        return any(
            sub.unique_id == unique_id and sub.subentry_id != ignore
            for sub in self._get_entry().subentries.values()
        )

    def _finish(self, data: dict[str, Any]) -> SubentryFlowResult:
        unique_id = unique_id_for(data)
        if self._reconfiguring:
            subentry = self._get_reconfigure_subentry()
            if self._duplicate(unique_id, ignore=subentry.subentry_id):
                return self.async_abort(reason="already_configured")
            return self.async_update_and_abort(
                self._get_entry(), subentry, title=self._title(data), data=data, unique_id=unique_id
            )
        if self._duplicate(unique_id):
            return self.async_abort(reason="already_configured")
        return self.async_create_entry(title=self._title(data), data=data, unique_id=unique_id)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Edit direction and filters; the station itself stays."""
        await self.hass.async_add_executor_job(stations.load_catalogue)
        subentry = self._get_reconfigure_subentry()
        self._reconfiguring = True
        self._service = subentry.data[CONF_SERVICE]
        self._station = subentry.data[CONF_STATION]
        self._defaults = dict(subentry.data)
        if CONF_DIRECTION not in subentry.data:
            # Made before directions existed, when "towards" was the only way to pick a
            # direction; it drops trains that turn back early, so start clean.
            self._defaults.pop(CONF_TOWARDS, None)
        await self._load_board()
        return await self.async_step_direction()
