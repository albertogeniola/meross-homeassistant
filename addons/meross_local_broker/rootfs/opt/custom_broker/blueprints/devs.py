"""Flask blueprint for device-specific API"""
import re
from hashlib import md5
from typing import Tuple

from authentication import _hash_password
from db_helper import dbhelper
from flask import Blueprint, request
from logger import get_logger
from meross_iot.model.enums import OnlineStatus
from model.enums import EventType


devs_blueprint = Blueprint('_devs', __name__)
_LOGGER = get_logger(__name__)
_DEV_PASSWORD_RE = re.compile("^([0-9]+)_([a-zA-Z0-9]+)$")
_CLIENTID_DEVICE_OR_APP_RE = re.compile(
    '^(fmware|app):([a-zA-Z0-9]+)(_([a-zA-Z0-9]+))?$')


@devs_blueprint.route('/acl', methods=['POST'])
def device_acl():
    """Endpoint called by the MQTT broker plugin to verify ACLs."""
    # This method is responsible to check whether a device can subscribe
    # to a given MQTT topic or not.
    username = request.json.get('username')
    topic = request.json.get('topic')
    acc = request.json.get('acc')
    clientid = request.json.get('clientid')

    _LOGGER.debug("DEVICE_ACL=> username: %s, topic: %s, acc: %s, clientid: %s", str(username),
                  str(topic), str(acc), str(clientid))

    # TODO: implement ACL checks.
    # For now, just return 200: allow connection from anyone to every topic
    return "ok", 200


@devs_blueprint.route('/superuser', methods=['POST'])
def superuser_acl():
    """Endpoint called by the MQTT broker plugin to verify ACLS for super-users"""
    # TODO: add logging and implement super-user logic
    # For now, just return 403: no one can connect as super-user.
    return "ko", 403


@devs_blueprint.route('/auth', methods=['POST'])
def device_login():
    """Endpoint called by the MQTT broker plugin to authenticate devices."""
    content = request.json

    if content is None:
        _LOGGER.debug("DEVICE_AUTH=> Raw message content: %s", request.data)
        _LOGGER.error(
            "DEVICE_AUTH=> Expected JSON body has not been received.")
        dbhelper.store_event(event_type=EventType.CONNECT_FAILURE, details=f"Invalid connection attempted from {str(request.remote_addr)}")
        return "ko", 403

    username = request.json.get('username')
    password = request.json.get('password')
    topic = request.json.get('topic')
    acc = request.json.get('acc')
    clientid = request.json.get('clientid')

    _LOGGER.debug("LOGIN_CHECK=> username: %s, password: %s, clientid: %s, topic: %s, acc: %s", str(
        username), str(password), str(clientid), str(topic), str(acc))

    # Differentiate login based on clientid
    clientid_match = _CLIENTID_DEVICE_OR_APP_RE.fullmatch(clientid)
    if clientid_match is None:
        _LOGGER.debug(
            "LOGIN_CHECK=> clientid (%s) does not belong to app/device: performing custom login.", str(clientid))
        res = _custom_login(email=username, password=password)
        return res

    login_type = clientid_match.group(1)
    if login_type == "fmware":
        # Device authentication basically is basically a "binding" to a given user id
        # Username => device mac addresss
        # Password => userid_md5(mac+key)
        # Clientid: fmware:deviceuuid_<?>
        _LOGGER.debug(
            "LOGIN_CHECK=> recognized device clientid format (clientid: %s). Logging-in as device.", str(clientid))
        pwd_match = _DEV_PASSWORD_RE.match(password)
        if pwd_match is None:
            _LOGGER.error(
                "LOGIN_CHECK=> Provided device password does not comply with expected format for device with clientid: %s.", str(clientid))
            _LOGGER.debug("LOGIN_CHECK=> Provided password: %s", password)
            return "ko", 400
        mac = username
        user_id = pwd_match.group(1)
        md5hash = pwd_match.group(2)
        device_uuid = clientid_match.group(2)
        res = _device_login(mac=mac, user_id=user_id,
                            device_uuid=device_uuid, md5hash=md5hash, clientid=clientid)
        return res

    elif login_type == "app":
        _LOGGER.debug(
            "LOGIN_CHECK=> recognized app clientid format (clientid: %s). Logging-in as app.", str(clientid))
        res = _app_login(user_id=username, md5hash=password)
        return res
    else:
        _LOGGER.error(
            "LOGIN_CHECK=> Invalid/unsupported client type derived from client id.")
        return "ko", 400


def _custom_login(email: str, password: str):
    # Lookup user email by the given username.
    user = dbhelper.get_user_by_email(email=email)
    if user is None:
        _LOGGER.error(
            "LOGIN_CHECK(custom)=> User \"%s\" does not exist.", email)
        dbhelper.store_event(event_type=EventType.USER_LOGIN_FAILURE, details=f"Custom login from {str(request.remote_addr)} failed: username {email} does not exist.")
        return "ko", 401

    hashed_pass = _hash_password(salt=user.salt, password=password)
    _LOGGER.debug(
        "LOGIN_CHECK(custom)=> Login attempt from user \"%s\", provided hash \"%s\", expected \"%s\".", str(email), str(hashed_pass), str(user.password))

    if hashed_pass == user.password:
        _LOGGER.info(
            "LOGIN_CHECK(custom)=> User login attempt succeeded UserId: %s", email)
        dbhelper.store_event(event_type=EventType.USER_LOGIN_SUCCESS, user_id=user.user_id, details=f"Custom login from {str(request.remote_addr)} succeeded.")
        return "ok", 200
    else:
        _LOGGER.warning(
            "LOGIN_CHECK(custom)=> User login attempt failed (UserId %s)", email)
        dbhelper.store_event(event_type=EventType.USER_LOGIN_FAILURE, details=f"Custom login from {str(request.remote_addr)} with email {email} failed: wrong credentials.")
        return "ko", 403


