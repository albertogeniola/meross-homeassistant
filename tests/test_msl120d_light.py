"""Focused wrapper tests using simulated devices, not the HA runtime."""
import ast, asyncio, types, unittest
from enum import StrEnum, IntEnum
from pathlib import Path

class ColorMode(StrEnum):
    RGB = 'rgb'
    COLOR_TEMP = 'color_temp'
    BRIGHTNESS = 'brightness'
    ONOFF = 'onoff'

class LightMode(IntEnum):
    MODE_RGB = 1
    MODE_TEMPERATURE = 2
    MODE_LUMINANCE = 4

class Namespace(StrEnum):
    CONTROL_LIGHT = 'light'
    SYSTEM_ALL = 'all'

class Base:

    def __init__(self, device, channel, **kw):
        self._device = device
        self._channel_id = channel

    @property
    def min_color_temp_kelvin(self):
        return self._attr_min_color_temp_kelvin

    @property
    def max_color_temp_kelvin(self):
        return self._attr_max_color_temp_kelvin

    async def _async_push_notification_received(self, *args):
        pass

class Device:

    def __init__(self):
        self.on = False
        self.temp = 50
        self.rgb = None
        self.lum = 100
        self.calls = []

    def get_supports_rgb(self, **kw):
        return True

    def get_supports_temperature(self, **kw):
        return True

    def get_supports_luminance(self, **kw):
        return True

    def get_light_is_on(self, **kw):
        return self.on

    def get_color_temperature(self, **kw):
        return self.temp

    def get_rgb_color(self, **kw):
        return self.rgb

    def get_luminance(self, **kw):
        return self.lum

    async def async_set_light_color(self, **kw):
        self.calls.append(kw)
        self.temp = kw.get('temperature', self.temp)
        self.rgb = kw.get('rgb', self.rgb)
        self.lum = kw.get('luminance', self.lum)

    async def async_turn_on(self, **kw):
        self.calls.append('on')
        self.on = True

    async def async_turn_off(self, **kw):
        self.on = False
node = next((n for n in ast.parse((Path(__file__).resolve().parents[1] / 'custom_components/meross_cloud/light.py').read_text()).body if isinstance(n, ast.ClassDef) and n.name == 'LightEntityWrapper'))
env = dict(MerossDevice=Base, LightEntity=object, MerossLightDevice=Device, HA_LIGHT='light', ColorMode=ColorMode, LightMode=LightMode, Namespace=Namespace, ATTR_RGB_COLOR='rgb_color', ATTR_HS_COLOR='hs_color', ATTR_COLOR_TEMP_KELVIN='color_temp_kelvin', ATTR_BRIGHTNESS='brightness')
exec(compile(ast.Module(body=[node], type_ignores=[]), 'patched-light', 'exec'), env)
Wrapper = env['LightEntityWrapper']

class Tests(unittest.IsolatedAsyncioTestCase):

    async def test_kelvin_endpoints_roundtrip_and_combined_brightness(self):
        for k in (2000, 2200, 2700, 4000, 6535):
            d = Device()
            w = Wrapper(0, d, None)
            await w.async_turn_on(color_temp_kelvin=k, brightness=26)
            self.assertEqual(len(d.calls), 2)
            self.assertEqual(d.calls[-1], 'on')
            self.assertTrue(1 <= d.temp <= 100)
            self.assertEqual(d.lum, 10)
            self.assertLessEqual(abs(w.color_temp_kelvin - k), 30)
            self.assertEqual(w.color_mode, ColorMode.COLOR_TEMP)

    async def test_rgb_and_brightness_preserve_mode(self):
        d = Device()
        w = Wrapper(0, d, None)
        await w.async_turn_on(rgb_color=[255, 64, 0])
        self.assertEqual(w.rgb_color, (255, 64, 0))
        await w.async_turn_on(brightness=128)
        self.assertEqual(w.color_mode, ColorMode.RGB)
        await w._async_push_notification_received(Namespace.SYSTEM_ALL, {'all': {'digest': {'light': {'channel': 0, 'capacity': 6}}}}, 'x')
        self.assertEqual(w.color_mode, ColorMode.COLOR_TEMP)
        await w._async_push_notification_received(Namespace.CONTROL_LIGHT, {'light': {'channel': 0, 'capacity': 4}}, 'x')
        self.assertEqual(w.color_mode, ColorMode.COLOR_TEMP)
        await w._async_push_notification_received(Namespace.CONTROL_LIGHT, {'light': {'channel': 1, 'capacity': 1}}, 'x')
        self.assertEqual(w.color_mode, ColorMode.COLOR_TEMP)
        await w._async_push_notification_received(Namespace.CONTROL_LIGHT, {'light': {'channel': 0, 'capacity': 5}}, 'x')
        self.assertEqual(w.color_mode, ColorMode.RGB)

    async def test_limits_and_modes(self):
        d = Device()
        w = Wrapper(0, d, None)
        for k, v in [(1000, 1), (9999, 100)]:
            await w.async_turn_on(color_temp_kelvin=k)
            self.assertEqual(d.temp, v)
        self.assertEqual(w.supported_color_modes, {ColorMode.RGB, ColorMode.COLOR_TEMP})
if __name__ == '__main__':
    unittest.main()
