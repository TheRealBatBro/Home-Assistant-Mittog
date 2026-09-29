"""Base entity: one device per station subentry."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import web_url
from .const import DOMAIN, SERVICE_STOG
from .coordinator import StationCoordinator


class MittogEntity(CoordinatorEntity[StationCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: StationCoordinator, key: str) -> None:
        super().__init__(coordinator)
        subentry = coordinator.subentry
        self.entity_description_key = key
        self._attr_unique_id = f"{subentry.subentry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="mittog.dk",
            model="S-tog" if coordinator.service == SERVICE_STOG else "Tog",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=web_url(coordinator.service, coordinator.station),
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None
