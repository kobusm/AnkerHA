"""Shared base entity for Anker SOLIX S5000."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnkerSolixCoordinator
from .s5000 import SUPPORTED_MODELS


def device_info(coordinator: AnkerSolixCoordinator) -> DeviceInfo:
    dev = coordinator.device
    model = SUPPORTED_MODELS.get(dev.get("device_pn", ""), "SOLIX S5000")
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.device_sn)},
        name=dev.get("alias") or f"Anker {model}",
        manufacturer="Anker",
        model=model,
        model_id=dev.get("device_pn"),
        serial_number=coordinator.device_sn,
        sw_version=dev.get("sw_version"),
    )


class AnkerSolixEntity(CoordinatorEntity[AnkerSolixCoordinator]):
    """Base entity bound to one S5000 device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnkerSolixCoordinator,
        entry: ConfigEntry,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_sn}_{description.key}"
        self._attr_device_info = device_info(coordinator)

    @property
    def data(self) -> dict:
        return self.coordinator.data or {}
