"""Fixtures: real mittog.dk board snapshots, with the WebSocket replaced by direct pushes.

stog_vng.json (Vinge, S-tog) and tog_kh.json (København H, regional trains, trimmed)
were captured from wss://api.mittog.dk on 2026-09-29 around 18:46 Danish time;
the clock is frozen there.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant

from custom_components.mittog.api import TZ, BoardStream, parse_board
from custom_components.mittog.config_flow import title_for, unique_id_for
from custom_components.mittog.const import (
    CONF_DELAY_THRESHOLD,
    CONF_DIRECTION,
    CONF_HIDE_CANCELLED,
    CONF_LINES,
    CONF_MAX_DEPARTURES,
    CONF_SERVICE,
    CONF_STATION,
    CONF_TOWARDS,
    CONF_TRACKS,
    DOMAIN,
    SUBENTRY_STATION,
)

pytest_plugins = ["pytest_homeassistant_custom_component"]

FIXTURES = Path(__file__).parent / "fixtures"
NOW = "2026-09-29 16:46:00+00:00"  # 18:46 in Copenhagen


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def frozen(freezer):
    freezer.move_to(NOW)
    return freezer


@pytest.fixture(autouse=True)
def no_sockets():
    """Streams never open a real socket; tests push snapshots with push()."""
    with patch.object(BoardStream, "start", lambda self, create_task: None):
        yield


def station_data(service: str, station: str, **extra: Any) -> dict[str, Any]:
    data = {
        CONF_SERVICE: service,
        CONF_STATION: station,
        CONF_DIRECTION: "both",
        CONF_TOWARDS: [],
        CONF_LINES: [],
        CONF_TRACKS: "",
        CONF_MAX_DEPARTURES: 10,
        CONF_DELAY_THRESHOLD: 3,
        CONF_HIDE_CANCELLED: False,
    }
    data.update(extra)
    return data


def subentry(data: dict[str, Any]) -> ConfigSubentryData:
    return ConfigSubentryData(
        subentry_type=SUBENTRY_STATION,
        title=title_for(data[CONF_SERVICE], data[CONF_STATION], data[CONF_TOWARDS])
        + ("" if data.get(CONF_DIRECTION, "both") == "both" else f" {data[CONF_DIRECTION]}"),
        unique_id=unique_id_for(data),
        data=data,
    )


def make_entry(*datas: dict[str, Any]) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN, title="Mittog", data={}, subentries_data=[subentry(d) for d in datas]
    )


async def push(hass: HomeAssistant, entry: MockConfigEntry, service: str, code: str, fixture: str) -> None:
    await push_message(hass, entry, service, code, load(fixture))


async def push_message(
    hass: HomeAssistant, entry: MockConfigEntry, service: str, code: str, message: dict[str, Any]
) -> None:
    stream = entry.runtime_data.streams[(service, code)]
    stream.board = parse_board(message, code)
    stream.last_message = datetime.now(TZ)
    stream.connected = True
    stream._notify()
    await hass.async_block_till_done()
