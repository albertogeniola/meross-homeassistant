import base64
import json
from logger import get_logger
import re
from functools import wraps

from flask import request, g

from authentication import verify_token
from codes import ExtendedErrorCodes
from messaging import verify_message_signature
from model.exception import BadRequestError, HttpApiError

TOKEN_EXTRACTOR = re.compile("^Basic ([a-zA-Z0-9]+)")
l = get_logger(__name__)


def meross_http_api(original_function=None, login_required=True):
    def _decorate(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            # AUTH TOKEN VERIFICATION
            # If login_required is specified, we should check the Authorization header
            if login_required:
                auth_str = request.headers.get("Authorization")
                if auth_str is None:
                    raise HttpApiError(error_code=ExtendedErrorCodes.CODE_TOKEN_ERROR)

                res = TOKEN_EXTRACTOR.match(auth_str)
                if not res:
                    raise HttpApiError(error_code=ExtendedErrorCodes.CODE_TOKEN_ERROR)

                token = res.group(1)
                l.debug("User provided token: %s", token)
                user = verify_token(token)
                if user is None:
                    raise HttpApiError(error_code=ExtendedErrorCodes.CODE_TOKEN_ERROR)

                l.info("User %s recognized by token %s", user, token)

                g.user_token = token
                g.user = user

            # MEROSS HTTP API requires a valid json payload that contains the following
            # - params: json-encoded parameters
            # - sign: message signature
            # - timestamp
            # - nonce
            if request.json is not None:
                l.debug("Found input json (%s)", str(request.json))
                j = request.json
                params = j.get('params')
                signature = j.get('sign')
                timestamp = j.get('timestamp')
                nonce = j.get('nonce')
            elif request.form is not None:
                l.debug("Parsing input from form data: %s", str(request.form))
                params = request.form.get('params')
                signature = request.form.get('sign')
                timestamp = request.form.get('timestamp')
                nonce = request.form.get('nonce')
            else:
                raise BadRequestError("Missing or invalid payload")

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
