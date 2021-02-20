import base64
import sqlite3
from typing import Tuple, Optional
import json
import uuid
from hashlib import sha256
from constants import _SECRET
from flask import Flask, request, jsonify
from hashlib import md5
import logging
from flask import g
from codes import ErrorCodes
from db_helper import DbHelper
from model.exception import HttpApiError, BadRequestError
import re


_LOG_URL = "/v1/log/user"
_DEV_LIST = "/v1/Device/devList"
_HUB_DUBDEV_LIST = "/v1/Hub/getSubDevices"
_LOGOUT_URL = "/v1/Profile/logout"

_DEV_PASSWORD_RE = re.compile("^([0-9]+)\_([a-zA-Z0-9]+)$")

_LOGGER = logging.getLogger(__name__)
app = Flask(__name__)


def _user_login(email: str, password: str) -> Tuple[str, str, str, str]:
    # Check user-password creds
    # email, userid, salt, password, mqtt_key
    data = DbHelper.get_db().get_user_by_email(email=email)
    if data is None:
        raise HttpApiError(ErrorCodes.CODE_UNEXISTING_ACCOUNT)
    
    email = data[0]
    userid = data[1]
    salt = data[2]
    dbpwd = data[3]
    mqtt_key = data[4]

    # Get the salt, compute the hashed password and compare it with the one stored in the db
    clearsaltedpwd = f"{salt}{password}"
    hashed_pass = sha256()
    hashed_pass.update(clearsaltedpwd.encode('utf8'))
    computed_hashed_password = hashed_pass.hexdigest()

    #_LOGGER.debug(f"Computed HASH: {computed_hashed_password}, expected HASH: {dbpwd} ")

    if computed_hashed_password != dbpwd:
        raise HttpApiError(ErrorCodes.CODE_WRONG_CREDENTIALS)

    # If ok, generate an HTTP_TOKEN
    hash = sha256()
    hash.update(uuid.uuid4().bytes)
    token = hash.hexdigest()

    # Store the new token
    DbHelper.get_db().store_new_user_token(userid, token)
    return token, mqtt_key, userid, email


def verify_message_signature(signature: str, timestamp_millis: str, nonce: str, b64params: str):
    message_hash = md5()
    datatosign = '%s%s%s%s' % (_SECRET, timestamp_millis, nonce, b64params)
    message_hash.update(datatosign.encode("utf8"))
    md5hash = message_hash.hexdigest()
    return md5hash == signature


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.errorhandler(BadRequestError)
def handle_exception(e):
    _LOGGER.error("BadRequest error: %s", e.msg)
    return make_api_response(data=None, info=e.msg, api_status=ErrorCodes.CODE_GENERIC_ERROR, status_code=400)


@app.errorhandler(HttpApiError)
def handle_exception(e):
    _LOGGER.error("HttpApiError: %s", e.error_code.name)
    return make_api_response(data=None, info=e.error_code.name, api_status=e.error_code)


@app.route('/_devs_/acl', methods=['POST'])
def device_acl():
    # For now, just return 200: allow connection from anyone
    return "ok", 200


@app.route('/_devs_/superuser', methods=['POST'])
def superuser_acl():
    # For now, just return 403
    return "ko", 403


@app.route('/_devs_/auth', methods=['POST'])
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
        userid=int(userid)
    except ValueError as e:
        _LOGGER.error(f"UserId \"{userid}\" is invalid.")
        return "ko", 400

    userrow = DbHelper.get_db().get_user_by_id(userid=userid)
    if userrow is None:
        _LOGGER.error(f"UserId \"{userid}\" does not exist.")
        return "ko", 401

    email = userrow[0]
    userid = userrow[1]
    key = userrow[3]
    
    expected_md5hash = md5()
    expected_md5hash.update(f"{mac}{key}".encode())
    expected_digest = expected_md5hash.hexdigest()

    _LOGGER.debug(f"Login attempt from \"{mac}\", provided hash \"{md5hash}\", expected \"{expected_digest}\".")

    if expected_digest == md5hash:
        DbHelper.get_db().associate_user_device(userid=userid, mac=mac)
        _LOGGER.info(f"Device login attempt succeeded. Device with mac \"{mac}\" has been associated to userid \"{userid}\"")
        return "ok", 200
    else:
        _LOGGER.warning(f"Device login attempt failed (device with mac \"{mac}\", userid \"{userid}\")")
        return "ko", 403


@app.route('/v1/Auth/Login', methods=['POST'])
def login():
    j = request.get_json()
    params = j.get('params')
    signature = j.get('sign')
    timestamp = j.get('timestamp')
    nonce = j.get('nonce')

    if params is None:
        raise BadRequestError("Empty params payload")
    if signature is None:
        raise BadRequestError("Missing signature")
    if timestamp is None:
        raise BadRequestError("Missing timestamp")
    if nonce is None:
        raise BadRequestError("Missing nonce")

    if not verify_message_signature(signature, timestamp, nonce, params):
        raise BadRequestError("Key verification failed")

    jsondata = base64.standard_b64decode(params)
    payload = json.loads(jsondata)
    email = payload.get("email")
    password = payload.get("password")

    token, key, userid, email = _user_login(email, password)
    _LOGGER.info("User: %s successfully logged in" % email)
    data = {
        "token": str(token),
        "key": str(key),
        "userid": str(userid),
        "email": str(email)
    }
    return make_api_response(data=data)


def make_api_response(data: Optional[dict], api_status: ErrorCodes = ErrorCodes.CODE_NO_ERROR, info: str = None, status_code: int = 200):
    return jsonify({
        "apiStatus": api_status.value,
        "info": info,
        "data": data
    }), status_code


if __name__ == '__main__':
    # Start flask
    app.run(debug=True, host="0.0.0.0", port=2002)
