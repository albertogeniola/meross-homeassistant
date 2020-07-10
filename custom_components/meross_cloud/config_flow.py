import logging
from urllib.error import HTTPError

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from meross_iot.http_api import MerossHttpClient
from meross_iot.model.credentials import MerossCloudCreds
from meross_iot.model.http.exception import UnauthorizedException
from requests.exceptions import ConnectTimeout

from .common import PLATFORM, CONF_STORED_CREDS

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1


class MerossFlowHandler(config_entries.ConfigFlow, domain=PLATFORM):
    """Handle Meross config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Initialize the meross configuration flow."""
        """Initialize."""
        self.schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str
        })

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user interface"""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(PLATFORM)
        self._abort_if_unique_id_configured()

        if not user_input:
            return self._show_form()

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        # Test the connection to the Meross Cloud.
        try:
            creds = await self._test_authorization(username, password)
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
                CONF_PASSWORD: password,
                CONF_STORED_CREDS: {
                    'token': creds.token,
                    'key': creds.key,
                    'user_id': creds.user_id,
                    'user_email': creds.user_email,
                    'issued_on': creds.issued_on.isoformat()
                }
            }
        )

    @staticmethod
    async def _test_authorization(username: str, password: str) -> MerossCloudCreds:
        client = await MerossHttpClient.async_from_user_password(email=username, password=password)
        return client.cloud_credentials

    @callback
    def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=self.schema,
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            _LOGGER.warning("Only one configuration of Meross is allowed. If you added Meross via configuration.yaml, "
                            "you should now remove that and use the integration menu con configure it.")
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user(import_config)

