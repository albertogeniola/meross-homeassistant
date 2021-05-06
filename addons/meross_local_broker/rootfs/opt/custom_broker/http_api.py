from codes import ExtendedErrorCodes
from logger import get_logger

from flask import Flask
from flask.logging import default_handler
from flask_cors import CORS

from blueprints.auth import auth_blueprint
from blueprints.devs import devs_blueprint
from blueprints.profile import profile_blueprint
from blueprints.admin import admin_blueprint
from blueprints.device import device_blueprint
from database import db_session, init_db
from messaging import make_api_response
from model.exception import HttpApiError, BadRequestError

#_HUB_DUBDEV_LIST = "/v1/Hub/getSubDevices"
#_LOGOUT_URL = "/v1/Profile/logout"


# Configure main logger
_LOGGER = get_logger("http_api")


app = Flask(__name__)
CORS(app)  # TODO: Fix this. Maybe we can restrict the origin access. In case we use an nginx, this might be superfluous


app.register_blueprint(auth_blueprint, url_prefix="/v1/Auth")
app.register_blueprint(profile_blueprint, url_prefix="/v1/Profile")
app.register_blueprint(device_blueprint, url_prefix="/v1/Device")
app.register_blueprint(devs_blueprint, url_prefix="/_devs_")
app.register_blueprint(admin_blueprint, url_prefix="/_admin_")
#app.register_blueprint(hub_blueprint)


init_db()


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


@app.errorhandler(Exception)
def handle_exception(e):
    _LOGGER.exception("Uncaught exception: %s", str(e))
    return make_api_response(data=None, info=str(e), api_status=ExtendedErrorCodes.CODE_GENERIC_ERROR, status_code=500)


@app.errorhandler(BadRequestError)
def handle_bad_exception(e):
    _LOGGER.exception("BadRequest error: %s", e.msg)
    return make_api_response(data=None, info=e.msg, api_status=ExtendedErrorCodes.CODE_GENERIC_ERROR, status_code=400)


@app.errorhandler(HttpApiError)
def handle_http_exception(e):
    _LOGGER.error("HttpApiError: %s", e.error_code.name)
    return make_api_response(data=None, info=e.error_code.name, api_status=e.error_code)


if __name__ == '__main__':
    app.run(port=2002, host="0.0.0.0")