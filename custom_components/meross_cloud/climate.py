import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate import ClimateEntityFeature, HVACMode, HVACAction
# Conditional import for switch device
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.thermostat import ThermostatModeMixin, ThermostatModeBMixin
from meross_iot.controller.subdevice import Mts100v3Valve
from meross_iot.manager import MerossManager
from meross_iot.model.enums import ThermostatV3Mode, ThermostatMode
from meross_iot.model.http.device import HttpDeviceInfo
from typing import Optional, List, Dict

from . import MerossDevice
from .common import (DOMAIN, MANAGER, HA_CLIMATE, DEVICE_LIST_COORDINATOR)

_LOGGER = logging.getLogger(__name__)


class ValveEntityWrapper(MerossDevice, ClimateEntity):
    """Wrapper class to adapt the Meross devices into the Homeassistant platform"""
    _device: Mts100v3Valve
    _enable_turn_on_off_backwards_compatibility = False
    # For now, we assume that every Meross Valve supports the following modes.
    # This might be improved in the future by looking at the device abilities via get_abilities()
    _flags = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF

    def __init__(self,
                 channel: int,
                 device: Mts100v3Valve,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_CLIMATE)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        # Turn on the device if not already on
        if hvac_mode == HVACMode.OFF:
            await self._device.async_turn_off()
            return
        elif not self._device.is_on():
            await self._device.async_turn_on()

        if hvac_mode == HVACMode.HEAT:
            await self._device.async_set_mode(ThermostatV3Mode.HEAT)
        elif hvac_mode == HVACMode.AUTO:
            await self._device.async_set_mode(ThermostatV3Mode.AUTO)
        elif hvac_mode == HVACMode.COOL:
            await self._device.async_set_mode(ThermostatV3Mode.COOL)
        else:
            _LOGGER.warning(f"Unsupported mode for this device ({self.name}): {hvac_mode}")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._device.async_set_mode(ThermostatV3Mode[preset_mode])

    async def async_set_temperature(self, **kwargs):
        target = kwargs.get('temperature')
        await self._device.async_set_target_temperature(target)

    @property
    def temperature_unit(self) -> str:
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> Optional[float]:
        return self._device.last_sampled_temperature

    @property
    def target_temperature(self) -> Optional[float]:
        return self._device.target_temperature

    @property
    def target_temperature_step(self) -> Optional[float]:
        return 0.5

    @property
    def max_temp(self) -> Optional[float]:
        return self._device.max_supported_temperature

    @property
    def min_temp(self) -> Optional[float]:
        return self._device.min_supported_temperature

    @property
    def hvac_mode(self) -> str:
        if not self._device.is_on():
            return HVACMode.OFF
        elif self._device.mode == ThermostatV3Mode.AUTO:
            return HVACMode.AUTO
        elif self._device.mode == ThermostatV3Mode.HEAT:
            return HVACMode.HEAT
        elif self._device.mode == ThermostatV3Mode.COOL:
            return HVACMode.COOL
        elif self._device.mode == ThermostatV3Mode.ECONOMY:
            return HVACMode.AUTO
        elif self._device.mode == ThermostatV3Mode.CUSTOM:
            if self._device.last_sampled_temperature < self._device.target_temperature:
                return HVACMode.HEAT
            else:
                return HVACMode.COOL
        else:
            raise ValueError("Unsupported thermostat mode reported.")

    @property
    def hvac_action(self) -> Optional[str]:
        if not self._device.is_on():
            return HVACAction.OFF
        elif self._device.is_heating:
            return HVACAction.HEATING
        elif self._device.mode == HVACAction.COOLING:
            return HVACAction.COOLING
        else:
            return HVACAction.IDLE

    @property
    def hvac_modes(self) -> List[str]:
        return [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL]

    @property
    def preset_mode(self) -> Optional[str]:
        if self._device.mode is not None:
            return self._device.mode.name
        return None

    @property
    def preset_modes(self) -> List[str]:
        return [e.name for e in ThermostatV3Mode]

    @property
    def supported_features(self):
        return self._flags

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEATING)


class MerossThermostatDevice(ThermostatModeMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class ThermostatEntityWrapper(MerossDevice, ClimateEntity):
    """Wrapper class to adapt the Meross thermostat-enabled devices into the Homeassistant platform"""
    _device: MerossThermostatDevice
    _enable_turn_on_off_backwards_compatibility = False
    _flags = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF  # | ClimateEntityFeature.PRESET_MODE

    def __init__(self,
                 channel: int,
                 device: Mts100v3Valve,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_CLIMATE)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        # Turn on the device if not already on
        if hvac_mode == HVACMode.OFF:
            await self._device.async_set_thermostat_config(on_not_off=False, channel=self._channel_id)
            return
        elif not self._device.get_thermostat_state(channel=self._channel_id).is_on:
            await self._device.async_set_thermostat_config(on_not_off=True, channel=self._channel_id)

        if hvac_mode == HVACMode.HEAT:
            await self._device.async_set_thermostat_config(mode=ThermostatMode.HEAT)
        elif hvac_mode == HVACMode.AUTO:
            await self._device.async_set_thermostat_config(mode=ThermostatMode.AUTO)
        elif hvac_mode == HVACMode.COOL:
            await self._device.async_set_thermostat_config(mode=ThermostatMode.COOL)
        else:
            _LOGGER.warning(f"Unsupported mode for this device ({self.name}): {hvac_mode}")

    async def async_set_temperature(self, **kwargs):
        target = kwargs.get('temperature')
        await self._device.async_set_thermostat_config(channel=self._channel_id, mode=ThermostatMode.MANUAL, manual_temperature_celsius=target)

    @property
    def temperature_unit(self) -> str:
        # TODO: Check if there is a way for retrieving the Merasurement Unit from the library
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> Optional[float]:
        return self._device.get_thermostat_state(channel=self._channel_id).current_temperature_celsius

    @property
    def target_temperature(self) -> Optional[float]:
        return self._device.get_thermostat_state(channel=self._channel_id).target_temperature_celsius

    @property
    def target_temperature_step(self) -> Optional[float]:
        return 0.5

    @property
    def max_temp(self) -> Optional[float]:
        return self._device.get_thermostat_state().max_temperature_celsius

    @property
    def min_temp(self) -> Optional[float]:
        return self._device.get_thermostat_state().min_temperature_celsius

    @property
    def hvac_mode(self) -> HVACMode:
        status = self._device.get_thermostat_state(channel=self._channel_id)
        if not status.is_on:
            return HVACMode.OFF
        elif status.mode == ThermostatMode.AUTO:
            return HVACMode.AUTO
        elif status.mode == ThermostatMode.HEAT:
            return HVACMode.HEAT
        elif status.mode == ThermostatMode.COOL:
            return HVACMode.COOL
        elif status.mode == ThermostatMode.ECONOMY:
            return HVACMode.AUTO
        elif status.mode == ThermostatMode.MANUAL:
            if status.current_temperature_celsius < status.target_temperature_celsius:
                return HVACMode.HEAT
            else:
                return HVACMode.COOL
        else:
            raise ValueError("Unsupported thermostat mode reported.")

    @property
    def hvac_action(self) -> Optional[str]:
        status = self._device.get_thermostat_state(channel=self._channel_id)
        if not status.is_on:
            return HVACAction.OFF
        elif status.current_temperature_celsius < status.target_temperature_celsius:
            return HVACAction.HEATING
        elif status.current_temperature_celsius > status.target_temperature_celsius:
            return HVACAction.COOLING
        elif status.current_temperature_celsius == status.target_temperature_celsius:
            return HVACAction.IDLE

    @property
    def hvac_modes(self) -> List[HVACMode]:
        return [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL]

    @property
    def supported_features(self):
        return self._flags

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEATING)


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    def entity_adder_callback():
        """Discover and adds new Meross entities"""
        manager: MerossManager = hass.data[DOMAIN][MANAGER]  # type
        coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
        devices = manager.find_devices()
        new_entities = []

        # Handle smart valves
        valves = filter(lambda d: isinstance(d, Mts100v3Valve), devices)
        for d in valves:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = ValveEntityWrapper(device=d, channel=channel_index, device_list_coordinator=coordinator)
                if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                    new_entities.append(w)

        # Handle classic thermostats
        thermostats = filter(lambda d: isinstance(d, ThermostatModeMixin), devices)
        for d in thermostats:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = ThermostatEntityWrapper(device=d, channel=channel_index, device_list_coordinator=coordinator)
                if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                    new_entities.append(w)

        # Handle ModeB thermostats
        thermostats = filter(lambda d: isinstance(d, ThermostatModeBMixin), devices)
        for d in thermostats:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = ThermostatEntityWrapper(device=d, channel=channel_index,
                                            device_list_coordinator=coordinator)
                if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                    new_entities.append(w)

        # Add all entities to HA
        async_add_entities(new_entities, True)

    coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
    coordinator.async_add_listener(entity_adder_callback)
    # Run the entity adder a first time during setup
    entity_adder_callback()

# TODO: Implement entry unload
# TODO: Unload entry
# TODO: Remove entry


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass

