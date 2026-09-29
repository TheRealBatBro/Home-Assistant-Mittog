"""Departure sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import stations
from .api import Departure, web_url
from .coordinator import MittogConfigEntry, StationCoordinator, StationData
from .entity import MittogEntity


def _nth(data: StationData, index: int) -> Departure | None:
    active = data.active
    return active[index] if len(active) > index else None


def _minutes(data: StationData) -> int | None:
    if (dep := _nth(data, 0)) is None:
        return None
    return max(0, int((dep.expected - data.now).total_seconds() // 60))


@dataclass(frozen=True, kw_only=True)
class MittogSensorDescription(SensorEntityDescription):
    value_fn: Callable[[StationData], Any]
    departure_index: int | None = None


SENSORS: tuple[MittogSensorDescription, ...] = (
    MittogSensorDescription(
        key="next_departure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: (dep.expected if (dep := _nth(d, 0)) else None),
        departure_index=0,
    ),
    MittogSensorDescription(
        key="second_departure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: (dep.expected if (dep := _nth(d, 1)) else None),
        departure_index=1,
    ),
    MittogSensorDescription(
        key="minutes_until",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=_minutes,
    ),
    MittogSensorDescription(
        key="delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda d: (dep.delay_minutes if (dep := _nth(d, 0)) else None),
    ),
    MittogSensorDescription(
        key="notices",
        value_fn=lambda d: len(d.notices),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MittogConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        async_add_entities(
            [MittogSensor(coordinator, description) for description in SENSORS],
            config_subentry_id=subentry_id,
        )


class MittogSensor(MittogEntity, SensorEntity):
    entity_description: MittogSensorDescription
    # The board changes every few seconds; keep the recorder database small.
    _unrecorded_attributes = frozenset({"departures", "notices", "minutes", "url", "updated"})

    def __init__(self, coordinator: StationCoordinator, description: MittogSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> datetime | int | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self.coordinator.data
        coordinator = self.coordinator
        key = self.entity_description.key
        if key == "notices":
            return {
                "notices": [
                    {"header": n.header, "body": n.body, "urgent": n.urgent, "updated": n.updated}
                    for n in data.notices
                ]
            }
        index = self.entity_description.departure_index
        if index is None:
            return None
        attrs: dict[str, Any] = {}
        if (dep := _nth(data, index)) is not None:
            attrs.update(dep.as_dict(data.now))
        if index == 0:
            attrs["station"] = stations.name(coordinator.station)
            attrs["station_code"] = coordinator.station
            attrs["direction"] = coordinator.direction
            attrs["towards"] = [stations.name(c) for c in sorted(coordinator.towards)]
            attrs["departures"] = [d.as_dict(data.now) for d in data.departures]
            attrs["updated"] = data.updated.isoformat() if data.updated else None
            attrs["url"] = web_url(coordinator.service, coordinator.station)
        return attrs
