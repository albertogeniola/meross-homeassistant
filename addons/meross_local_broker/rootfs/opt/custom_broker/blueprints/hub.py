from typing import Dict

from flask import Blueprint, g
from meross_iot.http_api import ErrorCodes

from db_helper import dbhelper
from decorator import meross_http_api
from logger import get_logger
from messaging import make_api_response
from model.exception import HttpApiError

hub_blueprint = Blueprint('hub', __name__)
_LOGGER = get_logger(__name__)


@hub_blueprint.route('/getSubDevices', methods=['POST'])
@meross_http_api(login_required=True)
def get_subdevices(api_payload: Dict, *args, **kwargs):
    user = g.user
    _LOGGER.debug("User %s requested getSubDevices", user)

    # Make sure api payload contains a valid hub device uuid
    parent_uuid = api_payload.get('uuid')
    if parent_uuid is None:
        _LOGGER.error("Missing uuid parameter.")
        raise HttpApiError(error_code=ErrorCodes.CODE_GENERIC_ERROR)

    device = dbhelper.get_device_by_uuid(parent_uuid)

    # Make sure the user owns the device for which he's retrieving subdevs
    if device is None or device.owner_user.email != user.email:
        _LOGGER.error("Invalid UUID or device not enrolled")
        raise HttpApiError(error_code=ErrorCodes.CODE_GENERIC_ERROR)

    return make_api_response(data=device.child_subdevices)
