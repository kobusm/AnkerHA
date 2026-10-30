"""End-to-end setup: entities from MQTT data, push updates, and commands."""
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.anker_solix_s5000.const import DOMAIN

from .conftest import DEVICE_SN, ENTRY_DATA


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_SN, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _eid(hass: HomeAssistant, platform: str, key: str) -> str:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{DEVICE_SN}_{key}")


async def test_setup_creates_entities(hass: HomeAssistant, mock_api):
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    api = mock_api[0]
    assert api.fake_session.subscriptions == {f"dt/anker_power/AS510/{DEVICE_SN}/#"}
    # status request + realtime trigger were published on connect
    assert len(api.fake_session.published) >= 2

    assert hass.states.get(_eid(hass, "sensor", "battery_soc")).state == "76"
    assert hass.states.get(_eid(hass, "sensor", "ac_output_power")).state == "350"
    assert hass.states.get(_eid(hass, "binary_sensor", "ac_input_connected")).state == STATE_ON
    assert hass.states.get(_eid(hass, "binary_sensor", "solar_charging")).state == STATE_OFF
    assert hass.states.get(_eid(hass, "switch", "ac_output")).state == STATE_ON
    assert hass.states.get(_eid(hass, "select", "display_mode")).state == "Medium"
    assert hass.states.get(_eid(hass, "select", "device_timeout")).state == "Never"

    number = hass.states.get(_eid(hass, "number", "ac_charge_limit"))
    assert float(number.state) == 1200
    # max follows the device-reported ac_input_limit_max once the library sees it
    assert number.attributes["min"] == 100


async def test_mqtt_push_updates_state(hass: HomeAssistant, mock_api):
    await _setup(hass)
    api = mock_api[0]
    await hass.async_add_executor_job(api.fake_session.receive, api, {"battery_soc": 80})
    await hass.async_block_till_done()
    assert hass.states.get(_eid(hass, "sensor", "battery_soc")).state == "80"


async def test_switch_turn_off_publishes_and_is_optimistic(hass: HomeAssistant, mock_api):
    await _setup(hass)
    api = mock_api[0]
    before = len(api.fake_session.published)
    eid = _eid(hass, "switch", "ac_output")
    await hass.services.async_call("switch", "turn_off", {"entity_id": eid}, blocking=True)
    assert len(api.fake_session.published) == before + 1
    assert hass.states.get(eid).state == STATE_OFF


async def test_select_min_soc_sends_both_limits(hass: HomeAssistant, mock_api):
    await _setup(hass)
    api = mock_api[0]
    before = len(api.fake_session.published)
    eid = _eid(hass, "select", "min_soc")
    await hass.services.async_call(
        "select", "select_option", {"entity_id": eid, "option": "20"}, blocking=True
    )
    assert len(api.fake_session.published) == before + 1


async def test_unload(hass: HomeAssistant, mock_api):
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert mock_api[0].mqttsession is None


async def test_ac_charge_limit_max_follows_device(hass: HomeAssistant, mock_api):
    """The S2000 map caps AC charging at 1200 W; the S5000's reported max must lift it."""
    await _setup(hass)
    api = mock_api[0]
    # Real library path: decoded MQTT values -> cache -> dynamic descriptors
    await hass.async_add_executor_job(
        api.fake_session.receive, api, {"ac_input_limit_max": 3600}
    )
    await hass.async_block_till_done()
    eid = _eid(hass, "number", "ac_charge_limit")
    assert hass.states.get(eid).attributes["max"] == 3600
    await hass.services.async_call(
        "number", "set_value", {"entity_id": eid, "value": 3000}, blocking=True
    )
    assert float(hass.states.get(eid).state) == 3000
