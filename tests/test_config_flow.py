"""Config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.anker_solix_s5000.config_flow import InvalidAuth
from custom_components.anker_solix_s5000.const import DOMAIN
from custom_components.anker_solix_s5000.solixapi import errors

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


async def test_already_configured_device_aborts_with_hint(hass: HomeAssistant):
    """A leftover entry (e.g. from a failed setup) must be named, not reported as 'no devices'."""
    MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_SN, data=ENTRY_DATA).add_to_hass(hass)
    result = await _start(hass)
    with patch(DISCOVER, return_value={DEVICE_SN: DEVICE}):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_already_configured"
    assert result["description_placeholders"]["devices"] == "Garage S5000 (model AS510)"


async def test_no_supported_device_lists_what_was_found(hass: HomeAssistant):
    other = {"device_sn": "X1", "device_pn": "A1790", "alias": "Shed F3800"}
    result = await _start(hass)
    with patch(DISCOVER, return_value={"X1": other}):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "no_devices"}
    assert result["description_placeholders"]["error_detail"] == "Shed F3800 (model A1790)"


async def test_empty_account(hass: HomeAssistant):
    result = await _start(hass)
    with patch(DISCOVER, return_value={}):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["description_placeholders"]["error_detail"] == "none"


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


API = "custom_components.anker_solix_s5000.config_flow.AnkerSolixApi"


def _api_raising(exc: Exception):
    from unittest.mock import AsyncMock, MagicMock

    api = MagicMock()
    api.async_authenticate = AsyncMock(side_effect=exc)
    return api


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (errors.InvalidCredentialsError("(26156) Anker Api Error: wrong password"), "invalid_auth"),
        (errors.AuthorizationError("Login failed for user x"), "invalid_auth"),
        (errors.NeedVerifyCodeError("(26052) Anker Api Error: need code"), "verify_code"),
        (errors.BusyError("(21105) busy"), "cannot_connect"),
    ],
)
async def test_library_errors_shown_with_anker_message(hass: HomeAssistant, exc, error):
    result = await _start(hass)
    with patch(API, return_value=_api_raising(exc)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": error}
    assert result["description_placeholders"]["error_detail"] == str(exc)


async def test_login_forces_fresh_token(hass: HomeAssistant):
    from unittest.mock import AsyncMock, MagicMock

    api = MagicMock()
    api.async_authenticate = AsyncMock(return_value=False)
    result = await _start(hass)
    with patch(API, return_value=api):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    api.async_authenticate.assert_awaited_once_with(restart=True)
    assert result["errors"] == {"base": "invalid_auth"}
