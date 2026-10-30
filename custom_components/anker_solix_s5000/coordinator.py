"""DataUpdateCoordinator for Anker SOLIX S5000 (cloud login + Anker MQTT push)."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COUNTRY,
    CONF_DEVICE_SN,
    DOMAIN,
    REALTIME_TRIGGER_TIMEOUT,
    SCAN_INTERVAL,
)
from .s5000 import register_s5000_profile
from .solixapi import errors
from .solixapi.api import AnkerSolixApi
from .solixapi.mqtt_device import SolixMqttDevice
from .solixapi.mqtt_factory import SolixMqttDeviceFactory

_LOGGER = logging.getLogger(__name__)

_AUTH_ERRORS = (errors.AuthorizationError, errors.InvalidCredentialsError)


class AnkerSolixCoordinator(DataUpdateCoordinator[dict]):
    """Manages one S5000 via the Anker cloud and distributes MQTT data to entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._entry = entry
        self.device_sn: str = entry.data[CONF_DEVICE_SN]
        self.api: AnkerSolixApi | None = None
        self.mqtt_device: SolixMqttDevice | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    @property
    def device(self) -> dict:
        """Cloud device record (alias, model, firmware)."""
        if self.api is None:
            return {}
        return self.api.devices.get(self.device_sn) or {}

    async def async_setup(self) -> None:
        """Log in, locate the device and open the MQTT session."""
        register_s5000_profile()
        self.api = AnkerSolixApi(
            self._entry.data[CONF_EMAIL],
            self._entry.data[CONF_PASSWORD],
            self._entry.data[CONF_COUNTRY],
            async_get_clientsession(self.hass),
            _LOGGER,
        )
        try:
            # The return value is False when a cached token was merely loaded
            # (the config flow just cached one); the first request validates it
            # and re-logs in on 401. Real rejections arrive as exceptions.
            await self.api.async_authenticate()
            await self.api.update_sites()
            await self.api.get_bind_devices()
        except _AUTH_ERRORS as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except errors.AnkerSolixError as err:
            raise ConfigEntryNotReady(f"Anker cloud error: {err}") from err

        if self.device_sn not in self.api.devices:
            raise ConfigEntryNotReady(
                f"Device {self.device_sn} not found on this Anker account"
            )

        self.mqtt_device = SolixMqttDeviceFactory(
            api_instance=self.api, device_sn=self.device_sn
        ).create_device()
        self.api.mqtt_update_callback(self._on_mqtt_update)
        await self._async_ensure_mqtt()

    async def async_shutdown(self) -> None:
        """Close the MQTT session (paho joins its network thread, so run off-loop)."""
        await super().async_shutdown()
        if self.api is not None:
            await self.hass.async_add_executor_job(self.api.stopMqttSession)

    def _snapshot(self) -> dict:
        return dict(self.device.get("mqtt_data") or {})

    def _on_mqtt_update(self, device_sn: str) -> None:
        """Called from the paho network thread whenever new values were decoded."""
        if device_sn != self.device_sn:
            return
        # Copy on the paho thread, which is the only writer of mqtt_data
        data = self._snapshot()
        self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, data)

    async def _async_ensure_mqtt(self) -> None:
        """(Re)connect, subscribe to the device topic and re-arm real-time publishing."""
        assert self.api is not None and self.mqtt_device is not None
        session = self.api.mqttsession
        if session is None or not session.is_connected():
            session = await self.api.startMqttSession()
            if session is None:
                raise UpdateFailed("Cannot connect to Anker MQTT server")
            # subscribe() is idempotent and the session re-subscribes on reconnect
            if prefix := session.get_topic_prefix(deviceDict=self.device):
                session.subscribe(f"{prefix}#")
            # One-off full status (message 0900) so entities populate immediately
            await self.mqtt_device.status_request()
        await self.mqtt_device.realtime_trigger(timeout=REALTIME_TRIGGER_TIMEOUT)

    async def _async_update_data(self) -> dict:
        """Periodic: keep the MQTT session alive and the real-time stream armed."""
        try:
            await self._async_ensure_mqtt()
        except UpdateFailed:
            raise
        except _AUTH_ERRORS as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001 - library raises a wide range
            raise UpdateFailed(f"Anker MQTT error: {err}") from err
        return self._snapshot() or self.data or {}

    async def async_run_command(
        self,
        cmd: str,
        value: Any = None,
        parm: str | None = None,
        parm_map: dict | None = None,
    ) -> None:
        """Validate and publish a device command, then apply the optimistic state."""
        if self.mqtt_device is None:
            raise HomeAssistantError("S5000 is not connected")
        resp = await self.mqtt_device.run_command(
            cmd=cmd, value=value, parm=parm, parm_map=parm_map
        )
        if resp is None:
            raise HomeAssistantError(
                f"S5000 command '{cmd}' was rejected (invalid value, or device in local MQTT mode)"
            )
        if resp:
            # resp holds the expected state fields; the device confirms via MQTT shortly
            self.async_set_updated_data({**(self.data or {}), **resp})

    def supports(self, cmd: str) -> bool:
        """True if the library exposes this control for the device model."""
        return self.mqtt_device is not None and cmd in self.mqtt_device.controls
