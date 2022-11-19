import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from urllib.error import HTTPError

import voluptuous as vol
from aiohttp import ClientConnectorSSLError, ClientConnectorError
from zeroconf import ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow, ConfigError
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode
from meross_iot.http_api import MerossHttpClient
from meross_iot.model.credentials import MerossCloudCreds
from meross_iot.model.http.exception import UnauthorizedException, BadLoginException
from requests.exceptions import ConnectTimeout
from homeassistant.components import zeroconf


from .common import DOMAIN, CONF_STORED_CREDS, CONF_WORKING_MODE, CONF_WORKING_MODE_LOCAL_MODE, \
    CONF_WORKING_MODE_CLOUD_MODE, \
    CONF_HTTP_ENDPOINT, CONF_MQTT_SKIP_CERT_VALIDATION, CONF_OPT_CUSTOM_USER_AGENT, HTTP_API_RE, MEROSS_CLOUD_API_URL, \
    MEROSS_LOCAL_API_URL, MEROSS_LOCAL_MDNS_SERVICE_TYPES, MEROSS_LOCAL_MDNS_MQTT_SERVICE_TYPE, \
    MEROSS_LOCAL_MDNS_API_SERVICE_TYPE, CONF_OVERRIDE_MQTT_ENDPOINT, MULTIPLE_APIS_FOUND, MULTIPLE_BROKERS_FOUND, \
    UNKNOWN_ERROR, \
    DIFFERENT_HOSTS_FOR_BROKER_AND_API, MEROSS_LOCAL_MQTT_BROKER_URI, CONF_OPT_LAN, CONF_OPT_LAN_MQTT_ONLY, \
    CONF_OPT_LAN_HTTP_FIRST, CONF_OPT_LAN_HTTP_FIRST_ONLY_GET, DEFAULT_USER_AGENT

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1


class ConfigUiException(Exception):
    def __init__(self, error_code = UNKNOWN_ERROR, *args: object) -> None:
        super().__init__(*args)
        self._code = error_code

    @property
    def code(self):
        return self._code


class MerossFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Meross config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self) -> None:
        """Initialize flow."""
        self._http_api: Optional[str] = None
        self._mqtt_boker: Optional[str] = None
        self._username: Optional[str] = None
        self._password: Optional[str] = None
        self._local_mode: bool = False
        self._skip_cert_validation: Optional[bool] = None
        self._discovered_services: List[AsyncServiceInfo] = []

    def _build_setup_schema(
            self,
            http_endpoint: str = None,
            username: str = None,
            password: str = None,
            override_mqtt_endpoint: str = None,
            skip_cert_validation: bool = None
    ) -> vol.Schema:
        http_endpoint_default = http_endpoint if http_endpoint is not None else self._http_api
        mqtt_endpoint_default = override_mqtt_endpoint if override_mqtt_endpoint is not None else self._mqtt_boker
        username_default = username if username is not None else self._username
        password_default = password if password is not None else self._password
        skip_cert_validation_default = skip_cert_validation if skip_cert_validation is not None else self._skip_cert_validation

        if self._local_mode:
            schema = vol.Schema({
                vol.Required(CONF_HTTP_ENDPOINT, default=http_endpoint_default): str,
                vol.Required(CONF_OVERRIDE_MQTT_ENDPOINT, default=mqtt_endpoint_default): str,
                vol.Required(CONF_USERNAME, default=username_default): str,
                vol.Required(CONF_PASSWORD, default=password_default): str,
                vol.Required(CONF_MQTT_SKIP_CERT_VALIDATION, default=skip_cert_validation_default): bool,
            })
        else:
            schema = vol.Schema({
                vol.Required(CONF_HTTP_ENDPOINT, default=http_endpoint_default): str,
                vol.Required(CONF_USERNAME, default=username_default): str,
                vol.Required(CONF_PASSWORD, default=password_default): str,
                vol.Required(CONF_MQTT_SKIP_CERT_VALIDATION, default=skip_cert_validation_default): bool,
            })

        return schema

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

    async def _resolve_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        _LOGGER.debug("MDNS resolving service type: %s, name: %s", service_type, name)
        info = AsyncServiceInfo(service_type, name)
        await info.async_request(zeroconf, 3000)
        if info:
            self._discovered_services.append(info)

    def _async_on_service_state_change(self, zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        _LOGGER.debug("MDNS discovery state: %s, service type: %s, name: %s", str(state_change), service_type, name)
        if state_change is not ServiceStateChange.Added:
            return
        # Resolve the service on a different async task
        asyncio.ensure_future(self._resolve_service(zeroconf, service_type, name))

    async def _discover_services(self) -> Tuple[Optional[str], Optional[str]]:
        self._discovered_services.clear()
        aiozc = await zeroconf.async_get_async_instance(self.hass)
        browser = AsyncServiceBrowser(aiozc.zeroconf, MEROSS_LOCAL_MDNS_SERVICE_TYPES, handlers=[self._async_on_service_state_change])
        # Wait a bit to collect MDNS responses and then stop the browser
        await asyncio.sleep(5)
        await browser.async_cancel()
        api_endpoint_info = None
        mqtt_endpoint_info = None

        mqtt_count = 0
        api_count = 0
        _LOGGER.info("Found %d mdns services.", len(self._discovered_services))
        for info in self._discovered_services:
            if info.type == MEROSS_LOCAL_MDNS_API_SERVICE_TYPE:
                api_count += 1
                api_endpoint_info = info
                _LOGGER.info("Found [%d] Local Meross API service listening on %s:%d", api_count, api_endpoint_info.server, api_endpoint_info.port)
            elif info.type == MEROSS_LOCAL_MDNS_MQTT_SERVICE_TYPE:
                mqtt_count += 1
                mqtt_endpoint_info = info
                _LOGGER.info("Found [%d] Local Meross MQTT service listening on %s:%d", mqtt_count, mqtt_endpoint_info.server, mqtt_endpoint_info.port)

        if mqtt_count < 1 or api_count <1:
            _LOGGER.info("The API/MQTT discovery was unable to find any relevant service.")
            return None, None

        if mqtt_count > 1:
            raise ConfigUiException(MULTIPLE_BROKERS_FOUND)
        
        if api_count > 1:
            raise ConfigUiException(MULTIPLE_APIS_FOUND)

        if api_endpoint_info.server != mqtt_endpoint_info.server:
            raise ConfigUiException(DIFFERENT_HOSTS_FOR_BROKER_AND_API)

        api_endpoint = f"http://{api_endpoint_info.server[:-1]}:{api_endpoint_info.port}"
        mqtt_endpoint = f"{mqtt_endpoint_info.server[:-1]}:{mqtt_endpoint_info.port}"
        return api_endpoint, mqtt_endpoint

    async def async_step_user(self, user_input=None) -> Dict[str, Any]:
        """Choose mode step handler"""
        _LOGGER.debug("Starting STEP_USER")
        if not user_input:
            _LOGGER.debug("Empty user_input, showing mode selection form")
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_WORKING_MODE, default=CONF_WORKING_MODE_CLOUD_MODE): SelectSelector(SelectSelectorConfig(
                    options=[
                        {"value": CONF_WORKING_MODE_CLOUD_MODE, "label": "Connect to Meross Official Cloud (requires internet)"},
                        {"value": CONF_WORKING_MODE_LOCAL_MODE, "label": "Connect to LAN-only broker (requires Meross Local Addon)"}],
                    mode=SelectSelectorMode.LIST,
                ))}),
                errors={})

        mode = user_input.get(CONF_WORKING_MODE)
        if mode == CONF_WORKING_MODE_CLOUD_MODE:
            self._local_mode = False
            self._http_api = MEROSS_CLOUD_API_URL
            self._skip_cert_validation = False
            return self.async_show_form(
                step_id="configure_manager",
                data_schema=self._build_setup_schema(),
                errors={},
            )
        elif mode == CONF_WORKING_MODE_LOCAL_MODE:
            self._local_mode = True
            self._http_api = MEROSS_LOCAL_API_URL
            self._mqtt_boker = MEROSS_LOCAL_MQTT_BROKER_URI
            self._skip_cert_validation = True

            # Look for local brokers via zeroconf
            api = None
            mqtt = None
            try:
                api, mqtt = await self._discover_services()
            except ConfigUiException as e:
                return self.async_show_form(
                step_id="configure_manager",
                data_schema=self._build_setup_schema(http_endpoint=api, override_mqtt_endpoint=mqtt),
                errors={"base": e.code},
            )

            # If no service was found, set an error
            errors = {}
            if api is None or mqtt is None:
                errors["base"] = "mdns_lookup_failed"

            return self.async_show_form(
                step_id="configure_manager",
                data_schema=self._build_setup_schema(http_endpoint=api, override_mqtt_endpoint=mqtt),
                errors=errors,
            )
        else:
            raise ConfigError("Invalid selection")

    async def async_step_configure_manager(self, user_input=None) -> Dict[str, Any]:
        """Handle a flow initialized by the user interface"""
        _LOGGER.debug("Starting CONFIGURE_MANAGER")
        if not user_input:
            _LOGGER.debug("Empty user_input, showing default prefilled form")
            return self.async_show_form(
                step_id="configure_manager",
                data_schema=self._build_setup_schema(),
                errors={},
            )

        _LOGGER.debug("UserInput was provided: form data will be populated with that")
        http_api_endpoint = user_input.get(CONF_HTTP_ENDPOINT)
        username = user_input.get(CONF_USERNAME)
        password = user_input.get(CONF_PASSWORD)
        mqtt_host = user_input.get(CONF_OVERRIDE_MQTT_ENDPOINT)
        skip_cert_validation = user_input.get(CONF_MQTT_SKIP_CERT_VALIDATION)

        data_schema = self._build_setup_schema(
            http_endpoint=http_api_endpoint,
            username=username,
            password=password,
            override_mqtt_endpoint=mqtt_host
        )

        # Check if we have everything we need
        if username is None or password is None or http_api_endpoint is None:
            return self.async_show_form(
                step_id="configure_manager",
                data_schema=data_schema,
                errors={"base": "missing_credentials"},
            )

        # Check the base-url is valid
        match = HTTP_API_RE.fullmatch(http_api_endpoint)

        if match is None:
            _LOGGER.error("Invalid Meross HTTTP API endpoint: %s", http_api_endpoint)
            return self.async_show_form(
                step_id="configure_manager",
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
            _LOGGER.debug("Passing data_schema: %s", str(data_schema))
            return self.async_show_form(
                step_id="configure_manager",
                data_schema=data_schema,
                errors={"base": "invalid_credentials"}
            )
        except (UnauthorizedException, ConnectTimeout, HTTPError) as ex:
            _LOGGER.error("Unable to connect to Meross HTTP api: %s", str(ex))
            return self.async_show_form(
                step_id="configure_manager",
                data_schema=data_schema,
                errors={"base": "connection_error"}
            )
        except ClientConnectorSSLError as ex:
            _LOGGER.error("Unable to connect to Meross HTTP api: %s", str(ex))
            return self.async_show_form(
                step_id="configure_manager",
                data_schema=data_schema,
                errors={"base": "api_invalid_ssl_code"}
            )
        except ClientConnectorError as ex:
            _LOGGER.error("Connection ERROR to HTTP api: %s", str(ex))
            if isinstance(ex.os_error, ConnectionRefusedError):
                return self.async_show_form(
                    step_id="configure_manager",
                    data_schema=data_schema,
                    errors={"base": "api_connection_refused"}
                )
            else:
                return self.async_show_form(
                    step_id="configure_manager",
                    data_schema=data_schema,
                    errors={"base": "client_connection_error"}
                )
        except Exception as ex:
            _LOGGER.exception("Unable to connect to Meross HTTP api, ex: %s", str(ex))
            return self.async_show_form(
                step_id="configure_manager",
                data_schema=data_schema,
                errors={"base": "unknown_error"}
            )

        # TODO: Test MQTT connection?
        data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_HTTP_ENDPOINT: http_api_endpoint,
            CONF_OVERRIDE_MQTT_ENDPOINT: mqtt_host,
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

        return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({
                    vol.Optional(CONF_OPT_CUSTOM_USER_AGENT, default=saved_options.get(CONF_OPT_CUSTOM_USER_AGENT, DEFAULT_USER_AGENT)): str,
                    vol.Required(CONF_OPT_LAN, default=saved_options.get(CONF_OPT_LAN, CONF_OPT_LAN_MQTT_ONLY)): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": CONF_OPT_LAN_MQTT_ONLY,
                                 "label": "Do not rely on local HTTP communication at all, just use the MQTT broker"},
                                {"value": CONF_OPT_LAN_HTTP_FIRST,
                                 "label": "Attempt local HTTP communication first and fall-back to MQTT broker"},
                                {"value": CONF_OPT_LAN_HTTP_FIRST_ONLY_GET,
                                 "label": "Attempt local HTTP communication first only for GET commands, fall-back to MQTT broker"}
                            ], mode=SelectSelectorMode.LIST)
                    )
                })
            )
