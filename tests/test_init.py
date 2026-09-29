"""Entities fed by pushed boards."""

from __future__ import annotations

from datetime import timedelta

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.mittog.diagnostics import async_get_config_entry_diagnostics

from .conftest import make_entry, push, station_data


def _eid(hass: HomeAssistant, sub, key: str) -> str:
    domain = "binary_sensor" if key in ("disruption", "connection") else "sensor"
    entity_id = er.async_get(hass).async_get_entity_id(domain, "mittog", f"{sub.subentry_id}_{key}")
    assert entity_id, key
    return entity_id


def _sub(entry, title: str):
    return next(s for s in entry.subentries.values() if s.title == title)


async def test_two_directions_one_socket(hass: HomeAssistant) -> None:
    entry = make_entry(
        station_data("stog", "VNG", towards=["KH"]),
        station_data("stog", "VNG", towards=["FS"]),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(entry.runtime_data.streams) == 1
    to_kh = _sub(entry, "Vinge → København H")
    to_fs = _sub(entry, "Vinge → Frederikssund")

    assert hass.states.get(_eid(hass, to_kh, "next_departure")).state == STATE_UNAVAILABLE

    await push(hass, entry, "stog", "VNG", "stog_vng.json")

    state = hass.states.get(_eid(hass, to_kh, "next_departure"))
    assert state.state == "2026-09-29T16:46:00+00:00"
    assert state.attributes["destination"] == "Klampenborg"
    assert state.attributes["line"] == "C"
    assert state.attributes["towards"] == ["København H"]
    assert len(state.attributes["departures"]) == 3
    assert all(d["destination"] != "Frederikssund" for d in state.attributes["departures"])
    second = hass.states.get(_eid(hass, to_kh, "second_departure"))
    assert second.state == "2026-09-29T17:12:00+00:00"
    assert state.attributes["departures"][2]["destination"] == "Svanemøllen"

    assert hass.states.get(_eid(hass, to_fs, "next_departure")).attributes["destination"] == "Frederikssund"
    assert hass.states.get(_eid(hass, to_fs, "minutes_until")).state == "2"
    assert hass.states.get(_eid(hass, to_kh, "disruption")).state == STATE_OFF
    assert hass.states.get(_eid(hass, to_kh, "connection")).state == STATE_ON

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert sorted(d.name for d in devices) == ["Vinge → Frederikssund", "Vinge → København H"]

    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["streams"][0]["listeners"] == 2


async def test_filters_delay_and_staleness(hass: HomeAssistant, frozen) -> None:
    entry = make_entry(
        station_data("tog", "KH", lines=["IC"]),
        station_data("tog", "KH", tracks="1"),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await push(hass, entry, "tog", "KH", "tog_kh.json")

    subs = {tuple(s.data["lines"]): s for s in entry.subentries.values()}
    ic_sub, track_sub = subs[("IC",)], subs[()]

    ic = hass.states.get(_eid(hass, ic_sub, "next_departure"))
    assert ic.attributes["line"] == "IC"
    assert ic.attributes["destination"] == "Østerport"
    assert all(d["line"] == "IC" for d in ic.attributes["departures"])
    assert hass.states.get(_eid(hass, ic_sub, "delay")).state == "15"
    assert hass.states.get(_eid(hass, ic_sub, "disruption")).state == STATE_ON
    assert hass.states.get(_eid(hass, ic_sub, "notices")).state == "2"

    track1 = hass.states.get(_eid(hass, track_sub, "next_departure"))
    assert track1.attributes["departures"]
    assert all(d["track"] == "1" for d in track1.attributes["departures"])

    # No pushes for more than three minutes: the board is stale.
    frozen.tick(timedelta(minutes=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(_eid(hass, ic_sub, "next_departure")).state == STATE_UNAVAILABLE
    assert hass.states.get(_eid(hass, ic_sub, "connection")).state == STATE_OFF

    # A fresh (old) snapshot arrives: every IC on it has left by now.
    await push(hass, entry, "tog", "KH", "tog_kh.json")
    assert hass.states.get(_eid(hass, ic_sub, "next_departure")).state == STATE_UNKNOWN


async def test_unload(hass: HomeAssistant) -> None:
    entry = make_entry(station_data("stog", "VNG"))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await push(hass, entry, "stog", "VNG", "stog_vng.json")
    hub = entry.runtime_data
    (coordinator,) = hub.coordinators.values()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hub.streams == {}
    assert coordinator.stream.listener_count == 0
