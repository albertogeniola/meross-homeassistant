"""Meross devices platform loader"""
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Mapping, Any, Dict, Optional, Collection

import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from meross_iot.http_api import MerossHttpClient, ErrorCodes
from meross_iot.manager import MerossManager
from meross_iot.model.credentials import MerossCloudCreds
from meross_iot.model.enums import OnlineStatus, Namespace
from meross_iot.model.exception import CommandTimeoutError
from meross_iot.model.http.device import HttpDeviceInfo
from meross_iot.controller.device import BaseDevice
from meross_iot.model.http.exception import (
    TokenExpiredException,
    TooManyTokensException,
    UnauthorizedException,
    HttpApiError, BadLoginException,
)

from .common import (
    ATTR_CONFIG,
    CLOUD_HANDLER,
    DOMAIN,
    HA_CLIMATE,
    HA_COVER,
    HA_FAN,
    HA_LIGHT,
    HA_SENSOR,
    HA_SWITCH,
    MANAGER,
    MEROSS_PLATFORMS,
    SENSORS,
    dismiss_notification,
    notify_error,
    log_exception,
    CONF_STORED_CREDS,
    LIMITER,
    CONF_HTTP_ENDPOINT, CONF_MQTT_SKIP_CERT_VALIDATION, HTTP_API_RE,
    HTTP_UPDATE_INTERVAL, DEVICE_LIST_COORDINATOR, calculate_id, DEFAULT_USER_AGENT, CONF_OPT_CUSTOM_USER_AGENT,
    CONF_OVERRIDE_MQTT_ENDPOINT, CONF_OPT_LAN, CONF_OPT_LAN_MQTT_ONLY, TRANSPORT_MODES_TO_ENUM
)
from .version import MEROSS_IOT_VERSION

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HTTP_ENDPOINT): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_MQTT_SKIP_CERT_VALIDATION): cv.boolean,
                vol.Optional(CONF_STORED_CREDS): cv.string,
                vol.Optional(CONF_OVERRIDE_MQTT_ENDPOINT): cv.string
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def print_startup_message(http_devices: List[HttpDeviceInfo]):
    http_info = "\n".join(
        [f"- {x.dev_name} ({x.device_type}) - {x.online_status}" for x in http_devices]
    )

    start_message = (
        f"\n"
        f"===============================\n"
        f"Meross Cloud Custom component\n"
        f"Developed by Alberto Geniola\n"
        f"Low level library version: {MEROSS_IOT_VERSION}\n"
        f"-------------------------------\n"
        f"This custom component is under development and not yet ready for production use.\n"
        f"In case of errors/misbehave, please report it here: \n"
        f"https://github.com/albertogeniola/meross-homeassistant/issues\n"
        f"\n"
        f"If you like this extension and you want to support it, please consider donating.\n"
        f"-------------------------------\n"
        f"List of devices reported by HTTP API:\n"
        f"{http_info}"
        f"\n==============================="
    )
    _LOGGER.warning(start_message)


