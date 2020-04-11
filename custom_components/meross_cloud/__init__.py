"""Meross devices platform loader"""
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import HomeAssistantType
from meross_iot.api import UnauthorizedException
from meross_iot.logger import ROOT_MEROSS_LOGGER, h
from meross_iot.manager import MerossManager

from .common import (ATTR_CONFIG, CLOUD_HANDLER, DOMAIN, HA_CLIMATE, HA_COVER,
                     HA_FAN, HA_LIGHT, HA_SENSOR, HA_SWITCH, MANAGER,
                     MEROSS_PLATFORMS, SENSORS, dismiss_notification, notify_error)

# Unset the default stream handler for logger of the meross_iot library
ROOT_MEROSS_LOGGER.removeHandler(h)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def print_version():
    try:
        import json
        import os
        fname = os.path.join(os.path.dirname(__file__), "manifest.json")
        with open(fname, "rt") as f:
            data = json.load(f)
            _LOGGER.info("MerossCloudVersion: %s" % data.get("meross_cloud_version"))
    except:
        _LOGGER.error("Failed to print version")


async def async_setup_entry(hass: HomeAssistantType, config_entry):
    """
    This class is called by the HomeAssistant framework when a configuration entry is provided.
    For us, the configuration entry is the username-password credentials that the user
    needs to access the Meross cloud.
    """

    try:
        print_version()

        # These will contain the initialized devices
        # The following call can cause am UnauthorizedException if bad login credentials are provided
        # or if a network exception occurs.
        manager = MerossManager(meross_email=config_entry.data.get(CONF_USERNAME), meross_password=config_entry.data.get(CONF_PASSWORD))
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
        _LOGGER.exception("Your Meross login credentials are invalid or the network could not be reached "
                          "at the moment.")

        raise ConfigEntryNotReady()
        #return False

    except Exception as e:
        _LOGGER.exception("An exception occurred while setting up the meross manager. Setup will be retried...")
        raise ConfigEntryNotReady()
        #return False


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
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT},
                data=conf
            )
        )

    return True
