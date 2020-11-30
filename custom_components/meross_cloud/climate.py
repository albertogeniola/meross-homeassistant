import logging
from datetime import timedelta
from typing import Optional, Iterable, List

from homeassistant.components.climate import SUPPORT_TARGET_TEMPERATURE, SUPPORT_PRESET_MODE, HVAC_MODE_OFF, \
    HVAC_MODE_HEAT
from homeassistant.components.climate.const import HVAC_MODE_AUTO, HVAC_MODE_COOL, CURRENT_HVAC_IDLE, CURRENT_HVAC_HEAT, \
    CURRENT_HVAC_OFF, CURRENT_HVAC_COOL
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from meross_iot.controller.device import BaseDevice
from meross_iot.controller.known.subdevice import Mts100v3Valve
from meross_iot.manager import MerossManager
from meross_iot.model.enums import OnlineStatus, Namespace, ThermostatV3Mode
from meross_iot.model.exception import CommandTimeoutError
from meross_iot.model.push.generic import GenericPushNotification

from .common import (PLATFORM, MANAGER, log_exception, RELAXED_SCAN_INTERVAL, calculate_valve_id,
                     extract_subdevice_notification_data)

# Conditional import for switch device
try:
    from homeassistant.components.climate import ClimateEntity
except ImportError:
    from homeassistant.components.climate import ClimateDevice as ClimateEntity


_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=RELAXED_SCAN_INTERVAL)


class ValveEntityWrapper(ClimateEntity):
    """Wrapper class to adapt the Meross switches into the Homeassistant platform"""

    def __init__(self, device: Mts100v3Valve):
        self._device = device

        # If the current device has more than 1 channel, we need to setup the device name and id accordingly
        self._id = calculate_valve_id(device.internal_id)
        self._entity_name = "{} ({})".format(device.name, device.type)

        # For now, we assume that every Meross Thermostat supports the following modes.
        # This might be improved in the future by looking at the device abilities via get_abilities()
        self._flags = 0
        self._flags |= SUPPORT_TARGET_TEMPERATURE
        self._flags |= SUPPORT_PRESET_MODE

    # region Device wrapper common methods
    async def async_update(self):
        if self._device.online_status == OnlineStatus.ONLINE:
            try:
                await self._device.async_update()
            except CommandTimeoutError as e:
                log_exception(logger=_LOGGER, device=self._device)
                pass

    async def async_added_to_hass(self) -> None:
        self._device.register_push_notification_handler_coroutine(self._async_push_notification_received)
        self.hass.data[PLATFORM]["ADDED_ENTITIES_IDS"].add(self.unique_id)

    async def _async_push_notification_received(self, namespace: Namespace, data: dict, device_internal_id: str):
        update_state = False
        full_update = False

        if namespace == Namespace.CONTROL_UNBIND:
            _LOGGER.warning(f"Received unbind event. Removing device {self.name} from HA")
            await self.platform.async_remove_entity(self.entity_id)
        elif namespace == Namespace.SYSTEM_ONLINE:
            _LOGGER.warning(f"Device {self.name} reported online event.")
            online = OnlineStatus(int(data.get('online').get('status')))
            update_state = True
            full_update = online == OnlineStatus.ONLINE
        elif namespace == Namespace.HUB_ONLINE:
            _LOGGER.warning(f"Device {self.name} reported (HUB) online event.")
            online_event_data = extract_subdevice_notification_data(data=data, 
                                                                    filter_accessor='online', 
                                                                    subdevice_id=self._device.subdevice_id)
            online = OnlineStatus(int(online_event_data.get('status')))
            update_state = True
            full_update = online == OnlineStatus.ONLINE
        else:
            update_state = True
            full_update = False

        # In all other cases, just tell HA to update the internal state representation
        if update_state:
            self.async_schedule_update_ha_state(force_refresh=full_update)

    async def async_will_remove_from_hass(self) -> None:
        self._device.unregister_push_notification_handler_coroutine(self._async_push_notification_received)
        self.hass.data[PLATFORM]["ADDED_ENTITIES_IDS"].remove(self.unique_id)

    # endregion

    # region Device wrapper common properties
    @property
    def unique_id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._entity_name

    @property
    def device_info(self):
        return {
            'identifiers': {(PLATFORM, self._device.internal_id)},
            'name': self._device.name,
            'manufacturer': 'Meross',
            'model': self._device.type + " " + self._device.hardware_version,
            'sw_version': self._device.firmware_version
        }

    @property
    def available(self) -> bool:
        # A device is available if the client library is connected to the MQTT broker and if the
        # device we are contacting is online
        return self._device.online_status == OnlineStatus.ONLINE

    @property
    def should_poll(self) -> bool:
        return False

    # endregion

    # region Platform-specific command methods
    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        # Turn on the device if not already on
        if hvac_mode == HVAC_MODE_OFF:
            await self._device.async_turn_off()
            return
        elif not self._device.is_on():
            await self._device.async_turn_on()

        if hvac_mode == HVAC_MODE_HEAT:
            await self._device.async_set_mode(ThermostatV3Mode.HEAT)
        elif hvac_mode == HVAC_MODE_AUTO:
            await self._device.async_set_mode(ThermostatV3Mode.AUTO)
        elif hvac_mode == HVAC_MODE_COOL:
            await self._device.async_set_mode(ThermostatV3Mode.COOL)
        else:
            _LOGGER.warning(f"Unsupported mode for this device ({self.name}): {hvac_mode}")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._device.async_set_mode(ThermostatV3Mode[preset_mode])

    async def async_set_temperature(self, **kwargs):
        target = kwargs.get('temperature')
        await self._device.async_set_target_temperature(target)

    # endregion

    # region Platform specific properties
    @property
    def temperature_unit(self) -> str:
        # TODO: Check if there is a way for retrieving the Merasurement Unit from the library
        return TEMP_CELSIUS

    @property
    def current_temperature(self) -> Optional[float]:
        return self._device.last_sampled_temperature

    @property
    def target_temperature(self) -> Optional[float]:
        return self._device.target_temperature

    @property
    def target_temperature_step(self) -> Optional[float]:
        return 0.5

    @property
    def max_temp(self) -> Optional[float]:
        return self._device.max_supported_temperature

    @property
    def min_temp(self) -> Optional[float]:
        return self._device.min_supported_temperature

    @property
    def hvac_mode(self) -> str:
        if not self._device.is_on():
            return HVAC_MODE_OFF
        elif self._device.mode == ThermostatV3Mode.AUTO:
            return HVAC_MODE_AUTO
        elif self._device.mode == ThermostatV3Mode.HEAT:
            return HVAC_MODE_HEAT
        elif self._device.mode == ThermostatV3Mode.COOL:
            return HVAC_MODE_COOL
        elif self._device.mode == ThermostatV3Mode.ECONOMY:
            return HVAC_MODE_AUTO
        elif self._device.mode == ThermostatV3Mode.CUSTOM:
            if self._device.last_sampled_temperature < self._device.target_temperature:
                return HVAC_MODE_HEAT
            else:
                return HVAC_MODE_COOL
        else:
            raise ValueError("Unsupported thermostat mode reported.")

    @property
    def hvac_action(self) -> Optional[str]:
        if not self._device.is_on():
            return CURRENT_HVAC_OFF
        elif self._device.is_heating:
            return CURRENT_HVAC_HEAT
        elif self._device.mode == HVAC_MODE_COOL:
            return CURRENT_HVAC_COOL
        else:
            return CURRENT_HVAC_IDLE

    @property
    def hvac_modes(self) -> List[str]:
        return [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_COOL]

    @property
    def preset_mode(self) -> str:
        return self._device.mode.name

    @property
    def preset_modes(self) -> List[str]:
        return [e.name for e in ThermostatV3Mode]

    @property
    def supported_features(self):
        return self._flags

    # endregion