class MerossCoordinator(DataUpdateCoordinator):
    def __init__(self,
                 hass: HomeAssistantType,
                 config_entry: ConfigEntry,
                 http_api_endpoint: str,
                 email: str,
                 password: str,
                 cached_creds: Optional[MerossCloudCreds],
                 mqtt_skip_cert_validation: bool,
                 mqtt_override_address: Optional[Tuple[str, int]],
                 update_interval: timedelta,
                 ua_header: str):

        self._entry = config_entry
        self._http_api_endpoint = http_api_endpoint
        self._email = email
        self._password = password
        self._cached_creds = cached_creds
        self._skip_cert_validation = mqtt_skip_cert_validation
        self._mqtt_override_address = mqtt_override_address
        self._setup_done = False
        self._ua_header = ua_header

        # Objects not to be initialized here
        self._client = None
        self._manager = None

        super().__init__(hass=hass, logger=_LOGGER, name="meross_http_coordinator", update_interval=update_interval,
                         update_method=self._async_fetch_http_data)

    async def _async_fetch_http_data(self):
        try:
            async with async_timeout.timeout(10):
                # Fetch devices and compose a quick-access dictionary
                devices = await self._client.async_list_devices()
                return {device.uuid: device for device in devices}

        except (BadLoginException, TokenExpiredException, UnauthorizedException) as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except HttpApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    async def initial_setup(self):
        if self._setup_done:
            raise ValueError("This coordinator was already set up")

        # Test the stored credentials if any. In case the credentials are invalid
        # try to retrieve a new token
        try:
            self._client, http_devices, creds_renewed = await get_or_renew_creds(
                http_api_url=self._http_api_endpoint,
                email=self._email,
                password=self._password,
                stored_creds=self._cached_creds,
                ua_header=self._ua_header
            )
        except (BadLoginException, TokenExpiredException, UnauthorizedException) as err:
            raise ConfigEntryAuthFailed from err
        except HttpApiError as err:
            raise ConfigEntryNotReady(f"Error communicating with API: {err}") from err

        # If a new token was issued, store it into the current entry
        if creds_renewed:
            # Override the new credentials and store them into HA entry
            self._cached_creds = self._client.cloud_credentials
            self.hass.config_entries.async_update_entry(
                entry=self._entry,
                data={
                    CONF_USERNAME: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_STORED_CREDS: {
                        "token": self._cached_creds.token,
                        "key": self._cached_creds.key,
                        "user_id": self._cached_creds.user_id,
                        "user_email": self._cached_creds.user_email,
                        "issued_on": self._cached_creds.issued_on.isoformat(),
                    },
                },
            )

        # Now that we are logged in at HTTP api level, instantiate the manager.
        self._manager = MerossManager(
            http_client=self._client,
            mqtt_override_server=self._mqtt_override_address,
            auto_reconnect=True,
            mqtt_skip_cert_validation=self._skip_cert_validation,
        )

        # Since we already have fetched for the DeviceList, publish it right away
        self.async_set_updated_data({device.uuid: device for device in http_devices})

        # Print startup message, start the manager and issue a first discovery
        print_startup_message(http_devices=self.data.values())
        _LOGGER.info("Starting meross manager")
        await self._manager.async_init()
        _LOGGER.info("Discovering Meross devices...")
        await self._manager.async_device_discovery()

        # If no exception is thrown so far, it means setup was successful
        self._setup_done = True

    @property
    def manager(self) -> MerossManager:
        return self._manager

    @property
    def client(self) -> MerossHttpClient:
        return self._client


