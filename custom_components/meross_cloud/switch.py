import logging

# Fallback import in case of old HA releases
try:
    from homeassistant.components.switch import SwitchEntity
except ImportError:
    from homeassistant.components.switch import SwitchDevice as SwitchEntity

from meross_iot.cloud.client_status import ClientStatus
from meross_iot.cloud.devices.power_plugs import GenericPlug
from meross_iot.cloud.exceptions.CommandTimeoutException import CommandTimeoutException
from meross_iot.manager import MerossManager

from .common import (DOMAIN, HA_SWITCH, MANAGER, calculate_switch_id, ConnectionWatchDog, MerossEntityWrapper,
                     log_exception)

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1


class SwitchEntityWrapper(SwitchEntity, MerossEntityWrapper):
    """Wrapper class to adapt the Meross switches into the Homeassistant platform"""

    def __init__(self, device: GenericPlug, channel: int):
        self._device = device

        # If the current device has more than 1 channel, we need to setup the device name and id accordingly
        if len(device.get_channels()) > 1:
            self._id = calculate_switch_id(device.uuid, channel)
            channel_data = device.get_channels()[channel]
            self._entity_name = "{} - {}".format(device.name, channel_data.get('devName', 'Main Switch'))
        else:
            self._id = device.uuid
            self._entity_name = device.name

        # Device properties
        self._channel_id = channel
        self._available = True  # Assume the mqtt client is connected
        self._first_update_done = False
        self._ignore_update = False

    def update(self):
        if self._ignore_update:
            _LOGGER.warning("Skipping UPDATE as ignore_update is set.")
            return

        if self._device.online:
            try:
                self._device.get_status(force_status_refresh=True)
                self._first_update_done = True
            except CommandTimeoutException as e:
                log_exception(logger=_LOGGER, device=self._device)
                pass

    def device_event_handler(self, evt):
        # Update the device state when an event occurs
        self.schedule_update_ha_state(False)

    def notify_client_state(self, status: ClientStatus):
        # When a connection change occurs, update the internal state
        # If we are connecting back, schedule a full refresh of the device
        # In any other case, mark the device unavailable
        # and only update the UI
        client_online = status == ClientStatus.SUBSCRIBED
        self._available = client_online
        self.schedule_update_ha_state(True)

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
            'identifiers': {(DOMAIN, self._device.uuid)},
            'name': self._device.name,
            'manufacturer': 'Meross',
            'model': self._device.type + " " + self._device.hwversion,
            'sw_version': self._device.fwversion
        }

    @property
    def available(self) -> bool:
        # A device is available if the client library is connected to the MQTT broker and if the
        # device we are contacting is online
        return self._available and self._device.online

    @property
    def should_poll(self) -> bool:
        # The current state propagation is handled via PUSH notification from the server.
        # Therefore, we don't want Homeassistant to waste resources to poll the server.
        return False

    @property
    def is_on(self) -> bool:
        if not self._first_update_done:
            # Schedule update and return
            self.schedule_update_ha_state(True)
            return False

        return self._device.get_status(channel=self._channel_id)

    @property
    def assumed_state(self) -> bool:
        return not self._first_update_done

    def turn_off(self, **kwargs) -> None:
        self._device.turn_off_channel(self._channel_id)

    def turn_on(self, **kwargs) -> None:
        self._device.turn_on_channel(self._channel_id)

    async def async_added_to_hass(self) -> None:
        self._device.register_event_callback(self.device_event_handler)
        self._ignore_update = False

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_event_callback(self.device_event_handler)
        self._ignore_update = True


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
    async_add_entities(switch_entities, True)


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.info("SETUP PLATFORM")
    pass
