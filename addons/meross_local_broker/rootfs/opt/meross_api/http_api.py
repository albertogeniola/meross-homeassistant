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
from model.exception import HttpApiError


_LOG_URL = "/v1/log/user"
_DEV_LIST = "/v1/Device/devList"
_HUB_DUBDEV_LIST = "/v1/Hub/getSubDevices"
_LOGOUT_URL = "/v1/Profile/logout"

_LOGGER = logging.getLogger(__name__)
app = Flask(__name__)


def _user_login(email, password) -> Tuple[str, str, str, str]:
    # Check user-password creds
    data = DbHelper.get_db().get_user_by_email_password(email=email, password=password)
    if data is None:
        raise HttpApiError(ErrorCodes.CODE_WRONG_CREDENTIALS)

    email = data[0]
    userid = data[1]
    key = data[3]

    # If ok, generate an HTTP_TOKEN
    hash = sha256()
    hash.update(uuid.uuid4().bytes)
    token = hash.hexdigest()

    # Store the new token
    DbHelper.get_db().store_new_user_token(userid, token)
    return token, key, userid, email


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


@app.errorhandler(HttpApiError)
def handle_exception(e):
    return make_api_response(data=None, api_status=e.error_code)


@app.route('/v1/Auth/Login', methods=['POST'])
def login():
    params = request.values.get('params')
    signature = request.values.get('sign')
    timestamp = request.values.get('timestamp')
    nonce = request.values.get('nonce')

    if params is None:
        raise HttpApiError("Empty params payload")
    if signature is None:
        raise HttpApiError("Missing signature")
    if timestamp is None:
        raise HttpApiError("Missing timestamp")
    if nonce is None:
        raise HttpApiError("Missing nonce")

    if not verify_message_signature(signature, timestamp, nonce, params):
        raise Exception("Key verification failed")

    jsondata = base64.standard_b64decode(params)
    payload = json.loads(jsondata)
    email = payload.get("email")
    password = payload.get("password")

    token, key, userid, email = _user_login(email, password)
    _LOGGER.info("User: %s successfully logged in" % email)
    data = {
        "token": token,
        "key": key,
        "userid": userid,
        "email": email}
    return make_api_response(data=data)


def make_api_response(data: Optional[dict], api_status: ErrorCodes = ErrorCodes.CODE_NO_ERROR, status_code: int = 200):
    return jsonify({
        "apiStatus": api_status.value,
        "data": data
    }), status_code


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=2002)
