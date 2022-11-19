import logging
from typing import Any, Dict

from meross_iot.controller.device import BaseDevice
from meross_iot.model.enums import RollerShutterState
from meross_iot.controller.mixins.garage import GarageOpenerMixin
from meross_iot.controller.mixins.roller_shutter import RollerShutterTimerMixin
from meross_iot.manager import MerossManager
from meross_iot.model.http.device import HttpDeviceInfo

# Conditional Light import with backwards compatibility
from homeassistant.components.cover import CoverEntity, SUPPORT_STOP
from homeassistant.components.cover import DEVICE_CLASS_GARAGE, DEVICE_CLASS_SHUTTER, SUPPORT_OPEN, SUPPORT_CLOSE
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import MerossDevice
from .common import (DOMAIN, MANAGER, HA_COVER, DEVICE_LIST_COORDINATOR)

_LOGGER = logging.getLogger(__name__)


class MerossGarageDevice(GarageOpenerMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class GarageOpenerEntityWrapper(MerossDevice, CoverEntity):
    """Wrapper class to adapt the Meross Garage Opener into the Homeassistant platform"""

    _device: MerossGarageDevice

    def __init__(self,
                 channel: int,
                 device: MerossGarageDevice,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_COVER)

    async def async_close_cover(self, **kwargs):
        await self._device.async_close(channel=self._channel_id, skip_rate_limits=True)

    async def async_open_cover(self, **kwargs):
        await self._device.async_open(channel=self._channel_id, skip_rate_limits=True)

    def open_cover(self, **kwargs: Any) -> None:
        self.hass.async_add_executor_job(self.async_open_cover, **kwargs)

    def close_cover(self, **kwargs: Any) -> None:
        self.hass.async_add_executor_job(self.async_close_cover, **kwargs)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_GARAGE

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def is_closed(self):
        open_status = self._device.get_is_open(channel=self._channel_id)
        return not open_status

    @property
    def is_closing(self):
        # Not supported yet
        return None
    
    @property
    def is_opening(self):
        # Not supported yet
        return None


class MerossRollerShutterDevice(RollerShutterTimerMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class RollerShutterEntityWrapper(MerossDevice, CoverEntity):
    """Wrapper class to adapt the Meross roller shutter into the Homeassistant platform"""

    _device: MerossRollerShutterDevice

    def __init__(self,
                 channel: int,
                 device: MerossRollerShutterDevice,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_COVER)

    async def async_close_cover(self, **kwargs):
        await self._device.async_close(channel=self._channel_id, skip_rate_limits=True)

    async def async_open_cover(self, **kwargs):
        await self._device.async_open(channel=self._channel_id, skip_rate_limits=True)

    async def async_stop_cover(self, **kwargs):
        await self._device.async_stop(channel=self._channel_id, skip_rate_limits=True)

    def open_cover(self, **kwargs: Any) -> None:
        self.hass.async_add_executor_job(self.async_open_cover, **kwargs)

    def close_cover(self, **kwargs: Any) -> None:
        self.hass.async_add_executor_job(self.async_close_cover, **kwargs)

    def stop_cover(self, **kwargs) -> None:
        self.hass.async_add_executor_job(self.async_stop_cover, **kwargs)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SHUTTER

    @property
    def supported_features(self):
        """Flag supported features."""
        # So far, the Roller Shutter RST100 supports position, but it looks like it is fake and not reliable.
        # So we don't support that on HA neither.
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

    @property
    def is_closed(self):
        return self._device.get_position(channel=self._channel_id) == 0

    @property
    def is_closing(self):
        status = self._device.get_status(channel=self._channel_id)
        return status == RollerShutterState.CLOSING

    @property
    def is_opening(self):
        status = self._device.get_status(channel=self._channel_id)
        return status == RollerShutterState.OPENING


async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    def entity_adder_callback():
        """Discover and adds new Meross entities"""
        manager: MerossManager = hass.data[DOMAIN][MANAGER]
        coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
        devices = manager.find_devices(device_class=[GarageOpenerMixin, RollerShutterTimerMixin])
        new_entities = []
        for d in devices:
            # For multi-channel garage doors opener (like MSG200), the main channel is not operable and
            # does not provide meaningful states. For this reason, we will ignore the "main channel"
            # of any cover device which has more than 1 channels. Of course, we will keep working with channel
            # 0 when dealing with dingle-door openers.
            if len(d.channels) > 1:
                channels = [c.index for c in d.channels if c.index > 0]
            else:
                channels = [0]
            for channel_index in channels:
                if isinstance(d, GarageOpenerMixin):
                    w = GarageOpenerEntityWrapper(device=d, channel=channel_index, device_list_coordinator=coordinator)
                elif isinstance(d, RollerShutterTimerMixin):
                    w = RollerShutterEntityWrapper(device=d, channel=channel_index, device_list_coordinator=coordinator)
                else:
                    _LOGGER.warn("Invalid/Unsupported device class for cover platform.")
                    continue
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
