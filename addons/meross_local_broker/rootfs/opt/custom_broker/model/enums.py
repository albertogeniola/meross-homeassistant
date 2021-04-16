import logging
from enum import Enum
from typing import Union


_LOGGER = logging.getLogger(__name__)


class OnlineStatus(Enum):
    NOT_ONLINE = 0
    ONLINE = 1
    OFFLINE = 2
    UNKNOWN = -1
    UPGRADING = 3


class LightMode(Enum):
    MODE_LUMINANCE = 4
    MODE_TEMPERATURE = 2
    MODE_RGB = 1
    MODE_RGB_LUMINANCE = 5
    MODE_TEMPERATURE_LUMINANCE = 6


class SprayMode(Enum):
    OFF = 0
    CONTINUOUS = 1
    INTERMITTENT = 2


class CommandExecutionChannel(Enum):
    AUTO = 0
    MQTT = 1
    HTTP = 2


class ThermostatV3Mode(Enum):
    AUTO = 3
    COOL = 2
    CUSTOM = 0
    ECONOMY = 4
    HEAT = 1


class Namespace(Enum):
    # Common abilities
    SYSTEM_ALL = 'Appliance.System.All'
    SYSTEM_ABILITY = 'Appliance.System.Ability'
    SYSTEM_ONLINE = 'Appliance.System.Online'
    SYSTEM_REPORT = 'Appliance.System.Report'
    SYSTEM_DEBUG = 'Appliance.System.Debug'

    CONTROL_BIND = 'Appliance.Control.Bind'
    CONTROL_UNBIND = 'Appliance.Control.Unbind'
    CONTROL_TRIGGER = 'Appliance.Control.Trigger'
    CONTROL_TRIGGERX = 'Appliance.Control.TriggerX'

    CONFIG_WIFI_LIST = 'Appliance.Config.WifiList'
    CONFIG_TRACE = 'Appliance.Config.Trace'

    # Power plug/bulbs abilities
    CONTROL_TOGGLE = 'Appliance.Control.Toggle'
    CONTROL_TOGGLEX = 'Appliance.Control.ToggleX'
    CONTROL_ELECTRICITY = 'Appliance.Control.Electricity'
    CONTROL_CONSUMPTION = 'Appliance.Control.Consumption'
    CONTROL_CONSUMPTIONX = 'Appliance.Control.ConsumptionX'

    # Bulbs-only abilities
    CONTROL_LIGHT = 'Appliance.Control.Light'

    # Garage opener abilities
    GARAGE_DOOR_STATE = 'Appliance.GarageDoor.State'

    # Roller Shutter abilities
    ROLLER_SHUTTER_STATE = 'Appliance.RollerShutter.State'
    ROLLER_SHUTTER_POSITION = 'Appliance.RollerShutter.Position'
    ROLLER_SHUTTER_CONFIG = 'Appliance.RollerShutter.Config'

    # Humidifier
    CONTROL_SPRAY = 'Appliance.Control.Spray'

    SYSTEM_DIGEST_HUB = 'Appliance.Digest.Hub'

    # HUB
    HUB_EXCEPTION = 'Appliance.Hub.Exception'
    HUB_BATTERY = 'Appliance.Hub.Battery'
    HUB_TOGGLEX = 'Appliance.Hub.ToggleX'
    HUB_ONLINE = 'Appliance.Hub.Online'

    # SENSORS
    HUB_SENSOR_ALL = 'Appliance.Hub.Sensor.All'
    HUB_SENSOR_TEMPHUM = 'Appliance.Hub.Sensor.TempHum'
    HUB_SENSOR_ALERT = 'Appliance.Hub.Sensor.Alert'

    # MTS100
    HUB_MTS100_ALL = 'Appliance.Hub.Mts100.All'
    HUB_MTS100_TEMPERATURE = 'Appliance.Hub.Mts100.Temperature'
    HUB_MTS100_MODE = 'Appliance.Hub.Mts100.Mode'


def get_or_parse_namespace(namespace: Union[Namespace, str]):
    if isinstance(namespace, str):
        try:
            parsed_namespace = Namespace(namespace)
            return parsed_namespace
        except ValueError:
            _LOGGER.error(f"Namespace {namespace} is not currently handled/recognized.")
            raise
    elif isinstance(namespace, Namespace):
        return namespace
    else:
        raise ValueError("Unknown invalid namespace type. Only str/Namespace types are allowed here.")