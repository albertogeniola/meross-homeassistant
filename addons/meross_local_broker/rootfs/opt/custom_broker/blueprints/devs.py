from meross_iot.model.enums import OnlineStatus

from logger import get_logger
import re
from _md5 import md5
from flask import Blueprint, request
from db_helper import dbhelper


devs_blueprint = Blueprint('_devs', __name__)
_LOGGER = get_logger(__name__)
_DEV_PASSWORD_RE = re.compile("^([0-9]+)_([a-zA-Z0-9]+)$")
_CLIENTID_RE = re.compile('^fmware:([a-zA-Z0-9]+)_[a-zA-Z0-9]+$')


@devs_blueprint.route('/acl', methods=['POST'])
def device_acl():
    content = request.json
    _LOGGER.debug("LOGIN_CHECK=%s", str(content))

    username = request.json.get('username')
    topic = request.json.get('topic')
    acc = request.json.get('acc')
    clientid = request.json.get('clientid')

    _LOGGER.debug("ACL_CHECK=> username: %s, topic: %s, acc: %s, clientid: %s", str(username),
                  str(topic), str(acc), str(clientid))

    # TODO: implement ACL checks.
    # For now, just return 200: allow connection from anyone to every topic
    return "ok", 200


@devs_blueprint.route('/superuser', methods=['POST'])
def superuser_acl():
    # For now, just return 403
    return "ko", 403


@devs_blueprint.route('/auth', methods=['POST'])
def device_login():
    content = request.json

    if content is None:
        _LOGGER.error("Expected JSON body has not been received.")
        return "ko", 403

    username = request.json.get('username')
    password = request.json.get('password')
    topic = request.json.get('topic')
    acc = request.json.get('acc')
    clientid = request.json.get('clientid')

    _LOGGER.debug("LOGIN_CHECK=> username: %s, password: %s, clientid: %s", str(username), str(password), str(clientid))

    # Device authentication basically is basically a "binding" to a given user id
    # Username => device mac addresss
    # Password => userid_md5(mac+key)
    # Clientid: fmware:deviceuuid_<?>
    mac = username
    match = _DEV_PASSWORD_RE.match(password)
    if match is None:
        _LOGGER.error("Provided device password does not comply with expected format.")
        _LOGGER.debug("Provided password: %s", password)
        return "ko", 400

    userid = match.group(1)
    md5hash = match.group(2)

    # Parse the device uuid
    match = _CLIENTID_RE.fullmatch(clientid)
    if match is None:
        _LOGGER.error("Clientid %s is not valid", clientid)
        return "ko", 400

    dev_uuid = match.group(1)

    # Lookup key by the given username.
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
        dbhelper.associate_user_device(userid=userid, mac=mac, uuid=dev_uuid, device_client_id=clientid)
        dbhelper.update_device_status(device_uuid=dev_uuid, status=OnlineStatus.ONLINE)
        _LOGGER.info(
            f"Device login attempt succeeded. Device with mac \"{mac}\" (uuid {dev_uuid}) has been associated to "
            f"userid \"{userid}\"")
        return "ok", 200
    else:
        _LOGGER.warning(f"Device login attempt failed (device with mac \"{mac}\", userid \"{userid}\")")
        return "ko", 403