class MerossDevice(Entity):
    def __init__(self,
                 device: BaseDevice,
                 channel: int,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]],
                 platform: str,
                 supplementary_classifiers: Optional[List[str]] = None):
        self._coordinator = device_list_coordinator
        self._device = device
        self._channel_id = channel
        self._last_http_state = None
        self._cb_async_remove_listener = None

        base_name = f"{device.name} ({device.type})"
        if supplementary_classifiers is not None:
            self._id = calculate_id(platform=platform, uuid=device.internal_id, channel=channel,
                                    supplementary_classifiers=supplementary_classifiers)
            base_name += f" " + " ".join(supplementary_classifiers)
        else:
            self._id = calculate_id(platform=platform, uuid=device.internal_id, channel=channel)

        if device.channels is not None and len(device.channels) > 0:
            channel_data = device.channels[channel]
            self._entity_name = f"{base_name} - {channel_data.name}"
        else:
            self._entity_name = base_name

    @property
    def should_poll(self) -> bool:
        return False

    async def async_update(self):
        if self.online:
            try:
                await self._device.async_update()
            except CommandTimeoutError as e:
                log_exception(logger=_LOGGER, device=self._device)

    def _http_data_changed(self) -> None:
        new_data = self._coordinator.data.get(self._device.uuid)
        if self._last_http_state is not None and self._last_http_state.online_status != OnlineStatus.ONLINE and new_data.online_status == OnlineStatus.ONLINE:
            self._last_http_state = new_data
            self.async_schedule_update_ha_state(force_refresh=True)
        else:
            self._last_http_state = new_data
            self.async_schedule_update_ha_state(force_refresh=False)

    @property
    def online(self) -> bool:
        if not self._coordinator.last_update_success:
            return False
        elif self._last_http_state is not None:
            return self._last_http_state.online_status == OnlineStatus.ONLINE
        else:
            return self._coordinator.data.get(self._device.uuid).online_status == OnlineStatus.ONLINE

    @property
    def unique_id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._entity_name

    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._device.internal_id)},
            'name': self._device.name,
            'manufacturer': 'Meross',
            'model': self._device.type + " " + self._device.hardware_version,
            'sw_version': self._device.firmware_version
        }

    @property
    def available(self) -> bool:
        return self._coordinator.last_update_success and self.online

    async def _async_push_notification_received(self, namespace: Namespace, data: dict, device_internal_id: str):
        update_state = False
        full_update = False

        if namespace == Namespace.CONTROL_UNBIND:
            _LOGGER.warning(f"Received unbind event. Removing device %s from HA", self.name)
            await self.platform.async_remove_entity(self.entity_id)
        elif namespace == Namespace.SYSTEM_ONLINE:
            _LOGGER.warning(f"Device %s reported online event.", self.name)
            online = OnlineStatus(int(data.get('online').get('status')))
            update_state = True
            full_update = online == OnlineStatus.ONLINE
        elif namespace == Namespace.HUB_ONLINE:
            _LOGGER.warning(f"Device {self.name} reported (HUB) online event.")
            online = OnlineStatus(int(data.get('status')))
            update_state = True
            full_update = online == OnlineStatus.ONLINE
        else:
            update_state = True
            full_update = False

        # In all other cases, just tell HA to update the internal state representation
        if update_state:
            self.async_schedule_update_ha_state(force_refresh=full_update)

    async def async_added_to_hass(self) -> None:
        self._device.register_push_notification_handler_coroutine(self._async_push_notification_received)
        self._cb_async_remove_listener = self._coordinator.async_add_listener(self._http_data_changed)
        self.hass.data[DOMAIN]["ADDED_ENTITIES_IDS"].add(self.unique_id)

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_push_notification_handler_coroutine(self._async_push_notification_received)
        if self._cb_async_remove_listener is not None:
            self._cb_async_remove_listener()
        self.hass.data[DOMAIN]["ADDED_ENTITIES_IDS"].remove(self.unique_id)


async def get_or_renew_creds(
        email: str,
        password: str,
        stored_creds: MerossCloudCreds = None,
        http_api_url: str = "https://iot.meross.com",
        ua_header: str = DEFAULT_USER_AGENT
) -> Tuple[MerossHttpClient, List[HttpDeviceInfo], bool]:
    try:
        if stored_creds is None:
            http_client = await MerossHttpClient.async_from_user_password(
                email=email, password=password, api_base_url=http_api_url, ua_header=ua_header
            )
        else:
            http_client = MerossHttpClient(
                cloud_credentials=stored_creds, api_base_url=http_api_url, ua_header=ua_header
            )

        # Test device listing. If goes ok, return it immediately. There is no need to update the credentials
        http_devices = await http_client.async_list_devices()
        return http_client, http_devices, False

    except TokenExpiredException as e:
        # In case the current token is expired or invalid, let's try to re-login.
        _LOGGER.exception(
            "Current token has been refused by the Meross Cloud. Trying to generate a new one with "
            "stored user credentials..."
        )

        # Build a new client with username/password rather than using stored credentials
        http_client = await MerossHttpClient.async_from_user_password(
            email=email, password=password, api_base_url=http_api_url, ua_header=ua_header
        )
        http_devices = await http_client.async_list_devices()

        return http_client, http_devices, True


