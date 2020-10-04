import asyncio
import logging
from collections import Callable
from typing import Any

from meross_iot.controller.device import BaseDevice

from custom_components.meross_cloud.version import MEROSS_CLOUD_VERSION
import time

_LOGGER = logging.getLogger(__name__)

# Constants
PLATFORM = 'meross_cloud'
ATTR_CONFIG = "config"
MANAGER = 'manager'
LIMITER = 'limiter'
CLOUD_HANDLER = 'cloud_handler'
MEROSS_MANAGER = "%s.%s" % (PLATFORM, MANAGER)
SENSORS = 'sensors'
HA_SWITCH = 'switch'
HA_LIGHT = 'light'
HA_SENSOR = 'sensor'
HA_COVER = 'cover'
HA_CLIMATE = 'climate'
HA_FAN = 'fan'
MEROSS_COMPONENTS = (HA_LIGHT, HA_SWITCH, HA_COVER, HA_SENSOR, HA_CLIMATE, HA_FAN)
CONNECTION_TIMEOUT_THRESHOLD = 5
CONF_STORED_CREDS = 'stored_credentials'
CONF_RATE_LIMIT_PER_SECOND = 'rate_limit_per_second'
CONF_RATE_LIMIT_MAX_TOKENS = 'rate_limit_max_tokens'


# Constants
RELAXED_SCAN_INTERVAL = 180.0
SENSOR_POLL_INTERVAL_SECONDS = 15
UNIT_PERCENTAGE = "%"


def calculate_sensor_id(uuid: str, type: str, measurement_unit: str, channel: int = 0,):
    return "%s:%s:%s:%s:%d" % (HA_SENSOR, uuid, type, measurement_unit, channel)


def calculate_cover_id(uuid: str, channel: int):
    return "%s:%s:%d" % (HA_COVER, uuid, channel)


def calculate_switch_id(uuid: str, channel: int):
    return "%s:%s:%d" % (HA_SWITCH, uuid, channel)


def calculate_valve_id(uuid: str):
    return "%s:%s" % (HA_CLIMATE, uuid)


def calculate_light_id(uuid: str, channel: int):
    return "%s:%s:%d" % (HA_LIGHT, uuid, channel)


def calculate_humidifier_id(uuid: str, channel: int):
    return "%s:%s:%d" % (HA_FAN, uuid, channel)


def dismiss_notification(hass, notification_id):
    hass.async_create_task(
        hass.services.async_call(domain='persistent_notification', service='dismiss', service_data={
            'notification_id': "%s.%s" % (PLATFORM, notification_id)})
    )


def notify_error(hass, notification_id, title, message):
    hass.async_create_task(
        hass.services.async_call(domain='persistent_notification', service='create', service_data={
            'title': title,
            'message': message,
            'notification_id': "%s.%s" % (PLATFORM, notification_id)})
    )


def log_exception(message: str = None, logger: logging = None, device: BaseDevice = None):
    if logger is None:
        logger = logging.getLogger(__name__)

    if message is None:
        message = "An exception occurred"

    device_info = "<Unavailable>"
    if device is not None:
        device_info = f"\tName: {device.name}\n" \
                      f"\tUUID: {device.uuid}\n" \
                      f"\tType: {device.type}\n\t" \
                      f"HW Version: {device.hardware_version}\n" \
                      f"\tFW Version: {device.firmware_version}"

    formatted_message = f"Error occurred.\n" \
                        f"-------------------------------------\n" \
                        f"Component version: {MEROSS_CLOUD_VERSION}\n" \
                        f"Device info: \n" \
                        f"{device_info}\n" \
                        f"Error Message: \"{message}\""
    logger.exception(formatted_message)


def invoke_method_or_property(obj, method_or_property):
    # We only call the explicit method if the sampled value is older than 10 seconds.
    attr = getattr(obj, method_or_property)
    if callable(attr):
        return attr()
    else:
        return attr


class RateLimiter:
    """Rate limiter utility implementing token-bucket algorithm
    This class is not thread-safe."""

    def __init__(self, rate: int = 1, max_tokens: int = 10):
        self._rate = rate
        self._max_tokens = max_tokens
        self._tokens = self._max_tokens
        self.updated_at = time.monotonic()
        self._start = time.monotonic()

    async def acquire(self, *args, **kwargs):
        token_obtained = await self._wait_for_token()
        return token_obtained

    async def _wait_for_token(self, timeout: float = None):
        wait_started_at = time.monotonic()
        while self._tokens < 1:
            self._add_new_tokens()
            await asyncio.sleep(0.1)

            if timeout is not None and (time.monotonic()-wait_started_at) > timeout:
                return False

        self._tokens -= 1
        return True

    def _add_new_tokens(self):
        now = time.monotonic()
        time_since_update = now - self.updated_at
        new_tokens = time_since_update * self._rate
        if self._tokens + new_tokens >= 1:
            self._tokens = min(self._tokens + new_tokens, self._max_tokens)
            self.updated_at = now


class RateLimitedFunction(object):
    def __init__(self, rate_limiter_instance: RateLimiter, callable_function: Callable, *async_function_args, **async_function_kwargs):
        self._limiter = rate_limiter_instance
        self._function = callable_function
        self._args = async_function_args
        self._kwargs = async_function_kwargs

    async def __call__(self) -> Any:
        r = await self._limiter.acquire()
        if r:
            result = await self._function(*self._args, **self._kwargs)
            return result
        else:
            _LOGGER.warning("RATE LIMITER - Throttling...")
            return None
