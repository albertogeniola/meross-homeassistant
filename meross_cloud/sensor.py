from homeassistant.const import ATTR_VOLTAGE
from homeassistant.helpers.entity import Entity
from meross_iot.cloud.device import AbstractMerossDevice

from .common import (calculate_sensor_id, DOMAIN, SENSORS, ENROLLED_DEVICES, MANAGER)


class PowerSensorWrapper(Entity):
    """Wrapper class to adapt the Meross power sensors into the Homeassistant platform"""
    _device = None
    _id = None
    _device_name = None

    def __init__(self, device: AbstractMerossDevice):
        self._device = device
        self._id = calculate_sensor_id(self._device.uuid)
        self._device_name = self._device.name

    @property
    def available(self) -> bool:
        # A device is available if it's online
        return self._device.online

    @property
    def name(self) -> str:
        return self._device_name

    @property
    def should_poll(self) -> bool:
        # Power sensors must be polled manually. We leave this task to the HomeAssistant engine
        return True

    @property
    def unique_id(self) -> str:
        return self._id

    async def async_update(self):
        if self.available:
            sensor_info = self._device.get_electricity()
        else:
            sensor_info = None

        self.hass.data[DOMAIN][SENSORS][self.unique_id] = sensor_info

    @property
    def device_state_attributes(self):
        # Return device's state
        sensor_data = self.hass.data[DOMAIN][SENSORS].get(self.unique_id)
        if sensor_data is None:
            sensor_data = {}

        # Format voltage into Volts
        voltage = sensor_data.get('voltage')
        if voltage is not None:
            voltage = float(voltage)/10

        # Format current into Ampere
        current = sensor_data.get('current')
        if current is not None:
            current = float(current) / 1000

        # Format power into Watts
        power = sensor_data.get('power')
        if power is not None:
            power = float(power) / 1000

        attr = {
            ATTR_VOLTAGE: voltage,
            'current': current,
            'power': power
        }

        return attr

    @property
    def state_attributes(self):
        # Return the state attributes.
        attr = {
            ATTR_VOLTAGE: None,
            'current': None,
            'power': None
        }

        return attr

    @property
    def state(self) -> str:
        # Return the state attributes.
        sensor_data = self.hass.data[DOMAIN][SENSORS].get(self.unique_id)
        if sensor_data is None:
            sensor_data = {}

        data = sensor_data.get('power')
        if data is not None:
            data = str(float(data)/1000)

        return data

    @property
    def unit_of_measurement(self):
        return 'W'

    @property
    def device_class(self) -> str:
        return 'power'


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    device = hass.data[DOMAIN][MANAGER].get_device_by_uuid(discovery_info)
    dev = PowerSensorWrapper(device)
    async_add_entities((dev,))
    hass.data[DOMAIN][ENROLLED_DEVICES].add(device.uuid)
