"""Config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.anker_solix_s5000.config_flow import InvalidAuth
from custom_components.anker_solix_s5000.const import DOMAIN

from .conftest import DEVICE, DEVICE_SN, ENTRY_DATA

DISCOVER = "custom_components.anker_solix_s5000.config_flow._discover_devices"
USER_INPUT = {"email": " owner@example.com ", "password": "test-password", "country": "us"}


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_single_device_creates_entry(hass: HomeAssistant):
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    with patch(DISCOVER, return_value={DEVICE_SN: DEVICE}), patch(
        "custom_components.anker_solix_s5000.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garage S5000"
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == DEVICE_SN


async def test_multiple_devices_asks_which(hass: HomeAssistant):
    second = {"device_sn": "AS220SN", "device_pn": "AS220", "alias": ""}
    result = await _start(hass)
    with patch(DISCOVER, return_value={DEVICE_SN: DEVICE, "AS220SN": second}):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"
    with patch("custom_components.anker_solix_s5000.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_sn": "AS220SN"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Anker SOLIX S2000"


async def test_invalid_auth(hass: HomeAssistant):
    result = await _start(hass)
    with patch(DISCOVER, side_effect=InvalidAuth):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass: HomeAssistant):
    result = await _start(hass)
    with patch(DISCOVER, side_effect=OSError("boom")):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_already_configured_device_is_skipped(hass: HomeAssistant):
    MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_SN, data=ENTRY_DATA).add_to_hass(hass)
    result = await _start(hass)
    with patch(DISCOVER, return_value={DEVICE_SN: DEVICE}):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "no_devices"}


async def test_reauth_updates_password(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_SN, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    with patch(DISCOVER, return_value={DEVICE_SN: DEVICE}), patch(
        "custom_components.anker_solix_s5000.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-password"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new-password"
