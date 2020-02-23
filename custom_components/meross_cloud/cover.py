import logging
from homeassistant.components.cover import (SUPPORT_CLOSE, SUPPORT_OPEN,
                                            CoverDevice, DEVICE_CLASS_GARAGE)
from homeassistant.const import (STATE_CLOSED, STATE_CLOSING, STATE_OPEN,
                                 STATE_OPENING, STATE_UNKNOWN)
from meross_iot.cloud.devices.door_openers import GenericGarageDoorOpener
from meross_iot.meross_event import MerossEventType, DeviceDoorStatusEvent, DeviceOnlineStatusEvent
from .common import (DOMAIN, MANAGER, AbstractMerossEntityWrapper, cloud_io, HA_COVER)

_LOGGER = logging.getLogger(__name__)

ATTR_DOOR_STATE = 'door_state'


class OpenGarageCover(CoverDevice, AbstractMerossEntityWrapper):
    """Representation of a OpenGarage cover."""

    def __init__(self, device: GenericGarageDoorOpener):
        super().__init__(device)

        # Device properties
        self._device = device
        self._device_id = device.uuid
        self._id = device.uuid
        self._device_name = self._device.name
        self._channel = 0

        if len(self._device.get_channels()) > 1:
            _LOGGER.error(f"Garage opener {self._id} has more than 1 channel. This is currently not supported.")

        # Device specific state
        self._state = STATE_UNKNOWN
        self._state_before_move = STATE_UNKNOWN

        self._is_online = self._device.online
        if self._is_online:
            self.update()

    def force_state_update(self, ui_only=False):
        if not self.enabled:
            return

        force_refresh = not ui_only
        self.schedule_update_ha_state(force_refresh=force_refresh)

    @cloud_io
    def update(self):
        data = self._device.get_status(force_status_refresh=True)
        self._is_online = self._device.online
        if self._is_online:
            open = data.get(self._channel)
            if open:
                self._state = STATE_OPEN
            else:
                self._state = STATE_CLOSED

    def device_event_handler(self, evt):
        # Any event received from the device causes the reset of the error state
        self.reset_error_state()

        # Handle here events that are common to all the wrappers
        if isinstance(evt, DeviceOnlineStatusEvent):
            _LOGGER.info("Device %s reported online status: %s" % (self._device.name, evt.status))
            if evt.status not in ["online", "offline"]:
                raise ValueError("Invalid online status")
            self._is_online = evt.status == "online"

        elif isinstance(evt, DeviceDoorStatusEvent) and evt.channel == self._channel:
            # The underlying library only exposes "open" and "closed" statuses
            if evt.door_state == 'open':
                self._state = STATE_OPEN
            elif evt.door_state == 'closed':
                self._state = STATE_CLOSED
            else:
                _LOGGER.error("Unknown/Invalid event door_state: %s" % evt.door_state)
        else:
            _LOGGER.warning("Unhandled/ignored event: %s" % str(evt))

        # When receiving an event, let's immediately trigger the update state
        self.schedule_update_ha_state(False)

    @property
    def name(self) -> str:
        """Return the name of the cover."""
        return self._device_name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_online

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._state == STATE_CLOSED

    @property
    def is_open(self):
        """Return if the cover is closed."""
        return self._state == STATE_OPEN

    @property
    def is_opening(self):
        return self._state == STATE_OPENING

    @property
    def is_closing(self):
        return self._state == STATE_CLOSING

    @cloud_io
    def close_cover(self, **kwargs):
        """Close the cover."""
        if self._state not in [STATE_CLOSED, STATE_CLOSING]:
            self._state_before_move = self._state
            self._state = STATE_CLOSING
            self._device.close_door(channel=self._channel, ensure_closed=True)

            # We changed the state, thus we need to notify HA about it
            if self.enabled:
                self.schedule_update_ha_state(False)

    @cloud_io
    def open_cover(self, **kwargs):
        """Open the cover."""
        if self._state not in [STATE_OPEN, STATE_OPENING]:
            self._state_before_move = self._state
            self._state = STATE_OPENING
            self._device.open_door(channel=self._channel, ensure_opened=True)

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
            'identifiers': {(DOMAIN, self._device_id)},
            'name': self._device_name,
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

    cover_entities = await hass.async_add_executor_job(sync_logic)
    async_add_entities(cover_entities)


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
