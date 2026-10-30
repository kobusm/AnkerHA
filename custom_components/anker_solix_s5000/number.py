"""Number entities for Anker SOLIX S5000."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_AC_INPUT_LIMIT_MAX, DOMAIN
from .coordinator import AnkerSolixCoordinator
from .entity import AnkerSolixEntity
from .helpers import to_number
from .solixapi.mqttcmdmap import VALUE_MAX, VALUE_MIN, VALUE_STEP, SolixMqttCommands


@dataclass(frozen=True, kw_only=True)
class AnkerSolixNumberDescription(NumberEntityDescription):
    command: str = ""
    parm: str = ""
    state_key: str = ""


# Ranges come from the library's command descriptors at runtime (they track
# device state such as ac_input_limit_max); the values here are only fallbacks.
NUMBERS: tuple[AnkerSolixNumberDescription, ...] = (
    AnkerSolixNumberDescription(
        key="ac_charge_limit",
        name="AC Charging Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=NumberDeviceClass.POWER,
        native_min_value=100,
        native_max_value=DEFAULT_AC_INPUT_LIMIT_MAX,
        native_step=100,
        mode=NumberMode.SLIDER,
        icon="mdi:transmission-tower-import",
        command=SolixMqttCommands.ac_charge_limit,
        parm="set_ac_input_limit",
        state_key="ac_input_limit",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AnkerSolixCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AnkerSolixNumber(coordinator, entry, desc)
        for desc in NUMBERS
        if coordinator.supports(desc.command)
    )


class AnkerSolixNumber(AnkerSolixEntity, NumberEntity):
    """A numeric setting written to the S5000 via MQTT."""

    entity_description: AnkerSolixNumberDescription

    def _descriptor(self) -> dict:
        dev = self.coordinator.mqtt_device
        if dev is None:
            return {}
        desc = self.entity_description
        return dev.get_cmd_parms(cmd=desc.command, all=True).get(desc.parm, {})

    @property
    def native_min_value(self) -> float:
        return self._descriptor().get(VALUE_MIN, self.entity_description.native_min_value)

    @property
    def native_max_value(self) -> float:
        return self._descriptor().get(VALUE_MAX, self.entity_description.native_max_value)

    @property
    def native_step(self) -> float | None:
        return self._descriptor().get(VALUE_STEP, self.entity_description.native_step)

    @property
    def native_value(self) -> float | None:
        return to_number(self.data.get(self.entity_description.state_key))

    async def async_set_native_value(self, value: float) -> None:
        desc = self.entity_description
        await self.coordinator.async_run_command(
            desc.command, int(value), parm=desc.parm
        )
