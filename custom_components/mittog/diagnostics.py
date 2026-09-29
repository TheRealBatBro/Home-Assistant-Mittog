"""Diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import MittogConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MittogConfigEntry
) -> dict[str, Any]:
    hub = entry.runtime_data
    return {
        "streams": [
            {
                "url": stream.url,
                "connected": stream.connected,
                "listeners": stream.listener_count,
                "reconnects": stream.reconnects,
            }
            for stream in hub.streams.values()
        ],
        "stations": {
            coordinator.subentry.title: coordinator.diagnostics()
            for coordinator in hub.coordinators.values()
        },
    }
