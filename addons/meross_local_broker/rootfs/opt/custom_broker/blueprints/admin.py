import logging
from typing import Dict, List

from flask import jsonify
from flask import Blueprint
from db_helper import dbhelper
from model.db_models import Device

admin_blueprint = Blueprint('admin', __name__)
_LOGGER = logging.getLogger(__name__)


# TODO: check super-admin role...
@admin_blueprint.route('/devices', methods=['GET'])
def list_devices() -> List[Dict]:
    """ List all devices """
    devices = dbhelper.get_all_devices()
    return jsonify(Device.serialize_list(devices))



