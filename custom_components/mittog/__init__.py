"""Mittog: live Danish train and S-train departures from mittog.dk."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import stations
from .const import SUBENTRY_STATION
from .coordinator import MittogConfigEntry, MittogHub, StationCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MittogConfigEntry) -> bool:
    await hass.async_add_executor_job(stations.load_catalogue)
    hub = MittogHub(hass, entry)
    entry.runtime_data = hub
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_STATION:
            hub.coordinators[subentry.subentry_id] = StationCoordinator(hass, entry, subentry)
    for coordinator in hub.coordinators.values():
        coordinator.async_start(hub)

    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: MittogConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MittogConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for coordinator in entry.runtime_data.coordinators.values():
            coordinator.async_stop()
        await entry.runtime_data.async_stop()
    return unloaded
