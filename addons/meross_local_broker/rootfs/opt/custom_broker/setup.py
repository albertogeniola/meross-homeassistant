from meross_iot.model.credentials import MerossCloudCreds

from logger import get_logger
import argparse
from constants import DEFAULT_USER_ID, DEFAULT_USER_KEY
from database import init_db
from db_helper import dbhelper


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


def get_meross_credentials(email: str, password: str) -> MerossCloudCreds:
    import asyncio

    async def get_creds(email: str = email, password: str = password) -> MerossCloudCreds:
        creds = await MerossHttpClient.async_login(email=email, password=password)
        return creds
    return asyncio.run(get_creds(email=email, password=password))


def setup_account(email: str, password: str, enable_meross_link: bool):
    user_key = DEFAULT_USER_KEY
    user_id = DEFAULT_USER_ID
    if enable_meross_link:
        l.info("Trying to federate against Meross Cloud for user %s...", email)
        creds = get_meross_credentials(email=email, password=password)
        l.debug("Retrieved credentials from Meross: %s", str(creds.to_json()))
        user_id = int(creds.user_id)
        user_key = creds.key

    user = dbhelper.add_update_user(user_id=user_id, email=email, password=password, user_key=user_key, enable_meross_link=enable_meross_link)
    l.info(f"User: %s, mqtt_key: %s", user.email, user.mqtt_key)


def main():
    args = parse_args()
    init_db()
    setup_account(email=args.email, password=args.password, enable_meross_link=args.federate_remote_broker)
    

if __name__ == '__main__':
    main()
