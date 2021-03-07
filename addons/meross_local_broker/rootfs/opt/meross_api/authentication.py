import uuid
from _sha256 import sha256
from typing import Tuple, Optional

from codes import ErrorCodes
from db_helper import DbHelper
from model.exception import HttpApiError


def verify_token(token) -> Optional[str]:
    """
    Returns the user's id for a given token.
    """
    return DbHelper.get_db().get_userid_by_token(token)


def _user_logout(token: str) -> None:
    DbHelper.get_db().remove_user_token(token=token)


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

    if computed_hashed_password != dbpwd:
        raise HttpApiError(ErrorCodes.CODE_WRONG_CREDENTIALS)

    # If ok, generate an HTTP_TOKEN
    hash = sha256()
    hash.update(uuid.uuid4().bytes)
    token = hash.hexdigest()

    # Store the new token
    DbHelper.get_db().store_new_user_token(userid, token)
    return token, mqtt_key, userid, email


