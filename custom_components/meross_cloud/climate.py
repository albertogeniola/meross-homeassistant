import logging
from typing import List, Optional

from homeassistant.components.climate import (SUPPORT_PRESET_MODE,
                                              SUPPORT_TARGET_TEMPERATURE,
                                              ClimateDevice)
from homeassistant.components.climate.const import (CURRENT_HVAC_HEAT,
                                                    CURRENT_HVAC_IDLE,
                                                    CURRENT_HVAC_OFF,
                                                    HVAC_MODE_AUTO,
                                                    HVAC_MODE_HEAT,
                                                    HVAC_MODE_OFF, PRESET_NONE)
from homeassistant.const import TEMP_CELSIUS
from meross_iot.cloud.client_status import ClientStatus
from meross_iot.cloud.devices.subdevices.thermostats import (ThermostatMode,
                                                             ThermostatV3Mode,
                                                             ValveSubDevice)
from meross_iot.manager import MerossManager
from meross_iot.meross_event import (DeviceOnlineStatusEvent,
                                     DeviceSwitchStatusEvent,
                                     ThermostatModeChange,
                                     ThermostatTemperatureChange)

from .common import (DOMAIN, HA_CLIMATE, MANAGER, ConnectionWatchDog, cloud_io, MerossEntityWrapper)

_LOGGER = logging.getLogger(__name__)


THERMOSTAT_TIMEOUT = 120.0


def none_callback(err, resp):
    pass


