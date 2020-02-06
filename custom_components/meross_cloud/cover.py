import logging

from homeassistant.components.cover import (SUPPORT_CLOSE, SUPPORT_OPEN,
                                            CoverDevice, DEVICE_CLASS_GARAGE)
from homeassistant.const import (STATE_CLOSED, STATE_CLOSING, STATE_OPEN,
                                 STATE_OPENING, STATE_UNKNOWN)
from meross_iot.cloud.devices.door_openers import GenericGarageDoorOpener
from meross_iot.meross_event import MerossEventType

from .common import (DOMAIN, MANAGER)

_LOGGER = logging.getLogger(__name__)

ATTR_DOOR_STATE = 'door_state'


class OpenGarageCover(CoverDevice):
    """Representation of a OpenGarage cover."""

    def __init__(self, device: GenericGarageDoorOpener):
        """Initialize the cover."""
        self._state_before_move = STATE_UNKNOWN
        self._state = STATE_UNKNOWN
        self._device = device
        self._device_id = device.uuid
        self._id = device.uuid
        self._device_name = self._device.name
        device.register_event_callback(self.handler)

        if len(self._device.get_channels())>1:
            _LOGGER.error(f"Garage opener {self._id} has more than 1 channel. This is currently not supported.")

        self._channel = 0

        # If the device is online, we need to update its status from STATE_UNKNOWN
        if device.online and self._state == STATE_UNKNOWN:
            open = device.get_status().get(self._channel)
            if open:
                self._state = STATE_OPEN
            else:
                self._state = STATE_CLOSED

    def handler(self, evt) -> None:
        if evt.event_type == MerossEventType.GARAGE_DOOR_STATUS:
            if evt.channel == self._channel:
                # The underlying library only exposes "open" and "closed" statuses
                if evt.door_state == 'open':
                    self._state = STATE_OPEN
                elif evt.door_state == 'closed':
                    self._state = STATE_CLOSED
                else:
                    _LOGGER.error("Unknown/Invalid event door_state: %s" % evt.door_state)

        # In cny case update the UI
        self.async_schedule_update_ha_state(False)

    @property
    def name(self) -> str:
        """Return the name of the cover."""
        return self._device_name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.online

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

    def _door_callback(self, error, state):
        # TODO: check for errors
        self.async_schedule_update_ha_state(False)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        if self._state not in [STATE_CLOSED, STATE_CLOSING]:
            self._state_before_move = self._state
            self._state = STATE_CLOSING
            self._device.close_door(channel=self._channel, ensure_closed=True, callback=self._door_callback)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        if self._state not in [STATE_OPEN, STATE_OPENING]:
            self._state_before_move = self._state
            self._state = STATE_OPENING
            self._device.open_door(channel=self._channel, ensure_opened=True, callback=self._door_callback)

    def open_cover(self, **kwargs):
        if self._state not in [STATE_OPEN, STATE_OPENING]:
            self._state_before_move = self._state
            self._state = STATE_OPENING
            self._device.open_door(channel=self._channel, ensure_opened=True)

    def close_cover(self, **kwargs):
        """Close the cover."""
        if self._state not in [STATE_CLOSED, STATE_CLOSING]:
            self._state_before_move = self._state
            self._state = STATE_CLOSING
            self._device.close_door(channel=self._channel, ensure_closed=True)

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


async def async_setup_entry(hass, config_entry, async_add_entities):
    cover_entities = []
    manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
    openers = manager.get_devices_by_kind(GenericGarageDoorOpener)

    for opener in openers:  # type: GenericGarageDoorOpener
        w = OpenGarageCover(device=opener)
        cover_entities.append(w)

    async_add_entities(cover_entities)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
