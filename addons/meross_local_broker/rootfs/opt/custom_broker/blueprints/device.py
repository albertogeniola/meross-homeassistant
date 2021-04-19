import logging
from typing import Dict
from flask import Blueprint, g
from decorator import meross_http_api
from messaging import make_api_response
from model.db_models import Device

device_blueprint = Blueprint('device', __name__)
_LOGGER = logging.getLogger(__name__)


@device_blueprint.route('/devList', methods=['POST'])
@meross_http_api(login_required=True)
def list_devices(api_payload: Dict, *args, **kwargs):
    user = g.user
    _LOGGER.debug("User %s requested deviceList", user)
    data = Device.serialize_list(user.owned_devices)
    return make_api_response(data=data)
