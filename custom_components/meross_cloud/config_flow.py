"""Config flow for TP-Link."""
import logging
from urllib.error import HTTPError

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from meross_iot.api import MerossHttpClient, UnauthorizedException
from requests import ConnectTimeout

from .common import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MerossFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Meross config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Initialize the meross configuration flow."""
        """Initialize."""
        self.data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user interface"""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not user_input:
            return self._show_form()

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        # Test the connection to the Meross Cloud.
        try:
            await self.hass.async_add_executor_job(
                self._test_authorization, username, password
            )

        except UnauthorizedException as ex:
            _LOGGER.error("Unable to connect to Meross HTTP api: %s", str(ex))
            return self._show_form({"base": "invalid_credentials"})
        except (UnauthorizedException, ConnectTimeout, HTTPError) as ex:
            _LOGGER.error("Unable to connect to Meross HTTP api: %s", str(ex))
            return self._show_form({"base": "connection_error"})

        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password
            }
        )

    @staticmethod
    def _test_authorization(username, password):
        client = MerossHttpClient(email=username, password=password)
        client.get_cloud_credentials()

    @callback
    def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            _LOGGER.warning("Only one configuration of Meross is allowed.")
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user(import_config)



