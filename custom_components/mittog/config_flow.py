"""Config flow.

The config entry is just the "Mittog" hub. Every station is a subentry, so one
install can watch any number of stations, and the same station can be added
several times with different directions (e.g. once towards København H and once
towards Frederikssund).
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
    TextSelector,
)

from . import stations
from .api import Board, MittogError, async_fetch_board
from .const import (
    CONF_DELAY_THRESHOLD,
    CONF_HIDE_CANCELLED,
    CONF_LINES,
    CONF_MAX_DEPARTURES,
    CONF_SERVICE,
    CONF_STATION,
    CONF_TOWARDS,
    CONF_TRACKS,
    DEFAULT_DELAY_THRESHOLD,
    DEFAULT_MAX_DEPARTURES,
    DOMAIN,
    S_TRAIN_LINES,
    SERVICE_STOG,
    SERVICES,
    SUBENTRY_STATION,
)
from .coordinator import parse_filter

_LOGGER = logging.getLogger(__name__)

HUB_TITLE = "Mittog"
QUERY = "query"


def _number(lo: int, hi: int, unit: str | None = None) -> NumberSelector:
    config = NumberSelectorConfig(min=lo, max=hi, step=1, mode=NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


MAX_MATCHES = 30


def search_stations(query: str, service: str) -> list[stations.Station]:
    """Stations on this board matching a typed name or a mittog.dk station code.

    An exact code (as in the mittog.dk URL, e.g. VNG) or exact name wins outright;
    otherwise names starting with the text come first, then names containing it.
    """
    query = query.strip()
    candidates = stations.for_service(service)
    if not query:
        return []
    code = stations.normalize(query.upper())
    folded = query.casefold()
    exact = [s for s in candidates if s.code == code or s.name.casefold() == folded]
    if exact:
        return exact[:1]
    starts = [s for s in candidates if s.name.casefold().startswith(folded)]
    contains = [s for s in candidates if folded in s.name.casefold() and s not in starts]
    return (starts + contains)[:MAX_MATCHES]


def _towards_options(board: Board | None, service: str, here: str) -> list[SelectOptionDict]:
    """Stations the trains from here actually call at; the whole network if offline."""
    codes: list[str]
    if board and board.departures:
        seen: Counter[str] = Counter()
        for dep in board.departures:
            seen.update(set(dep.stops) | set(dep.destinations))
        codes = [c for c in seen if c != here]
    else:
        codes = [s.code for s in stations.for_service(service) if s.code != here]
    return sorted(
        (SelectOptionDict(value=c, label=stations.name(c)) for c in codes),
        key=lambda o: o["label"].casefold(),
    )


def _line_options(board: Board | None, service: str) -> list[str]:
    if service == SERVICE_STOG:
        return list(S_TRAIN_LINES)
    lines = sorted({d.line for d in board.departures}) if board else []
    return lines or ["Re", "IC", "ICL", "Øresundståg", "L", "RA", "MJ", "RE"]


def title_for(service: str, code: str, towards: list[str]) -> str:
    station = stations.get(code)
    title = stations.name(code)
    if station and len(station.services) > 1:
        title += " (S-tog)" if service == SERVICE_STOG else " (tog)"
    if towards:
        title += " → " + ", ".join(stations.name(c) for c in towards)
    return title


def unique_id_for(data: dict[str, Any]) -> str:
    def part(key: str) -> str:
        return ",".join(sorted(v.casefold() for v in parse_filter(data.get(key))))

    return "|".join(
        (data[CONF_SERVICE], data[CONF_STATION], part(CONF_TOWARDS), part(CONF_LINES), part(CONF_TRACKS))
    )


class _StationSteps:
    """Station and direction steps shared by the first setup and the subentry flow."""

    hass: Any
    _service: str
    _station: str
    _board: Board | None
    _defaults: dict[str, Any]

    def _station_steps_init(self) -> None:
        self._service = SERVICE_STOG
        self._station = ""
        self._board = None
        self._defaults = {}
        self._matches: list[stations.Station] = []

    def _service_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_SERVICE, default=SERVICE_STOG): SelectSelector(
                    SelectSelectorConfig(
                        options=list(SERVICES),
                        mode=SelectSelectorMode.LIST,
                        translation_key=CONF_SERVICE,
                    )
                )
            }
        )

    def _search_schema(self) -> vol.Schema:
        return vol.Schema({vol.Required(QUERY): TextSelector()})

    def _pick_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_STATION, default=self._matches[0].code): SelectSelector(
                    SelectSelectorConfig(
                        options=[SelectOptionDict(value=m.code, label=m.name) for m in self._matches],
                        mode=SelectSelectorMode.LIST,
                        sort=False,
                    )
                )
            }
        )

    async def async_step_station(self, user_input: dict[str, Any] | None = None) -> Any:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._matches = search_stations(user_input[QUERY], self._service)
            if len(self._matches) == 1:
                return await self._station_chosen(self._matches[0].code)
            if self._matches:
                return await self.async_step_pick_station()
            errors[QUERY] = "no_match"
        return self.async_show_form(step_id="station", data_schema=self._search_schema(), errors=errors)

    async def async_step_pick_station(self, user_input: dict[str, Any] | None = None) -> Any:
        if user_input is not None:
            return await self._station_chosen(user_input[CONF_STATION])
        return self.async_show_form(
            step_id="pick_station",
            data_schema=self._pick_schema(),
            description_placeholders={"count": str(len(self._matches))},
        )

    async def _station_chosen(self, code: str) -> Any:
        self._station = code
        await self._load_board()
        return await self.async_step_direction()

    def _direction_schema(self) -> vol.Schema:
        d = self._defaults
        return vol.Schema(
            {
                vol.Optional(CONF_TOWARDS, default=list(d.get(CONF_TOWARDS, []))): SelectSelector(
                    SelectSelectorConfig(
                        options=_towards_options(self._board, self._service, self._station),
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                        sort=False,
                    )
                ),
                vol.Optional(CONF_LINES, default=list(d.get(CONF_LINES, []))): SelectSelector(
                    SelectSelectorConfig(
                        options=_line_options(self._board, self._service),
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
                vol.Optional(CONF_TRACKS, default=d.get(CONF_TRACKS, "")): TextSelector(),
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

    async def _load_board(self) -> None:
        try:
            self._board = await async_fetch_board(
                async_get_clientsession(self.hass), self._service, self._station, timeout=20
            )
        except MittogError as err:
            _LOGGER.debug("Could not preview %s/%s: %s", self._service, self._station, err)
            self._board = None

    def _placeholders(self) -> dict[str, str]:
        count = len(self._board.departures) if self._board else 0
        return {"station": stations.name(self._station) if self._station else "", "count": str(count)}

    def _direction_data(self, user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        errors: dict[str, str] = {}
        towards: list[str] = []
        for value in user_input.get(CONF_TOWARDS) or []:
            code = stations.normalize(value.strip())
            if stations.get(code) is None:
                # Typed a name rather than picking from the list.
                code = next(
                    (s.code for s in stations.for_service(self._service) if s.name.casefold() == value.strip().casefold()),
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
            CONF_TOWARDS: towards,
            CONF_LINES: [v.strip() for v in user_input.get(CONF_LINES) or [] if v.strip()],
            CONF_TRACKS: ", ".join(sorted(parse_filter(user_input.get(CONF_TRACKS)))),
            CONF_MAX_DEPARTURES: int(user_input[CONF_MAX_DEPARTURES]),
            CONF_DELAY_THRESHOLD: int(user_input[CONF_DELAY_THRESHOLD]),
            CONF_HIDE_CANCELLED: bool(user_input[CONF_HIDE_CANCELLED]),
        }
        return data, errors


class MittogConfigFlow(_StationSteps, ConfigFlow, domain=DOMAIN):
    """Create the hub together with its first station."""

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._station_steps_init()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_STATION: StationSubentryFlow}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="already_configured_hub")
        await self.hass.async_add_executor_job(stations.load_catalogue)
        if user_input is not None:
            self._service = user_input[CONF_SERVICE]
            return await self.async_step_station()
        return self.async_show_form(step_id="user", data_schema=self._service_schema())

    async def async_step_direction(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = self._direction_data(user_input)
            if not errors:
                return self.async_create_entry(
                    title=HUB_TITLE,
                    data={},
                    subentries=[
                        ConfigSubentryData(
                            subentry_type=SUBENTRY_STATION,
                            title=title_for(self._service, self._station, data[CONF_TOWARDS]),
                            unique_id=unique_id_for(data),
                            data=data,
                        )
                    ],
                )
            self._defaults = user_input
        return self.async_show_form(
            step_id="direction",
            data_schema=self._direction_schema(),
            errors=errors,
            description_placeholders=self._placeholders(),
        )


class StationSubentryFlow(_StationSteps, ConfigSubentryFlow):
    """Add another station (or another direction for a station), or edit one."""

    def __init__(self) -> None:
        super().__init__()
        self._station_steps_init()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        await self.hass.async_add_executor_job(stations.load_catalogue)
        if user_input is not None:
            self._service = user_input[CONF_SERVICE]
            return await self.async_step_station()
        return self.async_show_form(step_id="user", data_schema=self._service_schema())

    def _duplicate(self, unique_id: str, ignore: str | None = None) -> bool:
        return any(
            sub.unique_id == unique_id and sub.subentry_id != ignore
            for sub in self._get_entry().subentries.values()
        )

    async def async_step_direction(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = self._direction_data(user_input)
            if not errors:
                unique_id = unique_id_for(data)
                if self._duplicate(unique_id):
                    return self.async_abort(reason="already_configured")
                return self.async_create_entry(
                    title=title_for(self._service, self._station, data[CONF_TOWARDS]),
                    data=data,
                    unique_id=unique_id,
                )
            self._defaults = user_input
        return self.async_show_form(
            step_id="direction",
            data_schema=self._direction_schema(),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        await self.hass.async_add_executor_job(stations.load_catalogue)
        subentry = self._get_reconfigure_subentry()
        if user_input is None:
            self._service = subentry.data[CONF_SERVICE]
            self._station = subentry.data[CONF_STATION]
            self._defaults = dict(subentry.data)
            await self._load_board()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = self._direction_data(user_input)
            if not errors:
                unique_id = unique_id_for(data)
                if self._duplicate(unique_id, ignore=subentry.subentry_id):
                    return self.async_abort(reason="already_configured")
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=title_for(self._service, self._station, data[CONF_TOWARDS]),
                    data=data,
                    unique_id=unique_id,
                )
            self._defaults = user_input
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._direction_schema(),
            errors=errors,
            description_placeholders=self._placeholders(),
        )
