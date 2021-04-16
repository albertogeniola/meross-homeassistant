import logging
from typing import Dict, List

from flask import jsonify, request
from flask import Blueprint
from db_helper import dbhelper
from model.db_models import Device
from model.exception import BadRequestError

admin_blueprint = Blueprint('admin', __name__)
_LOGGER = logging.getLogger(__name__)


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
    name = device_patch.get("device_name")
    if name is not None:
        device.device_name = name
        del device_patch["device_name"]

    # Raise an error if the user has tried to update any other attribute
    if len(device_patch.keys()) > 0:
        _LOGGER.warning("Unsupported patch arguments: %s", ",".join(device_patch.keys()))
        raise BadRequestError("Unsupported patch arguments: %s" % ",".join(device_patch.keys()))

    dbhelper.update_device(device)

    return jsonify(Device.serialize(device))

