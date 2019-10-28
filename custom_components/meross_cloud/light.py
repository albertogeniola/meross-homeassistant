import homeassistant.util.color as color_util
import logging

from homeassistant.components.light import Light, SUPPORT_BRIGHTNESS, SUPPORT_COLOR, SUPPORT_COLOR_TEMP, ATTR_HS_COLOR, ATTR_COLOR_TEMP, ATTR_BRIGHTNESS
from meross_iot.cloud.devices.light_bulbs import GenericBulb

from .common import (calculate_switch_id, DOMAIN, ENROLLED_DEVICES, MANAGER)

_LOGGER = logging.getLogger(__name__)

class LightEntityWrapper(Light):
    """Wrapper class to adapt the Meross switches into the Homeassistant platform"""
    _device = None
    _channel_id = None
    _id = None
    _device_name = None

    def __init__(self, device: GenericBulb, channel: int):
        self._device = device
        self._channel_id = channel
        self._id = calculate_switch_id(self._device.uuid, channel)

        if len(self._device.get_channels()) > 1:
            self._device_name = "%s (channel: %d)" % (self._device.name, channel)
        else:
            self._device_name = self._device.name

        self._device.register_event_callback(self.handler)

    def handler(self, evt):
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
        # Since Meross plugs may have more than 1 switch, we need to provide a composed ID
        # made of uuid and channel
        return self._id

    @property
    def is_on(self) -> bool:
        # Note that the following method is not fetching info from the device over the network.
        # Instead, it is reading the device status from the state-dictionary that is handled by the library.
        return self._device.get_channel_status(self._channel_id).get('onoff')

    def turn_off(self, **kwargs) -> None:
        _LOGGER.debug('turn_off(chan=%r)' % self._channel_id)
        self._device.turn_off(channel=self._channel_id)

    def turn_on(self, **kwargs) -> None:
        _LOGGER.debug('turn_on(chan=%r, %r)' % (self._channel_id, kwargs))
        self._device.turn_on(channel=self._channel_id)

        # Color is taken from either of these 2 values, but not both.
        rgb = None
        temperature = -1
        if ATTR_HS_COLOR in kwargs:
            h, s = kwargs[ATTR_HS_COLOR]
            rgb = color_util.color_hsv_to_RGB(h, s, 100)
            _LOGGER.debug("    color conversion: rgb=%r -- h=%r s=%r" % (rgb, h, s))
        elif ATTR_COLOR_TEMP in kwargs:
            mired = kwargs[ATTR_COLOR_TEMP]
            norm_value = (mired - self.min_mireds) / (self.max_mireds - self.min_mireds)
            temperature = 100 - (norm_value * 100)
            _LOGGER.debug("    temperature conversion: mired=%r meross=%r" % (mired, temperature))

        # Brightness must always be set, so take previous luminance if not explicitly set now.
        brightness = self._device.get_light_color(self._channel_id).get('luminance')
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS] * 100 / 255
            _LOGGER.debug("brightness change: %r" % brightness)

        _LOGGER.debug('    set_light_color(chan=%r, rgb=%r, luminance=%r, temperature=%r)' % (self._channel_id, rgb, brightness, temperature))
        self._device.set_light_color(self._channel_id, rgb=rgb, luminance=brightness, temperature=temperature)

    @property
    def brightness(self):
        # Meross bulbs support luminance between 0 and 100;
        # while the HA wants values from 0 to 255. Therefore, we need to scale the values.
        status = self._device.get_status(self._channel_id)
        _LOGGER.debug('get_brightness status=%r' % status)
        return status.get('luminance') / 100 * 255

    @property
    def hs_color(self):
        status = self._device.get_channel_status(self._channel_id)
        _LOGGER.debug('get_hs_color status=%r' % status)
        if status.get('capacity') == 5: # rgb mode
            color = status.get('rgb')
            blue = color & 255
            green = (color >> 8) & 255
            red = (color >> 16) & 255
            return color_util.color_RGB_to_hs(red, green, blue)
        return None

    @property
    def color_temp(self):
        status = self._device.get_channel_status(self._channel_id)
        _LOGGER.debug('get_color_temp status=%r' % status)
        if status.get('capacity') == 6: # White light mode
            value = status.get('temperature')
            norm_value = (100 - value) / 100.0
            return self.min_mireds + (norm_value * (self.max_mireds - self.min_mireds))
        return None

    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_COLOR_TEMP


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    bulb_devices = []
    device = hass.data[DOMAIN][MANAGER].get_device_by_uuid(discovery_info)
    for k, c in enumerate(device.get_channels()):
        w = LightEntityWrapper(device, k)
        bulb_devices.append(w)

    async_add_entities(bulb_devices)
    hass.data[DOMAIN][ENROLLED_DEVICES].add(device.uuid)
