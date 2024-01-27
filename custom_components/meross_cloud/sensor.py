import logging
from datetime import datetime
from datetime import timedelta
from typing import Optional, Dict

from meross_iot.controller.device import BaseDevice
from meross_iot.controller.mixins.consumption import ConsumptionXMixin
from meross_iot.controller.mixins.electricity import ElectricityMixin
from meross_iot.controller.subdevice import Ms100Sensor, Mts100v3Valve
from meross_iot.manager import MerossManager
from meross_iot.model.enums import OnlineStatus
from meross_iot.model.exception import CommandTimeoutError
from meross_iot.model.http.device import HttpDeviceInfo

from homeassistant.components.sensor import SensorStateClass, SensorEntity, SensorDeviceClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfPower
from homeassistant.helpers.typing import StateType, HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import MerossDevice
from .common import (DOMAIN, MANAGER, log_exception, HA_SENSOR,
                     HA_SENSOR_POLL_INTERVAL_SECONDS, invoke_method_or_property, DEVICE_LIST_COORDINATOR)

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(seconds=HA_SENSOR_POLL_INTERVAL_SECONDS)


class GenericSensorWrapper(MerossDevice, SensorEntity):
    """Wrapper class to adapt the a generic Meross sensor into the Homeassistant platform"""

    def __init__(self,
                 sensor_class: str,
                 measurement_unit: Optional[str],
                 device_method_or_property: str,
                 state_class: str,
                 device: BaseDevice,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]],
                 channel: int = 0):
        super().__init__(
            device=device,
            channel=channel,
            device_list_coordinator=device_list_coordinator,
            platform=HA_SENSOR,
            supplementary_classifiers=[sensor_class, measurement_unit])

        # Make sure the given device supports exposes the device_method_or_property passed as arg
        if not hasattr(device, device_method_or_property):
            _LOGGER.error("The device %s (%s) does not expose property %s", device.uuid, device.name,
                          device_method_or_property)
            raise ValueError(f"The device {device} does not expose property {device_method_or_property}")

        self._device_method_or_property = device_method_or_property
        self._attr_native_unit_of_measurement = measurement_unit
        self._attr_device_class = sensor_class
        self._attr_state_class = state_class

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return invoke_method_or_property(self._device, self._device_method_or_property)


class Ms100TemperatureSensorWrapper(GenericSensorWrapper):
    def __init__(self, device: Ms100Sensor, device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]],
                 channel: int = 0):
        super().__init__(
            sensor_class=SensorDeviceClass.TEMPERATURE,
            measurement_unit=UnitOfTemperature.CELSIUS,
            device_method_or_property='last_sampled_temperature',
            state_class=SensorStateClass.MEASUREMENT,
            device=device,
            device_list_coordinator=device_list_coordinator,
            channel=channel)


class Ms100HumiditySensorWrapper(GenericSensorWrapper):
    def __init__(self, device: Ms100Sensor, device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]],
                 channel: int = 0):
        super().__init__(sensor_class=SensorDeviceClass.HUMIDITY,
                         measurement_unit=PERCENTAGE,
                         device_method_or_property='last_sampled_humidity',
                         state_class=SensorStateClass.MEASUREMENT,
                         device=device,
                         device_list_coordinator=device_list_coordinator,
                         channel=channel)


class Mts100TemperatureSensorWrapper(GenericSensorWrapper):
    _device: Mts100v3Valve

    def __init__(self, device: Mts100v3Valve,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]]):
        super().__init__(sensor_class=SensorDeviceClass.TEMPERATURE,
                         measurement_unit=UnitOfTemperature.CELSIUS,
                         device_method_or_property='last_sampled_temperature',
                         state_class=SensorStateClass.MEASUREMENT,
                         device_list_coordinator=device_list_coordinator,
                         device=device)

    async def async_update(self):
        if self._device.online_status == OnlineStatus.ONLINE:
            try:
                _LOGGER.debug(f"Refreshing instant metrics for device {self.name}")
                await self._device.async_get_temperature()
            except CommandTimeoutError as e:
                log_exception(logger=_LOGGER, device=self._device)

    @property
    def should_poll(self) -> bool:
        return True


class ElectricitySensorDevice(ElectricityMixin, BaseDevice):
    """ Helper type """
    pass

