import logging

from homeassistant.const import ATTR_VOLTAGE
from homeassistant.helpers.entity import Entity
from meross_iot.cloud.devices.power_plugs import GenericPlug
from meross_iot.meross_event import DeviceOnlineStatusEvent

from .common import (DOMAIN, HA_SENSOR, MANAGER, calculate_sensor_id, ConnectionWatchDog, cloud_io)

_LOGGER = logging.getLogger(__name__)


class PowerSensorWrapper(Entity):
    """Wrapper class to adapt the Meross power sensors into the Homeassistant platform"""

    def __init__(self, device: GenericPlug):
        self._device = device

        # Device properties
        self._device_id = device.uuid
        self._id = calculate_sensor_id(device.uuid)
        self._device_name = device.name
        self._sensor_info = None

        self._is_online = self._device.online

    def device_event_handler(self, evt):
        # Handle here events that are common to all the wrappers
        if isinstance(evt, DeviceOnlineStatusEvent):
            _LOGGER.info("Device %s reported online status: %s" % (self._device.name, evt.status))
            if evt.status not in ["online", "offline"]:
                raise ValueError("Invalid online status")
            self._is_online = evt.status == "online"

        self.schedule_update_ha_state(False)

    @cloud_io()
    def update(self):
        # TODO: loading the entire device data at every iteration might be stressful. Need to re-engineer this
        self._device.get_status(force_status_refresh=False)
        self._is_online = self._device.online

        # Update electricity stats only if the device is online and currently turned on
        if self._is_online and self._device.get_status():
            self._sensor_info = self._device.get_electricity()
        else:
            self._sensor_info = {
                'voltage': 0,
                'current': 0,
                'power': 0
            }

    @property
    def available(self) -> bool:
        return self._is_online

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

    async def async_added_to_hass(self) -> None:
        self._device.register_event_callback(self.device_event_handler)

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_event_callback(self.device_event_handler)


async def async_setup_entry(hass, config_entry, async_add_entities):
    def sync_logic():
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
                hass.data[DOMAIN][HA_SENSOR][w.unique_id] = w
        # TODO: Then parse thermostat sensors?
        return sensor_entities

    # Register a connection watchdog to notify devices when connection to the cloud MQTT goes down.
    manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
    watchdog = ConnectionWatchDog(hass=hass, platform=HA_SENSOR)
    manager.register_event_handler(watchdog.connection_handler)

    sensor_entities = await hass.async_add_executor_job(sync_logic)
    async_add_entities(sensor_entities)


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
