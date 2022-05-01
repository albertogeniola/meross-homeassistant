from enum import Enum


class BridgeStatus(Enum):
    DISCONNECTED = "Disconnected"
    CONNECTED = "Connected"
    ERROR = "Error"


class EventType(Enum):
    # General / Uncathegorized
    CONNECT_FAILURE = "CONNECT_FAILURE"

    # User login
    USER_LOGIN_FAILURE = "USER_LOGIN_FAILURE"
    USER_LOGIN_SUCCESS= "USER_LOGIN_SUCCESS"

    # Device events
    DEVICE_CONNECT_FAILURE = "DEVICE_CONNECT_FAILURE"
    DEVICE_CONNECT_SUCCESS = "DEVICE_CONNECT_SUCCESS"
    DEVICE_DISCONNECTION = "DEVICE_DISCONNECTION"


