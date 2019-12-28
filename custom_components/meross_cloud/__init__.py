"""Meross devices platform loader"""
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
from meross_iot.api import UnauthorizedException
from meross_iot.cloud.client_status import ClientStatus
from meross_iot.cloud.devices.door_openers import GenericGarageDoorOpener
from meross_iot.cloud.devices.light_bulbs import GenericBulb
from meross_iot.cloud.devices.power_plugs import GenericPlug
from meross_iot.manager import MerossManager
from meross_iot.meross_event import MerossEventType

from .common import (DOMAIN, ATTR_CONFIG, MEROSS_PLATFORMS, ENROLLED_DEVICES, HA_COVER, HA_LIGHT, HA_SENSOR,
                     HA_SWITCH, MANAGER, SENSORS, dismiss_notification,
                     notify_error)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup_entry(hass: HomeAssistantType, config_entry):
    """
    This class is called by the HomeAssistant framework when a configuration entry is provided.
    For us, the configuration entry is the username-password credentials that the user
    needs to access the Meross cloud.
    """

    try:

        # These will contain the initialized devices
        # The following call can cause am UnauthorizedException if bad login credentials are provided
        # or if a network exception occurs.
        manager = MerossManager(meross_email=config_entry.data.get(CONF_USERNAME), meross_password=config_entry.data.get(CONF_PASSWORD))

        hass.data[DOMAIN][MANAGER] = manager
        hass.data[DOMAIN][SENSORS] = {}

        # Setup a set for keeping track of enrolled devices
        hass.data[DOMAIN][ENROLLED_DEVICES] = set()

        _LOGGER.info("Starting meross manager")
        manager.start()

        for platform in (MEROSS_PLATFORMS):
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, platform)
            )

        return True

    except UnauthorizedException as e:
        notify_error(hass, "http_connection", "Meross Cloud", "Could not connect to the Meross cloud. Please check"
                                                              " your internet connection and your Meross credentials")
        _LOGGER.exception("Your Meross login credentials are invalid or the network could not be reached "
                          "at the moment.")

        return False

    except Exception as e:
        _LOGGER.exception("An exception occurred while setting up the meross manager.")
        return False


async def async_setup(hass, config):
    """
    This method gets called if HomeAssistant has a valid meross_cloud: configuration entry within
    configurations.yaml.

    Thus, in this method we simply trigger the creation of a config entry.

    :return:
    """

    # TODO: check whether the integration has been already configured previously via User Config Entry or
    #       discovery

    conf = config.get(DOMAIN)
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ATTR_CONFIG] = conf

    if conf is not None:
        await hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT},
                data=conf
            )
        )

    return True

