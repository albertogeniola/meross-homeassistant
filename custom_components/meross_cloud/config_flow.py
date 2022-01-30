import logging
from typing import Dict, Any, Optional
from urllib.error import HTTPError

import voluptuous as vol
from aiohttp import ClientConnectorSSLError, ClientConnectorError
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import DiscoveryInfoType
from meross_iot.http_api import MerossHttpClient
from meross_iot.model.credentials import MerossCloudCreds
from meross_iot.model.http.exception import UnauthorizedException, BadLoginException
from requests.exceptions import ConnectTimeout

from .common import DOMAIN, CONF_STORED_CREDS, CONF_HTTP_ENDPOINT, CONF_MQTT_SKIP_CERT_VALIDATION, \
    CONF_OPT_CUSTOM_USER_AGENT, HTTP_API_RE

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1


class MerossFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Meross config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self) -> None:
        """Initialize flow."""
        self._http_api: str = "https://iot.meross.com"
        self._username: Optional[str] = None
        self._password: Optional[str] = None

    def _build_setup_schema(
        self,
        http_endpoint: str = None,
        username: str = None,
        password: str = None,
        skip_cert_validation: bool = True
    ) -> vol.Schema:
        http_endpoint_default = http_endpoint if http_endpoint is not None else self._http_api
        username_default = username if username is not None else self._username
        password_default = password if password is not None else self._password
        return vol.Schema(
            {
                vol.Required(CONF_HTTP_ENDPOINT, default=http_endpoint_default): str,
                vol.Required(CONF_USERNAME, default=username_default): str,
                vol.Required(CONF_PASSWORD, default=password_default): str,
                vol.Required(CONF_MQTT_SKIP_CERT_VALIDATION,
                             msg="Set this flag if using you local MQTT broker",
                             default=skip_cert_validation,
                             description="When set, Meross Manager skips MQTT certificate validation."): bool,
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

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType) -> FlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.info("Discovery info: %s", discovery_info)
        # Returns something like the following
        # {'host': '192.168.2.115', 'port': 2002, 'hostname': 'Meross Local Broker.local.', 'type': '_meross-api._tcp.local.', 'name': 'HTTP Local Broker._m...tcp.local.', 'properties': {'_raw': {}}}
        api_host = discovery_info[CONF_HOST]
        api_port = discovery_info[CONF_PORT]
        api_url = f"http://{api_host}:{api_port}"
        
        # Check if already configured
        await self.async_set_unique_id(api_url)
        self._abort_if_unique_id_configured(
            updates={CONF_HTTP_ENDPOINT: api_url}
        )

        for entry in self._async_current_entries():            
            # Is this address or IP address already configured?
            if CONF_HTTP_ENDPOINT in entry.data and entry.data[CONF_HTTP_ENDPOINT]==api_url:    
                return self.async_abort(reason="already_configured")
        
        self._http_api = api_url
        return await self.async_step_user()

    async def async_step_user(self, user_input=None) -> Dict[str, Any]:
        """Handle a flow initialized by the user interface"""
        _LOGGER.debug("Starting ASYNC_STEP_USER")
        if not user_input:
            _LOGGER.debug("Empty user_input, showing default prefilled form")
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_setup_schema(),
                errors={},
            )
        
        _LOGGER.debug("UserInput was provided: form data will be populated with that")
        http_api_endpoint = user_input.get(CONF_HTTP_ENDPOINT)
        username = user_input.get(CONF_USERNAME)
        password = user_input.get(CONF_PASSWORD)
        skip_cert_validation = user_input.get(CONF_MQTT_SKIP_CERT_VALIDATION)

        # Check if we have everything we need
        if username is None or password is None or http_api_endpoint is None:
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_setup_schema(
                    http_endpoint=http_api_endpoint),
                errors={"base": "missing_credentials"},
            )
        
        # Check the base-url is valid
        match = HTTP_API_RE.fullmatch(http_api_endpoint)

        data_schema = self._build_setup_schema(
            http_endpoint=http_api_endpoint,
            username=username,
            password=password,
        )

        if match is None:
            _LOGGER.error("Invalid Meross HTTTP API endpoint: %s", http_api_endpoint)
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors={"base": "invalid_http_endpoint"}
            )
        else:
            _LOGGER.debug("Meross HTTP API endpoint looks good: %s.", http_api_endpoint)

        schema, domain, colonport, port = match.groups()
        if schema is None:
            _LOGGER.warning("No schema specified, assuming http")
            http_api_endpoint = "http://" + http_api_endpoint

        # Test the connection to the Meross Cloud.
        try:
            creds = await self._test_authorization(
                api_base_url=http_api_endpoint, username=username, password=password
            )
            _LOGGER.info("HTTP API successful tested against %s.", http_api_endpoint)
        except (BadLoginException, UnauthorizedException) as ex:
            _LOGGER.error("Unable to connect to Meross HTTP api: %s", str(ex))
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors={"base": "invalid_credentials"}
            )
        except (UnauthorizedException, ConnectTimeout, HTTPError) as ex:
            _LOGGER.error("Unable to connect to Meross HTTP api: %s", str(ex))
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors={"base": "connection_error"}
            )
        except ClientConnectorSSLError as ex:
            _LOGGER.error("Unable to connect to Meross HTTP api: %s", str(ex))
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors={"base": "api_invalid_ssl_code"}
            )
        except ClientConnectorError as ex:
            _LOGGER.error("Connection ERROR to HTTP api: %s", str(ex))
            if isinstance(ex.os_error, ConnectionRefusedError):
                return self.async_show_form(
                    step_id="user",
                    data_schema=data_schema,
                    errors={"base": "api_connection_refused"}
                )
            else:
                return self.async_show_form(
                    step_id="user",
                    data_schema=data_schema,
                    errors={"base": "client_connection_error"}
                )
        except Exception as ex:
            _LOGGER.exception("Unable to connect to Meross HTTP api, ex: %s", str(ex))
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors={"base": "unknown_error"}
            )

        # TODO: Test MQTT connection?
        data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_HTTP_ENDPOINT: http_api_endpoint,
            CONF_STORED_CREDS: {
                "token": creds.token,
                "key": creds.key,
                "user_id": creds.user_id,
                "user_email": creds.user_email,
                "issued_on": creds.issued_on.isoformat(),
            },
            CONF_MQTT_SKIP_CERT_VALIDATION: skip_cert_validation
        }
        entry = await self.async_set_unique_id(http_api_endpoint)

        # If this is a re-auth for an existing entry, just update the entry configuration.
        if entry is not None:
            self._abort_if_unique_id_configured(updates=data, reload_on_update=True)  # No more needed
            await self.hass.config_entries.async_reload(entry.entry_id)

        # Otherwise create a new entry from scratch
        else:
            return self.async_create_entry(
                title=user_input[CONF_HTTP_ENDPOINT],
                data=data
            )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MerossOptionsFlowHandler(config_entry=config_entry)

    @staticmethod
    async def _test_authorization(
        api_base_url: str, username: str, password: str
    ) -> MerossCloudCreds:
        client = await MerossHttpClient.async_from_user_password(
            api_base_url=api_base_url, email=username, password=password
        )
        return client.cloud_credentials

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            _LOGGER.warning(
                "Only one configuration of Meross is allowed. If you added Meross via configuration.yaml, "
                "you should now remove that and use the integration menu con configure it."
            )
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user(import_config)


class MerossOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Meross Component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Meross options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={k: v for k, v in user_input.items() if v not in (None, "")},
            )

        saved_options = {}
        if self.config_entry is not None:
            saved_options = self.config_entry.options

        if saved_options == {}:
            data_schema = self._build_options_schema()    
        else:
            data_schema = self._build_options_schema(
                custom_user_agent=saved_options.get(CONF_OPT_CUSTOM_USER_AGENT),
            )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema
        )

    def _build_options_schema(self,
                              custom_user_agent: str = None,
                              ) -> vol.Schema:
        return vol.Schema({
            vol.Optional(CONF_OPT_CUSTOM_USER_AGENT,
                         msg="Specify a custom user agent to be used when polling Meross HTTP API",
                         default=custom_user_agent,
                         description="Custom user-agent header to use when polling Meross HTTP API."): str
        })
