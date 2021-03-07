import logging
from typing import Dict

from flask import Blueprint

from authentication import _user_login
from messaging import make_api_response
from decorator import meross_http_api
from model.exception import HttpApiError

auth_blueprint = Blueprint('auth', __name__)
_LOGGER = logging.getLogger(__name__)


@auth_blueprint.route('/Login', methods=['POST'])
@meross_http_api(login_required=False)
def login(api_payload: Dict, *args, **kwargs):
    email = api_payload.get("email")
    password = api_payload.get("password")

    if email is None:
        raise HttpApiError("Missing email parameter")
    if password is None:
        raise HttpApiError("Missing password parameter")

    token, key, userid, email = _user_login(email, password)
    _LOGGER.info("User: %s successfully logged in" % email)
    data = {
        "token": str(token),
        "key": str(key),
        "userid": str(userid),
        "email": str(email)
    }
    return make_api_response(data=data)
