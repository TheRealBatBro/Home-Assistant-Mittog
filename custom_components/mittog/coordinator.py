"""Push coordinators: one shared WebSocket per board, one filtered view per subentry."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import stations
from .api import Board, BoardStream, Departure, Notice, upcoming
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
    DEPARTED_GRACE,
    DOMAIN,
    STALE_AFTER,
)

_LOGGER = logging.getLogger(__name__)

TICK = timedelta(seconds=30)
# A train missing from one snapshot before it has left is kept this long, so the
# sensors don't flicker to unknown when the feed briefly drops it.
REMEMBER = timedelta(minutes=3)

type MittogConfigEntry = ConfigEntry[MittogHub]


class MittogHub:
    """Owns the board streams so several subentries on one station share a socket."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.streams: dict[tuple[str, str], BoardStream] = {}
        self.coordinators: dict[str, StationCoordinator] = {}

    def stream(self, service: str, code: str) -> BoardStream:
        key = (service, code)
        if key not in self.streams:
            stream = BoardStream(async_get_clientsession(self.hass), service, code)
            stream.start(
                lambda coro, name: self.entry.async_create_background_task(self.hass, coro, name)
            )
            self.streams[key] = stream
        return self.streams[key]

    async def async_stop(self) -> None:
        for stream in self.streams.values():
            await stream.stop()
        self.streams.clear()


@dataclass(slots=True)
class StationData:
    departures: list[Departure]
    notices: list[Notice]
    updated: datetime | None
    connected: bool
    unfiltered: int = 0
    now: datetime = field(default_factory=dt_util.now)

    @property
    def active(self) -> list[Departure]:
        return [d for d in self.departures if not d.cancelled]


def _key(departure: Departure) -> str:
    return f"{departure.train_id}|{departure.scheduled.isoformat()}"


def parse_filter(values: list[str] | str | None) -> set[str]:
    if not values:
        return set()
    if isinstance(values, str):
        values = values.replace(";", ",").split(",")
    return {v.strip() for v in values if v and v.strip()}


