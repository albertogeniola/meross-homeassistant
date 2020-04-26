import logging

from homeassistant.const import ATTR_VOLTAGE
from homeassistant.helpers.entity import Entity
from meross_iot.cloud.client_status import ClientStatus
from meross_iot.cloud.devices.power_plugs import GenericPlug
from meross_iot.cloud.exceptions.CommandTimeoutException import CommandTimeoutException
from meross_iot.meross_event import DeviceOnlineStatusEvent

from .common import (DOMAIN, HA_SENSOR, MANAGER, calculate_sensor_id, ConnectionWatchDog, MerossEntityWrapper,
                     log_exception)

_LOGGER = logging.getLogger(__name__)


class PowerSensorWrapper(Entity, MerossEntityWrapper):
    """Wrapper class to adapt the Meross power sensors into the Homeassistant platform"""

    def __init__(self, device: GenericPlug):
        self._device = device

        # Device properties
        self._id = calculate_sensor_id(device.uuid)
        self._sensor_info = None
        self._available = True  # Assume the mqtt client is connected

    def update(self):
        # Given that the device is online, we force a full state refresh.
        # This is necessary as this device is handled with HA should_poll=True
        # flag, so the UPDATE should every time update its status.
        try:
            self._sensor_info = {
                'voltage': 0,
                'current': 0,
                'power': 0
            }
            self._device.get_status(force_status_refresh=self._device.online)

            # Update electricity stats only if the device is online and currently turned on
            if self.available and self._device.get_status():
                self._sensor_info = self._device.get_electricity()

        except CommandTimeoutException as e:
            log_exception(logger=_LOGGER, device=self._device)
            raise

    def device_event_handler(self, evt):
        # Update the device state when an event occurs
        self.schedule_update_ha_state(False)

    def notify_client_state(self, status: ClientStatus):
        # When a connection change occurs, update the internal state
        # If we are connecting back, schedule a full refresh of the device
        # In any other case, mark the device unavailable
        # and only update the UI
        client_online = status == ClientStatus.SUBSCRIBED
        self._available = client_online
        self.schedule_update_ha_state(client_online)

    @property
    def available(self) -> bool:
        return self._available and self._device.online

    @property
    def name(self) -> str:
        return self._device.name

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
            'identifiers': {(DOMAIN, self._device.uuid)},
            'name': self._device.name,
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
