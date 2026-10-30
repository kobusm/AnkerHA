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


class VerifyCodeRequired(Exception):
    """Anker wants an emailed verification code before allowing this login."""


class CannotConnect(Exception):
    """Anker cloud unreachable or returned an unexpected error."""


_VERIFY_ERRORS = (
    errors.VerifyCodeError,
    errors.VerifyCodeExpiredError,
    errors.NeedVerifyCodeError,
    errors.VerifyCodeMaxError,
    errors.VerifyCodeNoneMatchError,
    errors.VerifyCodePasswordError,
)


async def _discover_devices(
    hass: HomeAssistant, email: str, password: str, country: str
) -> dict[str, dict]:
    """Log in and return {serial: device} for every device on the account.

    Raised exceptions carry Anker's own error text so the form can show it.
    """
    api = AnkerSolixApi(email, password, country, async_get_clientsession(hass), _LOGGER)
    try:
        # restart=True ignores the library's cached token for this email, so the
        # entered password is really checked (matters for reauth)
        if not await api.async_authenticate(restart=True):
            raise InvalidAuth("Anker returned no login token")
        await api.update_sites()
        await api.get_bind_devices()
    except (errors.AuthorizationError, errors.InvalidCredentialsError) as err:
        _LOGGER.warning("Anker login rejected for %s (%s): %s", email, country, err)
        raise InvalidAuth(str(err)) from err
    except _VERIFY_ERRORS as err:
        _LOGGER.warning("Anker login for %s needs verification: %s", email, err)
        raise VerifyCodeRequired(str(err)) from err
    except errors.AnkerSolixError as err:
        _LOGGER.warning("Anker cloud error for %s (%s): %s", email, country, err)
        raise CannotConnect(str(err)) from err
    _LOGGER.debug(
        "Anker account %s devices: %s",
        email,
        {sn: dev.get("device_pn") for sn, dev in api.devices.items()},
    )
    return dict(api.devices)


def _describe(devices: dict[str, dict]) -> str:
    """Short list of what the account returned, for the no-devices error."""
    if not devices:
        return "none"
    return ", ".join(
        f"{d.get('alias') or d.get('device_name') or 'unnamed'} (model {d.get('device_pn') or '?'})"
        for d in devices.values()
    )


async def _try_discover(
    hass: HomeAssistant, email: str, password: str, country: str
) -> tuple[dict[str, dict] | None, str | None, str]:
    """Run discovery; return (devices, error_key, Anker's error text)."""
    try:
        return await _discover_devices(hass, email, password, country), None, ""
    except InvalidAuth as err:
        return None, "invalid_auth", str(err)
    except VerifyCodeRequired as err:
        return None, "verify_code", str(err)
    except CannotConnect as err:
        return None, "cannot_connect", str(err)
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Unexpected error talking to the Anker cloud")
        return None, "cannot_connect", str(err) or type(err).__name__


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
        detail = ""

        if user_input is not None:
            creds = {
                CONF_EMAIL: user_input[CONF_EMAIL].strip(),
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_COUNTRY: user_input[CONF_COUNTRY].strip().upper(),
            }
            devices, error, detail = await _try_discover(
                self.hass, creds[CONF_EMAIL], creds[CONF_PASSWORD], creds[CONF_COUNTRY]
            )
            if error:
                errors_["base"] = error
            else:
                supported = {
                    sn: d for sn, d in devices.items() if d.get("device_pn") in SUPPORTED_MODELS
                }
                configured = self._async_current_ids(include_ignore=False)
                new = {sn: d for sn, d in supported.items() if sn not in configured}
                if supported and not new:
                    # e.g. an entry left over from an earlier failed setup
                    return self.async_abort(
                        reason="device_already_configured",
                        description_placeholders={"devices": _describe(supported)},
                    )
                if not new:
                    errors_["base"] = "no_devices"
                    detail = _describe(devices)
                else:
                    devices = new
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
        if user_input is not None:
            # keep email and country after a failed attempt
            schema = self.add_suggested_values_to_schema(
                schema,
                {CONF_EMAIL: user_input[CONF_EMAIL], CONF_COUNTRY: user_input[CONF_COUNTRY]},
            )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors_,
            description_placeholders={"error_detail": detail},
        )

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
        detail = ""
        entry = self._get_reauth_entry()

        if user_input is not None:
            _, error, detail = await _try_discover(
                self.hass,
                entry.data[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                entry.data[CONF_COUNTRY],
            )
            if error:
                errors_["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"email": entry.data[CONF_EMAIL], "error_detail": detail},
            errors=errors_,
        )