def _http_info_changed(known: Collection[HttpDeviceInfo], discovered: Collection[HttpDeviceInfo]) -> bool:
    """Tells when a new device is discovered among the known ones"""
    known_ids = [dev.uuid for dev in known]
    unknown = [dev for dev in discovered if dev.uuid not in known_ids]
    return len(unknown) > 0


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry):
    """
    This class is called by the HomeAssistant framework when a configuration entry is provided.
    For us, the configuration entry is the username-password credentials that the user
    needs to access the Meross cloud.
    """

    # Retrieve the stored credentials from config-flow
    http_api_endpoint = config_entry.data.get(CONF_HTTP_ENDPOINT)
    _LOGGER.info("Loaded %s: %s", CONF_HTTP_ENDPOINT, http_api_endpoint)

    email = config_entry.data.get(CONF_USERNAME)
    _LOGGER.info("Loaded %s: %s", CONF_USERNAME, http_api_endpoint)

    password = config_entry.data.get(CONF_PASSWORD)
    _LOGGER.info("Loaded %s: %s", CONF_PASSWORD, "******")

    str_creds = config_entry.data.get(CONF_STORED_CREDS)
    _LOGGER.info("Loaded %s: %s", CONF_STORED_CREDS, "******")

    mqtt_skip_cert_validation = config_entry.data.get(CONF_MQTT_SKIP_CERT_VALIDATION, True)
    _LOGGER.warning("Skip MQTT cert validation option set to: %s", mqtt_skip_cert_validation)

    mqtt_override_address = config_entry.data.get(CONF_OVERRIDE_MQTT_ENDPOINT)
    _LOGGER.info("Override MQTT address set to: %s", "no" if mqtt_override_address else "yes -> %s" % mqtt_override_address)

    # Make sure we have all the needed requirements
    if http_api_endpoint is None or HTTP_API_RE.fullmatch(http_api_endpoint) is None:
        raise ConfigEntryAuthFailed("Missing or wrong HTTP_API_ENDPOINT")
    if email is None:
        raise ConfigEntryAuthFailed("Missing USERNAME/EMAIL parameter from configuration")
    if password is None:
        raise ConfigEntryAuthFailed("Missing PASSWORD parameter from configuration")
    if mqtt_override_address is not None:
        mqtt_host = mqtt_override_address.split(":")[0]
        mqtt_port = int(mqtt_override_address.split(":")[1])
        mqtt_override_address = (mqtt_host, mqtt_port)

    creds = None
    if str_creds is not None:
        issued_on = datetime.fromisoformat(str_creds.get("issued_on"))
        creds = MerossCloudCreds(
            token=str_creds.get("token"),
            key=str_creds.get("key"),
            user_id=str_creds.get("user_id"),
            user_email=str_creds.get("user_email"),
            issued_on=issued_on,
        )
        _LOGGER.info(
            f"Found application token issued on {creds.issued_on} to {creds.user_email}. Using it."
        )

    # Initialize the HASS structure
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["ADDED_ENTITIES_IDS"] = set()
    # Keep a registry of added sensors
    # TODO: Do the same for other platforms?
    # TODO: Is this still needed?
    hass.data[DOMAIN][HA_SENSOR] = dict()

    # Retrieve options we need
    ua_header = config_entry.options.get(CONF_OPT_CUSTOM_USER_AGENT, DEFAULT_USER_AGENT)
    if ua_header == "" or not isinstance(ua_header, str):
        _LOGGER.warning("Invalid user-agent option specified in config <%s>; defaulting to <%s>", str(ua_header),
                        str(DEFAULT_USER_AGENT))
        ua_header = DEFAULT_USER_AGENT

    try:
        # Setup the coordinator
        meross_coordinator = MerossCoordinator(
            hass=hass,
            config_entry=config_entry,
            http_api_endpoint=http_api_endpoint,
            email=email,
            password=password,
            cached_creds=creds,
            mqtt_skip_cert_validation=mqtt_skip_cert_validation,
            mqtt_override_address=mqtt_override_address,
            update_interval=timedelta(seconds=HTTP_UPDATE_INTERVAL),
            ua_header=ua_header
        )

        # Initiate the coordinator. This method will also make sure to login to the API,
        # instantiates the manager, starts it and issues a first discovery.
        await meross_coordinator.initial_setup()
        manager = meross_coordinator.manager
        hass.data[DOMAIN][MANAGER] = manager
        hass.data[DOMAIN][DEVICE_LIST_COORDINATOR] = meross_coordinator

        # Once the manager is ok and the first discovery was issued, we can proceed with platforms setup.
        for platform in MEROSS_PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, platform)
            )

        def _http_api_polled(*args, **kwargs):
            # Whenever a new HTTP device is seen, we issue a discovery
            discovered_devices = meross_coordinator.data
            known_devices = manager.find_devices(device_uuids=discovered_devices.keys())
            if _http_info_changed(known_devices, discovered_devices.values()):
                _LOGGER.info("The HTTP API has found new devices that were unknown to us. Triggering discovery.")
                hass.create_task(manager.async_device_discovery(update_subdevice_status=True,
                                                                cached_http_device_list=discovered_devices.values()))

        # Register a handler for HTTP events so that we can check for new devices and trigger
        # a discovery when needed
        config_entry.async_on_unload(meross_coordinator.async_add_listener(_http_api_polled))
        config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

        return True

    except TooManyTokensException:
        msg = (
            "Too many tokens have been issued to this account. "
            "The Remote API refused to issue a new one."
        )
        notify_error(hass, "http_connection", "Meross Cloud", msg)
        log_exception(msg, logger=_LOGGER)
        raise ConfigEntryAuthFailed("Too many tokens have been issued")

    except (UnauthorizedException, HttpApiError) as ex:
        # Do not retry setup: user must update its credentials
        if ex is UnauthorizedException or ex.error_code in (
                ErrorCodes.CODE_TOKEN_INVALID,
                ErrorCodes.CODE_TOKEN_EXPIRED,
                ErrorCodes.CODE_TOKEN_ERROR,
        ):
            raise ConfigEntryAuthFailed("Invalid token or credentials")
        else:
            msg = "Your Meross login credentials are invalid or the network could not be reached at the moment."
            notify_error(
                hass,
                "http_connection",
                "Meross Cloud",
                "Could not connect to the Meross cloud. Please check"
                " your internet connection and your Meross credentials",
            )
            log_exception(msg, logger=_LOGGER)
            raise ConfigEntryNotReady()

    except Exception as e:
        log_exception(
            "An exception occurred while setting up the meross manager. Setup will be retried...",
            logger=_LOGGER,
        )
        raise ConfigEntryNotReady()


