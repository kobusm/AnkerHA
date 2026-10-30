"""Config flow for Anker SOLIX S5000."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_COUNTRY, CONF_DEVICE_SN, DOMAIN
from .s5000 import SUPPORTED_MODELS
from .solixapi import errors
from .solixapi.api import AnkerSolixApi

_LOGGER = logging.getLogger(__name__)


class InvalidAuth(Exception):
    """Credentials rejected by the Anker cloud."""


async def _discover_devices(
    hass: HomeAssistant, email: str, password: str, country: str
) -> dict[str, dict]:
    """Log in and return {serial: device} for supported models on the account."""
    api = AnkerSolixApi(email, password, country, async_get_clientsession(hass), _LOGGER)
    try:
        if not await api.async_authenticate():
            raise InvalidAuth
    except (errors.AuthorizationError, errors.InvalidCredentialsError) as err:
        raise InvalidAuth from err
    await api.update_sites()
    await api.get_bind_devices()
    return {
        sn: dev
        for sn, dev in api.devices.items()
        if dev.get("device_pn") in SUPPORTED_MODELS
    }


def _title(dev: dict) -> str:
    return dev.get("alias") or f"Anker {SUPPORTED_MODELS.get(dev.get('device_pn', ''), 'S5000')}"


class AnkerSolixS5000ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Anker SOLIX S5000."""

    VERSION = 1

    def __init__(self) -> None:
        self._credentials: dict[str, str] = {}
        self._devices: dict[str, dict] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors_: dict[str, str] = {}

        if user_input is not None:
            creds = {
                CONF_EMAIL: user_input[CONF_EMAIL].strip(),
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_COUNTRY: user_input[CONF_COUNTRY].strip().upper(),
            }
            try:
                devices = await _discover_devices(
                    self.hass, creds[CONF_EMAIL], creds[CONF_PASSWORD], creds[CONF_COUNTRY]
                )
            except InvalidAuth:
                errors_["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error talking to the Anker cloud")
                errors_["base"] = "cannot_connect"
            else:
                configured = self._async_current_ids()
                devices = {sn: d for sn, d in devices.items() if sn not in configured}
                if not devices:
                    errors_["base"] = "no_devices"
                else:
                    self._credentials = creds
                    self._devices = devices
                    if len(devices) == 1:
                        return await self._create(next(iter(devices)))
                    return await self.async_step_device()

        country = (self.hass.config.country or "US").upper()
        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_COUNTRY, default=country): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors_)

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self._create(user_input[CONF_DEVICE_SN])

        choices = {sn: f"{_title(d)} ({sn})" for sn, d in self._devices.items()}
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_SN): vol.In(choices)}),
        )

    async def _create(self, sn: str) -> ConfigFlowResult:
        await self.async_set_unique_id(sn)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=_title(self._devices[sn]),
            data={**self._credentials, CONF_DEVICE_SN: sn},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors_: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                await _discover_devices(
                    self.hass,
                    entry.data[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    entry.data[CONF_COUNTRY],
                )
            except InvalidAuth:
                errors_["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error talking to the Anker cloud")
                errors_["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors_,
        )
