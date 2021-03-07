import base64
import json
import re
from functools import wraps

from flask import request, g, app
import logging
from authentication import verify_token
from messaging import verify_message_signature
from model.exception import BadRequestError, UnauthorizedException

TOKEN_EXTRACTOR = re.compile("^Basic ([a-zA-Z0-9]+)")
l = logging.getLogger(__name__)


def meross_http_api(original_function=None, login_required=True):
    def _decorate(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            # AUTH TOKEN VERIFICATION
            # If login_required is specified, we should check the Authorization header
            if login_required:
                auth_str = request.headers.get("Authorization")
                if auth_str is None:
                    raise UnauthorizedException("Missing auth token")

                res = TOKEN_EXTRACTOR.match(auth_str)
                if not res:
                    raise UnauthorizedException("Missing auth token")

                token = res.group(1)
                l.debug("User provided token: %s", token)
                user_id = verify_token(token)
                if user_id is None:
                    raise UnauthorizedException("Invalid/Expired auth token")

                l.info("User %s recognized by token %s", user_id, token)

                g.user_token = token
                g.user_id = user_id

            # MEROSS HTTP API requires a valid json payload that contains the following
            # - params: json-encoded parameters
            # - sign: message signature
            # - timestamp
            # - nonce
            j = request.get_json()
            if j is None:
                raise BadRequestError("Missing json payload")

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

            return f(*args, **kwargs, api_payload=payload)
        return wrap

    if original_function:
        return _decorate(original_function)

    return _decorate