class ValveEntityWrapper(ClimateDevice, MerossEntityWrapper):
    """Wrapper class to adapt the Meross thermostat into the Homeassistant platform"""

    def __init__(self, device: ValveSubDevice):
        self._device = device

        self._id = self._device.uuid + ":" + self._device.subdevice_id

        # For now, we assume that every Meross Thermostat supports the following modes.
        # This might be improved in the future by looking at the device abilities via get_abilities()
        self._flags = 0
        self._flags |= SUPPORT_TARGET_TEMPERATURE
        self._flags |= SUPPORT_PRESET_MODE

        self._available = True  # Assume the mqtt client is connected
        self._first_update_done = False
        self._target_temperature = None

    @cloud_io()
    def update(self):
        if self._device.online:
            self._device.get_status(force_status_refresh=True)
            self._target_temperature = float(self._device.get_status().get('temperature').get('currentSet'))/10
            self._first_update_done = True

    def device_event_handler(self, evt):
        if isinstance(evt, ThermostatTemperatureChange):
            self._target_temperature = float(self._device.get_status().get('temperature').get('currentSet')) / 10

        self.schedule_update_ha_state(False)

    def notify_client_state(self, status: ClientStatus):
        # When a connection change occurs, update the internal state
        if status == ClientStatus.SUBSCRIBED:
            # If we are connecting back, schedule a full refresh of the device
            self.schedule_update_ha_state(True)
        else:
            # In any other case, mark the device unavailable
            # and only update the UI
            self._available = False
            self.schedule_update_ha_state(False)

    @property
    @cloud_io(default_return_value=None)
    def current_temperature(self) -> float:
        if not self._first_update_done:
            # Schedule update and return
            self.schedule_update_ha_state(True)
            return None

        return float(self._device.get_status().get('temperature').get('room'))/10

    @property
    @cloud_io(default_return_value=None)
    def hvac_action(self) -> str:
        if not self._first_update_done:
            # Schedule update and return
            self.schedule_update_ha_state(True)
            return None

        status = self._device.get_status()
        is_on = status.get('togglex').get('onoff') == 1
        heating = status.get('temperature').get('heating') == 1
        if not is_on:
            return CURRENT_HVAC_OFF
        elif heating:
            return CURRENT_HVAC_HEAT
        else:
            return CURRENT_HVAC_IDLE

    @property
    @cloud_io(default_return_value=HVAC_MODE_OFF)
    def hvac_mode(self) -> str:
        if not self._first_update_done:
            # Schedule update and return
            self.schedule_update_ha_state(True)
            return None

        status = self._device.get_status()
        is_on = status.get('togglex').get('onoff') == 1
        mode = status.get('mode').get('state')

        if not is_on:
            return HVAC_MODE_OFF
        elif mode == 3:
            return HVAC_MODE_AUTO
        elif mode == 0:
            return HVAC_MODE_HEAT
        else:
            return HVAC_MODE_HEAT

    @property
    def available(self) -> bool:
        # A device is available if the client library is connected to the MQTT broker and if the
        # device we are contacting is online
        return self._available and self._device.online

    @property
    def name(self) -> str:
        return self._device.name

    @property
    def unique_id(self) -> str:
        return self._id

    @property
    def supported_features(self):
        return self._flags

    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._id)},
            'name': self._device.name,
            'manufacturer': 'Meross',
            'model': self._device.type,
            'via_device': (DOMAIN, self._device.uuid)
        }

    @property
    def temperature_unit(self) -> str:
        return TEMP_CELSIUS

    @property
    def hvac_modes(self) -> List[str]:
        return [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_HEAT]

    @cloud_io()
    def set_temperature(self, **kwargs) -> None:
        target = kwargs.get('temperature')
        self._device.set_target_temperature(target, callback=none_callback, timeout=THERMOSTAT_TIMEOUT)
        # Assume update will work, thus update local state immediately
        self._target_temperature = target

    @cloud_io()
    def set_hvac_mode(self, hvac_mode: str) -> None:
        # NOTE: this method will also update the local state as the thermostat will take too much time to get the
        # command ACK.turn_on
        if hvac_mode == HVAC_MODE_OFF:
            self._device.turn_off(callback=none_callback, timeout=THERMOSTAT_TIMEOUT)
            self._is_on = False  # Update local state
            return

        if self._device.type == "mts100v3":
            if hvac_mode == HVAC_MODE_HEAT:
                def action(error, response):
                    if error is None:
                        self._device.set_mode(ThermostatV3Mode.CUSTOM, callback=none_callback, timeout=THERMOSTAT_TIMEOUT)
                self._device.turn_on(callback=action, timeout=THERMOSTAT_TIMEOUT)

                # Update local state
                self._device_mode = ThermostatV3Mode.CUSTOM
                self._is_on = True

            elif hvac_mode == HVAC_MODE_AUTO:
                def action(error, response):
                    if error is None:
                        self._device.set_mode(ThermostatV3Mode.AUTO, callback=none_callback, timeout=THERMOSTAT_TIMEOUT)
                self._device.turn_on(callback=action, timeout=THERMOSTAT_TIMEOUT)

                # Update local state
                self._is_on = True
                self._device_mode = ThermostatV3Mode.AUTO
            else:
                _LOGGER.warning("Unsupported mode for this device")

        elif self._device.type == "mts100":
            if hvac_mode == HVAC_MODE_HEAT:
                def action(error, response):
                    if error is None:
                        self._device.set_mode(ThermostatMode.CUSTOM, callback=none_callback, timeout=THERMOSTAT_TIMEOUT)
                self._device.turn_on(callback=action, timeout=THERMOSTAT_TIMEOUT)

                # Update local state
                self._is_on = True
                self._device_mode = ThermostatMode.CUSTOM
            elif hvac_mode == HVAC_MODE_AUTO:
                def action(error, response):
                    if error is None:
                        self._device.set_mode(ThermostatMode.SCHEDULE, callback=none_callback, timeout=THERMOSTAT_TIMEOUT)
                self._device.turn_on(callback=action, timeout=THERMOSTAT_TIMEOUT)

                # Update local state
                self._is_on = True
                self._device_mode = ThermostatMode.SCHEDULE
            else:
                _LOGGER.warning("Unsupported mode for this device")
        else:
            _LOGGER.warning("Unsupported mode for this device")

    @cloud_io()
    def set_preset_mode(self, preset_mode: str) -> None:
        if self._device.type == "mts100v3":
            self._device_mode = ThermostatV3Mode[preset_mode]  # Update local state
            self._device.set_mode(ThermostatV3Mode[preset_mode], callback=none_callback, timeout=THERMOSTAT_TIMEOUT)
        elif self._device.type == "mts100":
            self._device_mode = ThermostatMode[preset_mode]  # Update local state
            self._device.set_mode(ThermostatMode[preset_mode], callback=none_callback, timeout=THERMOSTAT_TIMEOUT)
        else:
            _LOGGER.warning("Unsupported preset for this device")

    @property
    def target_temperature(self) -> Optional[float]:
        if not self._first_update_done:
            # Schedule update and return
            self.schedule_update_ha_state(True)
            return None
        #if self._target_temperature is not None:
        return self._target_temperature
        #else:
        #    return float(self._device.get_status().get('temperature').get('currentSet'))/10

    @property
    def target_temperature_step(self) -> Optional[float]:
        return 0.5

    @property
    def preset_mode(self) -> Optional[str]:
        if not self._first_update_done:
            # Schedule update and return
            self.schedule_update_ha_state(True)
            return None

        return self._device.mode.name

    @property
    def preset_modes(self) -> Optional[List[str]]:
        if self._device.type == 'mts100v3':
            return [e.name for e in ThermostatV3Mode]
        elif self._device.type == 'mts100':
            return [e.name for e in ThermostatMode]
        else:
            _LOGGER.warning("Unknown valve mode type.")
            return [PRESET_NONE]

    @property
    def is_aux_heat(self) -> Optional[bool]:
        return False

    @property
    def target_temperature_high(self) -> Optional[float]:
        # Not supported
        return None

    @property
    def target_temperature_low(self) -> Optional[float]:
        # Not supported
        return None

    @property
    def fan_mode(self) -> Optional[str]:
        # Not supported
        return None

    @property
    def fan_modes(self) -> Optional[List[str]]:
        # Not supported
        return None

    @property
    def swing_mode(self) -> Optional[str]:
        # Not supported
        return None

    @property
    def swing_modes(self) -> Optional[List[str]]:
        # Not supported
        return None

    def set_humidity(self, humidity: int) -> None:
        pass

    def set_fan_mode(self, fan_mode: str) -> None:
        pass

    def set_swing_mode(self, swing_mode: str) -> None:
        pass

    def turn_aux_heat_on(self) -> None:
        pass

    def turn_aux_heat_off(self) -> None:
        pass

    async def async_added_to_hass(self) -> None:
        self._device.register_event_callback(self.device_event_handler)

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_event_callback(self.device_event_handler)


async def async_setup_entry(hass, config_entry, async_add_entities):
    def sync_logic():

        climante_devices = []
        manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager

        # Add smart thermostat valves
        valves = manager.get_devices_by_kind(ValveSubDevice)
        for valve in valves:  # type: ValveSubDevice
            w = ValveEntityWrapper(device=valve)
            climante_devices.append(w)
            hass.data[DOMAIN][HA_CLIMATE][w.unique_id] = w

        return climante_devices

    # Register a connection watchdog to notify devices when connection to the cloud MQTT goes down.
    manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
    watchdog = ConnectionWatchDog(hass=hass, platform=HA_CLIMATE)
    manager.register_event_handler(watchdog.connection_handler)

    thermostat_devices = await hass.async_add_executor_job(sync_logic)
    async_add_entities(thermostat_devices)


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
