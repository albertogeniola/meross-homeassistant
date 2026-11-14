import logging
from typing import Optional, Dict

from homeassistant.core import HomeAssistant
from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.light import LightMixin
from meross_iot.controller.mixins.diffuser_light import DiffuserLightMixin
from meross_iot.manager import MerossManager
from meross_iot.model.http.device import HttpDeviceInfo
from meross_iot.model.enums import DiffuserLightMode, Namespace, LightMode
import homeassistant.util.color as color_util
from homeassistant.components.light import LightEntity
from homeassistant.components.light import ColorMode, \
    ATTR_HS_COLOR, ATTR_COLOR_TEMP_KELVIN, ATTR_BRIGHTNESS, ATTR_RGB_COLOR
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import MerossDevice
from .common import (DOMAIN, MANAGER, HA_LIGHT, DEVICE_LIST_COORDINATOR)

_LOGGER = logging.getLogger(__name__)


class MerossOilDiffuserLightDevice(DiffuserLightMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class MerossLightDevice(LightMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class DiffuserLightEntityWrapper(MerossDevice, LightEntity):
    """Wrapper class to adapt the Meross OilDiffuserLight"""
    _device: MerossOilDiffuserLightDevice
    # For now, we assume OilDiffuserLight supports all the following features.
    # From Meross API it is in fact impossible to determine which exact features are supported by the device.
    _attr_supported_color_modes = {ColorMode.WHITE, ColorMode.RGB, ColorMode.COLOR_TEMP}

    def __init__(self,
                 channel: int,
                 device: MerossOilDiffuserLightDevice,
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

        if ATTR_HS_COLOR in kwargs:
            h, s = kwargs[ATTR_HS_COLOR]
            rgb = color_util.color_hsv_to_RGB(h, s, 100)
            _LOGGER.debug("color change: rgb=%r -- h=%r s=%r" % (rgb, h, s))
            await self._device.async_set_light_mode(channel=self._channel_id, mode=DiffuserLightMode.FIXED_RGB, rgb=rgb, onoff=True, skip_rate_limits=True)
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            mired = kwargs[ATTR_COLOR_TEMP_KELVIN]
            norm_value = (mired - self.min_mireds) / (self.max_mireds - self.min_mireds)
            temperature = 100 - (norm_value * 100)
            _LOGGER.debug("temperature change: mired=%r meross=%r" % (mired, temperature))
            await self._device.async_set_light_mode(channel=self._channel_id, mode=DiffuserLightMode.FIXED_LUMINANCE, onoff=True, rgb=65293, brightness=temperature, skip_rate_limits=True)

        # Brightness must always be set, so take previous luminance if not explicitly set now.
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS] * 100 / 255
            _LOGGER.debug("brightness change: %r" % brightness)
            await self._device.async_set_light_mode(channel=self._channel_id, luminance=brightness, skip_rate_limits=True)

    @property
    def is_on(self) -> Optional[bool]:
        return self._device.get_light_is_on(channel=self._channel_id)

    @property
    def hs_color(self):
        rgb = self._device.get_light_rgb_color(channel=self._channel_id)
        if rgb is not None and isinstance(rgb, tuple) and len(rgb) == 3:
            return color_util.color_RGB_to_hs(*rgb)
        else:
            return None  # Return None if RGB value is not available

    @property
    def brightness(self):
        luminance = self._device.get_light_brightness()
        if luminance is not None:
            return float(luminance) / 100 * 255
        return None


class LightEntityWrapper(MerossDevice, LightEntity):
    """Adapt bulb colour commands and reported mode to HA's Kelvin API."""
    _device: MerossLightDevice
    # Preserve the integration's previous advertised range; not a calibration.
    _attr_min_color_temp_kelvin = 2000
    _attr_max_color_temp_kelvin = 6535

    def __init__(self, channel, device, device_list_coordinator):
        self._last_color_mode = None
        super().__init__(device=device, channel=channel,
                         device_list_coordinator=device_list_coordinator,
                         platform=HA_LIGHT)

    def _capture_mode(self, light):
        if not isinstance(light, dict) or light.get("channel", 0) != self._channel_id:
            return
        capacity = light.get("capacity", 0)
        if capacity & LightMode.MODE_RGB.value:
            self._last_color_mode = ColorMode.RGB
        elif capacity & LightMode.MODE_TEMPERATURE.value:
            self._last_color_mode = ColorMode.COLOR_TEMP
        # Luminance-only updates preserve the active colour mode.

    async def _async_push_notification_received(self, namespace, data, device_internal_id):
        if namespace == Namespace.CONTROL_LIGHT:
            lights = data.get("light", {})
        elif namespace == Namespace.SYSTEM_ALL:
            lights = data.get("all", {}).get("digest", {}).get("light", {})
        else:
            lights = []
        for light in lights if isinstance(lights, list) else [lights]:
            self._capture_mode(light)
        await super()._async_push_notification_received(namespace, data, device_internal_id)

    async def async_turn_off(self, **kwargs):
        await self._device.async_turn_off(channel=self._channel_id, skip_rate_limits=True)

    async def async_turn_on(self, **kwargs):
        payload = {}
        mode = None
        if ATTR_RGB_COLOR in kwargs:
            payload["rgb"] = tuple(kwargs[ATTR_RGB_COLOR])
            mode = ColorMode.RGB
        elif ATTR_HS_COLOR in kwargs:
            payload["rgb"] = tuple(color_util.color_hsv_to_RGB(*kwargs[ATTR_HS_COLOR], 100))
            mode = ColorMode.RGB
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            kelvin = max(self.min_color_temp_kelvin,
                         min(self.max_color_temp_kelvin, kwargs[ATTR_COLOR_TEMP_KELVIN]))
            cold_mired = 1000000 / self.max_color_temp_kelvin
            warm_mired = 1000000 / self.min_color_temp_kelvin
            payload["temperature"] = round(1 + 99 * (warm_mired - 1000000 / kelvin)
                                           / (warm_mired - cold_mired))
            mode = ColorMode.COLOR_TEMP
        if ATTR_BRIGHTNESS in kwargs:
            payload["luminance"] = max(1, min(100, round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)))
        if payload:
            await self._device.async_set_light_color(channel=self._channel_id,
                                                     skip_rate_limits=True, **payload)
            if mode is not None:
                self._last_color_mode = mode
        # Apply colour before switching on, avoiding a flash at the old setting.
        if not self.is_on:
            await self._device.async_turn_on(channel=self._channel_id, skip_rate_limits=True)

    @property
    def supported_color_modes(self):
        modes = set()
        if self._device.get_supports_rgb(channel=self._channel_id):
            modes.add(ColorMode.RGB)
        if self._device.get_supports_temperature(channel=self._channel_id):
            modes.add(ColorMode.COLOR_TEMP)
        if not modes:
            modes.add(ColorMode.BRIGHTNESS if self._device.get_supports_luminance(
                channel=self._channel_id) else ColorMode.ONOFF)
        return modes

    @property
    def is_on(self):
        return self._device.get_light_is_on(channel=self._channel_id)

    @property
    def brightness(self):
        value = self._device.get_luminance(channel=self._channel_id)
        return round(value * 255 / 100) if value is not None else None

    @property
    def color_mode(self):
        if self._last_color_mode in self.supported_color_modes:
            return self._last_color_mode
        # Full-update callbacks normally supply capacity before HA reads state.
        if ColorMode.COLOR_TEMP in self.supported_color_modes and self._device.get_rgb_color(
                channel=self._channel_id) is None:
            return ColorMode.COLOR_TEMP
        return next(iter(sorted(self.supported_color_modes)))

    @property
    def rgb_color(self):
        return self._device.get_rgb_color(channel=self._channel_id)

    @property
    def color_temp_kelvin(self):
        if ColorMode.COLOR_TEMP not in self.supported_color_modes:
            return None
        value = self._device.get_color_temperature(channel=self._channel_id)
        if value is None:
            return None
        cold_mired = 1000000 / self.max_color_temp_kelvin
        warm_mired = 1000000 / self.min_color_temp_kelvin
        mired = warm_mired - (max(1, min(100, value)) - 1) * (warm_mired - cold_mired) / 99
        return round(1000000 / mired)


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    def entity_adder_callback():
        """Discover and adds new Meross entities"""
        manager: MerossManager = hass.data[DOMAIN][MANAGER]  # type
        coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
        devices = manager.find_devices()

        new_entities = []

        light_devs = filter(lambda d: isinstance(d, LightMixin), devices)
        for d in light_devs:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = LightEntityWrapper(device=d, channel=channel_index, device_list_coordinator=coordinator)
                if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                    new_entities.append(w)

        diffuser_devs = filter(lambda d: isinstance(d, DiffuserLightMixin), devices)
        for d in diffuser_devs:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = DiffuserLightEntityWrapper(device=d, channel=channel_index, device_list_coordinator=coordinator)
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
