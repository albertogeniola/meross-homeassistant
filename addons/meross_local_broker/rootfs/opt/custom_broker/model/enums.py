from enum import Enum


class BridgeStatus(Enum):
    DISCONNECTED = "Disconnected"
    CONNECTED = "Connected"
    ERROR = "Error"


class EventSeverity(Enum):
    INFO = "INFO"
    WARN = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
