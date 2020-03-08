import logging
from typing import Optional, List, Union, Any

from homeassistant.components.climate import ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_PRESET_MODE
from homeassistant.components.climate.const import HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF, PRESET_NONE, \
    CURRENT_HVAC_HEAT, CURRENT_HVAC_OFF, CURRENT_HVAC_IDLE
from homeassistant.components.fan import FanEntity
from homeassistant.const import TEMP_CELSIUS, STATE_UNKNOWN, STATE_OFF
from homeassistant.helpers.entity import Entity
from meross_iot.cloud.devices.subdevices.thermostats import ValveSubDevice, ThermostatV3Mode, ThermostatMode
from meross_iot.cloud.devices.humidifier import GenericHumidifier, SprayMode
from meross_iot.manager import MerossManager
from meross_iot.meross_event import ThermostatTemperatureChange, ThermostatModeChange, DeviceSwitchStatusEvent, \
    DeviceOnlineStatusEvent

from .common import DOMAIN, MANAGER, AbstractMerossEntityWrapper, cloud_io, HA_CLIMATE

_LOGGER = logging.getLogger(__name__)


THERMOSTAT_TIMEOUT = 120.0


def none_callback(err, resp):
    pass


class ValveEntityWrapper(ClimateDevice, AbstractMerossEntityWrapper):
    """Wrapper class to adapt the Meross thermostat into the Homeassistant platform"""

    def __init__(self, device: ValveSubDevice):
        super().__init__(device)

        self._id = self._device.uuid + ":" + self._device.subdevice_id
        self._device_name = self._device.name

        # For now, we assume that every Meross Thermostat supports the following modes.
        # This might be improved in the future by looking at the device abilities via get_abilities()
        self._flags = 0
        self._flags |= SUPPORT_TARGET_TEMPERATURE
        self._flags |= SUPPORT_PRESET_MODE

        # Device state
        self._current_temperature = None
        self._is_on = None
        self._device_mode = None
        self._target_temperature = None
        self._heating = None

        self._is_online = self._device.online
        if self._is_online:
            self.update()

    def device_event_handler(self, evt):
        # Any event received from the device causes the reset of the error state
        self.reset_error_state()

        # Handle here events that are common to all the wrappers
        if isinstance(evt, DeviceOnlineStatusEvent):
            _LOGGER.info("Device %s reported online status: %s" % (self._device.name, evt.status))
            if evt.status not in ["online", "offline"]:
                raise ValueError("Invalid online status")
            self._is_online = evt.status == "online"
        elif isinstance(evt, ThermostatTemperatureChange):
            self._current_temperature = float(evt.temperature.get('room'))/10
            self._target_temperature = float(evt.temperature.get('currentSet')) / 10
            self._heating = evt.temperature.get('heating') == 1
        elif isinstance(evt, ThermostatModeChange):
            self._device_mode = evt.mode
        elif isinstance(evt, DeviceSwitchStatusEvent):
            self._is_on = evt.switch_state == 1
        else:
            _LOGGER.warning("Unhandled/ignored event: %s" % str(evt))

        self.schedule_update_ha_state(False)

    def force_state_update(self, ui_only=False):
        if not self.enabled:
            return

        force_refresh = not ui_only
        self.schedule_update_ha_state(force_refresh=force_refresh)

    @cloud_io
    def update(self):
        state = self._device.get_status(True)
        self._is_online = self._device.online

        if self._is_online:
            self._is_on = state.get('togglex').get('onoff') == 1
            mode = state.get('mode').get('state')

            if self._device.type == "mts100v3":
                self._device_mode = ThermostatV3Mode(mode)
            elif self._device.type == "mts100":
                self._device_mode = ThermostatMode(mode)
            else:
                _LOGGER.warning("Unknown device type %s" % self._device.type)

            temp = state.get('temperature')
            self._current_temperature = float(temp.get('room')) / 10
            self._target_temperature = float(temp.get('currentSet')) / 10
            self._heating = temp.get('heating') == 1

    @property
    def current_temperature(self) -> float:
        return self._current_temperature

    @property
    def hvac_action(self) -> str:
        if not self._is_on:
            return CURRENT_HVAC_OFF
        elif self._heating:
            return CURRENT_HVAC_HEAT
        else:
            return CURRENT_HVAC_IDLE

    @property
    def hvac_mode(self) -> str:
        if not self._is_on:
            return HVAC_MODE_OFF
        elif self._device_mode == ThermostatV3Mode.AUTO:
            return HVAC_MODE_AUTO
        elif self._device_mode == ThermostatV3Mode.CUSTOM:
            return HVAC_MODE_HEAT
        elif self._device_mode == ThermostatMode.SCHEDULE:
            return HVAC_MODE_AUTO
        elif self._device_mode == ThermostatMode.CUSTOM:
            return HVAC_MODE_HEAT
        else:
            return HVAC_MODE_HEAT

    @property
    def available(self) -> bool:
        # A device is available if it's online
        return self._is_online

    @property
    def name(self) -> str:
        return self._device_name

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
            'name': self._device_name,
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

    @cloud_io
    def set_temperature(self, **kwargs) -> None:
        target = kwargs.get('temperature')
        self._device.set_target_temperature(target, callback=none_callback, timeout=THERMOSTAT_TIMEOUT)
        # Assume update will work, thus update local state immediately
        self._target_temperature = target

    @cloud_io
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

    @cloud_io
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
        return self._target_temperature

    @property
    def target_temperature_step(self) -> Optional[float]:
        return 0.5

    @property
    def preset_mode(self) -> Optional[str]:
        return self._device.mode.name

    @property
    def preset_modes(self) -> Optional[List[str]]:
        if isinstance(self._device_mode, ThermostatV3Mode):
            return [e.name for e in ThermostatV3Mode]
        elif isinstance(self._device_mode, ThermostatMode):
            return [e.name for e in ThermostatMode]
        elif self._device_mode is None:
            return []
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

    thermostat_devices = await hass.async_add_executor_job(sync_logic)
    async_add_entities(thermostat_devices)


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass

