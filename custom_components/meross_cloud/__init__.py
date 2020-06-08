"""Meross devices platform loader"""
import logging
from datetime import datetime

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import HomeAssistantType
from meross_iot.http_api import MerossHttpClient
from meross_iot.logger import ROOT_MEROSS_LOGGER, h
from meross_iot.manager import MerossManager
from meross_iot.model.credentials import MerossCloudCreds
from meross_iot.model.http.device import HttpDeviceInfo
from typing import List, Tuple

from meross_iot.model.http.exception import TokenExpiredException, TooManyTokensException, UnauthorizedException

from .common import (ATTR_CONFIG, CLOUD_HANDLER, DOMAIN, HA_CLIMATE, HA_COVER,
                     HA_FAN, HA_LIGHT, HA_SENSOR, HA_SWITCH, MANAGER,
                     MEROSS_PLATFORMS, SENSORS, dismiss_notification, notify_error, log_exception, CONF_STORED_CREDS)

# Unset the default stream handler for logger of the meross_iot library
from .version import MEROSS_CLOUD_VERSION

ROOT_MEROSS_LOGGER.removeHandler(h)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def print_startup_message(http_devices: List[HttpDeviceInfo]):
    http_info = "\n".join([f"- {x.dev_name} ({x.device_type}) - {x.online_status}" for x in http_devices])

    start_message = f"\n" \
                    f"===============================\n" \
                    f"Meross Cloud Custom component\n" \
                    f"Developed by Alberto Geniola\n" \
                    f"Low level library version: {MEROSS_CLOUD_VERSION}\n" \
                    f"-------------------------------\n" \
                    f"This custom component is under development and not yet ready for production use.\n" \
                    f"In case of errors/misbehave, please report it here: \n" \
                    f"https://github.com/albertogeniola/meross-homeassistant/issues\n" \
                    f"\n" \
                    f"If you like this extension and you want to support it, please consider donating.\n" \
                    f"-------------------------------\n" \
                    f"List of devices reported by HTTP API:\n" \
                    f"{http_info}" \
                    f"\n==============================="
    _LOGGER.info(start_message)


async def get_or_renew_creds(email: str,
                             password: str,
                             stored_creds: MerossCloudCreds = None) -> Tuple[MerossHttpClient, List[HttpDeviceInfo], bool]:
    try:
        if stored_creds is None:
            http_client = await MerossHttpClient.async_from_user_password(email=email, password=password)
        else:
            http_client = MerossHttpClient(cloud_credentials=stored_creds)

        # Test device listing. If goes ok, return it immediately. There is no need to update the credentials
        http_devices = await http_client.async_list_devices()
        return http_client, http_devices, False

    except TokenExpiredException as e:
        # In case the current token is expired or invalid, let's try to re-login.
        _LOGGER.exception("Current token has been refused by the Meross Cloud. Trying to generate a new one with "
                          "stored user credentials...")

        # Build a new client with username/password rather than using stored credentials
        http_client = await MerossHttpClient.async_from_user_password(email=email, password=password)
        http_devices = await http_client.async_list_devices()

        return http_client, http_devices, True


async def async_setup_entry(hass: HomeAssistantType, config_entry):
    """
    This class is called by the HomeAssistant framework when a configuration entry is provided.
    For us, the configuration entry is the username-password credentials that the user
    needs to access the Meross cloud.
    """

    # Retrieve the stored credentials from config-flow
    email = config_entry.data.get(CONF_USERNAME)
    password = config_entry.data.get(CONF_PASSWORD)
    str_creds = config_entry.data.get(CONF_STORED_CREDS)
    creds = None
    if str_creds is not None:
        issued_on = datetime.fromisoformat(str_creds.get('issued_on'))
        creds = MerossCloudCreds(
            token=str_creds.get('token'),
            key=str_creds.get('key'),
            user_id=str_creds.get('user_id'),
            user_email=str_creds.get('user_email'),
            issued_on=issued_on
        )
        _LOGGER.info(f"Found application token issued on {creds.issued_on} to {creds.user_email}. Using it.")

    try:
        client, http_devices, creds_renewed = await get_or_renew_creds(email=email, password=password, stored_creds=creds)
        if creds_renewed:
            creds = client.cloud_credentials
            hass.config_entries.async_update_entry(entry=config_entry, data={
                CONF_USERNAME: email,
                CONF_PASSWORD: password,
                CONF_STORED_CREDS: {
                    'token': creds.token,
                    'key': creds.key,
                    'user_id': creds.user_id,
                    'user_email': creds.user_email,
                    'issued_on': creds.issued_on.isoformat()
                }
            })

        manager = MerossManager(http_client=client, auto_reconnect=True)

        hass.data[DOMAIN] = {}
        hass.data[DOMAIN][MANAGER] = manager
        hass.data[DOMAIN][HA_CLIMATE] = {}
        hass.data[DOMAIN][HA_COVER] = {}
        hass.data[DOMAIN][HA_LIGHT] = {}
        hass.data[DOMAIN][HA_SENSOR] = {}
        hass.data[DOMAIN][HA_SWITCH] = {}
        hass.data[DOMAIN][HA_FAN] = {}

        print_startup_message(http_devices=http_devices)
        _LOGGER.info("Starting meross manager")
        await manager.async_init()

        # Perform the first discovery
        _LOGGER.info("Discovering Meross devices...")
        await manager.async_device_discovery()

        for platform in MEROSS_PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, platform)
            )

        return True

    except TooManyTokensException:
        msg = "Too many tokens have been issued to this account. " \
              "The Remote API refused to issue a new one."
        notify_error(hass, "http_connection", "Meross Cloud", msg)
        log_exception(msg, logger=_LOGGER)
        raise ConfigEntryNotReady()

    except UnauthorizedException:
        msg = "Your Meross login credentials are invalid or the network could not be reached at the moment."
        notify_error(hass, "http_connection", "Meross Cloud", "Could not connect to the Meross cloud. Please check"
                                                              " your internet connection and your Meross credentials")
        log_exception(msg, logger=_LOGGER)
        return False

    except Exception as e:
        log_exception("An exception occurred while setting up the meross manager. Setup will be retried...", logger=_LOGGER)
        raise ConfigEntryNotReady()


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    # Unload entities first
    _LOGGER.info("Removing Meross Cloud integration.")
    _LOGGER.info("Cleaning up resources...")
    for platform in MEROSS_PLATFORMS:
        _LOGGER.info(f"Cleaning up platform {platform}")
        await hass.config_entries.async_forward_entry_unload(entry, platform)

    # Invalidate the token
    manager = hass.data[DOMAIN][MANAGER]
    _LOGGER.info("Stopping manager...")
    # TODO: Invalidate the token?
    manager.close()

    _LOGGER.info("Cleaning up memory...")
    for plat in MEROSS_PLATFORMS:
        hass.data[DOMAIN][plat].clear()
        del hass.data[DOMAIN][plat]
    del hass.data[DOMAIN][MANAGER]
    hass.data[DOMAIN].clear()
    del hass.data[DOMAIN]

    _LOGGER.info("Meross cloud component removal done.")
    return True


async def async_remove_entry(hass, entry) -> None:
    _LOGGER.info("UNLOADING...")
    # TODO
    pass


async def async_setup(hass, config):
    """
    This method gets called if HomeAssistant has a valid me ross_cloud: configuration entry within
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
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT},
                data=conf
            )
        )

    return True
