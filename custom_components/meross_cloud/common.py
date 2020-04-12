import logging
import functools

from meross_iot.cloud.client_status import ClientStatus
from meross_iot.cloud.exceptions.CommandTimeoutException import CommandTimeoutException
from meross_iot.meross_event import (ClientConnectionEvent)

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


# TODO: better implement the following
# The following is a ugly workaround to fix the connection problems we are experiencing so far.
# The library needs a refactor.
class ConnectionWatchDog(object):
    def __init__(self, hass, platform):
        self._hass = hass
        self._platform = platform

    # TODO: Handle online status via abstract class?
    def connection_handler(self, event, *args, **kwargs):
        if isinstance(event, ClientConnectionEvent):
            if event.status == ClientStatus.CONNECTION_DROPPED:
                # Notify offline status
                for dev in self._hass.data[self._platform].entities:
                    dev._is_online = False
                    dev.schedule_update_ha_state(False)
            elif event.status == ClientStatus.SUBSCRIBED:
                for dev in self._hass.data[self._platform].entities:
                    # API
                    for d in self._hass.data[DOMAIN][MANAGER]._http_client.list_devices():
                        if dev._device.uuid == d['uuid']:
                            dev._is_online = d.get('onlineStatus', 0) == 1
                            # if the device is online, force a status refresh
                            dev.schedule_update_ha_state(dev._is_online)


def cloud_io(default_return_value=None):
    def cloud_io_inner(func):
        @functools.wraps(func)
        def func_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CommandTimeoutException as e:
                _LOGGER.warning("")
                if default_return_value is not None:
                    return default_return_value
                else:
                    return None
        return func_wrapper
    return cloud_io_inner