class EnergySensorDevice(ConsumptionXMixin, BaseDevice):
    """ Helper type """
    pass

class PowerSensorWrapper(GenericSensorWrapper):
    _device: ElectricitySensorDevice

    def __init__(self, device: ElectricitySensorDevice,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]], channel: int = 0):
        super().__init__(sensor_class=SensorDeviceClass.POWER,
                         measurement_unit=UnitOfPower.WATT,
                         device_method_or_property='get_last_sample',
                         state_class=SensorStateClass.MEASUREMENT,
                         device=device,
                         device_list_coordinator=device_list_coordinator,
                         channel=channel)

    @property
    def should_poll(self) -> bool:
        return True

    # For ElectricityMixin devices we need to explicitly call the async_get_instant_metrics
    async def async_update(self):
        if self._device.online_status == OnlineStatus.ONLINE:
            try:
                # We only call the explicit method if the sampled value is older than 10 seconds.
                power_info = self._device.get_last_sample(channel=self._channel_id)
                now = datetime.utcnow()
                if power_info is None or (now - power_info.sample_timestamp).total_seconds() > 10:
                    # Force device refresh
                    _LOGGER.info(f"Refreshing instant metrics for device {self.name}")
                    await self._device.async_get_instant_metrics(channel=self._channel_id)
                else:
                    # Use the cached value
                    _LOGGER.debug("Skipping data refresh for %s as its value is recent enough", self.name)

            except CommandTimeoutError as e:
                log_exception(logger=_LOGGER, device=self._device)
                pass

    @property
    def native_value(self) -> StateType:
        sample = self._device.get_last_sample(channel=self._channel_id)
        if sample is not None:
            return sample.power


class CurrentSensorWrapper(GenericSensorWrapper):
    _device: ElectricitySensorDevice

    def __init__(self, device: ElectricitySensorDevice,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]], channel: int = 0):
        super().__init__(sensor_class=SensorDeviceClass.CURRENT,
                         measurement_unit="A",
                         device_method_or_property='get_last_sample',
                         state_class=SensorStateClass.MEASUREMENT,
                         device=device,
                         device_list_coordinator=device_list_coordinator,
                         channel=channel)

    # For ElectricityMixin devices we need to explicitly call the async_Get_instant_metrics
    async def async_update(self):
        if self._device.online_status == OnlineStatus.ONLINE:
            try:
                # We only call the explicit method if the sampled value is older than 10 seconds.
                power_info = self._device.get_last_sample(channel=self._channel_id)
                now = datetime.utcnow()
                if power_info is None or (now - power_info.sample_timestamp).total_seconds() > 10:
                    # Force device refresh
                    _LOGGER.info(f"Refreshing instant metrics for device {self.name}")
                    await self._device.async_get_instant_metrics(channel=self._channel_id)
                else:
                    # Use the cached value
                    _LOGGER.debug(f"Skipping data refresh for {self.name} as its value is recent enough")

            except CommandTimeoutError as e:
                log_exception(logger=_LOGGER, device=self._device)
                pass

    @property
    def native_value(self) -> StateType:
        sample = self._device.get_last_sample(channel=self._channel_id)
        if sample is not None:
            return sample.current
        return 0

    @property
    def should_poll(self) -> bool:
        return True


class VoltageSensorWrapper(GenericSensorWrapper):
    _device: ElectricitySensorDevice

    def __init__(self, device: ElectricitySensorDevice,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]], channel: int = 0):
        super().__init__(sensor_class=SensorDeviceClass.VOLTAGE,
                         measurement_unit="V",
                         device_method_or_property='get_last_sample',
                         state_class=SensorStateClass.MEASUREMENT,
                         device=device,
                         device_list_coordinator=device_list_coordinator,
                         channel=channel)

    # For ElectricityMixin devices we need to explicitly call the async_Get_instant_metrics
    async def async_update(self):
        if self._device.online_status == OnlineStatus.ONLINE:
            try:
                # We only call the explicit method if the sampled value is older than 10 seconds.
                power_info = self._device.get_last_sample(channel=self._channel_id)
                now = datetime.utcnow()
                if power_info is None or (now - power_info.sample_timestamp).total_seconds() > 10:
                    # Force device refresh
                    _LOGGER.info(f"Refreshing instant metrics for device {self.name}")
                    await self._device.async_get_instant_metrics(channel=self._channel_id)
                else:
                    # Use the cached value
                    _LOGGER.debug(f"Skipping data refresh for {self.name} as its value is recent enough")

            except CommandTimeoutError as e:
                log_exception(logger=_LOGGER, device=self._device)
                pass

    @property
    def native_value(self) -> StateType:
        sample = self._device.get_last_sample(channel=self._channel_id)
        if sample is not None:
            return sample.voltage
        return 0

    @property
    def should_poll(self) -> bool:
        return True

