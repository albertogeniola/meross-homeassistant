import logging
from typing import Any, Optional, List, Dict

from homeassistant.core import HomeAssistant
from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.spray import SprayMixin
from meross_iot.controller.mixins.diffuser_spray import DiffuserSprayMixin
from meross_iot.manager import MerossManager
from meross_iot.model.enums import SprayMode, DiffuserSprayMode
from meross_iot.model.http.device import HttpDeviceInfo

from homeassistant.components.humidifier import HumidifierEntity, HumidifierEntityFeature, HumidifierDeviceClass
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import MerossDevice
from .common import (DOMAIN, MANAGER, HA_HUMIDIFIER, DEVICE_LIST_COORDINATOR)

_LOGGER = logging.getLogger(__name__)


SPRAY_MODE_FROM_HA = {
    "CONTINUOUS": SprayMode.CONTINUOUS,
    "INTERMITTENT": SprayMode.INTERMITTENT
}

SPRAY_MODE_TO_HA = {
    SprayMode.CONTINUOUS: "CONTINUOUS",
    SprayMode.INTERMITTENT: "INTERMITTENT"
}

OILSPRAY_MODE_FROM_HA = {
    "HEAVY SPRAY": DiffuserSprayMode.STRONG,
    "LIGHT SPRAY": DiffuserSprayMode.LIGHT,
}

OILSPRAY_MODE_TO_HA = {
    DiffuserSprayMode.STRONG: "HEAVY SPRAY",
    DiffuserSprayMode.LIGHT: "LIGHT SPRAY"
}


class MerossHumidifierDevice(SprayMixin, BaseDevice):
    """
    Type hints helper for humidifier
    """
    pass


class MerossOilDiffuserDevice(DiffuserSprayMixin, BaseDevice):
    """
    Type hints helper for oil diffuser
    """
    pass


class HumidifierEntityWrapper(MerossDevice, HumidifierEntity):
    """Wrapper class to adapt the Meross humidifier into the Homeassistant platform"""

    _device: MerossHumidifierDevice
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_supported_features: HumidifierEntityFeature = HumidifierEntityFeature.MODES
    _attr_available_modes = ["CONTINUOUS", "INTERMITTENT"]

    def __init__(self,
                 channel: int,
                 device: MerossHumidifierDevice,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_HUMIDIFIER)

    async def async_turn_off(self, **kwargs) -> None:
        await self._device.async_set_mode(mode=SprayMode.OFF, channel=self._channel_id, skip_rate_limits=True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        mode = self.mode
        if mode is None:
            mode = SprayMode.CONTINUOUS
        await self._device.async_set_mode(mode=mode, channel=self._channel_id, skip_rate_limits=True)

    async def async_set_mode(self, mode: str) -> None:
        parsed_mode = SPRAY_MODE_FROM_HA[mode]
        await self._device.async_set_mode(mode=parsed_mode, channel=self._channel_id, skip_rate_limits=True)

    @property
    def mode(self) -> str | None:
        """Return the current mode

        Requires HumidifierEntityFeature.MODES.
        """
        return SPRAY_MODE_TO_HA.get(self._device.get_current_mode())

    @property
    def is_on(self) -> Optional[bool]:
        mode = self._device.get_current_mode(channel=self._channel_id)
        if mode is None:
            return None
        return mode != SprayMode.OFF


class OilDiffuserEntityWrapper(MerossDevice, HumidifierEntity):
    """Wrapper class to adapt the Meross OilDiffuser into the Homeassistant platform"""

    _device: MerossOilDiffuserDevice
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_supported_features: HumidifierEntityFeature = HumidifierEntityFeature.MODES
    _attr_available_modes = ["HEAVY SPRAY", "LIGHT SPRAY"]

    def __init__(self,
                 channel: int,
                 device: MerossOilDiffuserDevice,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_HUMIDIFIER)

    async def async_turn_off(self, **kwargs) -> None:
        await self._device.async_set_spray_mode(mode=DiffuserSprayMode.OFF, channel=self._channel_id, skip_rate_limits=True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.async_set_spray_mode(mode=DiffuserSprayMode.LIGHT, channel=self._channel_id, skip_rate_limits=True)

    async def async_set_mode(self, mode: str) -> None:
        parsed_mode = OILSPRAY_MODE_FROM_HA[mode]
        await self._device.async_set_spray_mode(mode=parsed_mode, channel=self._channel_id, skip_rate_limits=True)

    @property
    def mode(self) -> str | None:
        """Return the current mode

        Requires HumidifierEntityFeature.MODES.
        """
        return OILSPRAY_MODE_TO_HA.get(self._device.get_current_spray_mode())

    @property
    def is_on(self) -> Optional[bool]:
        mode = self._device.get_current_spray_mode(channel=self._channel_id)
        if mode is None:
            return None
        return mode != DiffuserSprayMode.OFF


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    def entity_adder_callback():
        """Discover and adds new Meross entities"""
        manager: MerossManager = hass.data[DOMAIN][MANAGER]  # type
        coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
        new_entities = []

        # Add Humidifiers
        devices = manager.find_devices(device_class=SprayMixin)
        for d in devices:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = HumidifierEntityWrapper(device=d, channel=channel_index, device_list_coordinator=coordinator)
                if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                    new_entities.append(w)

        # Add OilDiffuser
        devices = manager.find_devices(device_class=DiffuserSprayMixin)
        for d in devices:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = OilDiffuserEntityWrapper(device=d, channel=channel_index, device_list_coordinator=coordinator)
                if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                    new_entities.append(w)

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
