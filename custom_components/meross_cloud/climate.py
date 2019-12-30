import logging
from typing import Optional, List

from homeassistant.components.climate import ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_PRESET_MODE
from homeassistant.components.climate.const import HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF, PRESET_NONE, \
    CURRENT_HVAC_HEAT, CURRENT_HVAC_OFF, CURRENT_HVAC_IDLE
from homeassistant.const import TEMP_CELSIUS
from meross_iot.cloud.devices.subdevices.thermostats import ValveSubDevice, ThermostatV3Mode, ThermostatMode
from meross_iot.manager import MerossManager

from .common import DOMAIN, MANAGER

_LOGGER = logging.getLogger(__name__)


class ValveEntityWrapper(ClimateDevice):
    """Wrapper class to adapt the Meross thermostat into the Homeassistant platform"""

    def __init__(self, device: ValveSubDevice):
        self._device = device
        self._id = self._device.uuid + ":" + self._device.subdevice_id
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
    def supported_features(self):
        if not self.available:
            return 0

        flags = 0
        flags |= SUPPORT_TARGET_TEMPERATURE
        flags |= SUPPORT_PRESET_MODE

        return flags

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
    def current_temperature(self) -> float:
        return self._device.room_temperature

    @property
    def hvac_action(self) -> str:
        if self._device.onoff == 0:
            return CURRENT_HVAC_OFF
        elif self._device.heating:
            return CURRENT_HVAC_HEAT
        else:
            return CURRENT_HVAC_IDLE

    @property
    def hvac_mode(self) -> str:
        if self._device.onoff == 0:
            return HVAC_MODE_OFF
        elif self._device.mode == ThermostatV3Mode.AUTO:
            return HVAC_MODE_AUTO
        elif self._device.mode == ThermostatV3Mode.CUSTOM:
            return HVAC_MODE_HEAT
        elif self._device.mode == ThermostatMode.SCHEDULE:
            return HVAC_MODE_AUTO
        elif self._device.mode == ThermostatMode.CUSTOM:
            return HVAC_MODE_HEAT
        else:
            return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> List[str]:
        return [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_HEAT]

    def set_temperature(self, **kwargs) -> None:
        self._device.set_target_temperature(kwargs.get('temperature'))

    def set_humidity(self, humidity: int) -> None:
        # Not supported
        pass

    def set_fan_mode(self, fan_mode: str) -> None:
        # Not supported
        pass

    def set_hvac_mode(self, hvac_mode: str) -> None:
        if hvac_mode == HVAC_MODE_OFF:
            self._device.turn_off()
            return

        if self._device.type == "mts100v3":
            if hvac_mode == HVAC_MODE_HEAT:
                def action(error, response):
                    if error is None:
                        self._device.set_mode(ThermostatV3Mode.CUSTOM)
                self._device.turn_on(callback=action)

            elif hvac_mode == HVAC_MODE_AUTO:
                def action(error, response):
                    if error is None:
                        self._device.set_mode(ThermostatV3Mode.AUTO)
                self._device.turn_on(callback=action)
            else:
                _LOGGER.warning("Unsupported mode for this device")

        elif self._device.type == "mts100":
            if hvac_mode == HVAC_MODE_HEAT:
                def action(error, response):
                    if error is None:
                        self._device.set_mode(ThermostatMode.CUSTOM)
                self._device.turn_on(callback=action)
            elif hvac_mode == HVAC_MODE_AUTO:
                def action(error, response):
                    if error is None:
                        self._device.set_mode(ThermostatMode.SCHEDULE)
                self._device.turn_on(callback=action)
            else:
                _LOGGER.warning("Unsupported mode for this device")
        else:
            _LOGGER.warning("Unsupported mode for this device")

    def set_swing_mode(self, swing_mode: str) -> None:
        # Not supported
        pass

    def set_preset_mode(self, preset_mode: str) -> None:
        if self._device.type == "mts100v3":
            self._device.set_mode(ThermostatV3Mode[preset_mode])
        elif self._device.type == "mts100":
            self._device.set_mode(ThermostatMode[preset_mode])
        else:
            _LOGGER.warning("Unsupported preset for this device")

    def turn_aux_heat_on(self) -> None:
        # Not supported
        pass

    def turn_aux_heat_off(self) -> None:
        # Not supported
        pass

    @property
    def target_temperature(self) -> Optional[float]:
        return self._device.target_temperature

    @property
    def target_temperature_high(self) -> Optional[float]:
        # Not supported
        return None

    @property
    def target_temperature_low(self) -> Optional[float]:
        # Not supported
        return None

    @property
    def target_temperature_step(self) -> Optional[float]:
        return 0.5

    @property
    def preset_mode(self) -> Optional[str]:
        return self._device.mode.name

    @property
    def preset_modes(self) -> Optional[List[str]]:
        if isinstance(self._device.mode, ThermostatV3Mode):
            return [e.name for e in ThermostatV3Mode]
        elif isinstance(self._device.mode, ThermostatMode):
            return [e.name for e in ThermostatMode]
        else:
            _LOGGER.warning("Unknown valve mode type.")
            return [PRESET_NONE]

    @property
    def is_aux_heat(self) -> Optional[bool]:
        return False

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


async def async_setup_entry(hass, config_entry, async_add_entities):
    thermostat_devices = []
    manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
    valves = manager.get_devices_by_kind(ValveSubDevice)
    for valve in valves:  # type: ValveSubDevice
        w = ValveEntityWrapper(device=valve)
        thermostat_devices.append(w)

    async_add_entities(thermostat_devices)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass

