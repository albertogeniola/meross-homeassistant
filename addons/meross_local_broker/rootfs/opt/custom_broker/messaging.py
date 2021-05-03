from hashlib import md5
from typing import Optional

from flask import jsonify
from codes import ExtendedErrorCodes
from constants import _SECRET


def make_api_response(data: Optional[dict], api_status: ExtendedErrorCodes = ExtendedErrorCodes.CODE_NO_ERROR, info: str = None, status_code: int = 200):
    return jsonify({
        "apiStatus": api_status.value,
        "info": info,
        "data": data
    }), status_code


def verify_message_signature(signature: str, timestamp_millis: str, nonce: str, b64params: str):
    message_hash = md5()
    datatosign = '%s%s%s%s' % (_SECRET, timestamp_millis, nonce, b64params)
    message_hash.update(datatosign.encode("utf8"))
    md5hash = message_hash.hexdigest()
    return md5hash == signature
