"""Meross devices platform loader"""
import logging
from datetime import datetime
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import HomeAssistantType
from meross_iot.api import UnauthorizedException
from meross_iot.credentials import MerossCloudCreds
from meross_iot.logger import ROOT_MEROSS_LOGGER, h
from meross_iot.manager import MerossManager

from .common import (ATTR_CONFIG, CLOUD_HANDLER, DOMAIN, HA_CLIMATE, HA_COVER,
                     HA_FAN, HA_LIGHT, HA_SENSOR, HA_SWITCH, MANAGER,
                     MEROSS_PLATFORMS, SENSORS, dismiss_notification, notify_error, log_exception, CONF_STORED_CREDS)

# Unset the default stream handler for logger of the meross_iot library
ROOT_MEROSS_LOGGER.removeHandler(h)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup_entry(hass: HomeAssistantType, config_entry):
    """
    This class is called by the HomeAssistant framework when a configuration entry is provided.
    For us, the configuration entry is the username-password credentials that the user
    needs to access the Meross cloud.
    """

    try:
        # TODO: Check config entry
        #  If credentials are stored and the email is new, trash the credentials and use the email/pwd
        #  to generate new ctored credentials
        """
        {'username': 'albertogeniola@gmail.com', 'password': 'ciaociao', 'stored_credentials': {'token': '227f95590c4816cb70e73df2e5c8ef8cd1a059ff31a5441c9694b48e92063b8f', 'key': 'b11d6c6af9fa3f476bccad7e060ef1ff', 'user_id': '46884', 'user_email': 'albertogeniola@gmail.com', 'issued_on': '2020-04-16T22:59:31.790794'}}
        """
        username = config_entry.data.get(CONF_USERNAME)
        password = config_entry.data.get(CONF_PASSWORD)
        str_creds = config_entry.data.get(CONF_STORED_CREDS)
        manager = None

        if str_creds is not None:
            try:
                issued_on = datetime.fromisoformat(str_creds.get('issued_on'))
                creds = MerossCloudCreds(
                    token=str_creds.get('token'),
                    key=str_creds.get('key'),
                    user_id=str_creds.get('user_id'),
                    user_email=str_creds.get('user_email'),
                    issued_on=issued_on
                )
                _LOGGER.info(f"Found application token issued on {creds.issued_on} to {creds.user_email}. Using it.")
                manager = MerossManager(cloud_credentials=creds,
                                        discovery_interval=30.0,
                                        auto_reconnect=True,
                                        logout_on_stop=False)
            except:
                _LOGGER.warning("Failed to parse stored credentials. Ignoring it.")
        else:
            _LOGGER.info("No token was found. Falling back to stored email/password to get a new one.")
            manager = MerossManager.from_email_and_password(meross_email=config_entry.data.get(CONF_USERNAME),
                                                            meross_password=config_entry.data.get(CONF_PASSWORD),
                                                            discovery_interval=30.0,
                                                            auto_reconnect=True,
                                                            logout_on_stop=False)
            # TODO: store configuration!

        # These will contain the initialized devices
        # The following call can cause am UnauthorizedException if bad login credentials are provided
        # or if a network exception occurs.
        hass.data[DOMAIN][MANAGER] = manager
        hass.data[DOMAIN][HA_CLIMATE] = {}
        hass.data[DOMAIN][HA_COVER] = {}
        hass.data[DOMAIN][HA_LIGHT] = {}
        hass.data[DOMAIN][HA_SENSOR] = {}
        hass.data[DOMAIN][HA_SWITCH] = {}
        hass.data[DOMAIN][HA_FAN] = {}

        _LOGGER.info("Starting meross manager")
        manager.start()

        _LOGGER.info("Starting meross cloud connection watchdog")

        for platform in MEROSS_PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, platform)
            )

        return True

    except UnauthorizedException as e:
        notify_error(hass, "http_connection", "Meross Cloud", "Could not connect to the Meross cloud. Please check"
                                                              " your internet connection and your Meross credentials")
        log_exception("Your Meross login credentials are invalid or the network could not be reached "
                          "at the moment.", logger=_LOGGER)

        raise ConfigEntryNotReady()

    except Exception as e:
        log_exception("An exception occurred while setting up the meross manager. Setup will be retried...", logger=_LOGGER)
        raise ConfigEntryNotReady()


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
