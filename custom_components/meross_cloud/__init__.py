"""Meross devices platform loader"""
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
from homeassistant.helpers.event import async_track_time_interval
from meross_iot.api import UnauthorizedException
from meross_iot.cloud.client_status import ClientStatus
from meross_iot.cloud.devices.door_openers import GenericGarageDoorOpener
from meross_iot.cloud.devices.light_bulbs import GenericBulb
from meross_iot.cloud.devices.power_plugs import GenericPlug
from meross_iot.manager import MerossManager
from meross_iot.meross_event import MerossEventType
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .common import (DOMAIN, ATTR_CONFIG, MEROSS_PLATFORMS, ENROLLED_DEVICES, HA_COVER, HA_LIGHT, HA_SENSOR,
                     HA_SWITCH, MANAGER, SENSORS, dismiss_notification,
                     notify_error)
from homeassistant import config_entries


_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def enroll_device(hass, conf, device):
    """Handle switch, light and garage openers."""
    if isinstance(device, GenericPlug):
        hass.async_create_task(discovery.async_load_platform(hass, HA_SWITCH, DOMAIN, device.uuid, conf))

        # Some switches also come with onboard sensors, so let's add them.
        # TODO: instead of checking the supports_power_consumption() (which is not available when the device
        #  is offline), we should retrieve this info somewhere else. The best would be to rely on some library
        #  maintained dictionary that states the capability of each device. For now that does not exist.
        if device.online and device.supports_consumption_reading():
            hass.async_create_task(discovery.async_load_platform(hass, HA_SENSOR, DOMAIN, device.uuid, conf))

    elif isinstance(device, GenericBulb):
        hass.async_create_task(discovery.async_load_platform(hass, HA_LIGHT, DOMAIN, device.uuid, conf))

    elif isinstance(device, GenericGarageDoorOpener):
        # A garage opener is sort of a switch.
        hass.async_create_task(discovery.async_load_platform(hass, HA_COVER, DOMAIN, device.uuid, conf))
    else:
        # TODO: log not supported devices
        pass


class EventHandlerWrapper:
    """Helper wrapper class for handling messages coming from HASSIO CLOUD"""

    def __init__(self, hass, conf):
        self._hass = hass
        self._conf = conf
        self._update_status_interval = timedelta(seconds=20)
        self._interval_handle = None

    def event_handler(self, evt):
        if evt.event_type == MerossEventType.DEVICE_ONLINE_STATUS:
            # If this is the first time we see this device, we need to add it.
            if evt.device.uuid not in self._hass.data[DOMAIN][ENROLLED_DEVICES]:
                enroll_device(self._hass, self._conf, evt.device)

        # If we lose the connection to the meross cloud, notify the user.
        if evt.event_type == MerossEventType.CLIENT_CONNECTION:
            if evt.status == ClientStatus.CONNECTION_DROPPED:
                _LOGGER.warn("Connection with the Meross cloud dropped.")
                notify_error(hass=self._hass, notification_id="connection_status",
                             title="Meross cloud connection", message="The connection to the Meross cloud **has been "
                                                                      "dropped**. If this is caused by a network issue,"
                                                                      "dont' worry, a connection will be reestablished "
                                                                      "as soon as Internet access is back.")
                self._interval_handle = async_track_time_interval(self._hass, self.test_client_connection,
                                                                  self._update_status_interval)
            elif evt.status == ClientStatus.INITIALIZED:
                pass
            else:
                # Dismiss any network down notification
                _LOGGER.warn("Connected to the Meross cloud.")
                dismiss_notification(self._hass, "connection_status")

                # Dismiss the recurrent task
                if self._interval_handle is not None:
                    self._interval_handle()

    def test_client_connection(self, evt):
        try:
            _LOGGER.info("Trying to establish a connection with the Meross cloud...")
            manager = self._hass.data[DOMAIN][MANAGER]
            _LOGGER.debug("Stopping manager...")
            manager.stop()
            _LOGGER.debug("Starting manager...")
            manager.start()

        except UnauthorizedException as e:
            _LOGGER.error("Your Meross login credentials are invalid or the network could not be reached "
                          "at the moment.")
        except Exception as e:
            _LOGGER.exception("Connection to the meross client failed.")


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

        """
        for platform in ABODE_PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, platform)
            )
        """

        #wrapper = EventHandlerWrapper(hass, conf)
        hass.data[DOMAIN][MANAGER] = manager
        hass.data[DOMAIN][SENSORS] = {}
        #manager.register_event_handler(wrapper.event_handler)

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
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True