async def update_listener(hass, entry):
    """Handle options update."""
    # Update options
    custom_ua = entry.options.get(CONF_OPT_CUSTOM_USER_AGENT, DEFAULT_USER_AGENT)
    transport_mode = entry.options.get(CONF_OPT_LAN, CONF_OPT_LAN_MQTT_ONLY)
    manager_transport_mode = TRANSPORT_MODES_TO_ENUM[transport_mode]
    manager: MerossManager = hass.data[DOMAIN][MANAGER]
    manager.default_transport_mode = manager_transport_mode
    # So far, the underlying Meross Library requires some "monkey patching" to set the
    # http user agent to be used. It's not nice, but until a public setter gets exposed, we need
    # to do so.
    manager._http_client._ua_header = custom_ua


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    # Unload entities first
    _LOGGER.info("Removing Meross Cloud integration.")
    _LOGGER.info("Cleaning up resources...")

    for platform in MEROSS_PLATFORMS:
        _LOGGER.info(f"Cleaning up platform {platform}")
        await hass.config_entries.async_forward_entry_unload(entry, platform)

    _LOGGER.info("Stopping manager...")
    manager = hass.data[DOMAIN][MANAGER]
    # TODO: Invalidate the token?
    manager.close()

    _LOGGER.info("Cleaning up memory...")
    for plat in MEROSS_PLATFORMS:
        if plat in hass.data[DOMAIN]:
            hass.data[DOMAIN][plat].clear()
            del hass.data[DOMAIN][plat]
    del hass.data[DOMAIN][MANAGER]
    hass.data[DOMAIN].clear()
    del hass.data[DOMAIN]

    _LOGGER.info("Meross cloud component removal done.")
    return True


async def async_remove_entry(hass, entry) -> None:
    # TODO
    pass


async def async_setup(hass, config):
    """
    This method gets called if HomeAssistant has a valid meross_cloud: configuration entry within
    configurations.yaml.

    Thus, in this method we simply trigger the creation of a config entry.

    :return:
    """

    conf = config.get(DOMAIN)
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ATTR_CONFIG] = conf

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf
            )
        )

    return True