class EnergySensorWrapper(GenericSensorWrapper):
    _device: EnergySensorDevice

    def __init__(self, device: EnergySensorDevice,
                 device_list_coordinator: DataUpdateCoordinator[Dict[str, HttpDeviceInfo]], channel: int = 0):
        super().__init__(sensor_class=SensorDeviceClass.ENERGY,
                         measurement_unit="kWh",
                         device_method_or_property='async_get_daily_power_consumption',
                         state_class=SensorStateClass.TOTAL_INCREASING,
                         device=device,
                         device_list_coordinator=device_list_coordinator,
                         channel=channel)

        # Device properties
        self._daily_consumption = None

    # For ElectricityMixin devices we need to explicitly call the async_Get_instant_metrics
    async def async_update(self):
        if self.online:
            await super().async_update()

            _LOGGER.info(f"Refreshing instant metrics for device {self.name}")
            self._daily_consumption = await self._device.async_get_daily_power_consumption(channel=self._channel_id)

    @property
    def native_value(self) -> StateType:
        if self._daily_consumption is not None:
            today = datetime.today()
            total = 0
            daystart = datetime(year=today.year, month=today.month, day=today.day, hour=0, second=0)
            for x in self._daily_consumption:
              if x['date'] == daystart:
                total = x['total_consumption_kwh']
            return total

    @property
    def should_poll(self) -> bool:
        return True

# ----------------------------------------------
# PLATFORM METHODS
# ----------------------------------------------
async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    def entity_adder_callback():
        """Discover and adds new Meross entities"""
        manager: MerossManager = hass.data[DOMAIN][MANAGER]  # type
        coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
        devices = manager.find_devices()

        new_entities = []

        # For now, we handle the following sensors:
        # -> Temperature-Humidity (Ms100Sensor)
        # -> Power-sensing smart plugs (Mss310)
        # -> MTS100 Valve temperature (MTS100V3)
        humidity_temp_sensors = filter(lambda d: isinstance(d, Ms100Sensor), devices)
        mts100_temp_sensors = filter(lambda d: isinstance(d, Mts100v3Valve), devices)
        power_sensors = filter(lambda d: isinstance(d, ElectricityMixin), devices)
        energy_sensors = filter(lambda d: isinstance(d, ConsumptionXMixin), devices)

        # Add MS100 Temperature & Humidity sensors
        for d in humidity_temp_sensors:
            new_entities.append(Ms100HumiditySensorWrapper(device=d, device_list_coordinator=coordinator, channel=0))
            new_entities.append(Ms100TemperatureSensorWrapper(device=d, device_list_coordinator=coordinator, channel=0))

        # Add MTS100Valve Temperature sensors
        for d in mts100_temp_sensors:
            new_entities.append(Mts100TemperatureSensorWrapper(device=d, device_list_coordinator=coordinator))

        # Add Power Sensors
        for d in power_sensors:
            channels = [c.index for c in d.channels] if len(d.channels) > 0 else [0]
            for channel_index in channels:
                new_entities.append(
                    PowerSensorWrapper(device=d, device_list_coordinator=coordinator, channel=channel_index))
                new_entities.append(
                    CurrentSensorWrapper(device=d, device_list_coordinator=coordinator, channel=channel_index))
                new_entities.append(
                    VoltageSensorWrapper(device=d, device_list_coordinator=coordinator, channel=channel_index))

        # Add Energy Sensors
        for d in energy_sensors:
                new_entities.append(
                     EnergySensorWrapper(device=d, device_list_coordinator=coordinator, channel=channel_index))

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
