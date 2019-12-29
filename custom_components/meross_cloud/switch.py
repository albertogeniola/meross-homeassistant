from homeassistant.components.switch import SwitchDevice
from meross_iot.cloud.devices.power_plugs import GenericPlug

from .common import DOMAIN, MANAGER, calculate_switch_id


class SwitchEntityWrapper(SwitchDevice):
    """Wrapper class to adapt the Meross switches into the Homeassistant platform"""

    def __init__(self, device: GenericPlug, channel: int):
        self._device = device
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

        device.register_event_callback(self.handler)

    def handler(self, evt):
        self.async_schedule_update_ha_state(False)

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
        return self._device.online

    # TODO
    #@property
    #def device_state_attributes(self):
    #    """Return the state attributes of the device."""
    #    return self._emeter_params


    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        return None

    @property
    def should_poll(self) -> bool:
        # In general, we don't want HomeAssistant to poll this device.
        # Instead, we will notify HA when an event is received.
        return False

    @property
    def is_on(self) -> bool:
        # Note that the following method is not fetching info from the device over the network.
        # Instead, it is reading the device status from the state-dictionary that is handled by the library.
        return self._device.get_channel_status(self._channel_id)

    def turn_off(self, **kwargs) -> None:
        self._device.turn_off_channel(self._channel_id)

    def turn_on(self, **kwargs) -> None:
        self._device.turn_on_channel(self._channel_id)


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

