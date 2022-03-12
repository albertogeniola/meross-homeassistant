import uuid
from _sha256 import sha256
from typing import Tuple, Optional

from meross_iot.http_api import ErrorCodes
from meross_iot.model.http.exception import HttpApiError

from db_helper import dbhelper
from model.db_models import User, UserToken
from utilities import _hash_password


def verify_token(token) -> Optional[User]:
    """
    Returns the user's id for a given token.
    """
    return dbhelper.get_user_by_token(token)


def _user_logout(token: str) -> None:
    dbhelper.remove_user_token(token=token)


def _user_login(email: str, password: str) -> Tuple[User, UserToken]:
    # Check user-password creds
    # email, userid, salt, password, mqtt_key
    user = dbhelper.get_user_by_email(email=email)
    if user is None:
        raise HttpApiError(ErrorCodes.CODE_UNEXISTING_ACCOUNT)

    computed_hashed_password = _hash_password(salt=user.salt, password=password)

    if computed_hashed_password != user.password:
        raise HttpApiError(ErrorCodes.CODE_WRONG_CREDENTIALS)

    # If ok, generate an HTTP_TOKEN
    hash = sha256()
    hash.update(uuid.uuid4().bytes)
    token = hash.hexdigest()

    # Store the new token
    token = dbhelper.store_new_user_token(user.user_id, token)
    return user, token


