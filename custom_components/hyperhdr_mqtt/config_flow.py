"""Config flow for HyperHDR MQTT integration."""

from __future__ import annotations
import asyncio

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .mqtt import HyperHDRManger
from .const import DOMAIN, CONF_TOPIC, CONF_BROKER, PRIORITY


from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_PORT

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOPIC, default="HyperHDR"): str,
        vol.Required(CONF_BROKER, default=""): str,
        vol.Required(CONF_PORT, default=1883): int,
        vol.Required(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
        vol.Required(PRIORITY, default=50): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=253, mode=selector.NumberSelectorMode.BOX
            )
        ),
    }
)
STEP_USER_DATA_SCHEMA_CONFIGURE = vol.Schema(
    {
        vol.Required(CONF_BROKER, default="192.168.1.250"): str,
        vol.Required(CONF_PORT, default=1883): int,
        vol.Required(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
        vol.Required(PRIORITY, default=50): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=253, mode=selector.NumberSelectorMode.BOX
            )
        ),
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    errors = {}
    if "/JsonAPI" in data[CONF_TOPIC]:
        raise ValueError("Topic without /JsonAPI")

    client = HyperHDRManger(data)
    await client.async_connect()

    if not client.connected:
        raise InvalidAuth

    try:
        info = await client.serverInfo()
    except asyncio.TimeoutError:
        raise ValueError(
            "Cannot get server info from hyperhdr, make sure HyperHDR Is configured and connected to the same MQTT Broker."
        )
    if type(info) is dict:
        sucess = info.get("success")
        if not sucess:
            raise ValueError(
                "No responses from HypherHDR, make sure MQTT is connected in HyperHDR and works!"
            )

    client.disconnect()

    return True


class HyperHDRMQTTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HyperHDR MQTT."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow for this handler."""
        return HyperHDRMQTTOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders = {}
        if user_input is not None:
            await self.check_uniqueID(user_input)
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except ValueError as ex:
                placeholders["val_error"] = str(ex)
                errors["base"] = "value_error"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_TOPIC], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders=placeholders,
            errors=errors,
        )

    async def check_uniqueID(self, data):
        unique_id = data.get(CONF_TOPIC)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()


class HyperHDRMQTTOptionsFlow(config_entries.OptionsFlow):
    """Handle a config flow for HyperHDR MQTT."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize HyperHDR MQTT options flow."""
        self.config_entry = config_entry
        self._topic = config_entry.data.get(CONF_TOPIC)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders = {}
        if user_input is not None:
            user_input[CONF_TOPIC] = self._topic
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except ValueError as ex:
                placeholders["val_error"] = str(ex)
                errors["base"] = "value_error"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_TOPIC], data=user_input
                )

        return self.async_show_form(
            step_id="init",
            data_schema=STEP_USER_DATA_SCHEMA_CONFIGURE,
            description_placeholders=placeholders,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
