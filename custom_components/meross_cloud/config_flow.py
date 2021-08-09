import logging
from typing import Dict, Any
from urllib.error import HTTPError

import voluptuous as vol
from aiohttp import ClientConnectorSSLError, ClientConnectorError
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.typing import DiscoveryInfoType
from meross_iot.http_api import MerossHttpClient
from meross_iot.model.credentials import MerossCloudCreds
from meross_iot.model.http.exception import UnauthorizedException, BadLoginException
from requests.exceptions import ConnectTimeout
import re

from .common import PLATFORM, CONF_STORED_CREDS, CONF_HTTP_ENDPOINT, CONF_MQTT_HOST, CONF_MQTT_PORT

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1
HTTP_API_RE = re.compile("(http:\/\/|https:\/\/)?([^:]+)(:([0-9]+))?")


class MerossFlowHandler(config_entries.ConfigFlow, domain=PLATFORM):
    """Handle Meross config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Initialize the meross configuration flow."""
        pass

    def _build_prefilled_schema(
        self,
        http_endpoint_default: str = "https://iot.meross.com",
        mqtt_host_default: str = "iot.meross.com",
        mqtt_host_port_default: int = 2001,
        username_default: str = "",
        password_default: str = "",
    ):
        return vol.Schema(
            {
                vol.Required(CONF_HTTP_ENDPOINT, default=http_endpoint_default): str,
                vol.Required(CONF_MQTT_HOST, default=mqtt_host_default): str,
                vol.Required(CONF_MQTT_PORT, default=mqtt_host_port_default): int,
                vol.Required(CONF_USERNAME, default=username_default): str,
                vol.Required(CONF_PASSWORD, password_default): str,
            }
        )

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle zeroconf discovery."""
        # Hostname is format: livingroom.local.
        _LOGGER.info("Discovery info: %s", discovery_info)

    async def async_step_user(self, user_input=None) -> Dict[str, Any]:
        """Handle a flow initialized by the user interface"""
        if not user_input:
            return self._show_form(schema=self._build_prefilled_schema())

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        http_api_endpoint = user_input[CONF_HTTP_ENDPOINT]  # type:str
        mqtt_host = user_input[CONF_MQTT_HOST]
        mqtt_host_port = user_input[CONF_MQTT_PORT]

        # Check the base-url is valid
        match = HTTP_API_RE.fullmatch(http_api_endpoint)

        data_schema = self._build_prefilled_schema(
            http_endpoint_default=http_api_endpoint,
            mqtt_host_default=mqtt_host,
            mqtt_host_port_default=mqtt_host_port,
            username_default=username,
            password_default=password,
        )

        if match is None:
            _LOGGER.error("Invalid Meross HTTTP api endpoint: %s", http_api_endpoint)
            return self._show_form(
                schema=data_schema, errors={"base": "invalid_http_endpoint"}
            )

        schema, domain, colonport, port = match.groups()
        if schema is None:
            _LOGGER.warning("No schema specified, assuming http")
            http_api_endpoint = "http://" + http_api_endpoint

        # Test the connection to the Meross Cloud.
        try:
            creds = await self._test_authorization(
                api_base_url=http_api_endpoint, username=username, password=password
            )
        except (BadLoginException, UnauthorizedException) as ex:
            _LOGGER.error("Unable to connect to Meross HTTP api: %s", str(ex))
            return self._show_form(
                schema=data_schema, errors={"base": "invalid_credentials"}
            )
        except (UnauthorizedException, ConnectTimeout, HTTPError) as ex:
            _LOGGER.error("Unable to connect to Meross HTTP api: %s", str(ex))
            return self._show_form(
                schema=data_schema, errors={"base": "connection_error"}
            )
        except ClientConnectorSSLError as ex:
            _LOGGER.error("Unable to connect to Meross HTTP api: %s", str(ex))
            return self._show_form(
                schema=data_schema, errors={"base": "api_invalid_ssl_code"}
            )
        except ClientConnectorError as ex:
            _LOGGER.error("Connection ERROR to HTTP api: %s", str(ex))
            if isinstance(ex.os_error, ConnectionRefusedError):
                return self._show_form(
                    schema=data_schema, errors={"base": "api_connection_refused"}
                )
        except Exception as ex:
            _LOGGER.exception("Unable to connect to Meross HTTP api, ex: %s", str(ex))
            return self._show_form(schema=data_schema, errors={"base": "unknown_error"})

        # TODO: Test MQTT connection?

        await self.async_set_unique_id(username)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_HTTP_ENDPOINT: http_api_endpoint,
                CONF_MQTT_HOST: mqtt_host,
                CONF_MQTT_PORT: mqtt_host_port,
                CONF_STORED_CREDS: {
                    "token": creds.token,
                    "key": creds.key,
                    "user_id": creds.user_id,
                    "user_email": creds.user_email,
                    "issued_on": creds.issued_on.isoformat(),
                },
            },
        )

    @staticmethod
    async def _test_authorization(
        api_base_url: str, username: str, password: str
    ) -> MerossCloudCreds:
        client = await MerossHttpClient.async_from_user_password(
            api_base_url=api_base_url, email=username, password=password
        )
        return client.cloud_credentials

    @callback
    def _show_form(self, schema, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            _LOGGER.warning(
                "Only one configuration of Meross is allowed. If you added Meross via configuration.yaml, "
                "you should now remove that and use the integration menu con configure it."
            )
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user(import_config)
