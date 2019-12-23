from typing import Optional, List

from homeassistant.components.climate import ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_PRESET_MODE, \
    HVAC_MODE_COOL
from homeassistant.components.climate.const import HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF
from homeassistant.const import TEMP_CELSIUS
from meross_iot.manager import MerossManager
from meross_iot.cloud.devices.hubs import GenericHub
from meross_iot.cloud.devices.subdevices.thermostats import ValveSubDevice, ThermostatV3Mode, ThermostatMode
from .common import DOMAIN, ENROLLED_DEVICES, MANAGER
import logging


_LOGGER = logging.getLogger(__name__)


class ValveEntityWrapper(ClimateDevice):
    """Wrapper class to adapt the Meross thermostat into the Homeassistant platform"""

    def __init__(self, device: ValveSubDevice):
        self._device = device

        self._hub_id = self._device._hub.uuid

        # The id of a valve is the concatenation of the hubid and the subdevice id
        self._subdevice_id = self._device.id
        self._id = f"{self._device._hub.uuid}:{self._subdevice_id}"

        # TODO: The device name should be gathered from the library somehow...
        self._device_name = 'Meross Thermostat'

        # TODO
        # self._device.register_event_callback(self.handler)

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
            # TODO: 'model': self._device.type + " " + self._device.hwversion,
            # TODO: 'sw_version': self._device.fwversion,
            # TODO:'via_device': (DOMAIN, self._hub_id)
        }

    @property
    def temperature_unit(self) -> str:
        # TODO: check if this is always the case
        return TEMP_CELSIUS

    @property
    def hvac_mode(self) -> str:
        if self._device.onoff == 0:
            return HVAC_MODE_OFF
        elif self._device.mode == ThermostatV3Mode.COOL:
            return HVAC_MODE_COOL
        elif self._device.mode == ThermostatV3Mode.AUTO:
            return HVAC_MODE_AUTO
        elif self._device.mode == ThermostatV3Mode.HEAT:
            return HVAC_MODE_HEAT
        else:
            return HVAC_MODE_AUTO

    @property
    def hvac_modes(self) -> List[str]:
        if isinstance(self._device.mode, ThermostatV3Mode):
            return [HVAC_MODE_COOL, HVAC_MODE_AUTO, HVAC_MODE_HEAT]
        else:
            return []

    def set_temperature(self, **kwargs) -> None:
        # TODO
        pass

    def set_humidity(self, humidity: int) -> None:
        # TODO: Not supported
        pass

    def set_fan_mode(self, fan_mode: str) -> None:
        # TODO: Not supported
        pass

    def set_hvac_mode(self, hvac_mode: str) -> None:
        # TODO: Not supported
        pass

    def set_swing_mode(self, swing_mode: str) -> None:
        # TODO: Not supported
        pass

    def set_preset_mode(self, preset_mode: str) -> None:
        # TODO: Not supported
        pass

    def turn_aux_heat_on(self) -> None:
        # TODO: Not supported
        pass

    def turn_aux_heat_off(self) -> None:
        # TODO: Not supported
        pass

    @property
    def target_temperature_high(self) -> Optional[float]:
        return None

    @property
    def target_temperature_low(self) -> Optional[float]:
        return None

    @property
    def preset_mode(self) -> Optional[str]:
        return None

    @property
    def preset_modes(self) -> Optional[List[str]]:
        return None

    @property
    def is_aux_heat(self) -> Optional[bool]:
        return None

    @property
    def fan_mode(self) -> Optional[str]:
        return None

    @property
    def fan_modes(self) -> Optional[List[str]]:
        return None

    @property
    def swing_mode(self) -> Optional[str]:
        return None

    @property
    def swing_modes(self) -> Optional[List[str]]:
        return None


async def async_setup_entry(hass, config_entry, async_add_entities):
    thermostat_devices = []
    manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
    #valves = manager.get_devices_by_kind(ValveSubDevice)
    # for valve in valves:  # type: ValveSubDevice
    #    w = ValveEntityWrapper(device=valve)
    #    thermostat_devices.append(w)

    hubs = manager.get_devices_by_kind(GenericHub)
    for hub in hubs:  # type: GenericHub
        for k, device in hub._sub_devices.items():
            if isinstance(device, ValveSubDevice):
                w = ValveEntityWrapper(device=device)
                thermostat_devices.append(w)

    async_add_entities(thermostat_devices)

    # hass.data[DOMAIN][ENROLLED_DEVICES].add(device.uuid)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass

