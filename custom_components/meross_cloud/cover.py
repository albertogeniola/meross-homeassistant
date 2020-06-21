import logging
from datetime import timedelta
from typing import Any, Iterable

from homeassistant.components.cover import DEVICE_CLASS_GARAGE, SUPPORT_OPEN, SUPPORT_CLOSE
from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.garage import GarageOpenerMixin
from meross_iot.manager import MerossManager
from meross_iot.model.enums import OnlineStatus, Namespace
from meross_iot.model.exception import CommandTimeoutError
from meross_iot.model.push.bind import BindPushNotification
from meross_iot.model.push.generic import GenericPushNotification

from .common import (DOMAIN, MANAGER, log_exception, RELAXED_SCAN_INTERVAL, calculate_cover_id, HA_COVER)

# Conditional Light import with backwards compatibility
try:
    from homeassistant.components.cover import CoverEntity
except ImportError:
    from homeassistant.components.cover import CoverDevice as CoverEntity


_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=RELAXED_SCAN_INTERVAL)


class MerossCoverWrapper(GarageOpenerMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class CoverEntityWrapper(CoverEntity):
    """Wrapper class to adapt the Meross bulbs into the Homeassistant platform"""
    def __init__(self, device: MerossCoverWrapper, channel: int):
        self._device = device

        # If the current device has more than 1 channel, we need to setup the device name and id accordingly
        if len(device.channels) > 1:
            self._id = calculate_cover_id(device.internal_id, channel)
            channel_data = device.channels[channel]
            self._entity_name = "{} - {}".format(device.name, channel_data.name)
        else:
            self._id = device.uuid
            self._entity_name = device.name

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

    async def _async_push_notification_received(self, namespace: Namespace, data: dict):
        if namespace == Namespace.CONTROL_UNBIND:
            _LOGGER.info("Received unbind event. Removing the device from HA")
            await self.platform.async_remove_entity(self.entity_id)
        elif namespace == Namespace.SYSTEM_ONLINE:
            online = OnlineStatus(int(data.get('online').get('status')))
            if online == OnlineStatus.ONLINE:
                # The device has just gone online again. Update its status.
                self.async_schedule_update_ha_state(force_refresh=True)
        elif namespace == Namespace.HUB_ONLINE:
            # TODO Verify that this event is only provided to wrappers implementing
            #  subdevices. If not, then we might have a problem, i.e. we would be triggering
            #  updates too often
            online = OnlineStatus(int(data.get('status')))
            if online == OnlineStatus.ONLINE:
                # The device has just gone online again. Update its status.
                self.async_schedule_update_ha_state(force_refresh=True)
        else:
            # In all other cases, just tell HA to update the internal state representation
            self.async_schedule_update_ha_state(force_refresh=False)

    async def async_added_to_hass(self) -> None:
        self._device.register_push_notification_handler_coroutine(self._async_push_notification_received)

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_push_notification_handler_coroutine(self._async_push_notification_received)
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
            'identifiers': {(DOMAIN, self._device.internal_id)},
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
    async def async_close_cover(self, **kwargs):
        await self._device.async_close(channel=self._channel_id)

    async def async_open_cover(self, **kwargs):
        await self._device.async_open(channel=self._channel_id)

    def open_cover(self, **kwargs: Any) -> None:
        self.hass.async_add_executor_job(self.async_open_cover, **kwargs)

    def close_cover(self, **kwargs: Any) -> None:
        self.hass.async_add_executor_job(self.async_close_cover, **kwargs)
    # endregion

    # region Platform specific properties
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

    # endregion


# ----------------------------------------------
# PLATFORM METHODS
# ----------------------------------------------
def _add_entities(hass, devices: Iterable[BaseDevice], async_add_entities):
    new_entities = []
    # Identify all the devices that expose the Light capability
    devs = filter(lambda d: isinstance(d, GarageOpenerMixin), devices)
    for d in devs:
        for channel_index, channel in enumerate(d.channels):
            w = CoverEntityWrapper(device=d, channel=channel_index)
            if w.unique_id not in hass.data[DOMAIN][HA_COVER]:
                _LOGGER.debug(f"Device {w.unique_id} is new, will be added to HA")
                new_entities.append(w)
            else:
                _LOGGER.debug(f"Skipping device {w.unique_id} as it's already present in HA")
    async_add_entities(new_entities, True)


async def async_setup_entry(hass, config_entry, async_add_entities):
    # When loading the platform, immediately add currently available
    # bulbs.
    manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
    devices = manager.find_devices()
    _add_entities(hass=hass, devices=devices, async_add_entities=async_add_entities)

    # Register a listener for the Bind push notification so that we can add new entities at runtime
    async def platform_async_add_entities(push_notification: GenericPushNotification, target_device: BaseDevice):
        if isinstance(push_notification, BindPushNotification):
            devs = manager.find_devices(device_uuids=(push_notification.hwinfo.uuid,))
            _add_entities(hass=hass, devices=devs, async_add_entities=async_add_entities)

    # Register a listener for new bound devices
    manager.register_push_notification_handler_coroutine(platform_async_add_entities)


# TODO: Unload entry
# TODO: Remove entry


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.info("SETUP PLATFORM")
    pass