class StationCoordinator(DataUpdateCoordinator[StationData]):
    """Applies one subentry's direction and filters to its board stream."""

    config_entry: MittogConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: MittogConfigEntry, subentry: ConfigSubentry
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {subentry.title}",
            update_interval=None,
        )
        self.subentry = subentry
        data = subentry.data
        self.service: str = data[CONF_SERVICE]
        self.station: str = data[CONF_STATION]
        direction = data.get(CONF_DIRECTION) or BOTH_DIRECTIONS
        self.direction: str | None = None if direction == BOTH_DIRECTIONS else direction
        self.towards = {stations.normalize(c) for c in parse_filter(data.get(CONF_TOWARDS))}
        self.lines = {v.casefold() for v in parse_filter(data.get(CONF_LINES))}
        self.tracks = {v.casefold() for v in parse_filter(data.get(CONF_TRACKS))}
        self.max_departures = int(data.get(CONF_MAX_DEPARTURES, DEFAULT_MAX_DEPARTURES))
        self.hide_cancelled = bool(data.get(CONF_HIDE_CANCELLED, False))
        self.delay_threshold = int(data.get(CONF_DELAY_THRESHOLD, DEFAULT_DELAY_THRESHOLD))
        self.stream: BoardStream | None = None
        self._unsubs: list[CALLBACK_TYPE] = []
        # Trains recently on the board: key -> (departure, last seen).
        self._recent: dict[str, tuple[Departure, datetime]] = {}
        # Stations seen on the way to each destination, learnt from trains that do
        # list their stops; used for trains that arrive without a stop list.
        self._route: dict[str, set[str]] = {}

    def _stops_at_wanted(self, departure: Departure) -> bool:
        if departure.calls_at(self.towards):
            return True
        if len([c for c in departure.stops if c not in departure.destinations]) > 0:
            # The train lists its stops and the wanted station isn't one of them:
            # it skips it (e.g. every other evening C train runs past Vinge).
            return False
        # No stop list: go by what other trains to the same destination stop at.
        return any(self.towards & self._route.get(dest, set()) for dest in departure.destinations)

    def matches(self, departure: Departure) -> bool:
        if self.direction and departure.direction != self.direction:
            return False
        if self.towards and not self._stops_at_wanted(departure):
            return False
        if self.lines and departure.line.casefold() not in self.lines and departure.product.casefold() not in self.lines:
            return False
        if self.tracks and (departure.track or "").casefold() not in self.tracks:
            return False
        if self.hide_cancelled and departure.cancelled:
            return False
        return True

    def _learn(self, board: Board) -> None:
        for dep in board.departures:
            if len(dep.stops) > 1:
                for dest in dep.destinations:
                    self._route.setdefault(dest, set()).update(dep.stops)

    def _with_recent(self, departures: list[Departure], now: datetime) -> list[Departure]:
        """Add back trains that dropped out of this snapshot but haven't left yet."""
        current = {_key(d) for d in departures}
        for dep in departures:
            self._recent[_key(dep)] = (dep, now)
        kept = list(departures)
        for key, (dep, seen) in list(self._recent.items()):
            if key in current:
                continue
            if now - seen > REMEMBER or dep.expected < now:
                del self._recent[key]
            else:
                kept.append(dep)
        kept.sort(key=lambda d: d.expected)
        return kept

    def build(self, board: Board, now: datetime, connected: bool) -> StationData:
        self._learn(board)
        live = upcoming(self._with_recent(board.departures, now), now, DEPARTED_GRACE)
        chosen = [d for d in live if self.matches(d)]
        return StationData(
            departures=chosen[: self.max_departures],
            notices=board.notices,
            updated=board.created,
            connected=connected,
            unfiltered=len(live),
            now=now,
        )

    @callback
    def async_start(self, hub: MittogHub) -> None:
        self.stream = hub.stream(self.service, self.station)
        self._unsubs.append(self.stream.add_listener(self._handle_push))
        self._unsubs.append(async_track_time_interval(self.hass, self._tick, TICK))
        if self.stream.board is not None:
            self._handle_push()

    @callback
    def async_stop(self) -> None:
        while self._unsubs:
            self._unsubs.pop()()

    @callback
    def _handle_push(self) -> None:
        self._refresh()

    @callback
    def _tick(self, _now: datetime) -> None:
        self._refresh()

    @callback
    def _refresh(self) -> None:
        stream = self.stream
        if stream is None or stream.board is None:
            return
        now = dt_util.now()
        stale = stream.last_message is None or (now - stream.last_message).total_seconds() > STALE_AFTER
        if stale:
            self.async_set_update_error(UpdateFailed(f"No update from mittog.dk for {STALE_AFTER} s"))
            return
        self.async_set_updated_data(self.build(stream.board, now, stream.connected))

    async def _async_update_data(self) -> StationData:
        # Push only; HA calls this on manual refresh (homeassistant.update_entity).
        if self.stream is None or self.stream.board is None:
            raise UpdateFailed("Waiting for the first board from mittog.dk")
        return self.build(self.stream.board, dt_util.now(), self.stream.connected)

    def diagnostics(self) -> dict[str, Any]:
        stream = self.stream
        return {
            "service": self.service,
            "station": self.station,
            "direction": self.direction,
            "towards": sorted(self.towards),
            "lines": sorted(self.lines),
            "tracks": sorted(self.tracks),
            "connected": stream.connected if stream else None,
            "reconnects": stream.reconnects if stream else None,
            "last_message": stream.last_message.isoformat() if stream and stream.last_message else None,
            "board_departures": len(stream.board.departures) if stream and stream.board else None,
            "shown": [d.as_dict() for d in self.data.departures] if self.data else None,
            # Every train on the board and why it is or isn't shown, for bug reports.
            "board": [
                {
                    "expected": d.expected.isoformat(),
                    "line": d.line,
                    "destinations": d.destinations,
                    "direction": d.direction,
                    "track": d.track,
                    "cancelled": d.cancelled,
                    "departed": d.departed,
                    "stops": d.stops,
                    "shown": self.matches(d),
                }
                for d in (stream.board.departures if stream and stream.board else [])
            ],
        }
