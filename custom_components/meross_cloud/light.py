import logging
from datetime import timedelta
from typing import Any, Optional, Iterable, List

import homeassistant.util.color as color_util
from homeassistant.components.light import SUPPORT_BRIGHTNESS, SUPPORT_COLOR, SUPPORT_COLOR_TEMP, \
    ATTR_HS_COLOR, ATTR_COLOR_TEMP, ATTR_BRIGHTNESS
from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.light import LightMixin
from meross_iot.manager import MerossManager
from meross_iot.model.enums import OnlineStatus, Namespace
from meross_iot.model.exception import CommandTimeoutError
from meross_iot.model.push.bind import BindPushNotification
from meross_iot.model.push.generic import GenericPushNotification

from .common import (PLATFORM, MANAGER, log_exception, RELAXED_SCAN_INTERVAL,
                     calculate_light_id)

# Conditional Light import with backwards compatibility
try:
    from homeassistant.components.light import LightEntity
except ImportError:
    from homeassistant.components.light import Light as LightEntity


_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=RELAXED_SCAN_INTERVAL)


class MerossLightDevice(LightMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class LightEntityWrapper(LightEntity):
    """Wrapper class to adapt the Meross bulbs into the Homeassistant platform"""

    def __init__(self, device: MerossLightDevice, channel: int):
        # TODO: verify channel is 0
        self._device = device

        # If the current device has more than 1 channel, we need to setup the device name and id accordingly
        self._id = calculate_light_id(device.internal_id, channel)
        channel_data = device.channels[channel]
        self._entity_name = "{} ({}) - {}".format(device.name, device.type, channel_data.name)

        # Device properties
        self._channel_id = channel

    # region Device wrapper common methods
    async def async_update(self):
        if self._device.online_status == OnlineStatus.ONLINE:
            try:
                await self._device.async_update()
            except CommandTimeoutError as e:
                log_exception(logger=_LOGGER, device=self._device)
                pass

    async def _async_push_notification_received(self, namespace: Namespace, data: dict, device_internal_id: str):
        update_state = False
        full_update = False

        if namespace == Namespace.CONTROL_UNBIND:
            _LOGGER.warning(f"Received unbind event. Removing device {self.name} from HA")
            await self.platform.async_remove_entity(self.entity_id)
        elif namespace == Namespace.SYSTEM_ONLINE:
            _LOGGER.warning(f"Device {self.name} reported online event.")
            online = OnlineStatus(int(data.get('online').get('status')))
            update_state = True
            full_update = online == OnlineStatus.ONLINE
        elif namespace == Namespace.HUB_ONLINE:
            _LOGGER.warning(f"Device {self.name} reported (HUB) online event.")
            online = OnlineStatus(int(data.get('status')))
            update_state = True
            full_update = online == OnlineStatus.ONLINE
        else:
            update_state = True
            full_update = False

        # In all other cases, just tell HA to update the internal state representation
        if update_state:
            self.async_schedule_update_ha_state(force_refresh=full_update)

    async def async_added_to_hass(self) -> None:
        self._device.register_push_notification_handler_coroutine(self._async_push_notification_received)
        self.hass.data[PLATFORM]["ADDED_ENTITIES_IDS"].add(self.unique_id)

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_push_notification_handler_coroutine(self._async_push_notification_received)
        self.hass.data[PLATFORM]["ADDED_ENTITIES_IDS"].remove(self.unique_id)
    # endregion

    # region Device wrapper common properties
    @property
    def unique_id(self) -> str:
        # Since Meross plugs may have more than 1 switch, we need to provide a composed ID
        # made of uuid and channel
        return self._id

    @property
    def name(self) -> str:
        return self._entity_name

    @property
    def device_info(self):
        return {
            'identifiers': {(PLATFORM, self._device.internal_id)},
            'name': self._device.name,
            'manufacturer': 'Meross',
            'model': self._device.type + " " + self._device.hardware_version,
            'sw_version': self._device.firmware_version
        }

    @property
    def available(self) -> bool:
        # A device is available if the client library is connected to the MQTT broker and if the
        # device we are contacting is online
        return self._device.online_status == OnlineStatus.ONLINE

    @property
    def should_poll(self) -> bool:
        return False
    # endregion

    # region Platform-specific command methods
    async def async_turn_off(self, **kwargs) -> None:
        await self._device.async_turn_off(channel=self._channel_id)

    async def async_turn_on(self, **kwargs) -> None:
        if not self.is_on:
            await self._device.async_turn_on(channel=self._channel_id)

        # Color is taken from either of these 2 values, but not both.
        if ATTR_HS_COLOR in kwargs:
            h, s = kwargs[ATTR_HS_COLOR]
            rgb = color_util.color_hsv_to_RGB(h, s, 100)
            _LOGGER.debug("color change: rgb=%r -- h=%r s=%r" % (rgb, h, s))
            await self._device.async_set_light_color(channel=self._channel_id, rgb=rgb, onoff=True)
        elif ATTR_COLOR_TEMP in kwargs:
            mired = kwargs[ATTR_COLOR_TEMP]
            norm_value = (mired - self.min_mireds) / (self.max_mireds - self.min_mireds)
            temperature = 100 - (norm_value * 100)
            _LOGGER.debug("temperature change: mired=%r meross=%r" % (mired, temperature))
            await self._device.async_set_light_color(channel=self._channel_id, temperature=temperature)

        # Brightness must always be set, so take previous luminance if not explicitly set now.
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS] * 100 / 255
            _LOGGER.debug("brightness change: %r" % brightness)
            await self._device.async_set_light_color(channel=self._channel_id, luminance=brightness)

    def turn_on(self, **kwargs: Any) -> None:
        self.hass.async_add_executor_job(self.async_turn_on, **kwargs)

    def turn_off(self, **kwargs: Any) -> None:
        self.hass.async_add_executor_job(self.async_turn_off, **kwargs)
    # endregion

    # region Platform specific properties
    @property
    def supported_features(self):
        flags = 0
        if self._device.get_supports_luminance(channel=self._channel_id):
            flags |= SUPPORT_BRIGHTNESS
        if self._device.get_supports_rgb(channel=self._channel_id):
            flags |= SUPPORT_COLOR
        if self._device.get_supports_temperature(channel=self._channel_id):
            flags |= SUPPORT_COLOR_TEMP
        return flags

    @property
    def is_on(self) -> Optional[bool]:
        return self._device.get_light_is_on(channel=self._channel_id)

    @property
    def brightness(self):
        if not self._device.get_supports_luminance(self._channel_id):
            return None

        luminance = self._device.get_luminance()
        if luminance is not None:
            return float(luminance) / 100 * 255

        return None

    @property
    def hs_color(self):
        if self._device.get_supports_rgb(channel=self._channel_id):
            rgb = self._device.get_rgb_color()
            return color_util.color_RGB_to_hs(*rgb)
        return None

    @property
    def color_temp(self):
        if self._device.get_supports_temperature(channel=self._channel_id):
            value = self._device.get_color_temperature()
            norm_value = (100 - value) / 100.0
            return self.min_mireds + (norm_value * (self.max_mireds - self.min_mireds))
        return None
    # endregion


