"""Switch entities for Anker SOLIX S5000."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AnkerSolixCoordinator
from .entity import AnkerSolixEntity
from .helpers import is_on
from .solixapi.mqttcmdmap import SolixMqttCommands


@dataclass(frozen=True, kw_only=True)
class AnkerSolixSwitchDescription(SwitchEntityDescription):
    command: str = ""
    state_key: str = ""


SWITCHES: tuple[AnkerSolixSwitchDescription, ...] = (
    AnkerSolixSwitchDescription(
        key="ac_output",
        name="AC Output",
        device_class=SwitchDeviceClass.OUTLET,
        icon="mdi:power-socket",
        command=SolixMqttCommands.ac_output_switch,
        state_key="ac_output_power_switch",
    ),
    AnkerSolixSwitchDescription(
        key="ac_fast_charge",
        name="AC Fast Charging",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:battery-charging-high",
        command=SolixMqttCommands.ac_fast_charge_switch,
        state_key="ac_fast_charge_switch",
    ),
    AnkerSolixSwitchDescription(
        key="display",
        name="Display",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:monitor",
        command=SolixMqttCommands.display_switch,
        state_key="display_switch",
        entity_category=EntityCategory.CONFIG,
    ),
    AnkerSolixSwitchDescription(
        key="port_memory",
        name="Port Memory",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:memory",
        command=SolixMqttCommands.port_memory_switch,
        state_key="port_memory_switch",
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
        AnkerSolixSwitch(coordinator, entry, desc)
        for desc in SWITCHES
        if coordinator.supports(desc.command)
    )


class AnkerSolixSwitch(AnkerSolixEntity, SwitchEntity):
    """A switch that publishes an MQTT command to the S5000."""

    entity_description: AnkerSolixSwitchDescription

    @property
    def is_on(self) -> bool | None:
        return is_on(self.data.get(self.entity_description.state_key))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_run_command(self.entity_description.command, "on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_run_command(self.entity_description.command, "off")
