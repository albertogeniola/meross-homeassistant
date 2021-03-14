import logging
import re
from hashlib import md5

from flask import Flask, request
from flask import g

from database import db_session, init_db
from blueprints.auth import auth_blueprint
from blueprints.profile import profile_blueprint
from codes import ErrorCodes
from db_helper import dbhelper
from messaging import make_api_response
from model.exception import HttpApiError, BadRequestError
from flask.logging import default_handler


_LOG_URL = "/v1/log/user"
_DEV_LIST = "/v1/Device/devList"
_HUB_DUBDEV_LIST = "/v1/Hub/getSubDevices"
_LOGOUT_URL = "/v1/Profile/logout"


_DEV_PASSWORD_RE = re.compile("^([0-9]+)\_([a-zA-Z0-9]+)$")

_LOGGER = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(auth_blueprint, url_prefix="/v1/Auth")
app.register_blueprint(profile_blueprint, url_prefix="/v1/Profile")
#app.register_blueprint(device_bludprint)
#app.register_blueprint(hub_blueprint)


root = logging.getLogger()
root.addHandler(default_handler)

# TODO: make this configurable
root.setLevel(logging.DEBUG)

init_db()


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


@app.errorhandler(Exception)
def handle_exception(e):
    _LOGGER.exception("Uncaught exception: %s", str(e))
    return make_api_response(data=None, info=str(e), api_status=ErrorCodes.CODE_GENERIC_ERROR, status_code=500)


@app.errorhandler(BadRequestError)
def handle_bad_exception(e):
    _LOGGER.exception("BadRequest error: %s", e.msg)
    return make_api_response(data=None, info=e.msg, api_status=ErrorCodes.CODE_GENERIC_ERROR, status_code=400)


@app.errorhandler(HttpApiError)
def handle_http_exception(e):
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

    userrow = dbhelper.get_user_by_id(userid=userid)
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
        dbhelper.associate_user_device(userid=userid, mac=mac)
        _LOGGER.info(f"Device login attempt succeeded. Device with mac \"{mac}\" has been associated to userid \"{userid}\"")
        return "ok", 200
    else:
        _LOGGER.warning(f"Device login attempt failed (device with mac \"{mac}\", userid \"{userid}\")")
        return "ko", 403

