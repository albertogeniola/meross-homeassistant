from logger import get_logger
from typing import Dict, List

from flask import jsonify, request
from flask import Blueprint
from db_helper import dbhelper
from model.db_models import Device
from model.exception import BadRequestError
from s6 import service_manager


admin_blueprint = Blueprint('admin', __name__)
_LOGGER = get_logger(__name__)


# TODO: check super-admin role...
@admin_blueprint.route('/devices', methods=['GET'])
def list_devices() -> List[Dict]:
    """ List all devices """
    devices = dbhelper.get_all_devices()
    return jsonify(Device.serialize_list(devices))


# TODO: check super-admin role...
@admin_blueprint.route('/devices/<uuid>', methods=['PUT'])
def update_device(uuid: str) -> Dict:
    """ Update the given device """
    device_patch = request.get_json(force=True)

    # Check if the given device exists
    device = dbhelper.get_device_by_uuid(device_uuid=uuid)
    if device is None:
        _LOGGER.warning("Device with UUID %s does not exist", uuid)
        raise BadRequestError(msg=f"Device with UUID {uuid} does not exist")

    # Path supported methods: device name
    name = device_patch.get("dev_name")
    if name is not None:
        device.dev_name = name
        del device_patch["dev_name"]

    # Raise an error if the user has tried to update any other attribute
    if len(device_patch.keys()) > 0:
        _LOGGER.warning("Unsupported patch arguments: %s", ",".join(device_patch.keys()))
        raise BadRequestError("Unsupported patch arguments: %s" % ",".join(device_patch.keys()))

    dbhelper.update_device(device)

    return jsonify(Device.serialize(device))


# TODO: check super-admin role...
@admin_blueprint.route('/subdevices', methods=['GET'])
def list_subdevices() -> List[Dict]:
    """ List all subdevices """
    subdevices = dbhelper.get_all_subdevices()
    return jsonify(Device.serialize_list(subdevices))


# TODO: check super-admin role...
@admin_blueprint.route('/services', methods=['GET'])
def list_services() -> List[Dict]:
    """ List services """
    services = service_manager.get_services_info()
    return jsonify([s.serialize() for s in services])


# TODO: check super-admin role...
@admin_blueprint.route('/services/<service_name>/execute/<command>', methods=['POST'])
def execute_service_command(service_name: str, command: str) -> bool:
    """ Executes a command on a service """
    cmd = command.lower()
    result = False
    if cmd == "start": 
        result = service_manager.start_service(service_name)
    elif cmd == "stop":
        result = service_manager.stop_service(service_name)
    elif command == "restart":
        result = service_manager.restart_service(service_name)
    else:
        raise BadRequestError(msg="Invalid command specified.")
    return jsonify(result)