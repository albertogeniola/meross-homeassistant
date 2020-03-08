import functools
from abc import ABC, abstractmethod
from typing import Union

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from meross_iot.cloud.client_status import ClientStatus
from meross_iot.cloud.exceptions.CommandTimeoutException import CommandTimeoutException
from meross_iot.cloud.device import AbstractMerossDevice
from meross_iot.manager import MerossManager
from meross_iot.meross_event import DeviceOnlineStatusEvent, DeviceSwitchStatusEvent, MerossEvent, ClientConnectionEvent
from threading import Timer
import logging


_LOGGER = logging.getLogger(__name__)

# Constants
DOMAIN = 'meross_cloud'
ATTR_CONFIG = "config"
MANAGER = 'manager'
CLOUD_HANDLER = 'cloud_handler'
MEROSS_MANAGER = "%s.%s" % (DOMAIN, MANAGER)
SENSORS = 'sensors'
HA_SWITCH = 'switch'
HA_LIGHT = 'light'
HA_SENSOR = 'sensor'
HA_COVER = 'cover'
HA_CLIMATE = 'climate'
HA_FAN = 'fan'
MEROSS_PLATFORMS = (HA_LIGHT, HA_SWITCH, HA_COVER, HA_SENSOR, HA_CLIMATE, HA_FAN)
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


def cloud_io(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        instance = args[0]  # type: Union[AbstractMerossEntityWrapper, Entity]
        try:
            value = func(*args, **kwargs)
            instance.reset_error_state()
            return value
        except CommandTimeoutException:
            _LOGGER.debug("Exception info")

            if not instance._error:
                _LOGGER.error("A timeout exception occurred while executing function %s " % str(func))
                instance.notify_error()

    return wrapper_decorator


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
        self._error = False

    @abstractmethod
    def device_event_handler(self, evt):
        pass

    @abstractmethod
    @cloud_io
    def force_state_update(self, ui_only=False):
        pass

    def reset_error_state(self):
        if self._error:
            self._cloud_errors = 0
            self._is_online = True
            self.force_state_update(ui_only=True)
            self._error = False

    def notify_error(self):
        if self._cloud_errors == CONNECTION_TIMEOUT_THRESHOLD:
            _LOGGER.warning("Detected more than %d connection errors. This means either the device is "
                            "offline, or the MerossCloud cannot be reached or we are offline."
                            "" % CONNECTION_TIMEOUT_THRESHOLD)
            self._is_online = False
            self.force_state_update(ui_only=True)
            self._error = True

        self._cloud_errors += 1


class MerossCloudConnectionWatchdog(object):
    def __init__(self,
                 manager,               # type: MerossManager
                 hass,                  # type: HomeAssistantType
                 retry_interval=10.0    # type: float
                ):
        self._manager = manager
        self._registered = False
        self._retry_interval = retry_interval
        self._hass = hass

    def register_manager(self):
        if self._registered:
            _LOGGER.info("This manager has already been registered.")
            return
        self._manager.register_event_handler(self._cloud_event_handler)
        _LOGGER.info("Meross connection watchdog registered to connection events.")

    def unregister_manager(self):
        if not self._registered:
            _LOGGER.info("This manager has not been registered yet.")
            return
        self._manager.unregister_event_handler(self._cloud_event_handler)
        _LOGGER.info("Meross connection watchdog unregistered from connection events.")

    def _cloud_event_handler(self, event):
        _LOGGER.debug(event)
        if isinstance(event, ClientConnectionEvent):
            if event.status == ClientStatus.CONNECTION_DROPPED:
                _LOGGER.warning("Detected MerossCloud connection drop."
                                "Scheduling connection retry in {} seconds.".format(self._retry_interval))
                self._manager.stop()
                self._schedule_connection_retry(self._retry_interval)
                self._force_full_device_update()

            elif event.status == ClientStatus.CONNECTED:
                _LOGGER.info("MerossCloud connected.")
                self._cancel_connection_retry()
                self._force_full_device_update()

    def _schedule_connection_retry(self, interval):
        self._t = Timer(interval=interval, function=self.__retry_connection)
        self._t.start()

    def _cancel_connection_retry(self):
        if self._t is not None and self._t.is_alive():
            self._t.cancel()
            self._t = None

    def __retry_connection(self):
        try:
            self._manager.stop()
            _LOGGER.info("Retrying connection to MerossCloud...")
            self._manager.start()
        except Exception as e:
            _LOGGER.debug("Connection to MerossCloud failed.")
            _LOGGER.exception("Connection to MerossCloud failed.")
            _LOGGER.error("Connection to MerossCloud failed. Rescheduling")
            self._schedule_connection_retry(self._retry_interval)

    def _force_full_device_update(self):
        for plat in MEROSS_PLATFORMS:
            # TODO: find a better way to handle device offline exceptions.
            # Maybe a viable option is to rely on HTTP api to check online devices.
            for uuid, device in self._hass.data[DOMAIN][plat].items():  # type:AbstractMerossEntityWrapper
                _LOGGER.info("Forcing state update for device %s" % uuid)
                try:
                    device.force_state_update()
                except:
                    _LOGGER.exception("Error occurred while refreshing status for device %s" % device.name)

