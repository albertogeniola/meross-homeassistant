import logging
import re
from _md5 import md5

from flask import Blueprint, request

from db_helper import dbhelper

devs_blueprint = Blueprint('_devs', __name__)
_LOGGER = logging.getLogger(__name__)
_DEV_PASSWORD_RE = re.compile("^([0-9]+)\_([a-zA-Z0-9]+)$")


@devs_blueprint.route('/acl', methods=['POST'])
def device_acl():
    # For now, just return 200: allow connection from anyone
    return "ok", 200


@devs_blueprint.route('/superuser', methods=['POST'])
def superuser_acl():
    # For now, just return 403
    return "ko", 403


@devs_blueprint.route('/auth', methods=['POST'])
def device_login():
    username = request.values.get('username')
    password = request.values.get('password')
    topic = request.values.get('topic')
    acc = request.values.get('acc')

    # Device authentication basically is basically a "binding" to a given user id
    # Username => device mac addresss
    # Password => userid_md5(mac+key)
    mac = username
    match = _DEV_PASSWORD_RE.match(password)
    if match is None:
        _LOGGER.error("Provided device password does not comply with expected format.")
        _LOGGER.debug("Provided password: %s", password)
        return "ko", 400

    userid = match.group(1)
    md5hash = match.group(2)

    # Lookup key by the given username...
    try:
        userid = int(userid)
    except ValueError as e:
        _LOGGER.error(f"UserId \"{userid}\" is invalid.")
        return "ko", 400

    user = dbhelper.get_user_by_id(userid=userid)
    if user is None:
        _LOGGER.error(f"User with ID \"{userid}\" does not exist.")
        return "ko", 401

    expected_md5hash = md5()
    expected_md5hash.update(f"{mac}{user.mqtt_key}".encode())
    expected_digest = expected_md5hash.hexdigest()

    _LOGGER.debug(f"Login attempt from \"{mac}\", provided hash \"{md5hash}\", expected \"{expected_digest}\".")

    if expected_digest == md5hash:
        dbhelper.associate_user_device(userid=userid, mac=mac)
        _LOGGER.info(
            f"Device login attempt succeeded. Device with mac \"{mac}\" has been associated to userid \"{userid}\"")
        return "ok", 200
    else:
        _LOGGER.warning(f"Device login attempt failed (device with mac \"{mac}\", userid \"{userid}\")")
        return "ko", 403


