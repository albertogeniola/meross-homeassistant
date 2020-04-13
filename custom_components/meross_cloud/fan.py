import logging
from typing import Any, Optional

from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
from meross_iot.cloud.client_status import ClientStatus
from meross_iot.cloud.devices.humidifier import GenericHumidifier, SprayMode
from meross_iot.manager import MerossManager
from meross_iot.meross_event import (DeviceOnlineStatusEvent,
                                     HumidifierSpryEvent)

from .common import (DOMAIN, HA_FAN, MANAGER, ConnectionWatchDog, cloud_io, MerossEntityWrapper)

_LOGGER = logging.getLogger(__name__)


class MerossSmartHumidifier(FanEntity, MerossEntityWrapper):
    """
    At the time of writing, Homeassistant does not offer any specific device implementation that we can extend
    for implementing the smart humidifier. We'll exploit the fan entity to do so
    """

    def __init__(self, device: GenericHumidifier):
        self._device = device
        self._id = device.uuid

        # Device state
        self._available = True  # Assume the mqtt client is connected
        self._first_update_done = False

    @cloud_io()
    def update(self):
        if self._device.online:
            self._device.get_status(force_status_refresh=True)
            self._first_update_done = True

    def device_event_handler(self, evt):
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

    async def async_added_to_hass(self) -> None:
        self._device.register_event_callback(self.device_event_handler)

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_event_callback(self.device_event_handler)

    @property
    def available(self) -> bool:
        # A device is available if the client library is connected to the MQTT broker and if the
        # device we are contacting is online
        return self._available and self._device.online

    @property
    def is_on(self) -> bool:
        if not self._first_update_done:
            # Schedule update and return
            self.schedule_update_ha_state(True)
            return None

        # This device is considered "on" if spry mode is continuous or intermittent
        spry_mode = SprayMode(self._device.get_status().get('spray')[0].get('mode'))
        return spry_mode != SprayMode.OFF

    @property
    @cloud_io(default_return_value=None)
    def speed(self) -> Optional[str]:
        if not self._first_update_done:
            # Schedule update and return
            self.schedule_update_ha_state(True)
            return None
        spry_mode = SprayMode(self._device.get_status().get('spray')[0].get('mode'))
        return spry_mode.name

    @property
    def supported_features(self) -> int:
        return 0 | SUPPORT_SET_SPEED

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [e.name for e in SprayMode]

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
        if speed is None:
            mode = SprayMode.CONTINUOUS
        else:
            mode = SprayMode[speed]

        self._device.set_spray_mode(mode)

    @cloud_io()
    def turn_off(self, **kwargs: Any) -> None:
        self._device.set_spray_mode(SprayMode.OFF)

    @property
    def name(self) -> Optional[str]:
        return self._device.name

    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._id)},
            'name': self._device.name,
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
