from homeassistant.components.switch import SwitchDevice
from meross_iot.cloud.devices.power_plugs import GenericPlug
from meross_iot.meross_event import DeviceOnlineStatusEvent, DeviceSwitchStatusEvent

from .common import DOMAIN, MANAGER, calculate_switch_id
import logging


_LOGGER = logging.getLogger(__name__)


class SwitchEntityWrapper(SwitchDevice):
    """Wrapper class to adapt the Meross switches into the Homeassistant platform"""

    def __init__(self, device: GenericPlug, channel: int):
        # Device State
        self._is_on = None
        self._is_online = None

        # Reference to the device object
        self._device = device

        # Devide properties
        self._channel_id = channel
        self._device_id = device.uuid
        self._device_name = self._device.name

        # If the current device has more than 1 channel, we need to setup the device name and id accordingly
        if len(device.get_channels())>1:
            self._id = calculate_switch_id(self._device.uuid, channel)
            channelData = self._device.get_channels()[channel]
            self._entity_name = "{} - {}".format(self._device.name, channelData.get('devName', 'Main Switch'))
        else:
            self._id = self._device.uuid
            self._entity_name = self._device.name

        # Load the current device status
        self._is_online = self._device.online

        device.register_event_callback(self.handler)

    def handler(self, evt):
        if isinstance(evt, DeviceOnlineStatusEvent):
            if evt.status not in ["online", "offline"]:
                raise ValueError("Invalid online status")
            self._is_online = evt.status == "online"
        elif isinstance(evt, DeviceSwitchStatusEvent):
            if evt.channel_id == self._channel_id:
                self._is_on = evt.switch_state
        else:
            # TODO
            pass

        # When receiving an event, let's immediately trigger the update state
        self.async_schedule_update_ha_state(True)

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
        # Although we rely on PUSH notification to promptly update our state
        # sometimes polling helps when connection is dropped and the underlying library is not
        # pushing any update
        # TODO
        return False

    @property
    def is_on(self) -> bool:
        return self._is_on

    def turn_off(self, **kwargs) -> None:
        try:
            self._device.turn_off_channel(self._channel_id)
        except:
            _LOGGER.exception("Error when turning off the device %s" % self._device_name)

    def turn_on(self, **kwargs) -> None:
        try:
            self._device.turn_on_channel(self._channel_id)
        except:
            _LOGGER.exception("Error when turning on the device %s" % self._device_name)


async def async_setup_entry(hass, config_entry, async_add_entities):
    switch_entities = []
    manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
    plugs = manager.get_devices_by_kind(GenericPlug)

    for plug in plugs:  # type: GenericPlug
        # Every Meross plug might have multiple switches onboard. For this reason we need to
        # instantiate multiple switch entities for every channel.
        for channel_index, channel in enumerate(plug.get_channels()):
            w = SwitchEntityWrapper(device=plug, channel=channel_index)
            switch_entities.append(w)

    async_add_entities(switch_entities)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass

