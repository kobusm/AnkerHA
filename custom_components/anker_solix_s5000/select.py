"""Select entities for Anker SOLIX S5000."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AnkerSolixCoordinator
from .entity import AnkerSolixEntity
from .helpers import build_option_labels, label_for_value
from .solixapi.mqttcmdmap import SolixMqttCommands


@dataclass(frozen=True, kw_only=True)
class AnkerSolixSelectDescription(SelectEntityDescription):
    command: str = ""
    parm: str | None = None
    state_key: str = ""
    zero_label: str | None = None
    # Other parameters of a multi-parameter command: parm -> state key holding its current value
    sibling_parms: dict[str, str] = field(default_factory=dict)


SELECTS: tuple[AnkerSolixSelectDescription, ...] = (
    AnkerSolixSelectDescription(
        key="display_mode",
        name="Display Brightness",
        icon="mdi:brightness-6",
        command=SolixMqttCommands.display_mode_select,
        state_key="display_mode",
        entity_category=EntityCategory.CONFIG,
    ),
    AnkerSolixSelectDescription(
        key="display_timeout",
        name="Display Timeout (s)",
        icon="mdi:monitor-off",
        command=SolixMqttCommands.display_timeout_seconds,
        state_key="display_timeout_seconds",
        zero_label="Never",
        entity_category=EntityCategory.CONFIG,
    ),
    AnkerSolixSelectDescription(
        key="device_timeout",
        name="Device Auto-Off (min)",
        icon="mdi:timer-off-outline",
        command=SolixMqttCommands.device_timeout_minutes,
        state_key="device_timeout_minutes",
        zero_label="Never",
        entity_category=EntityCategory.CONFIG,
    ),
    AnkerSolixSelectDescription(
        key="ac_output_timeout",
        name="AC Output Auto-Off (min)",
        icon="mdi:power-socket-off",
        command=SolixMqttCommands.ac_output_timeout_minutes,
        state_key="ac_output_timeout_minutes",
        zero_label="Never",
        entity_category=EntityCategory.CONFIG,
    ),
    AnkerSolixSelectDescription(
        key="max_soc",
        name="Max Charge Level (%)",
        icon="mdi:battery-arrow-up",
        command=SolixMqttCommands.soc_limits,
        parm="set_max_soc",
        state_key="max_soc",
        sibling_parms={"set_min_soc": "min_soc"},
        entity_category=EntityCategory.CONFIG,
    ),
    AnkerSolixSelectDescription(
        key="min_soc",
        name="Min Discharge Level (%)",
        icon="mdi:battery-arrow-down",
        command=SolixMqttCommands.soc_limits,
        parm="set_min_soc",
        state_key="min_soc",
        sibling_parms={"set_max_soc": "max_soc"},
        entity_category=EntityCategory.CONFIG,
    ),
    AnkerSolixSelectDescription(
        key="temp_unit",
        name="Temperature Unit",
        icon="mdi:thermometer",
        command=SolixMqttCommands.temp_unit_switch,
        state_key="temp_unit_fahrenheit",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AnkerSolixCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        AnkerSolixSelect(coordinator, entry, desc)
        for desc in SELECTS
        if coordinator.supports(desc.command)
    ]
    async_add_entities(e for e in entities if e.options)


class AnkerSolixSelect(AnkerSolixEntity, SelectEntity):
    """An option setting written to the S5000 via MQTT; options come from the library."""

    entity_description: AnkerSolixSelectDescription

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        desc = self.entity_description
        option_map = self.coordinator.mqtt_device.get_cmd_parm_option_map(
            cmd=desc.command, parm=desc.parm
        )
        self._labels: dict[str, Any] = build_option_labels(option_map, desc.zero_label)
        self._attr_options = list(self._labels)

    @property
    def current_option(self) -> str | None:
        return label_for_value(self._labels, self.data.get(self.entity_description.state_key))

    async def async_select_option(self, option: str) -> None:
        desc = self.entity_description
        if option not in self._labels:
            raise HomeAssistantError(f"Unsupported option: {option}")
        value = self._labels[option]
        if desc.sibling_parms:
            # Multi-parameter command: resend the other limits unchanged
            parm_map = {desc.parm: value}
            for parm, state_key in desc.sibling_parms.items():
                if (current := self.data.get(state_key)) is None:
                    raise HomeAssistantError(
                        f"Current '{state_key}' unknown yet, try again once the device reported it"
                    )
                parm_map[parm] = current
            await self.coordinator.async_run_command(desc.command, parm_map=parm_map)
        else:
            await self.coordinator.async_run_command(desc.command, value, parm=desc.parm)
