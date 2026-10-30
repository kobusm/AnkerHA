"""Binary sensor entities for Anker SOLIX S5000."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AnkerSolixCoordinator
from .entity import AnkerSolixEntity
from .helpers import is_on, to_number


def _positive(key: str) -> Callable[[dict], bool | None]:
    def fn(d: dict) -> bool | None:
        num = to_number(d.get(key))
        return None if num is None else num > 0

    return fn


def _flag(key: str) -> Callable[[dict], bool | None]:
    return lambda d: is_on(d.get(key))


@dataclass(frozen=True, kw_only=True)
class AnkerSolixBinarySensorDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[dict], bool | None] = lambda _: None


BINARY_SENSORS: tuple[AnkerSolixBinarySensorDescription, ...] = (
    AnkerSolixBinarySensorDescription(
        key="ac_input_connected",
        name="AC Input Connected",
        device_class=BinarySensorDeviceClass.PLUG,
        is_on_fn=_flag("ac_input_plug_status"),
    ),
    AnkerSolixBinarySensorDescription(
        key="ac_charging",
        name="AC Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=_positive("ac_input_power"),
    ),
    AnkerSolixBinarySensorDescription(
        key="solar_charging",
        name="Solar / DC Charging",
        device_class=BinarySensorDeviceClass.POWER,
        icon="mdi:solar-power",
        is_on_fn=_positive("dc_input_power_total"),
    ),
    AnkerSolixBinarySensorDescription(
        key="usb_output_active",
        name="USB Output Active",
        device_class=BinarySensorDeviceClass.POWER,
        icon="mdi:usb",
        is_on_fn=_flag("usb_status"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AnkerSolixCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AnkerSolixBinarySensor(coordinator, entry, desc) for desc in BINARY_SENSORS
    )


class AnkerSolixBinarySensor(AnkerSolixEntity, BinarySensorEntity):
    """A binary sensor derived from decoded MQTT fields."""

    entity_description: AnkerSolixBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.data)
