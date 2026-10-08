"""Config flow: searchable station, live directions, filters limited to that direction."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.mittog.api import MittogError, parse_board
from custom_components.mittog.config_flow import resolve_station, station_choices
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

from .conftest import load, make_entry, station_data

FETCH = "custom_components.mittog.config_flow.async_fetch_board"
FILTERS = {
    CONF_TOWARDS: [],
    CONF_LINES: [],
    CONF_TRACKS: [],
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


def _values(result, key):
    return [o["value"] if isinstance(o, dict) else o for o in _options(result, key)]


def _labels(result, key):
    return [o["label"] if isinstance(o, dict) else o for o in _options(result, key)]


def test_station_choices() -> None:
    choices = station_choices()
    assert choices["Vinge (S-tog)"] == ("stog", "VNG")
    assert choices["København H (S-tog)"] == ("stog", "KH")
    assert choices["København H (Tog)"] == ("tog", "KH")
    assert "Aalborg (S-tog)" not in choices
    assert resolve_station("Vinge (S-tog)") == ("stog", "VNG")
    assert resolve_station("vng") == ("stog", "VNG")  # code from the mittog.dk URL
    assert resolve_station("Aalborg") == ("tog", "AB")
    assert resolve_station("KH") == ("stog", "KH")  # both boards: S-tog wins
    assert resolve_station("nowhere") is None


async def test_first_setup(hass: HomeAssistant, fetch) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "user"
    assert "Vinge (S-tog)" in _options(result, CONF_STATION)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STATION: "nowhere"})
    assert result["errors"] == {CONF_STATION: "unknown_station"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STATION: "Vinge (S-tog)"})

    # Only the directions trains actually leave Vinge in, named after where they go.
    assert result["step_id"] == "direction"
    assert result["description_placeholders"] == {"station": "Vinge (S-tog)", "count": "6"}
    assert _values(result, CONF_DIRECTION) == ["UP", "DOWN", "both"]
    up, down, both = _labels(result, CONF_DIRECTION)
    assert up == "Towards Klampenborg, Svanemøllen · via København H · next stop Ølstykke"
    assert down == "Towards Frederikssund"
    assert both == "Both directions"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_DIRECTION: "UP"})
    assert result["step_id"] == "filters"
    stops = _values(result, CONF_TOWARDS)
    assert stops[:2] == ["ØL", "EGD"]  # route order, nearest first
    assert "KH" in stops and "FS" not in stops  # only the chosen direction
    assert _options(result, CONF_LINES) == ["C"]
    assert _options(result, CONF_TRACKS) == ["1"]

    assert "VNG" not in stops
    result = await hass.config_entries.flow.async_configure(result["flow_id"], FILTERS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.title == "Mittog"
    (sub,) = entry.subentries.values()
    assert sub.title == "Vinge → København H"
    assert sub.data[CONF_DIRECTION] == "UP"
    assert sub.data[CONF_MAX_DEPARTURES] == 5


async def test_danish_labels(hass: HomeAssistant, fetch) -> None:
    hass.config.language = "da"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STATION: "VNG"})
    assert _labels(result, CONF_DIRECTION)[1:] == ["Mod Frederikssund", "Begge retninger"]


async def test_add_integration_again_adds_station_to_hub(hass: HomeAssistant, fetch) -> None:
    """Starting from "Add integration" / "Add device" with a hub joins the existing hub."""
    entry = make_entry(station_data("stog", "VNG", direction="UP"))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STATION: "Vinge (S-tog)"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_DIRECTION: "DOWN"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], FILTERS)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "station_added"
    assert result["description_placeholders"] == {"title": "Vinge → Frederikssund"}
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert sorted(s.title for s in entry.subentries.values()) == ["Vinge UP", "Vinge → Frederikssund"]
    assert len(entry.runtime_data.coordinators) == 2  # reloaded with the new station

    # The same station and direction again is refused.
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STATION: "Vinge (S-tog)"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_DIRECTION: "DOWN"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], FILTERS)
    assert result["reason"] == "already_configured"


async def test_feed_unreachable(hass: HomeAssistant) -> None:
    with patch(FETCH, AsyncMock(side_effect=MittogError("down"))):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STATION: "Vinge (S-tog)"})
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_empty_board_gives_generic_directions(hass: HomeAssistant) -> None:
    empty = {"data": {"StationId": "VNG", "Trains": []}, "pico": []}
    with patch(FETCH, AsyncMock(return_value=parse_board(empty, "VNG"))):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STATION: "Vinge (S-tog)"})
    assert _labels(result, CONF_DIRECTION) == ["Direction 1", "Direction 2", "Both directions"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_DIRECTION: "DOWN"})
    assert _options(result, CONF_LINES) == ["A", "B", "Bx", "C", "E", "F", "H"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], FILTERS)
    assert result["result"].subentries[next(iter(result["result"].subentries))].title == "Vinge (down)"


async def _add(hass: HomeAssistant, entry, station: str, direction: str, **filters):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_STATION), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {CONF_STATION: station})
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {CONF_DIRECTION: direction})
    last = result
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {**FILTERS, **filters})
    return last, result


async def test_add_more_stations_and_directions(hass: HomeAssistant, fetch) -> None:
    entry = make_entry(station_data("stog", "VNG", direction="UP"))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    _, result = await _add(hass, entry, "Vinge (S-tog)", "DOWN")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vinge → Frederikssund"

    _, result = await _add(hass, entry, "Vinge (S-tog)", "UP")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    filters, result = await _add(hass, entry, "København H (Tog)", "UP", **{CONF_LINES: ["IC"], CONF_TRACKS: ["8"]})
    assert "Re" in _options(filters, CONF_LINES)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"].startswith("København H (Tog) → ")
    await hass.async_block_till_done()

    assert len(entry.subentries) == 3
    hub = entry.runtime_data
    assert len(hub.coordinators) == 3
    assert set(hub.streams) == {("stog", "VNG"), ("tog", "KH")}


async def test_reconfigure(hass: HomeAssistant, fetch) -> None:
    entry = make_entry(station_data("stog", "VNG", direction="UP", towards=["KH"]))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    (sub,) = entry.subentries.values()
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    assert result["step_id"] == "direction"
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {CONF_DIRECTION: "DOWN"})
    assert result["step_id"] == "filters"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**FILTERS, CONF_HIDE_CANCELLED: True}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    sub = entry.subentries[sub.subentry_id]
    assert sub.title == "Vinge → Frederikssund"
    assert sub.data[CONF_DIRECTION] == "DOWN"
    assert sub.data[CONF_HIDE_CANCELLED] is True


async def test_reconfigure_old_towards_entry(hass: HomeAssistant, fetch) -> None:
    data = station_data("stog", "VNG", towards=["KL"])
    data.pop(CONF_DIRECTION)  # created by 1.0.0
    entry = make_entry(data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    (sub,) = entry.subentries.values()
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {CONF_DIRECTION: "UP"})
    towards = next(m for m in result["data_schema"].schema if m == CONF_TOWARDS)
    assert towards.default() == []
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], FILTERS)
    sub = entry.subentries[sub.subentry_id]
    assert sub.title == "Vinge → København H"
    assert sub.data[CONF_DIRECTION] == "UP" and sub.data[CONF_TOWARDS] == []
