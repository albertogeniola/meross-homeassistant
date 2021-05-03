from meross_iot.model.credentials import MerossCloudCreds

from logger import get_logger
import argparse
import random

from authentication import _hash_password
from constants import BASE62_ALPHABET
from database import db_session, init_db
from model.db_models import User

from meross_iot.http_api import MerossHttpClient

l = get_logger("setup")


def parse_args():
    parser = argparse.ArgumentParser(description='Setup utility')
    parser.add_argument('--email', required=True, type=str, help='User email/username')
    parser.add_argument('--password', required=True, type=str, help='User password')
    parser.add_argument('--federate-remote-broker', action='store_true',
                        help='When set, mirrors the remote Meross account to the local broker. '
                             'In this case, the email/password must be valid Meross credentials.')

    return parser.parse_args()


def add_update_user(email: str, password: str, user_key: str, user_id: int = 1) -> User:
    # Check if the given user/password already exists or is valid.
    u = db_session.query(User).filter(User.email == email).first()
    if u is None:
        l.info(f"User %s not found in db. Adding a new entry...", email)
        if user_key is None:
            user_key = ''.join(random.choice(BASE62_ALPHABET) for i in range(16))
        salt = ''.join(random.choice(BASE62_ALPHABET) for i in range(16))
        hashed_pass = _hash_password(salt=salt, password=password)
        u = User(email=email, user_id=user_id, salt=salt, password=hashed_pass, mqtt_key=user_key)
        db_session.add(u)
        db_session.commit()
    else:
        l.warning(f"User %s already exists. Updating its password/userid/mqttkey...", email)
        salt = u.salt
        hashed_pass = _hash_password(salt=salt, password=password)
        u.password = hashed_pass

        if user_key is not None:
            u.mqtt_key = user_key

        if user_id is not None:
            u.user_id = user_id

        db_session.add(u)
        db_session.commit()
    return u


def get_meross_credentials(email: str, password: str) -> MerossCloudCreds:
    import asyncio

    async def get_creds(email: str = email, password: str = password) -> MerossCloudCreds:
        creds = await MerossHttpClient.async_login(email=email, password=password)
        return creds
    return asyncio.run(get_creds(email=email, password=password))


def main():
    args = parse_args()
    init_db()

    user_key = None
    user_id = None

    if args.federate_remote_broker:
        l.info("Trying to federate against Meross Cloud for user %s...", args.email)
        creds = get_meross_credentials(email=args.email, password=args.password)
        l.debug("Retrieved credentials from Meross: %s", str(creds.to_json()))
        user_id = int(creds.user_id)
        user_key = creds.key

    user = add_update_user(email=args.email, password=args.password, user_key=user_key, user_id=user_id)
    l.info(f"User: %s, mqtt_key: %s", user.email, user.mqtt_key)


if __name__ == '__main__':
    main()
