"""Sensor entities for Anker SOLIX S5000."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AnkerSolixCoordinator
from .entity import AnkerSolixEntity
from .helpers import is_on, to_number


@dataclass(frozen=True, kw_only=True)
class AnkerSolixSensorDescription(SensorEntityDescription):
    # MQTT field name as decoded by the library (S2000 / AS220 schema)
    data_key: str = ""
    numeric: bool = True


def _power(key: str, name: str, **kw) -> AnkerSolixSensorDescription:
    return AnkerSolixSensorDescription(
        key=key,
        data_key=key,
        name=name,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        **kw,
    )


SENSORS: tuple[AnkerSolixSensorDescription, ...] = (
    # ── Battery ─────────────────────────────────────────────────────────────
    AnkerSolixSensorDescription(
        key="battery_soc",
        data_key="battery_soc",
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AnkerSolixSensorDescription(
        key="main_battery_soc",
        data_key="main_battery_soc",
        name="Main Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    AnkerSolixSensorDescription(
        key="battery_soh",
        data_key="battery_soh",
        name="Battery Health",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-heart-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AnkerSolixSensorDescription(
        key="remaining_time_hours",
        data_key="remaining_time_hours",
        name="Remaining Time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    AnkerSolixSensorDescription(
        key="temperature",
        data_key="temperature",
        name="Temperature",
        # Unit follows the device's own °C/°F setting, see native_unit_of_measurement
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # ── Power flow ──────────────────────────────────────────────────────────
    _power("input_power_total", "Total Input Power"),
    _power("output_power_total", "Total Output Power"),
    _power("ac_input_power", "AC Input Power"),
    _power("ac_output_power", "AC Output Power"),
    _power("dc_input_power_total", "Solar / DC Input Power", icon="mdi:solar-power"),
    _power("usb_power", "USB Output Power", icon="mdi:usb"),
    AnkerSolixSensorDescription(
        key="ac_frequency",
        data_key="ac_frequency",
        name="AC Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # ── Settings mirrored as read-only diagnostics ─────────────────────────
    _power(
        "ac_input_limit_max",
        "AC Charging Power Max",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    AnkerSolixSensorDescription(
        key="ac_output_timer_remaining_seconds",
        data_key="ac_output_timer_remaining_seconds",
        name="AC Output Timer Remaining",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
    ),
    # ── Diagnostics ─────────────────────────────────────────────────────────
    AnkerSolixSensorDescription(
        key="wifi_signal",
        data_key="wifi_signal",
        name="Wi-Fi Signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Raw status codes: meaning not yet decoded for the S2000/S5000
    AnkerSolixSensorDescription(
        key="battery_status",
        data_key="battery_status",
        name="Battery Status Code",
        icon="mdi:battery-unknown",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    AnkerSolixSensorDescription(
        key="working_status",
        data_key="working_status",
        name="Working Status Code",
        icon="mdi:state-machine",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    AnkerSolixSensorDescription(
        key="sw_version",
        data_key="sw_version",
        name="Firmware Version",
        icon="mdi:chip",
        numeric=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AnkerSolixCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AnkerSolixSensor(coordinator, entry, desc) for desc in SENSORS
    )


class AnkerSolixSensor(AnkerSolixEntity, SensorEntity):
    """A sensor reading one decoded MQTT field."""

    entity_description: AnkerSolixSensorDescription

    @property
    def native_value(self):
        value = self.data.get(self.entity_description.data_key)
        if not self.entity_description.numeric:
            return None if value is None else str(value)
        return to_number(value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if (
            self.entity_description.device_class == SensorDeviceClass.TEMPERATURE
            and is_on(self.data.get("temp_unit_fahrenheit"))
        ):
            return UnitOfTemperature.FAHRENHEIT
        return self.entity_description.native_unit_of_measurement
