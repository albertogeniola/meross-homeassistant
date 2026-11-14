import logging
from datetime import timedelta
from typing import Dict

from meross_iot.controller.device import BaseDevice
from meross_iot.controller.subdevice import Ms405Sensor
from meross_iot.manager import MerossManager
from meross_iot.model.enums import OnlineStatus
from meross_iot.model.http.device import HttpDeviceInfo

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import MerossDevice
from .common import (DOMAIN, MANAGER, HA_BINARY_SENSOR,
                     HA_SENSOR_POLL_INTERVAL_SECONDS, DEVICE_LIST_COORDINATOR)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=HA_SENSOR_POLL_INTERVAL_SECONDS)


class WaterLeakSensor(MerossDevice, BinarySensorEntity):
    """Wrapper class to adapt the Meross MS405 water-leak sensor into the Homeassistant platform"""
    _device:Ms405Sensor

    def __init__(self, device: BaseDevice, device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]], channel: int = 0):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_BINARY_SENSOR)

        self._attr_device_class = BinarySensorDeviceClass.MOISTURE

    @property
    def should_poll(self) -> bool:
        return True

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self._device.online_status == OnlineStatus.ONLINE:
            return self._device.is_leaking

        return None

# ----------------------------------------------
# PLATFORM METHODS
# ----------------------------------------------
async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    def entity_adder_callback():
        """Discover and adds new Meross entities"""
        manager: MerossManager = hass.data[DOMAIN][MANAGER]  # type
        coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
        devices = manager.find_devices()

        new_entities = []

        # For now, we handle the following sensors:
        # -> Water leak MS40
        water_lean_sensors = filter(lambda d: isinstance(d, Ms405Sensor), devices)

        # Add Energy Sensors
        for wls in water_lean_sensors:
            channels = [c.index for c in wls.channels] if len(wls.channels) > 0 else [0]
            for channel_index in channels:
                new_entities.append(
                     WaterLeakSensor(device=wls, device_list_coordinator=coordinator, channel=channel_index))

        unique_new_devs = filter(lambda d: d.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"], new_entities)
        async_add_entities(list(unique_new_devs), True)

    coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
    coordinator.async_add_listener(entity_adder_callback)
    # Run the entity adder a first time during setup
    entity_adder_callback()


# TODO: Implement entry unload
# TODO: Unload entry
# TODO: Remove entry


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
