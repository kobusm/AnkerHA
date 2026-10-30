"""S5000 profile registration on the vendored library."""
from custom_components.anker_solix_s5000 import s5000
from custom_components.anker_solix_s5000.solixapi import mqtt_pps
from custom_components.anker_solix_s5000.solixapi.mqttcmdmap import SolixMqttCommands
from custom_components.anker_solix_s5000.solixapi.mqttmap import SOLIXMQTTMAP


def test_profile_registers_s5000_as_s2000_clone():
    s5000.register_s5000_profile()
    assert "AS510" in SOLIXMQTTMAP
    assert SOLIXMQTTMAP["AS510"].keys() == SOLIXMQTTMAP["AS220"].keys()
    assert "AS510" in mqtt_pps.MODELS
    # FEATURES shares the MODELS set, so controls are enabled too
    assert "AS510" in mqtt_pps.FEATURES[SolixMqttCommands.ac_output_switch]


def test_profile_is_idempotent():
    s5000.register_s5000_profile()
    assert s5000.register_s5000_profile() is False


def test_s5000_map_is_independent_copy():
    s5000.register_s5000_profile()
    assert SOLIXMQTTMAP["AS510"] is not SOLIXMQTTMAP["AS220"]
    SOLIXMQTTMAP["AS510"]["__probe__"] = {}
    try:
        assert "__probe__" not in SOLIXMQTTMAP["AS220"]
    finally:
        del SOLIXMQTTMAP["AS510"]["__probe__"]
