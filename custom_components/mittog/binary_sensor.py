"""Disruption and connection binary sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MittogConfigEntry, StationCoordinator
from .entity import MittogEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MittogConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        async_add_entities(
            [DisruptionSensor(coordinator), ConnectionSensor(coordinator)],
            config_subentry_id=subentry_id,
        )


class DisruptionSensor(MittogEntity, BinarySensorEntity):
    """On when a shown departure is cancelled or at least the threshold late."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _unrecorded_attributes = frozenset({"affected"})

    def __init__(self, coordinator: StationCoordinator) -> None:
        super().__init__(coordinator, "disruption")

    def _problems(self) -> list[dict[str, Any]]:
        threshold = self.coordinator.delay_threshold
        return [
            d.as_dict()
            for d in self.coordinator.data.departures
            if d.cancelled or d.delay_minutes >= threshold
        ]

    @property
    def is_on(self) -> bool:
        return bool(self._problems())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        problems = self._problems()
        return {
            "cancelled": sum(1 for p in problems if p["cancelled"]),
            "delayed": sum(1 for p in problems if not p["cancelled"]),
            "affected": problems,
        }


class ConnectionSensor(MittogEntity, BinarySensorEntity):
    """Whether the live WebSocket to mittog.dk is up."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: StationCoordinator) -> None:
        super().__init__(coordinator, "connection")

    @property
    def available(self) -> bool:
        return self.coordinator.stream is not None

    @property
    def is_on(self) -> bool:
        stream = self.coordinator.stream
        return bool(stream and stream.connected and self.coordinator.last_update_success)