async def _add_entities(hass: HomeAssistant, devices: Iterable[BaseDevice], async_add_entities):
    new_entities = []

    # Identify all the Mts100V3Valves
    devs = filter(lambda d: isinstance(d, Mts100v3Valve), devices)
    for d in devs:
        w = ValveEntityWrapper(device=d)
        if w.unique_id not in hass.data[PLATFORM]["ADDED_ENTITIES_IDS"]:
            new_entities.append(w)
        else:
            _LOGGER.info(f"Skipping device {w} as it was already added to registry once.")
    async_add_entities(new_entities, True)


async def async_setup_entry(hass, config_entry, async_add_entities):
    manager = hass.data[PLATFORM][MANAGER]  # type:MerossManager
    devices = manager.find_devices()
    await _add_entities(hass=hass, devices=devices, async_add_entities=async_add_entities)

    # Register a listener for the Bind push notification so that we can add new entities at runtime
    async def platform_async_add_entities(push_notification: GenericPushNotification, target_devices: List[BaseDevice]):
        if push_notification.namespace == Namespace.CONTROL_BIND \
                or push_notification.namespace == Namespace.SYSTEM_ONLINE \
                or push_notification.namespace == Namespace.HUB_ONLINE:

            # TODO: Discovery needed only when device becomes online?
            await manager.async_device_discovery(push_notification.namespace == Namespace.HUB_ONLINE,
                                                 meross_device_uuid=push_notification.originating_device_uuid)
            devs = manager.find_devices(device_uuids=(push_notification.originating_device_uuid,))
            await _add_entities(hass=hass, devices=devs, async_add_entities=async_add_entities)

    # Register a listener for new bound devices
    manager.register_push_notification_handler_coroutine(platform_async_add_entities)


# TODO: Unload entry
# TODO: Remove entry


def setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass
