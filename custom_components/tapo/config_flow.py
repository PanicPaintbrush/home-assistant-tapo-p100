"""Config flow for tapo integration."""
import logging
import re

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant import data_entry_flow
from plugp100 import TapoApiClient, TapoApiClientConfig

from custom_components.tapo.const import (
    DOMAIN,
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
)  # pylint:disable=unused-import


_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_HOST, description="The IP address of your tapo device (must be static)"
        ): str,
        vol.Required(
            CONF_USERNAME, description="The username used with Tapo App, so your email"
        ): str,
        vol.Required(CONF_PASSWORD, description="The password used with Tapo App"): str,
    }
)


@config_entries.HANDLERS.register(DOMAIN)
class TapoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for tapo."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors = {}

        try:
            entry_metadata = await self._validate_input(user_input)
            # check if the same device has already been configured
            await self.async_set_unique_id(entry_metadata["unique_id"])
            self._abort_if_unique_id_configured()
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except InvalidHost:
            errors["base"] = "invalid_hostname"
        except data_entry_flow.AbortFlow:
            return self.async_abort(reason="already_configured")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=entry_metadata["title"], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def _validate_input(self, data):
        """Validate the user input allows us to connect.

        Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
        """

        if not data[CONF_HOST]:
            raise InvalidHost

        tapo_api = await self._test_credentials(
            data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD]
        )

        state = await tapo_api.get_state()
        if not state:
            raise CannotConnect

        # Return info that you want to store in the config entry.
        return {"title": state.nickname, "unique_id": state.device_id}

    async def _test_credentials(self, address, username, password) -> TapoApiClient:
        try:
            session = async_create_clientsession(self.hass)
            config = TapoApiClientConfig(address, username, password, session)
            client = TapoApiClient.from_config(config)
            await client.login()
            return client
        except Exception as error:
            raise InvalidAuth from error


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
