import logging

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE, SUPPORT_CLOSE, SUPPORT_OPEN, CoverDevice)
from homeassistant.const import (STATE_CLOSED, STATE_CLOSING, STATE_OPEN,
                                 STATE_OPENING, STATE_UNKNOWN)
from meross_iot.cloud.client_status import ClientStatus
from meross_iot.cloud.devices.door_openers import GenericGarageDoorOpener
from meross_iot.meross_event import (DeviceDoorStatusEvent,
                                     DeviceOnlineStatusEvent)

from .common import (DOMAIN, HA_COVER, MANAGER, ConnectionWatchDog, cloud_io, MerossEntityWrapper)

_LOGGER = logging.getLogger(__name__)

ATTR_DOOR_STATE = 'door_state'


class OpenGarageCover(CoverDevice, MerossEntityWrapper):
    """Representation of a OpenGarage cover."""

    def __init__(self, device: GenericGarageDoorOpener):

        # Device properties
        self._device = device
        self._id = device.uuid
        self._channel = 0

        if len(self._device.get_channels()) > 1:
            _LOGGER.error(f"Garage opener {self._id} has more than 1 channel. This is currently not supported.")

        # Device state
        self._available = True  # Assume the mqtt client is connected
        self._first_update_done = False
        self._opening = False
        self._closing = False

    @cloud_io()
    def update(self):
        if self._device.online:
            self._device.get_status(force_status_refresh=True)
            # Reset derived states
            self._opening = False
            self._closing = False
            # Mark first update done
            self._first_update_done = True

    def device_event_handler(self, evt):
        # Whenever an open/closed push notitication is received, make sure to reset the
        # derived state
        if isinstance(evt, DeviceDoorStatusEvent):
            if evt.channel == self._channel:
                if evt.door_state in ('open', 'closed'):
                    self._opening = False
                    self._closing = False

        # Update the device state when an event occurs
        self.schedule_update_ha_state(False)

    def notify_client_state(self, status: ClientStatus):
        # When a connection change occurs, update the internal state
        if status == ClientStatus.SUBSCRIBED:
            # If we are connecting back, schedule a full refresh of the device
            self.schedule_update_ha_state(True)
        else:
            # In any other case, mark the device unavailable
            # and only update the UI
            self._available = False
            self.schedule_update_ha_state(False)

    @property
    def name(self) -> str:
        """Return the name of the cover."""
        return self._device.name

    @property
    def available(self) -> bool:
        # A device is available if the client library is connected to the MQTT broker and if the
        # device we are contacting is online
        return self._available and self._device.online

    @property
    @cloud_io(default_return_value=True)
    def is_closed(self):
        if not self._first_update_done:
            # Schedule update and return
            self.schedule_update_ha_state(True)
            return None

        # The low-level IO library, returns TRUE if the garage door is open, false otherwise.
        return not self._device.get_status(False).get(self._channel)

    @property
    @cloud_io(default_return_value=False)
    def is_open(self):
        if not self._first_update_done:
            # Schedule update and return
            self.schedule_update_ha_state(True)
            return None

        # The low-level IO library, returns TRUE if the garage door is open, false otherwise.
        return self._device.get_status(False).get(self._channel)

    @property
    @cloud_io(default_return_value=False)
    def is_opening(self):
        if not self._first_update_done:
            # Schedule update and return
            self.schedule_update_ha_state(True)
            return None

        # The low-level IO library, returns TRUE if the garage door is open, false otherwise.
        return self._opening

    @property
    @cloud_io(default_return_value=False)
    def is_closing(self):
        if not self._first_update_done:
            # Schedule update and return
            self.schedule_update_ha_state(True)
            return None
        return self._closing

    @cloud_io()
    def close_cover(self, **kwargs):
        """Close the cover."""
        is_closed = not self._device.get_status(False).get(self._channel)
        is_closed_or_closing = is_closed or self._closing
        if not is_closed_or_closing:
            self._device.close_door(channel=self._channel, ensure_closed=True)
            self._closing = True
            # We changed the state, thus we need to notify HA about it
            if self.enabled:
                self.schedule_update_ha_state(False)

    @cloud_io()
    def open_cover(self, **kwargs):
        """Open the cover."""
        is_open = self._device.get_status(False).get(self._channel)
        is_open_or_opening = is_open or self._opening

        if not is_open_or_opening:
            self._device.open_door(channel=self._channel, ensure_opened=True)
            self._opening = True
            # We changed the state, thus we need to notify HA about it
            if self.enabled:
                self.schedule_update_ha_state(False)

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def unique_id(self) -> str:
        # Since Meross plugs may have more than 1 switch, we need to provide a composed ID
        # made of uuid and channel
        return self._id

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_GARAGE

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._device.uuid)},
            'name': self._device.name,
            'manufacturer': 'Meross',
            'model': self._device.type + " " + self._device.hwversion,
            'sw_version': self._device.fwversion
        }

    async def async_added_to_hass(self) -> None:
        self._device.register_event_callback(self.device_event_handler)

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_event_callback(self.device_event_handler)


async def async_setup_entry(hass, config_entry, async_add_entities):
    def sync_logic():
        cover_entities = []
        manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
        openers = manager.get_devices_by_kind(GenericGarageDoorOpener)

        for opener in openers:  # type: GenericGarageDoorOpener
            w = OpenGarageCover(device=opener)
            cover_entities.append(w)
            hass.data[DOMAIN][HA_COVER][w.unique_id] = w
        return cover_entities

    # Register a connection watchdog to notify devices when connection to the cloud MQTT goes down.
    manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
    watchdog = ConnectionWatchDog(hass=hass, platform=HA_COVER)
    manager.register_event_handler(watchdog.connection_handler)

    cover_entities = await hass.async_add_executor_job(sync_logic)
    async_add_entities(cover_entities)


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
