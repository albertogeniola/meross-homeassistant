import logging
from datetime import timedelta
from typing import Any, Optional, Iterable, List

from homeassistant.core import HomeAssistant
from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.spray import SprayMixin
from meross_iot.manager import MerossManager
from meross_iot.model.enums import OnlineStatus, Namespace, SprayMode
from meross_iot.model.exception import CommandTimeoutError
from meross_iot.model.push.generic import GenericPushNotification

from .common import (PLATFORM, MANAGER, calculate_humidifier_id, log_exception, SENSOR_POLL_INTERVAL_SECONDS)

# Conditional import for fan device device
try:
    from homeassistant.components.fan import FanEntity, SUPPORT_SET_SPEED
except ImportError:
    from homeassistant.components.switch import FanDevice as FanEntity


_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=SENSOR_POLL_INTERVAL_SECONDS)


class MerossHumidifierDevice(SprayMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class HumidifierEntityWrapper(FanEntity):
    """Wrapper class to adapt the Meross humidifier into the Homeassistant platform"""

    def __init__(self, device: MerossHumidifierDevice, channel: int):
        self._device = device

        # If the current device has more than 1 channel, we need to setup the device name and id accordingly
        self._id = calculate_humidifier_id(device.internal_id, channel)
        channel_data = device.channels[channel]
        self._entity_name = "{} ({}) - {}".format(device.name, device.type, channel_data.name)

        # Device properties
        self._channel_id = channel

    # region Device wrapper common methods
    async def async_update(self):
        if self._device.online_status == OnlineStatus.ONLINE:
            try:
                await self._device.async_update()
            except CommandTimeoutError as e:
                log_exception(logger=_LOGGER, device=self._device)
                pass

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

    async def async_added_to_hass(self) -> None:
        self._device.register_push_notification_handler_coroutine(self._async_push_notification_received)
        self.hass.data[PLATFORM]["ADDED_ENTITIES_IDS"].add(self.unique_id)

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_push_notification_handler_coroutine(self._async_push_notification_received)
        self.hass.data[PLATFORM]["ADDED_ENTITIES_IDS"].remove(self.unique_id)

    # endregion

    # region Device wrapper common properties
    @property
    def unique_id(self) -> str:
        # Since Meross plugs may have more than 1 switch, we need to provide a composed ID
        # made of uuid and channel
        return self._id

    @property
    def name(self) -> str:
        return self._entity_name

    @property
    def device_info(self):
        return {
            'identifiers': {(PLATFORM, self._device.internal_id)},
            'name': self._device.name,
            'manufacturer': 'Meross',
            'model': self._device.type + " " + self._device.hardware_version,
            'sw_version': self._device.firmware_version
        }

    @property
    def available(self) -> bool:
        # A device is available if the client library is connected to the MQTT broker and if the
        # device we are contacting is online
        return self._device.online_status == OnlineStatus.ONLINE

    @property
    def should_poll(self) -> bool:
        return False
    # endregion

    # region Platform-specific command methods
    async def async_turn_off(self, **kwargs) -> None:
        await self._device.async_set_mode(mode=SprayMode.OFF, channel=self._channel_id)

    async def async_turn_on(self, speed: Optional[str] = None, **kwargs: Any) -> None:
        if speed is None:
            mode = SprayMode.CONTINUOUS
        else:
            mode = SprayMode[speed]
        await self._device.async_set_mode(mode=mode, channel=self._channel_id)

    async def async_set_speed(self, speed: str) -> None:
        mode = SprayMode[speed]
        await self._device.async_set_mode(mode=mode, channel=self._channel_id)

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
    # endregion

    # region Platform specific properties
    @property
    def supported_features(self) -> int:
        return SUPPORT_SET_SPEED

    @property
    def is_on(self) -> Optional[bool]:
        mode = self._device.get_current_mode(channel=self._channel_id)
        if mode is None:
            return None
        return mode != SprayMode.OFF

    @property
    def speed_list(self) -> list:
        return [e.name for e in SprayMode]

    @property
    def speed(self) -> Optional[str]:
        mode = self._device.get_current_mode(channel=self._channel_id)
        if mode is None:
            return None
        return mode.name

    # endregion


async def _add_entities(hass: HomeAssistant, devices: Iterable[BaseDevice], async_add_entities):
    new_entities = []

    # Identify all the devices that expose the Spray capability
    devs = filter(lambda d: isinstance(d, SprayMixin), devices)

    for d in devs:
        for channel_index, channel in enumerate(d.channels):
            w = HumidifierEntityWrapper(device=d, channel=channel_index)
            if w.unique_id not in hass.data[PLATFORM]["ADDED_ENTITIES_IDS"]:
                new_entities.append(w)
            else:
                _LOGGER.info(f"Skipping device {w} as it was already added to registry once.")
    async_add_entities(new_entities, True)


async def async_setup_entry(hass, config_entry, async_add_entities):
    # When loading the platform, immediately add currently available
    # switches.
    manager = hass.data[PLATFORM][MANAGER]  # type:MerossManager
    devices = manager.find_devices()
    await _add_entities(hass=hass, devices=devices, async_add_entities=async_add_entities)

    # Register a listener for the Bind push notification so that we can add new entities at runtime
    async def platform_async_add_entities(push_notification: GenericPushNotification, target_devices: List[BaseDevice]):
        if push_notification.namespace == Namespace.CONTROL_BIND \
                or push_notification.namespace == Namespace.SYSTEM_ONLINE \
                or push_notification.namespace == Namespace.HUB_ONLINE:

            # TODO: Discovery needed only when device becomes online?
            await manager.async_device_discovery(push_notification.namespace == Namespace.HUB_ONLINE,
                                                 meross_device_uuid=push_notification.originating_device_uuid)
            devs = manager.find_devices(device_uuids=(push_notification.originating_device_uuid,))
            await _add_entities(hass=hass, devices=devs, async_add_entities=async_add_entities)

    # Register a listener for new bound devices
    manager.register_push_notification_handler_coroutine(platform_async_add_entities)


# TODO: Unload entry
# TODO: Remove entry


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
