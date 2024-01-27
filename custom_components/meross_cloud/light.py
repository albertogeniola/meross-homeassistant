import logging
from typing import Optional, Dict

from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.light import LightMixin
from meross_iot.manager import MerossManager
from meross_iot.model.http.device import HttpDeviceInfo

import homeassistant.util.color as color_util
# Conditional Light import with backwards compatibility
from homeassistant.components.light import LightEntity
from homeassistant.components.light import SUPPORT_BRIGHTNESS, SUPPORT_COLOR, SUPPORT_COLOR_TEMP, \
    ATTR_HS_COLOR, ATTR_COLOR_TEMP, ATTR_BRIGHTNESS
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import MerossDevice
from .common import (DOMAIN, MANAGER, HA_LIGHT, DEVICE_LIST_COORDINATOR)

_LOGGER = logging.getLogger(__name__)


class MerossLightDevice(LightMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class LightEntityWrapper(MerossDevice, LightEntity):
    """Wrapper class to adapt the Meross bulbs into the Homeassistant platform"""
    _device: MerossLightDevice

    def __init__(self,
                 channel: int,
                 device: MerossLightDevice,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]):

        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_LIGHT)

    async def async_turn_off(self, **kwargs) -> None:
        await self._device.async_turn_off(channel=self._channel_id, skip_rate_limits=True)

    async def async_turn_on(self, **kwargs) -> None:
        if not self.is_on:
            await self._device.async_turn_on(channel=self._channel_id, skip_rate_limits=True)

        # Color is taken from either of these 2 values, but not both.
        if ATTR_HS_COLOR in kwargs:
            h, s = kwargs[ATTR_HS_COLOR]
            rgb = color_util.color_hsv_to_RGB(h, s, 100)
            _LOGGER.debug("color change: rgb=%r -- h=%r s=%r" % (rgb, h, s))
            await self._device.async_set_light_color(channel=self._channel_id, rgb=rgb, onoff=True, skip_rate_limits=True)
        elif ATTR_COLOR_TEMP in kwargs:
            mired = kwargs[ATTR_COLOR_TEMP]
            norm_value = (mired - self.min_mireds) / (self.max_mireds - self.min_mireds)
            temperature = 100 - (norm_value * 100)
            _LOGGER.debug("temperature change: mired=%r meross=%r" % (mired, temperature))
            await self._device.async_set_light_color(channel=self._channel_id, temperature=temperature, skip_rate_limits=True)

        # Brightness must always be set, so take previous luminance if not explicitly set now.
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS] * 100 / 255
            _LOGGER.debug("brightness change: %r" % brightness)
            await self._device.async_set_light_color(channel=self._channel_id, luminance=brightness, skip_rate_limits=True)

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
        rgb = self._device.get_rgb_color(channel=self._channel_id)
        if rgb is not None and isinstance(rgb, tuple) and len(rgb) == 3:
            return color_util.color_RGB_to_hs(*rgb)
        else:
            return None  # Return None if RGB value is not available

    @property
    def color_temp(self):
        if self._device.get_supports_temperature(channel=self._channel_id):
            value = self._device.get_color_temperature()
            norm_value = (100 - value) / 100.0
            return self.min_mireds + (norm_value * (self.max_mireds - self.min_mireds))
        return None


async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    def entity_adder_callback():
        """Discover and adds new Meross entities"""
        manager: MerossManager = hass.data[DOMAIN][MANAGER]  # type
        coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
        devices = manager.find_devices()

        new_entities = []

        devs = filter(lambda d: isinstance(d, LightMixin), devices)
        for d in devs:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = LightEntityWrapper(device=d, channel=channel_index, device_list_coordinator=coordinator)
                if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                    new_entities.append(w)

        async_add_entities(new_entities, True)

    coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
    coordinator.async_add_listener(entity_adder_callback)
    # Run the entity adder a first time during setup
    entity_adder_callback()


# TODO: Implement entry unload
# TODO: Unload entry
# TODO: Remove entry


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
