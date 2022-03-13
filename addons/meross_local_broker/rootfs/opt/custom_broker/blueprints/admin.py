from logger import get_logger
from typing import Dict, List

from flask import jsonify, request
from flask import Blueprint
from db_helper import dbhelper
from model.db_models import Device
from model.exception import BadRequestError
from constants import DEFAULT_USER_ID
from s6 import service_manager
from setup import setup_account
import time


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
def execute_service_command(service_name: str, command: str):
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


# TODO: check super-admin role...
@admin_blueprint.route('/services/<service_name>/log', methods=['GET'])
def get_service_log(service_name: str):
    """ Returns the log of the given service """
    return jsonify(service_manager.get_log(service_name))


# TODO: check super-admin role...
@admin_blueprint.route('/configuration/account', methods=['GET'])
def get_account():
    """ Returns the configured account """
    user = dbhelper.get_user_by_id(userid=DEFAULT_USER_ID)
    if user is None:
        raise BadRequestError(msg=f"Invalid/Missing userid {DEFAULT_USER_ID} in the DB. Please set it again.")
    return jsonify(user.serialize())


# TODO: check super-admin role...
@admin_blueprint.route('/configuration/account', methods=['PUT'])
def set_account():
    """ Configures the Meross Account to be use as authentication method """
    # Arg checks
    payload = request.get_json(force=True)
    if payload is None:
        raise BadRequestError(msg=f"Missing json payload.")
    email: str = payload.get('email')
    password: str = payload.get('password')
    meross_link: bool = payload.get('enableMerossLink')
    if email is None:
        raise BadRequestError(msg=f"Missing or invalid email.")
    if password is None:
        raise BadRequestError(msg=f"Missing or invalid password.")
    if meross_link is None:
        raise BadRequestError(msg=f"Missing or invalid enableMerossLink option.")
    
    # Setup Account
    user = setup_account(email=email, password=password, enable_meross_link=meross_link)

    # As soon as the Account is set, we need to restart the mosquitto and the broker services
    #_LOGGER.warn("Stopping broker & MQTT services (due to account configuration changes)")
    #service_manager.stop_service("Local Agent")
    #service_manager.stop_service("MQTT Service")
    #time.sleep(10)
    #_LOGGER.warn("Starting broker & MQTT services (due to account configuration changes)")
    #service_manager.start_service("Local Agent")
    #service_manager.start_service("MQTT Service")
    service_manager.restart_service("Local Agent")
    service_manager.restart_service("MQTT Service")
    
    # TODO: Restart/Reload broker?
    return jsonify(user.serialize())