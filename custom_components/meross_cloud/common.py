import logging
from abc import ABC

from meross_iot.cloud.client_status import ClientStatus
from meross_iot.cloud.device import AbstractMerossDevice
from meross_iot.meross_event import (ClientConnectionEvent)

from custom_components.meross_cloud.version import MEROSS_CLOUD_VERSION

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
CONF_STORED_CREDS = 'stored_credentials'


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


class ConnectionWatchDog(object):
    def __init__(self, hass, platform):
        self._hass = hass
        self._platform = platform

    def connection_handler(self, event, *args, **kwargs):
        if isinstance(event, ClientConnectionEvent):
            for uuid, dev in self._hass.data[DOMAIN][self._platform].items():
                try:
                    dev.notify_client_state(status=event.status)
                except:
                    log_exception("Error occurred while notifying connection change", device=dev._device)


class MerossEntityWrapper(ABC):
    def notify_client_state(self, status: ClientStatus):
        pass


def log_exception(message: str = None, logger: logging = None, device: AbstractMerossDevice = None):
    if logger is None:
        logger = logging.getLogger(__name__)

    if message is None:
        message = "An exception occurred"

    device_info = "<Unavailable>"
    if device is not None:
        device_info = f"\tName: {device.name}\n" \
                      f"\tUUID: {device.uuid}\n" \
                      f"\tType: {device.type}\n\t" \
                      f"HW Version: {device.hwversion}\n" \
                      f"\tFW Version: {device.fwversion}"

    formatted_message = f"Error occurred.\n" \
                        f"-------------------------------------\n" \
                        f"Component version: {MEROSS_CLOUD_VERSION}\n" \
                        f"Device info: \n" \
                        f"{device_info}\n" \
                        f"Error Message: \"{message}\""
    logger.exception(formatted_message)
