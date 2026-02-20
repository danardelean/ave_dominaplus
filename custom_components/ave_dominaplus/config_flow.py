"""Config flow for the AVE ws integration."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

import voluptuous as vol

import homeassistant
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .web_server import AveWebServer

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS, default="192.168.1.10"): str,
        vol.Required("get_entities_names", default=True): bool,
        vol.Required("fetch_sensor_areas", default=True): bool,
        vol.Required("fetch_sensors", default=True): bool,
        vol.Required("fetch_lights", default=True): bool,
        vol.Required("fetch_thermostats", default=True): bool,
    }
)


class AveWsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AVE ws."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS]}
            )

            try:
                info = await self.validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # self.async_set_unique_id(user_id)
            # self._abort_if_unique_id_mismatch()
            try:
                await self.validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def validate_input(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate the user input allows us to connect.

        Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
        """
        webserver = AveWebServer(settings_data=MappingProxyType(data), hass=self.hass)
        resp_code, _resp_content = await webserver.get_device_list_bridge()
        if resp_code == 900:
            raise CannotConnect
        if resp_code != 200:
            _LOGGER.error("AVE dominaplus: Cannot connect to the web server")
            raise CannotConnect

        mac_address: str = await self._configure_unique_id(webserver)
        return {"title": f"AVE webserver {mac_address}"}

    async def _configure_unique_id(self, webserver: AveWebServer) -> str:
        mac_address: str | None = await webserver.tryget_mac_address()
        if mac_address is None:
            mac_address = ""
        else:
            mac_address = homeassistant.helpers.device_registry.format_mac(mac_address)
            await self.async_set_unique_id(mac_address)
        return mac_address


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
