import colorsys

from homeassistant.components.light import Light, SUPPORT_BRIGHTNESS, SUPPORT_COLOR
from meross_iot.cloud.devices.light_bulbs import GenericBulb, to_rgb

from .common import (calculate_switch_id, DOMAIN, ENROLLED_DEVICES, MANAGER)


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
        self._device.turn_off(channel=self._channel_id)

    def turn_on(self, **kwargs) -> None:
        self._device.turn_on(channel=self._channel_id)
        rgb = self._device.get_light_color(self._channel_id).get('rgb')
        brightness = self._device.get_light_color(self._channel_id).get('luminance')

        if 'hs_color' in kwargs:
            h, s = kwargs['hs_color']
            r, g, b = colorsys.hsv_to_rgb(h/360, s/100, 255)
            rgb = to_rgb((int(r), int(g), int(b)))
        elif 'brightness' in kwargs:
            brightness = kwargs['brightness'] / 255 * 100

        self._device.set_light_color(self._channel_id, rgb=rgb, luminance=brightness)

    @property
    def brightness(self):
        # Meross bulbs support luminance between 0 and 100;
        # while the HA wants values from 0 to 255. Therefore, we need to scale the values.
        status = self._device.get_status(self._channel_id)
        return status.get('luminance') / 100 * 255

    @property
    def hs_color(self):
        color = self._device.get_channel_status(self._channel_id).get('rgb')
        blue = color & 255
        green = (color >> 8) & 255
        red = (color >> 16) & 255
        h, s, v = colorsys.rgb_to_hsv(red, green, blue)
        return [h*360, s*100]

    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR

        # TODO: Handle temperature/luminance support.


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    bulb_devices = []
    device = hass.data[DOMAIN][MANAGER].get_device_by_uuid(discovery_info)
    for k, c in enumerate(device.get_channels()):
        w = LightEntityWrapper(device, k)
        bulb_devices.append(w)

    async_add_entities(bulb_devices)
    hass.data[DOMAIN][ENROLLED_DEVICES].add(device.uuid)
