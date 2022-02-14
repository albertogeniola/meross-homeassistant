from asyncore import read
from subprocess import Popen, PIPE
from typing import Dict, Optional, List

_SERVICE_DIRS = {
    "MQTT Broker": "/var/run/s6/services/mosquitto",
    "Python API": "/var/run/s6/services/api",
    "Python Broker": "/var/run/s6/services/broker",
    "Reverse Proxy": "/var/run/s6/services/nginx",
    "mDNS": "/var/run/s6/services/avahi",
    "mDNS HTTP service": "/var/run/s6/services/http-service-advertise",
    "mDNS MQTT service": "/var/run/s6/services/mqtt-service-advertise"
}

class ServiceInfo:
    def __init__(self, name:str, up: bool, ready: bool, pid: int, exit_code: int = None) -> None:
        self._name = name
        self._up = up
        self._ready = ready
        self._pid = pid
        self._exit_code = exit_code
    
    @property
    def name(self):
        return self._name

    @property
    def status(self):
        if self._up:
            return "RUNNING"
        elif self._ready:
            return "STOPPED"
        else:
            return "DOWN"
    
    @property
    def exit_code(self) -> Optional[int]:
        if self._up:
            return None
        return self._exit_code

    @property
    def pid(self) -> Optional[int]:
        if self._up:
            return self._pid
        return None

    def serialize(self) -> Dict:
        return {
            "name": self.name,
            "status": self.status,
            "exit_code": self.exit_code,
            "pid": self.pid
        }

def get_service_info(service_name: str) -> ServiceInfo:
    service_dir=_SERVICE_DIRS[service_name]
    process = Popen(['s6-svstat', '-o', 'up,ready,pid,exitcode', service_dir], stdout=PIPE, universal_newlines=True)
    stdout, stderr = process.communicate()
    up, ready, pid, exitcode = stdout.split()
    return ServiceInfo(name=service_name, up=up, ready=ready, pid=pid, exit_code=exitcode)

def get_services_info() -> List[ServiceInfo]:
    return [get_service_info(s) for s in _SERVICE_DIRS]
