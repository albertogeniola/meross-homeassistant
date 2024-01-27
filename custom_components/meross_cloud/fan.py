import logging
from typing import Any, Optional, List, Dict

from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.spray import SprayMixin
from meross_iot.manager import MerossManager
from meross_iot.model.enums import SprayMode
from meross_iot.model.http.device import HttpDeviceInfo

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import MerossDevice
from .common import (DOMAIN, MANAGER, HA_FAN, DEVICE_LIST_COORDINATOR)

_LOGGER = logging.getLogger(__name__)


class MerossHumidifierDevice(SprayMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class HumidifierEntityWrapper(MerossDevice, FanEntity):
    """Wrapper class to adapt the Meross humidifier into the Homeassistant platform"""

    _device: MerossHumidifierDevice

    def __init__(self,
                 channel: int,
                 device: MerossHumidifierDevice,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_FAN)

    async def async_turn_off(self, **kwargs) -> None:
        await self._device.async_set_mode(mode=SprayMode.OFF, channel=self._channel_id, skip_rate_limits=True)

    async def async_turn_on(self, speed: Optional[str] = None, **kwargs: Any) -> None:
        if speed is None:
            mode = SprayMode.CONTINUOUS
        else:
            mode = SprayMode[speed]
        await self._device.async_set_mode(mode=mode, channel=self._channel_id, skip_rate_limits=True)

    async def async_set_speed(self, speed: str) -> None:
        mode = SprayMode[speed]
        await self._device.async_set_mode(mode=mode, channel=self._channel_id, skip_rate_limits=True)

    def set_direction(self, direction: str) -> None:
        # Not supported
        pass

    def set_speed(self, speed: str) -> None:
        # Not implemented: use async method instead...
        pass

    def turn_on(self, speed: Optional[str] = None, **kwargs) -> None:
        # Not implemented: use async method instead...
        pass

    def turn_off(self, **kwargs: Any) -> None:
        # Not implemented: use async method instead...
        pass

    @property
    def supported_features(self) -> int:
        return FanEntityFeature.PRESET_MODE

    @property
    def is_on(self) -> Optional[bool]:
        mode = self._device.get_current_mode(channel=self._channel_id)
        if mode is None:
            return None
        return mode != SprayMode.OFF

    @property
    def percentage(self) -> Optional[int]:
        mode = self._device.get_current_mode(channel=self._channel_id)
        if mode == SprayMode.OFF:
            return 0
        elif mode == SprayMode.INTERMITTENT:
            return 50
        elif mode == SprayMode.CONTINUOUS:
            return 100
        else:
            raise ValueError("Invalid SprayMode value.")

    @property
    def preset_mode(self) -> Optional[str]:
        mode = self._device.get_current_mode(channel=self._channel_id)
        if mode is not None:
            return mode.name
        else:
            return None

    @property
    def preset_modes(self) -> List[str]:
        return [x.name for x in SprayMode]


async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    def entity_adder_callback():
        """Discover and adds new Meross entities"""
        manager: MerossManager = hass.data[DOMAIN][MANAGER]  # type
        coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
        devices = manager.find_devices(device_class=SprayMixin)

        new_entities = []

        for d in devices:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                w = HumidifierEntityWrapper(device=d, channel=channel_index, device_list_coordinator=coordinator)
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