def _app_login(user_id: str, md5hash: str) -> Tuple[str, int]:
    try:
        userid = int(user_id)
    except ValueError:
        _LOGGER.error("LOGIN_CHECK(app)=> UserId \"%s\" is invalid.", str(user_id))
        dbhelper.store_event(event_type=EventType.USER_LOGIN_FAILURE, user_id=user_id, details=f"App login from {str(request.remote_addr)} with user_id {str(user_id)} failed: invalid user_id, it should be numerical.")
        return "ko", 400

    # Lookup key by the given username.
    user = dbhelper.get_user_by_id(userid=userid)
    if user is None:
        _LOGGER.error(
            "LOGIN_CHECK(app)=> User with ID \"%s\" does not exist.", str(userid))
        dbhelper.store_event(event_type=EventType.USER_LOGIN_FAILURE, user_id=user_id, details=f"App login from {str(request.remote_addr)} with user_id {str(user_id)} failed: user id does not exist.")
        return "ko", 401

    # Calculate the expected hash: MD5(<userid><mqtt_key>).hex()
    expected_md5hash = md5()
    expected_md5hash.update(f"{user_id}{user.mqtt_key}".encode())
    expected_digest = expected_md5hash.hexdigest()

    _LOGGER.debug("LOGIN_CHECK(app)=> Login attempt from userid \"%s\", provided hash \"%s\", expected \"%s\".", str(
        user_id), str(md5hash), str(expected_digest))

    if expected_digest == md5hash:
        _LOGGER.info(
            "LOGIN_CHECK(app)=> App login attempt succeeded UserId: %s", str(userid))
        dbhelper.store_event(event_type=EventType.USER_LOGIN_SUCCESS, user_id=user_id, details=f"App login from {str(request.remote_addr)} with user_id {str(user_id)} succeeded.")
        return "ok", 200
    else:
        _LOGGER.warning(
            "LOGIN_CHECK(app)=> App login attempt failed (UserId %s)", str(userid))
        dbhelper.store_event(event_type=EventType.USER_LOGIN_FAILURE, user_id=user_id, details=f"App login from {str(request.remote_addr)} with user_id {str(user_id)} failed: invalid user/password combination.")
        return "ko", 403


def _device_login(mac: str, user_id: str, device_uuid: str, md5hash: str, clientid: str) -> Tuple[str, int]:
    try:
        userid = int(user_id)
    except ValueError:
        _LOGGER.error(
            "LOGIN_CHECK(device)=> UserId \"%s\" is invalid.", str(user_id))
        dbhelper.store_event(event_type=EventType.DEVICE_CONNECT_FAILURE, user_id=user_id, details=f"Device {device_uuid} ({str(request.remote_addr)}) failed authentication: invalid user_id specified.")
        return "ko", 400

    # Lookup key by the given username.
    user = dbhelper.get_user_by_id(userid=userid)
    if user is None:
        _LOGGER.error(
            "LOGIN_CHECK(device)=> User with ID \"%s\" does not exist.", str(userid))
        dbhelper.store_event(event_type=EventType.DEVICE_CONNECT_FAILURE, user_id=user_id, details=f"Device {device_uuid} ({str(request.remote_addr)}) failed authentication: provided user_id {str(user_id)} does not exist.")
        return "ko", 401

    expected_md5hash = md5()
    expected_md5hash.update(f"{mac}{user.mqtt_key}".encode())
    expected_digest = expected_md5hash.hexdigest()

    _LOGGER.debug(
        "LOGIN_CHECK(device)=> Login attempt from \"%s\", provided hash \"%s\", expected \"%s\".", str(mac), str(md5hash), str(expected_digest))

    if expected_digest == md5hash:
        dbhelper.associate_user_device(
            userid=userid, mac=mac, uuid=device_uuid, device_client_id=clientid)
        dbhelper.update_device_status(
            device_uuid=device_uuid, status=OnlineStatus.ONLINE)
        _LOGGER.info(
            "Device login attempt succeeded. Device with mac \"%s\" (uuid %s) has been associated to "
            "userid \"%s\"", str(mac), str(device_uuid), str(userid))
        dbhelper.store_event(event_type=EventType.DEVICE_CONNECT_SUCCESS, user_id=user_id, device_uuid=device_uuid, details=f"Device {device_uuid} ({str(request.remote_addr)}) successfully authenticated.")
        return "ok", 200
    else:
        _LOGGER.warning(
            "Device login attempt failed (device with mac \"%s\", userid \"%s\")", str(mac), str(userid))
        dbhelper.store_event(event_type=EventType.DEVICE_CONNECT_FAILURE, user_id=user_id, device_uuid=device_uuid, details=f"Device {device_uuid} ({str(request.remote_addr)}) failed authentication.")
        return "ko", 403
