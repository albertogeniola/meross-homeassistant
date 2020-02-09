import functools
from abc import ABC, abstractmethod
from typing import Union

from homeassistant.helpers.entity import Entity
from meross_iot.cloud.exceptions.CommandTimeoutException import CommandTimeoutException
from meross_iot.cloud.device import AbstractMerossDevice
from meross_iot.meross_event import DeviceOnlineStatusEvent, DeviceSwitchStatusEvent, MerossEvent
import logging


_LOGGER = logging.getLogger(__name__)

# Constants
DOMAIN = 'meross_cloud'
ATTR_CONFIG = "config"
MANAGER = 'manager'
MEROSS_MANAGER = "%s.%s" % (DOMAIN, MANAGER)
SENSORS = 'sensors'
HA_SWITCH = 'switch'
HA_LIGHT = 'light'
HA_SENSOR = 'sensor'
HA_COVER = 'cover'
HA_CLIMATE = 'climate'
MEROSS_PLATFORMS = (HA_LIGHT, HA_SWITCH, HA_COVER, HA_SENSOR, HA_CLIMATE)
CONNECTION_TIMEOUT_THRESHOLD = 5


def calculate_switch_id(uuid: str, channel: int):
    return "%s:%s:%d" % (HA_SWITCH, uuid, channel)


def calculate_sensor_id(uuid: str):
    return "%s:%s" % (HA_SENSOR, uuid)


def calculate_gerage_door_opener_id(uuid: str, channel: int):
    return "%s:%s:%d" % (HA_COVER, uuid, channel)


def dismiss_notification(hass, notification_id):
    hass.async_create_task(
        hass.services.async_call(domain='persistent_notification', service='dismiss', service_data={
            'notification_id': "%s.%s" % (DOMAIN, notification_id)})
    )


def notify_error(hass, notification_id, title, message):
    hass.async_create_task(
        hass.services.async_call(domain='persistent_notification', service='create', service_data={
                                           'title': title,
                                           'message': message,
                                           'notification_id': "%s.%s" % (DOMAIN, notification_id)})
    )


class AbstractMerossEntityWrapper(ABC):
    """This method wraps utilities and common behavior to all the MerossDeviceWrappers"""
    def __init__(self,
                 device  # type:AbstractMerossDevice
                 ):
        self._device = device
        self._is_online = None
        self._cloud_errors = 0

        # Load the current device status
        self._is_online = self._device.online
        device.register_event_callback(self.common_handler)

    def common_handler(self,
                       evt  # type: MerossEvent
                       ):
        # Any event received from the device causes the reset of the error state
        self.reset_error_state()

        # Handle here events that are common to all the wrappers
        if isinstance(evt, DeviceOnlineStatusEvent):
            if evt.status not in ["online", "offline"]:
                raise ValueError("Invalid online status")
            self._is_online = evt.status == "online"
        else:
            # Call the specific class-implementation event
            self.device_event_handler(evt)

    @abstractmethod
    def device_event_handler(self, evt):
        pass

    def reset_error_state(self):
        self._cloud_errors = 0
        self._is_online = True

    def notify_error(self):
        self._cloud_errors += 1
        if self._cloud_errors > CONNECTION_TIMEOUT_THRESHOLD:
            _LOGGER.warning("Detected more than %d connection errors. This means either the device is "
                            "offline, or the MerossCloud cannot be reached or we are offline."
                            "" % CONNECTION_TIMEOUT_THRESHOLD)
            self._is_online = False
            # TODO: start a timed poller
            # TODO: update state?


def cloud_io(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        instance = args[0]  # type: Union[AbstractMerossEntityWrapper, Entity]
        try:
            value = func(*args, **kwargs)
            instance.reset_error_state()
            return value
        except CommandTimeoutException:
            _LOGGER.error("A timeout exception occurred while executing function %s " % str(func))
            _LOGGER.debug("Exception info")
            instance.notify_error()

    return wrapper_decorator
