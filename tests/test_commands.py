"""Every control the entities use must exist for AS510 and encode to an MQTT payload."""
import pytest

from custom_components.anker_solix_s5000.number import NUMBERS
from custom_components.anker_solix_s5000.s5000 import register_s5000_profile
from custom_components.anker_solix_s5000.select import SELECTS
from custom_components.anker_solix_s5000.solixapi.mqtt_factory import SolixMqttDeviceFactory
from custom_components.anker_solix_s5000.solixapi.mqtt_pps import SolixMqttDevicePps
from custom_components.anker_solix_s5000.switch import SWITCHES

from .conftest import DEVICE, DEVICE_SN, make_api


@pytest.fixture
def device() -> SolixMqttDevicePps:
    register_s5000_profile()
    api = make_api("owner@example.com", "pw", "US")
    api._update_dev(dict(DEVICE))
    dev = SolixMqttDeviceFactory(api_instance=api, device_sn=DEVICE_SN).create_device()
    assert isinstance(dev, SolixMqttDevicePps)
    return dev


def test_all_entity_commands_supported(device):
    used = {d.command for d in (*SWITCHES, *NUMBERS, *SELECTS)}
    assert used - set(device.controls) == set()


@pytest.mark.parametrize("desc", SWITCHES, ids=lambda d: d.key)
@pytest.mark.parametrize("value", ["on", "off"])
async def test_switch_commands_encode(device, desc, value):
    resp = await device.run_command(cmd=desc.command, value=value, toFile=True)
    assert resp == {desc.state_key: 1 if value == "on" else 0}


async def test_ac_charge_limit_encodes(device):
    desc = NUMBERS[0]
    resp = await device.run_command(desc.command, 800, parm=desc.parm, toFile=True)
    assert resp == {"ac_input_limit": 800}


async def test_ac_charge_limit_out_of_range_rejected(device):
    desc = NUMBERS[0]
    assert await device.run_command(desc.command, 50, parm=desc.parm, toFile=True) is None


@pytest.mark.parametrize("desc", SELECTS, ids=lambda d: d.key)
async def test_select_options_encode(device, desc):
    options = device.get_cmd_parm_option_map(cmd=desc.command, parm=desc.parm)
    assert options, f"no options for {desc.key}"
    value = next(iter(options.values()))
    if desc.sibling_parms:
        parm_map = {desc.parm: value, **{p: 100 if "max" in p else 10 for p in desc.sibling_parms}}
        resp = await device.run_command(desc.command, parm_map=parm_map, toFile=True)
    else:
        resp = await device.run_command(desc.command, value, parm=desc.parm, toFile=True)
    assert resp is not None
