import logging

from homeassistant.components.switch import SwitchDevice
from meross_iot.cloud.devices.power_plugs import GenericPlug
from meross_iot.manager import MerossManager
from meross_iot.meross_event import (DeviceOnlineStatusEvent,
                                     DeviceSwitchStatusEvent)

from .common import (DOMAIN, HA_SWITCH, MANAGER, calculate_switch_id, ConnectionWatchDog, cloud_io)

_LOGGER = logging.getLogger(__name__)


class SwitchEntityWrapper(SwitchDevice):
    """Wrapper class to adapt the Meross switches into the Homeassistant platform"""

    def __init__(self, device: GenericPlug, channel: int):
        self._device = device

        # If the current device has more than 1 channel, we need to setup the device name and id accordingly
        if len(device.get_channels()) > 1:
            self._id = calculate_switch_id(device.uuid, channel)
            channelData = device.get_channels()[channel]
            self._entity_name = "{} - {}".format(device.name, channelData.get('devName', 'Main Switch'))
        else:
            self._id = device.uuid
            self._entity_name = device.name

        # Device properties
        self._channel_id = channel
        self._device_id = device.uuid
        self._device_name = device.name

        # Device state
        self._is_on = None
        self._is_online = self._device.online
        if self._is_online:
            self.update()

    @cloud_io()
    def update(self):
        self._device.get_status(force_status_refresh=True)
        self._is_online = self._device.online

        if self._is_online:
            self._is_on = self._device.get_channel_status(self._channel_id)

    def device_event_handler(self, evt):
        # Handle here events that are common to all the wrappers
        if isinstance(evt, DeviceOnlineStatusEvent):
            _LOGGER.info("Device %s reported online status: %s" % (self._device.name, evt.status))
            if evt.status not in ["online", "offline"]:
                raise ValueError("Invalid online status")
            self._is_online = evt.status == "online"

        elif isinstance(evt, DeviceSwitchStatusEvent):
            if evt.channel_id == self._channel_id:
                self._is_on = evt.switch_state
        else:
            _LOGGER.warning("Unhandled/ignored event: %s" % str(evt))

        # When receiving an event, let's immediately trigger the update state
        self.schedule_update_ha_state(False)

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
            'identifiers': {(DOMAIN, self._device_id)},
            'name': self._device_name,
            'manufacturer': 'Meross',
            'model': self._device.type + " " + self._device.hwversion,
            'sw_version': self._device.fwversion
        }

    @property
    def available(self) -> bool:
        # A device is available if it's online
        return self._is_online

    @property
    def should_poll(self) -> bool:
        # The current state propagation is handled via PUSH notification from the server.
        # Therefore, we don't want Homeassistant to waste resources to poll the server.
        return False

    @property
    def is_on(self) -> bool:
        return self._is_on

    @cloud_io()
    def turn_off(self, **kwargs) -> None:
        self._device.turn_off_channel(self._channel_id)

    @cloud_io()
    def turn_on(self, **kwargs) -> None:
        self._device.turn_on_channel(self._channel_id)

    async def async_added_to_hass(self) -> None:
        self._device.register_event_callback(self.device_event_handler)

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_event_callback(self.device_event_handler)


async def async_setup_entry(hass, config_entry, async_add_entities):
    def sync_logic():
        switch_entities = []
        manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
        plugs = manager.get_devices_by_kind(GenericPlug)

        for plug in plugs:  # type: GenericPlug
            # Every Meross plug might have multiple switches onboard. For this reason we need to
            # instantiate multiple switch entities for every channel.
            for channel_index, channel in enumerate(plug.get_channels()):
                w = SwitchEntityWrapper(device=plug, channel=channel_index)
                switch_entities.append(w)
                hass.data[DOMAIN][HA_SWITCH][w.unique_id] = w
        return switch_entities

    # Register a connection watchdog to notify devices when connection to the cloud MQTT goes down.
    manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
    watchdog = ConnectionWatchDog(hass=hass, platform=HA_SWITCH)
    manager.register_event_handler(watchdog.connection_handler)

    switch_entities = await hass.async_add_executor_job(sync_logic)
    async_add_entities(switch_entities)


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
