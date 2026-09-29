"""Config flow: hub with first station, more stations and directions as subentries."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.mittog.api import MittogTimeout, parse_board
from custom_components.mittog.const import (
    CONF_DELAY_THRESHOLD,
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

from .conftest import load, make_entry, station_data

FETCH = "custom_components.mittog.config_flow.async_fetch_board"
DIRECTION = {
    CONF_TOWARDS: ["KH"],
    CONF_LINES: [],
    CONF_TRACKS: "",
    CONF_MAX_DEPARTURES: 5,
    CONF_DELAY_THRESHOLD: 3,
    CONF_HIDE_CANCELLED: False,
}


@pytest.fixture
def fetch():
    async def _fetch(session, service, code, timeout=30):
        return parse_board(load("tog_kh.json" if code == "KH" else "stog_vng.json"), code)

    with patch(FETCH, side_effect=_fetch) as mock:
        yield mock


def _options(result, key):
    for marker, selector in result["data_schema"].schema.items():
        if marker == key:
            return selector.config["options"]
    raise KeyError(key)


async def test_first_setup_creates_hub_with_station(hass: HomeAssistant, fetch) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_SERVICE: "stog"})
    assert result["step_id"] == "station"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"query": "Aalborg"})
    assert result["errors"] == {"query": "no_match"}  # Aalborg has no S-tog board
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"query": "vi"})
    assert result["step_id"] == "pick_station"
    picks = [o["label"] for o in _options(result, CONF_STATION)]
    assert picks[0] == "Vigerslev Allé" and "Vinge" in picks and "Ålholm" not in picks
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STATION: "VNG"})
    assert result["step_id"] == "direction"
    assert result["description_placeholders"] == {"station": "Vinge", "count": "6"}
    towards = _options(result, CONF_TOWARDS)
    assert {"value": "KH", "label": "København H"} in towards
    assert {"value": "FS", "label": "Frederikssund"} in towards

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**DIRECTION, CONF_TOWARDS: ["VNG"]}
    )
    assert result["errors"] == {CONF_TOWARDS: "towards_self"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**DIRECTION, CONF_TOWARDS: ["København H"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.title == "Mittog"
    (sub,) = entry.subentries.values()
    assert sub.title == "Vinge → København H"
    assert sub.data[CONF_TOWARDS] == ["KH"]
    assert sub.data[CONF_MAX_DEPARTURES] == 5


async def test_only_one_hub(hass: HomeAssistant) -> None:
    make_entry().add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT


async def _start_subentry(hass: HomeAssistant, entry, service: str, station: str):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_STATION), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {CONF_SERVICE: service})
    # Station codes from the mittog.dk URL go straight through.
    return await hass.config_entries.subentries.async_configure(result["flow_id"], {"query": station})


async def test_add_more_stations_and_directions(hass: HomeAssistant, fetch) -> None:
    entry = make_entry(station_data("stog", "VNG", towards=["KH"]))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    # Same station, other direction.
    result = await _start_subentry(hass, entry, "stog", "VNG")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**DIRECTION, CONF_TOWARDS: ["FS"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vinge → Frederikssund"

    # Same station and direction again is refused.
    result = await _start_subentry(hass, entry, "stog", "VNG")
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], DIRECTION)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # A regional-train board at a station that has both boards.
    result = await _start_subentry(hass, entry, "tog", "KH")
    lines = _options(result, CONF_LINES)
    assert "IC" in lines and "Øresundståg" in lines
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**DIRECTION, CONF_TOWARDS: [], CONF_LINES: ["IC"], CONF_TRACKS: "8, 1"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "København H (tog)"
    await hass.async_block_till_done()

    titles = sorted(s.title for s in entry.subentries.values())
    assert titles == ["København H (tog)", "Vinge → Frederikssund", "Vinge → København H"]
    kh = next(s for s in entry.subentries.values() if s.data[CONF_STATION] == "KH")
    assert kh.data[CONF_TRACKS] == "1, 8"
    # The reload after adding subentries gave every station a coordinator; Vinge shares one socket.
    hub = entry.runtime_data
    assert len(hub.coordinators) == 3
    assert set(hub.streams) == {("stog", "VNG"), ("tog", "KH")}


async def test_direction_step_works_offline(hass: HomeAssistant) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    with patch(FETCH, AsyncMock(side_effect=MittogTimeout("nothing"))):
        result = await _start_subentry(hass, entry, "stog", "VNG")
    assert result["step_id"] == "direction"
    assert len(_options(result, CONF_TOWARDS)) > 80  # falls back to every S-tog station


async def test_reconfigure_direction(hass: HomeAssistant, fetch) -> None:
    entry = make_entry(station_data("stog", "VNG", towards=["KH"]))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    (sub,) = entry.subentries.values()
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**DIRECTION, CONF_TOWARDS: ["FS"], CONF_HIDE_CANCELLED: True}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    sub = entry.subentries[sub.subentry_id]
    assert sub.title == "Vinge → Frederikssund"
    assert sub.data[CONF_HIDE_CANCELLED] is True


def test_search_stations() -> None:
    from custom_components.mittog.config_flow import search_stations

    assert [s.code for s in search_stations("vng", "stog")] == ["VNG"]
    assert [s.code for s in search_stations("København H", "tog")] == ["KH"]
    nor = [s.name for s in search_stations("nør", "stog")]
    assert nor[:2] == ["Nørrebro", "Nørreport"]
    assert search_stations("", "stog") == []
