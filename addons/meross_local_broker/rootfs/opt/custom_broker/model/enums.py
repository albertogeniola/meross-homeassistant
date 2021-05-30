from enum import Enum


class BridgeStatus(Enum):
    DISCONNECTED = "Disconnected"
    CONNECTED = "Connected"
    ERROR = "Error"
