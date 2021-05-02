from logger import get_logger
from typing import Dict

from flask import Blueprint, g

from authentication import _user_logout
from decorator import meross_http_api
from messaging import make_api_response

profile_blueprint = Blueprint('profile', __name__)
_LOGGER = get_logger(__name__)


@profile_blueprint.route('/logout', methods=['POST'])
@meross_http_api(login_required=True)
def logout(api_payload: Dict):
    # Retrieve the current logged user
    user = g.user
    _LOGGER.info("Logging out user %s", user)

    # Invalidate the current token
    _user_logout(g.user_token)

    return make_api_response(data={}, status_code=200)
