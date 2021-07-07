from typing import Tuple

from meross_iot.model.enums import OnlineStatus

from authentication import _hash_password
from logger import get_logger
import re
from _md5 import md5
from flask import Blueprint, request
from db_helper import dbhelper


devs_blueprint = Blueprint('_devs', __name__)
_LOGGER = get_logger(__name__)
_DEV_PASSWORD_RE = re.compile("^([0-9]+)_([a-zA-Z0-9]+)$")
_CLIENTID_RE = re.compile('^(fmware|app):([a-zA-Z0-9]+)(_([a-zA-Z0-9]+))?$')


@devs_blueprint.route('/acl', methods=['POST'])
def device_acl():
    content = request.json

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

    # Differentiate login based on clientid
    cleintid_match = _CLIENTID_RE.fullmatch(clientid)
    if cleintid_match is None:
        return _custom_login(email=username, password=password)

    login_type = cleintid_match.group(1)
    if login_type == "fmware":
        # Device authentication basically is basically a "binding" to a given user id
        # Username => device mac addresss
        # Password => userid_md5(mac+key)
        # Clientid: fmware:deviceuuid_<?>
        pwd_match = _DEV_PASSWORD_RE.match(password)
        if pwd_match is None:
            _LOGGER.error("Provided device password does not comply with expected format.")
            _LOGGER.debug("Provided password: %s", password)
            return "ko", 400
        mac = username
        user_id = pwd_match.group(1)
        md5hash = pwd_match.group(2)
        device_uuid = cleintid_match.group(2)
        return _device_login(mac=mac, user_id=user_id, device_uuid=device_uuid, md5hash=md5hash, clientid=clientid)

    elif login_type == "app":
        return _app_login(user_id=username, md5hash=password)
    else:
        _LOGGER.error("Invalid/unsupported client type derived from client id.")
        return "ko", 400


def _custom_login(email: str, password: str):
    # Lookup user email by the given username.
    user = dbhelper.get_user_by_email(email=email)
    if user is None:
        _LOGGER.error(f"User \"{email}\" does not exist.")
        return "ko", 401

    hashed_pass = _hash_password(salt=user.salt, password=password)
    _LOGGER.debug(f"Login attempt from user \"{email}\", provided hash \"{hashed_pass}\", expected \"{user.password}\".")

    if hashed_pass == user.password:
        _LOGGER.info(f"App login attempt succeeded UserId: {email}")
        return "ok", 200
    else:
        _LOGGER.warning(f"App login attempt failed (UserId {email})")
        return "ko", 403


def _app_login(user_id: str, md5hash: str) -> Tuple[str, int]:
    try:
        userid = int(user_id)
    except ValueError as e:
        _LOGGER.error(f"UserId \"{user_id}\" is invalid.")
        return "ko", 400

    # Lookup key by the given username.
    user = dbhelper.get_user_by_id(userid=userid)
    if user is None:
        _LOGGER.error(f"User with ID \"{userid}\" does not exist.")
        return "ko", 401

    # Calculate the expected hash: MD5(<userid><mqtt_key>).hex()
    expected_md5hash = md5()
    expected_md5hash.update(f"{user_id}{user.mqtt_key}".encode())
    expected_digest = expected_md5hash.hexdigest()

    _LOGGER.debug(f"Login attempt from userid \"{user_id}\", provided hash \"{md5hash}\", expected \"{expected_digest}\".")

    if expected_digest == md5hash:
        _LOGGER.info(f"App login attempt succeeded UserId: {userid}")
        return "ok", 200
    else:
        _LOGGER.warning(f"App login attempt failed (UserId {userid})")
        return "ko", 403


def _device_login(mac: str, user_id: str, device_uuid: str, md5hash: str, clientid: str) -> Tuple[str, int]:
    try:
        userid = int(user_id)
    except ValueError as e:
        _LOGGER.error(f"UserId \"{user_id}\" is invalid.")
        return "ko", 400

    # Lookup key by the given username.
    user = dbhelper.get_user_by_id(userid=userid)
    if user is None:
        _LOGGER.error(f"User with ID \"{userid}\" does not exist.")
        return "ko", 401

    expected_md5hash = md5()
    expected_md5hash.update(f"{mac}{user.mqtt_key}".encode())
    expected_digest = expected_md5hash.hexdigest()

    _LOGGER.debug(f"Login attempt from \"{mac}\", provided hash \"{md5hash}\", expected \"{expected_digest}\".")

    if expected_digest == md5hash:
        dbhelper.associate_user_device(userid=userid, mac=mac, uuid=device_uuid, device_client_id=clientid)
        dbhelper.update_device_status(device_uuid=device_uuid, status=OnlineStatus.ONLINE)
        _LOGGER.info(
            f"Device login attempt succeeded. Device with mac \"{mac}\" (uuid {device_uuid}) has been associated to "
            f"userid \"{userid}\"")
        return "ok", 200
    else:
        _LOGGER.warning(f"Device login attempt failed (device with mac \"{mac}\", userid \"{userid}\")")
        return "ko", 403

