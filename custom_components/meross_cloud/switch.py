import logging
from datetime import datetime
from typing import Optional, Iterable, Dict

from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.consumption import ConsumptionXMixin
from meross_iot.controller.mixins.electricity import ElectricityMixin
from meross_iot.controller.mixins.garage import GarageOpenerMixin
from meross_iot.controller.mixins.light import LightMixin
from meross_iot.controller.mixins.toggle import ToggleXMixin, ToggleMixin
from meross_iot.manager import MerossManager
from meross_iot.model.enums import OnlineStatus, Namespace
from meross_iot.model.http.device import HttpDeviceInfo

# Conditional import for switch device
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import MerossDevice
from .common import (DOMAIN, MANAGER, DEVICE_LIST_COORDINATOR, HA_SWITCH)

_LOGGER = logging.getLogger(__name__)


class MerossSwitchDevice(ToggleXMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class SwitchEntityWrapper(MerossDevice, SwitchEntity):
    """Wrapper class to adapt the Meross switches into the Homeassistant platform"""
    _device: MerossSwitchDevice

    def __init__(self,
                 channel: int,
                 device: MerossSwitchDevice,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]):

        # If the current device has more than 1 channel, we need to setup the device name and id accordingly
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_SWITCH)

        # Device properties
        self._last_power_sample = None
        self._daily_consumption = None

    async def async_update(self):
        if self.online:
            await super().async_update()

            # If the device supports power reading, update it
            if isinstance(self._device, ElectricityMixin):
                self._last_power_sample = await self._device.async_get_instant_metrics(channel=self._channel_id)

            if isinstance(self._device, ConsumptionXMixin):
                self._daily_consumption = await self._device.async_get_daily_power_consumption(channel=self._channel_id)

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def is_on(self) -> bool:
        dev = self._device
        return dev.is_on(channel=self._channel_id)

    async def async_turn_off(self, **kwargs) -> None:
        dev = self._device
        await dev.async_turn_off(channel=self._channel_id, skip_rate_limits=True)

    async def async_turn_on(self, **kwargs) -> None:
        dev = self._device
        await dev.async_turn_on(channel=self._channel_id, skip_rate_limits=True)

    async def _async_push_notification_received(self, namespace: Namespace, data: dict, device_internal_id: str):
        update_state = False
        full_update = False

        if namespace == Namespace.CONTROL_UNBIND:
            _LOGGER.warning(f"Received unbind event. Removing device {self.name} from HA")
            await self.platform.async_remove_entity(self.entity_id)
        elif namespace == Namespace.SYSTEM_ONLINE:
            _LOGGER.warning(f"Device {self.name} reported online event.")
            online = OnlineStatus(int(data.get('online').get('status')))
            update_state = True
            full_update = online == OnlineStatus.ONLINE

        elif namespace == Namespace.HUB_ONLINE:
            _LOGGER.warning(f"Device {self.name} reported (HUB) online event.")
            online = OnlineStatus(int(data.get('status')))
            update_state = True
            full_update = online == OnlineStatus.ONLINE
        else:
            update_state = True
            full_update = False

        # In all other cases, just tell HA to update the internal state representation
        if update_state:
            self.async_schedule_update_ha_state(force_refresh=full_update)

    @property
    def current_power_w(self) -> Optional[float]:
        if self._last_power_sample is not None:
            return self._last_power_sample.power

    @property
    def today_energy_kwh(self) -> Optional[float]:
        if self._daily_consumption is not None:
            today = datetime.today()
            total = 0
            daystart = datetime(year=today.year, month=today.month, day=today.day, hour=0, second=0)
            for x in self._daily_consumption:
              if x['date'] == daystart:
                total = x['total_consumption_kwh']
            return total


async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    def entity_adder_callback():
        """Discover and adds new Meross entities"""
        manager: MerossManager = hass.data[DOMAIN][MANAGER]  # type
        coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
        devices = manager.find_devices()

        new_entities = []

        # Identify all the devices that expose the Toggle or ToggleX capabilities
        devs = filter(lambda d: isinstance(d, ToggleXMixin) or isinstance(d, ToggleMixin), devices)

        # Exclude garage openers and lights.
        devs = filter(lambda d: not (isinstance(d, GarageOpenerMixin) or isinstance(d, LightMixin)), devs)

        for d in devs:
            for channel_index, channel in enumerate(d.channels):
                w = SwitchEntityWrapper(device=d, channel=channel_index,
                                        device_list_coordinator=coordinator)
                if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                    new_entities.append(w)

        async_add_entities(new_entities, True)

    coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
    coordinator.async_add_listener(entity_adder_callback)
    # Run the entity adder a first time during setup
    entity_adder_callback()

# TODO: Implement entry unload
# async def async_unload_entry(hass: HomeAssistantType, config_entry: ConfigEntry):
#     manager.unregister_push_notification_handler_coroutine(platform_async_add_entities)

# TODO: Unload entry
# TODO: Remove entry


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
