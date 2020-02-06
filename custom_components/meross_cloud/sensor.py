import logging

from homeassistant.const import ATTR_VOLTAGE
from homeassistant.helpers.entity import Entity
from meross_iot.cloud.devices.power_plugs import GenericPlug

from .common import (DOMAIN, MANAGER, SENSORS,
                     calculate_sensor_id)

_LOGGER = logging.getLogger(__name__)


class PowerSensorWrapper(Entity):
    """Wrapper class to adapt the Meross power sensors into the Homeassistant platform"""

    def __init__(self, device: GenericPlug):
        self._device = device
        self._device_id = device.uuid
        self._id = calculate_sensor_id(self._device.uuid)
        self._device_name = self._device.name
        self._sensor_info = None

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
            self._sensor_info = self._device.get_electricity()

    @property
    def device_state_attributes(self):
        # Return device's state
        sensor_data = self._sensor_info
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
        sensor_data = self._sensor_info
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

    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._device_id)},
            'name': self._device_name,
            'manufacturer': 'Meross',
            'model': self._device.type + " " + self._device.hwversion,
            'sw_version': self._device.fwversion
        }


async def async_setup_entry(hass, config_entry, async_add_entities):
    sensor_entities = []
    manager = hass.data[DOMAIN][MANAGER]
    plugs = manager.get_devices_by_kind(GenericPlug)

    # First, parse power sensors that are embedded into power plugs
    for plug in plugs:  # type: GenericPlug
        if not plug.online:
            _LOGGER.warning("The plug %s is offline; it's impossible to determine if it supports any ability"
                            % plug.name)
        elif plug.type.startswith("mss310") or plug.supports_consumption_reading():
            w = PowerSensorWrapper(device=plug)
            sensor_entities.append(w)

    # TODO: Then parse thermostat sensors?

    async_add_entities(sensor_entities)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass