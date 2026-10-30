"""Shared fixtures: a real AnkerSolixApi with network and MQTT replaced by fakes."""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.anker_solix_s5000.const import CONF_COUNTRY, CONF_DEVICE_SN, DOMAIN
from custom_components.anker_solix_s5000.solixapi.api import AnkerSolixApi
from custom_components.anker_solix_s5000.solixapi.mqtt import AnkerSolixMqttSession
from custom_components.anker_solix_s5000.solixapi.mqtttypes import MqttDataStats

DEVICE_SN = "AS510TESTSN00001"
DEVICE = {"device_sn": DEVICE_SN, "device_pn": "AS510", "alias": "Garage S5000"}
ENTRY_DATA = {
    "email": "owner@example.com",
    "password": "test-password",
    CONF_COUNTRY: "US",
    CONF_DEVICE_SN: DEVICE_SN,
}

# Representative S2000-schema status as decoded from a 0421 message
STATUS = {
    "battery_soc": 76,
    "battery_soh": 100,
    "temperature": 27,
    "temp_unit_fahrenheit": 0,
    "ac_input_power": 1200,
    "ac_output_power": 350,
    "dc_input_power_total": 0,
    "input_power_total": 1200,
    "output_power_total": 362,
    "usb_power": 12,
    "usb_status": 1,
    "ac_input_plug_status": 1,
    "ac_output_power_switch": 1,
    "ac_fast_charge_switch": 0,
    "ac_input_limit": 1200,
    "ac_input_limit_max": 3600,
    "display_switch": 1,
    "display_mode": 2,
    "display_timeout_seconds": 60,
    "device_timeout_minutes": 0,
    "ac_output_timeout_minutes": 120,
    "port_memory_switch": 1,
    "max_soc": 100,
    "min_soc": 10,
    "remaining_time_hours": 12.5,
    "sw_version": "v1.2.3",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


class FakeMqttSession(AnkerSolixMqttSession):
    """Real library MQTT session with the broker connection replaced; records traffic."""

    def __init__(self, apisession) -> None:
        super().__init__(apisession=apisession)
        self.mqtt_info = {"app_name": "anker_power"}
        self.mqtt_stats = MqttDataStats()  # normally created on connect
        self.published: list[str] = []
        self.connected = True

    def is_connected(self) -> bool:
        return self.connected

    def subscribe(self, topic: str) -> None:
        self.subscriptions.add(topic)

    def publish(self, deviceDict: dict, hexbytes: str, encoding_type=None):
        self.published.append(hexbytes)
        info = MagicMock()
        info.is_published.return_value = True
        return None, info

    def cleanup(self) -> None:
        self.connected = False

    def receive(self, api: AnkerSolixApi, values: dict) -> None:
        """Replay what on_message does for a decoded device message (paho thread)."""
        self.mqtt_data.setdefault(DEVICE_SN, {}).update(values)
        api.mqtt_received(self, "dt/anker_power/AS510/sn/param_info", None, b"", "AS510", DEVICE_SN, values)


def make_api(*args, **kwargs) -> AnkerSolixApi:
    """Real library Api object, minus the cloud and the MQTT broker."""
    api = AnkerSolixApi(*args[:3], None, logging.getLogger("test.solixapi"))
    api.async_authenticate = AsyncMock(return_value=True)
    api.update_sites = AsyncMock(return_value={})

    async def bind_devices(*_a, **_k):
        api._update_dev(dict(DEVICE))
        return {}

    api.get_bind_devices = bind_devices
    session = FakeMqttSession(api.apisession)

    async def start_mqtt(*_a, **_k):
        api.mqttsession = session
        api.devices[DEVICE_SN]["mqtt_data"] = dict(STATUS)
        return session

    api.startMqttSession = start_mqtt
    api.fake_session = session
    return api


@pytest.fixture
def mock_api():
    """Patch the coordinator to build fake-backed Api objects; yields the created instances."""
    created: list[AnkerSolixApi] = []

    def factory(*args, **kwargs):
        api = make_api(*args, **kwargs)
        created.append(api)
        return api

    with patch(
        "custom_components.anker_solix_s5000.coordinator.AnkerSolixApi", side_effect=factory
    ):
        yield created


__all__ = ["DOMAIN", "DEVICE", "DEVICE_SN", "ENTRY_DATA", "STATUS", "make_api"]