# ----------------------------------------------
# PLATFORM METHODS
# ----------------------------------------------
async def _add_entities(hass, devices: Iterable[BaseDevice], async_add_entities):
    new_entities = []

    # Identify all the devices that expose the Light capability
    devs = filter(lambda d: isinstance(d, LightMixin), devices)
    for d in devs:
        for channel_index, channel in enumerate(d.channels):
            w = LightEntityWrapper(device=d, channel=channel_index)
            if w.unique_id not in hass.data[PLATFORM]["ADDED_ENTITIES_IDS"]:
                new_entities.append(w)
            else:
                _LOGGER.info(f"Skipping device {w} as it was already added to registry once.")
    async_add_entities(new_entities, True)


async def async_setup_entry(hass, config_entry, async_add_entities):
    # When loading the platform, immediately add currently available
    # bulbs.
    manager = hass.data[PLATFORM][MANAGER]  # type:MerossManager
    devices = manager.find_devices()
    await _add_entities(hass=hass, devices=devices, async_add_entities=async_add_entities)

    # Register a listener for the Bind push notification so that we can add new entities at runtime
    async def platform_async_add_entities(push_notification: GenericPushNotification, target_devices: List[BaseDevice]):
        if push_notification.namespace == Namespace.CONTROL_BIND \
                or push_notification.namespace == Namespace.SYSTEM_ONLINE \
                or push_notification.namespace == Namespace.HUB_ONLINE:
            await manager.async_device_discovery(push_notification.namespace == Namespace.HUB_ONLINE,
                                                 meross_device_uuid=push_notification.originating_device_uuid)
            devs = manager.find_devices(device_uuids=(push_notification.originating_device_uuid,))
            await _add_entities(hass=hass, devices=devs, async_add_entities=async_add_entities)

    # Register a listener for new bound devices
    manager.register_push_notification_handler_coroutine(platform_async_add_entities)


# TODO: Unload entry
# TODO: Remove entry


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
