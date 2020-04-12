import logging
from typing import Any, Optional

from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
from meross_iot.cloud.devices.humidifier import GenericHumidifier, SprayMode
from meross_iot.manager import MerossManager
from meross_iot.meross_event import (DeviceOnlineStatusEvent,
                                     HumidifierSpryEvent)

from .common import (DOMAIN, HA_FAN, MANAGER, ConnectionWatchDog, cloud_io)

_LOGGER = logging.getLogger(__name__)


class MerossSmartHumidifier(FanEntity):
    """
    At the time of writing, Homeassistant does not offer any specific device implementation that we can extend
    for implementing the smart humidifier. We'll exploit the fan entity to do so
    """

    def __init__(self, device: GenericHumidifier):
        self._device = device
        self._id = device.uuid
        self._device_name = device.name

        # Device state
        self._humidifier_mode = None
        self._is_on = None
        self._is_online = self._device.online

    def parse_spry_mode(self, spry_mode):
        if spry_mode == SprayMode.OFF:
            return False, self._humidifier_mode
        elif spry_mode == SprayMode.INTERMITTENT:
            return True, SprayMode.INTERMITTENT
        elif spry_mode == SprayMode.CONTINUOUS:
            return True, SprayMode.CONTINUOUS
        else:
            raise ValueError("Unsupported spry mode.")

    def device_event_handler(self, evt):
        if isinstance(evt, DeviceOnlineStatusEvent):
            _LOGGER.info("Device %s reported online status: %s" % (self._device.name, evt.status))
            if evt.status not in ["online", "offline"]:
                raise ValueError("Invalid online status")
            self._is_online = evt.status == "online"
        elif isinstance(evt, HumidifierSpryEvent):
            self._is_on, self._humidifier_mode = self.parse_spry_mode(evt.spry_mode)
        else:
            _LOGGER.warning("Unhandled/ignored event: %s" % str(evt))

        self.schedule_update_ha_state(False)

    @cloud_io()
    def update(self):
        state = self._device.get_status(True)
        self._is_online = self._device.online

        if self._is_online:
            self._is_on, self._humidifier_mode = self.parse_spry_mode(self._device.get_spray_mode())

    async def async_added_to_hass(self) -> None:
        self._device.register_event_callback(self.device_event_handler)

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_event_callback(self.device_event_handler)

    @property
    def available(self) -> bool:
        return self._is_online

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def speed(self) -> Optional[str]:
        if self._humidifier_mode is None:
            return None
        return self._humidifier_mode.name

    @property
    def supported_features(self) -> int:
        return 0 | SUPPORT_SET_SPEED

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [e.name for e in SprayMode if e != SprayMode.OFF]

    @cloud_io()
    def set_speed(self, speed: str) -> None:
        mode = SprayMode[speed]
        self._device.set_spray_mode(mode)

    @cloud_io()
    def set_direction(self, direction: str) -> None:
        # Not supported
        pass

    @cloud_io()
    def turn_on(self, speed: Optional[str] = None, **kwargs) -> None:
        # Assume the user wants to trigger the last mode
        mode = self._humidifier_mode
        # If a specific speed was provided, override the last mode
        if speed is not None:
            mode = SprayMode[speed]
        # Otherwise, assume we want intermittent mode
        if mode is None:
            mode = SprayMode.INTERMITTENT

        self._device.set_spray_mode(mode)

    @cloud_io()
    def turn_off(self, **kwargs: Any) -> None:
        self._device.set_spray_mode(SprayMode.OFF)

    @property
    def name(self) -> Optional[str]:
        return self._device_name

    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._id)},
            'name': self._device_name,
            'manufacturer': 'Meross',
            'model': self._device.type + " " + self._device.hwversion,
            'sw_version': self._device.fwversion
        }

    @property
    def should_poll(self) -> bool:
        """
        This device handles stat update via push notification
        :return:
        """
        return False


async def async_setup_entry(hass, config_entry, async_add_entities):
    def sync_logic():

        fan_devices = []
        manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager

        # Add smart humidifiers
        humidifiers = manager.get_devices_by_kind(GenericHumidifier)
        for humidifier in humidifiers:
            h = MerossSmartHumidifier(device=humidifier)
            fan_devices.append(h)
            hass.data[DOMAIN][HA_FAN][h.unique_id] = h

        return fan_devices

    # Register a connection watchdog to notify devices when connection to the cloud MQTT goes down.
    manager = hass.data[DOMAIN][MANAGER]  # type:MerossManager
    watchdog = ConnectionWatchDog(hass=hass, platform=HA_FAN)
    manager.register_event_handler(watchdog.connection_handler)

    devices = await hass.async_add_executor_job(sync_logic)
    async_add_entities(devices)
