import logging
from typing import Any

from homeassistant.components.switch import SwitchDevice
from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.toggle import ToggleXMixin
from meross_iot.manager import MerossManager
from meross_iot.model.enums import OnlineStatus
from meross_iot.model.exception import CommandTimeoutError
from datetime import timedelta
from .common import (DOMAIN, HA_SWITCH, MANAGER, calculate_switch_id, log_exception, RELAXED_SCAN_INTERVAL)

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=RELAXED_SCAN_INTERVAL)


class MerossSwitchDevice(ToggleXMixin, BaseDevice):
    """
    Type hints helper
    """
    pass


class SwitchEntityWrapper(SwitchDevice):
    """Wrapper class to adapt the Meross switches into the Homeassistant platform"""

    def __init__(self, device: MerossSwitchDevice, channel: int):
        self._device = device

        # If the current device has more than 1 channel, we need to setup the device name and id accordingly
        if len(device.channels) > 1:
            self._id = calculate_switch_id(device.internal_id, channel)
            channel_data = device.channels[channel]
            self._entity_name = "{} - {}".format(device.name, channel_data.name)
        else:
            self._id = device.uuid
            self._entity_name = device.name

        # Device properties
        self._channel_id = channel

    async def async_update(self):
        if self._device.online_status == OnlineStatus.ONLINE:
            try:
                await self._device.async_update()
            except CommandTimeoutError as e:
                log_exception(logger=_LOGGER, device=self._device)
                pass

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
        # Even though we use PUSH notifications to quickly react to cloud-events,
        # we also rely on a super-relaxed polling system which allows us to recover from
        # state inconsistency that might arise when connection quality is not good enough.
        return True

    @property
    def is_on(self) -> bool:
        return self._device.is_on(channel=self._channel_id)

    async def async_turn_off(self, **kwargs) -> None:
        await self._device.async_turn_off(channel=self._channel_id)

    async def async_turn_on(self, **kwargs) -> None:
        await self._device.async_turn_on(channel=self._channel_id)

    def turn_on(self, **kwargs: Any) -> None:
        self.hass.async_add_executor_job(self.async_turn_on)

    def turn_off(self, **kwargs: Any) -> None:
        self.hass.async_add_executor_job(self.async_turn_off)

    async def _async_push_notification_received(self, *args, **kwargs):
        _LOGGER.debug("Received push notification...")
        self.async_schedule_update_ha_state(force_refresh=False)

    async def async_added_to_hass(self) -> None:
        self._device.register_push_notification_handler_coroutine(self._async_push_notification_received)

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_push_notification_handler_coroutine(self._async_push_notification_received)


async def async_setup_entry(hass, config_entry, async_add_entities):
    # Identify all the devices that expose the ToggleX capability
    # TODO: do we need to care about Toggle capability?
    manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
    plugs = manager.find_devices(device_class=ToggleXMixin)
    switch_entities = []
    for plug in plugs:
        for channel_index, channel in enumerate(plug.channels):
            w = SwitchEntityWrapper(device=plug, channel=channel_index)
            switch_entities.append(w)
            hass.data[DOMAIN][HA_SWITCH][w.unique_id] = w
    async_add_entities(switch_entities, True)


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.info("SETUP PLATFORM")
    pass
