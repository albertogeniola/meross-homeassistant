import logging

import homeassistant.util.color as color_util
from homeassistant.components.light import (Light, SUPPORT_BRIGHTNESS, SUPPORT_COLOR, SUPPORT_COLOR_TEMP,
                                            ATTR_HS_COLOR, ATTR_COLOR_TEMP, ATTR_BRIGHTNESS)
from meross_iot.cloud.devices.light_bulbs import GenericBulb
from meross_iot.manager import MerossManager

from .common import DOMAIN, MANAGER

_LOGGER = logging.getLogger(__name__)


def rgb_int_to_tuple(color):
    blue = color & 255
    green = (color >> 8) & 255
    red = (color >> 16) & 255
    return (red, green, blue)


def expand_status(status):
    "Expand the status information for readability"
    out = dict(status)
    out['rgb'] = rgb_int_to_tuple(status['rgb'])
    return out


class LightEntityWrapper(Light):
    """Wrapper class to adapt the Meross switches into the Homeassistant platform"""

    def __init__(self, device: GenericBulb, channel: int):
        self._device = device
        self._channel_id = channel
        self._id = self._device.uuid
        self._device_name = self._device.name

        self._device.register_event_callback(self.handler)

    def handler(self, evt):
        _LOGGER.debug("event_handler(name=%r, evt=%r)" % (self._device_name, repr(vars((evt)))))
        self.async_schedule_update_ha_state(False)

    @property
    def available(self) -> bool:
        # A device is available if it's online
        return self._device.online

    @property
    def name(self) -> str:
        return self._device_name

    @property
    def unique_id(self) -> str:
        return self._id

    @property
    def is_on(self) -> bool:
        # Note that the following method is not fetching info from the device over the network.
        # Instead, it is reading the device status from the state-dictionary that is handled by the library.
        return self._device.get_channel_status(self._channel_id).get('onoff')

    def turn_off(self, **kwargs) -> None:
        _LOGGER.debug('turn_off(name=%r)' % self._device_name)
        self._device.turn_off(channel=self._channel_id)

    def turn_on(self, **kwargs) -> None:
        if not self.is_on:
            _LOGGER.debug('turn_on(name=%r)' % (self._device_name))
            self._device.turn_on(channel=self._channel_id) # Avoid a potential response event race between setting on and below set_light_color

        # Color is taken from either of these 2 values, but not both.
        if ATTR_HS_COLOR in kwargs:
            h, s = kwargs[ATTR_HS_COLOR]
            rgb = color_util.color_hsv_to_RGB(h, s, 100)
            _LOGGER.debug("color change: rgb=%r -- h=%r s=%r" % (rgb, h, s))
            self._device.set_light_color(self._channel_id, rgb=rgb)
        elif ATTR_COLOR_TEMP in kwargs:
            mired = kwargs[ATTR_COLOR_TEMP]
            norm_value = (mired - self.min_mireds) / (self.max_mireds - self.min_mireds)
            temperature = 100 - (norm_value * 100)
            _LOGGER.debug("temperature change: mired=%r meross=%r" % (mired, temperature))
            self._device.set_light_color(self._channel_id, temperature=temperature)

        # Brightness must always be set, so take previous luminance if not explicitly set now.
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS] * 100 / 255
            _LOGGER.debug("    brightness change: %r" % brightness)
            self._device.set_light_color(self._channel_id, luminance=brightness)

    @property
    def brightness(self):
        # Meross bulbs support luminance between 0 and 100;
        # while the HA wants values from 0 to 255. Therefore, we need to scale the values.
        status = self._device.get_status(self._channel_id)
        _LOGGER.debug('get_brightness(name=%r status=%r)' % (self._device_name, expand_status(status)))
        return status.get('luminance') / 100 * 255

    @property
    def hs_color(self):
        status = self._device.get_channel_status(self._channel_id)
        _LOGGER.debug('get_hs_color(name=%r status=%r)' % (self._device_name, expand_status(status)))
        if status.get('capacity') == 5:  # rgb mode
            rgb = rgb_int_to_tuple(status.get('rgb'))
            return color_util.color_RGB_to_hs(*rgb)
        return None

    @property
    def color_temp(self):
        status = self._device.get_channel_status(self._channel_id)
        _LOGGER.debug('get_color_temp(name=%r status=%r)' % (self._device_name, expand_status(status)))
        if status.get('capacity') == 6: # White light mode
            value = status.get('temperature')
            norm_value = (100 - value) / 100.0
            return self.min_mireds + (norm_value * (self.max_mireds - self.min_mireds))
        return None

    @property
    def supported_features(self):
        if not self.available:
            return 0

        flags = 0
        if self._device.supports_luminance():
           flags |= SUPPORT_BRIGHTNESS
        if self._device.is_rgb():
           flags |= SUPPORT_COLOR
        if self._device.is_light_temperature():
           flags |= SUPPORT_COLOR_TEMP
        return flags

    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._id)},
            'name': self._device_name,
            'manufacturer': 'Meross',
            'model': self._device.type + " " + self._device.hwversion,
            'sw_version': self._device.fwversion
        }


async def async_setup_entry(hass, config_entry, async_add_entities):
    bulb_devices = []
    manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
    bulbs = manager.get_devices_by_kind(GenericBulb)

    for bulb in bulbs:
        w = LightEntityWrapper(device=bulb, channel=0)
        bulb_devices.append(w)

    async_add_entities(bulb_devices)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass

