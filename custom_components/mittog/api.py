"""Client for the mittog.dk live departure feed.

mittog.dk has no request/response API: the web app opens a WebSocket per board and
the server pushes a full snapshot of the board every 10-60 seconds. Each snapshot is
{"data": {"StationId", "Created", "Trains": [...]}, "pico": [notices], "remarks": []}.
Times are local Danish time as "dd-mm-yyyy HH:MM:SS"; "01-01-0001 00:00:00" means unset.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import logging
import random
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import aiohttp

from . import stations
from .const import (
    HIDDEN_STOP_TYPES,
    LINE_COLORS,
    NON_PASSENGER_PRODUCTS,
    PRODUCTS,
    SERVICE_STOG,
    STALE_AFTER,
    WEB_BASE,
    WS_BASE,
)

_LOGGER = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Copenhagen")
# The public web app's origin; the server accepts connections without it, but it is polite.
HEADERS = {"Origin": "https://mittog.dk"}
MAX_MESSAGE = 16 * 1024 * 1024
BACKOFF_MIN = 5
BACKOFF_MAX = 300


class MittogError(Exception):
    """Talking to mittog.dk failed."""


class MittogTimeout(MittogError):
    """The server accepted the connection but sent no board (unknown station or outage)."""


def board_url(service: str, code: str) -> str:
    code = quote(code, safe="")
    if service == SERVICE_STOG:
        return f"{WS_BASE}/stog/departure/{code}/"
    return f"{WS_BASE}/departure/{code}/dinstation/"


def web_url(service: str, code: str) -> str:
    return f"{WEB_BASE}/{quote(code, safe='')}/{service}/"


def parse_time(value: Any) -> datetime | None:
    if not value or not isinstance(value, str) or value.startswith("01-01-0001"):
        return None
    try:
        return datetime.strptime(value, "%d-%m-%Y %H:%M:%S").replace(tzinfo=TZ)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=TZ)


@dataclass(slots=True)
class Departure:
    train_id: str
    number: str
    product: str
    line: str
    color: str
    operator: str
    destinations: list[str]
    stops: list[str]
    via: str | None
    track: str | None
    original_track: str | None
    scheduled: datetime
    expected: datetime
    cancelled: bool
    direction: str | None
    departed: bool

    @property
    def delay_minutes(self) -> int:
        seconds = (self.expected - self.scheduled).total_seconds()
        # mittog.dk only calls a train late or early once it is a full minute off.
        return round(seconds / 60) if abs(seconds) > 59 else 0

    @property
    def destination(self) -> str:
        return " / ".join(stations.name(code) for code in self.destinations)

    @property
    def track_changed(self) -> bool:
        return bool(self.original_track and self.track and self.original_track != self.track)

    def calls_at(self, codes: set[str]) -> bool:
        return any(code in codes for code in self.stops) or any(
            code in codes for code in self.destinations
        )

    def as_dict(self, now: datetime | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "line": self.line,
            "destination": self.destination,
            "track": self.track,
            "scheduled": self.scheduled.isoformat(),
            "expected": self.expected.isoformat(),
            "delay": self.delay_minutes,
            "cancelled": self.cancelled,
            "train_number": self.number,
            "product": self.product,
            "operator": self.operator,
            "color": self.color,
        }
        if self.via:
            data["via"] = stations.name(self.via)
        if self.track_changed:
            data["original_track"] = self.original_track
        if now is not None:
            data["minutes"] = max(0, int((self.expected - now).total_seconds() // 60))
        return data


@dataclass(slots=True)
class Notice:
    header: str
    body: str
    info_type: str
    updated: str | None

    @property
    def urgent(self) -> bool:
        return "URGENT" in self.info_type.upper()


@dataclass(slots=True)
class Board:
    station: str
    created: datetime | None
    departures: list[Departure] = field(default_factory=list)
    notices: list[Notice] = field(default_factory=list)


def _line(train: dict[str, Any]) -> tuple[str, str, str]:
    product = str(train.get("Product") or "")
    line_name = train.get("LineName")
    if product == "STRAIN" and line_name:
        label = "Bx" if line_name.upper() == "BX" else str(line_name)
        return label, LINE_COLORS.get(label.upper(), "#B41730"), str(train.get("TOC") or "DSB")
    if product in PRODUCTS:
        label, color, operator = PRODUCTS[product]
        return label, color, operator or str(train.get("TOC") or "")
    return str(line_name or product), "#000000", str(train.get("TOC") or "")


def parse_departure(train: dict[str, Any], station: str) -> Departure | None:
    """Turn one entry of Trains into a Departure, or None if mittog.dk would hide it."""
    product = str(train.get("Product") or "")
    if product in NON_PASSENGER_PRODUCTS:
        return None
    if train.get("TrainType") not in (None, "Passenger"):
        return None
    if train.get("StopType") in HIDDEN_STOP_TYPES or train.get("MayDepartEarly"):
        return None
    if train.get("IsLastStop"):
        return None
    if train.get("InformationType") not in (None, "NORMAL"):
        return None

    scheduled = parse_time(train.get("ScheduleTimeDeparture")) or parse_time(train.get("ScheduleTime"))
    if scheduled is None:
        return None
    expected = (
        parse_time(train.get("EstimatedTimeDeparture"))
        or parse_time(train.get("DelayTime"))
        or scheduled
    )

    routes = train.get("Routes") or []
    destinations: list[str] = []
    stops: list[str] = []
    via = None
    for route in routes:
        dest = route.get("DestinationStationId")
        if dest and stations.normalize(dest) not in destinations:
            destinations.append(stations.normalize(dest))
        via = via or route.get("ViaStation") or None
        for stop in route.get("Stations") or []:
            code = stop.get("StationId")
            if code and stations.normalize(code) not in stops:
                stops.append(stations.normalize(code))
    if not destinations:
        destinations = [stations.normalize(c) for c in train.get("TargetStation") or []]
    here = stations.normalize(station)
    if destinations and all(dest == here for dest in destinations):
        return None  # terminates here: an arrival, not a departure
    stops = [code for code in stops if code != here]

    cancelled = train.get("IsCancelledDeparture")
    if not isinstance(cancelled, bool):
        cancelled = bool(train.get("IsCancelled"))
    direction = train.get("DepartureDirection")
    line, color, operator = _line(train)
    return Departure(
        train_id=str(train.get("TrainId") or ""),
        number=str(train.get("PublicTrainId") or train.get("TrainId") or ""),
        product=product,
        line=line,
        color=color,
        operator=operator,
        destinations=destinations,
        stops=stops,
        via=via,
        track=train.get("TrackCurrent") or None,
        original_track=train.get("TrackOriginal") or None,
        scheduled=scheduled,
        expected=expected,
        cancelled=cancelled,
        direction=direction if direction in ("UP", "DOWN") else None,
        departed=parse_time(train.get("TrainDeparted")) is not None,
    )


def parse_board(message: dict[str, Any], station: str) -> Board:
    data = message.get("data") or {}
    created = None
    if isinstance(data.get("Created"), str):
        try:
            created = datetime.fromisoformat(data["Created"])
        except ValueError:
            created = None
    departures = []
    for train in data.get("Trains") or []:
        try:
            departure = parse_departure(train, station)
        except (TypeError, AttributeError, KeyError) as err:
            _LOGGER.debug("Skipping unparsable train %s: %s", train.get("TrainId"), err)
            continue
        if departure is not None:
            departures.append(departure)
    departures.sort(key=lambda d: d.expected)
    notices = [
        Notice(
            header=str(p.get("header") or ""),
            body=str(p.get("body") or ""),
            info_type=str(p.get("info_type") or ""),
            updated=p.get("updated"),
        )
        for p in message.get("pico") or []
        if isinstance(p, dict) and p.get("station_code") in (None, "", station)
    ]
    return Board(station=station, created=created, departures=departures, notices=notices)


def upcoming(departures: list[Departure], now: datetime, grace: int) -> list[Departure]:
    cutoff = now - timedelta(seconds=grace)
    return [d for d in departures if not d.departed and d.expected >= cutoff]


async def async_fetch_board(
    session: aiohttp.ClientSession, service: str, code: str, timeout: float = 30
) -> Board:
    """Open the board once and return the first snapshot."""
    try:
        async with asyncio.timeout(timeout):
            async with session.ws_connect(
                board_url(service, code), headers=HEADERS, max_msg_size=MAX_MESSAGE
            ) as ws:
                while True:
                    msg = await ws.receive()
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        return parse_board(json.loads(msg.data), code)
                    if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        raise MittogError(f"connection closed: {msg.extra}")
    except TimeoutError as err:
        raise MittogTimeout(f"no board for {service}/{code} within {timeout}s") from err
    except (aiohttp.ClientError, ValueError) as err:
        raise MittogError(str(err)) from err


class BoardStream:
    """One long-lived WebSocket to a board, shared by every subentry watching it."""

    def __init__(self, session: aiohttp.ClientSession, service: str, code: str) -> None:
        self.session = session
        self.service = service
        self.code = code
        self.url = board_url(service, code)
        self.board: Board | None = None
        self.last_message: datetime | None = None
        self.connected = False
        self.reconnects = 0
        self._listeners: set[Callable[[], None]] = set()
        self._task: asyncio.Task[None] | None = None

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    @property
    def listener_count(self) -> int:
        return len(self._listeners)

    def start(self, create_task: Callable[..., asyncio.Task[None]]) -> None:
        if self._task is None:
            self._task = create_task(self._run(), f"mittog {self.service}/{self.code}")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.connected = False

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    async def _run(self) -> None:
        backoff = BACKOFF_MIN
        while True:
            try:
                await self._session()
                backoff = BACKOFF_MIN
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                _LOGGER.debug("%s: no message for %ss, reconnecting", self.url, STALE_AFTER)
            except (aiohttp.ClientError, ValueError) as err:
                _LOGGER.debug("%s: %s", self.url, err)
            except Exception:  # noqa: BLE001 - the stream must survive anything
                _LOGGER.exception("Unexpected error on %s", self.url)
            if self.connected:
                self.connected = False
                self._notify()
            self.reconnects += 1
            await asyncio.sleep(backoff * random.uniform(0.8, 1.2))
            backoff = min(backoff * 2, BACKOFF_MAX)

    async def _session(self) -> None:
        async with self.session.ws_connect(
            self.url, headers=HEADERS, heartbeat=30, max_msg_size=MAX_MESSAGE
        ) as ws:
            _LOGGER.debug("Connected to %s", self.url)
            while True:
                msg = await ws.receive(timeout=STALE_AFTER)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self.board = parse_board(json.loads(msg.data), self.code)
                    self.last_message = datetime.now(TZ)
                    self.connected = True
                    self._notify()
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                    return
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    raise aiohttp.ClientError(str(ws.exception()))
