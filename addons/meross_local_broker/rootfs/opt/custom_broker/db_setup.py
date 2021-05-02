from logger import get_logger
import argparse
import random

from authentication import _hash_password
from constants import BASE62_ALPHABET
from database import db_session, init_db
from model.db_models import User


l = get_logger("db_setup")


def parse_args():
    parser = argparse.ArgumentParser(description='DB Setup utility')
    parser.add_argument('--email', required=True, type=str, help='User email/username')
    parser.add_argument('--password', required=True, type=str, help='User password')

    return parser.parse_args()


def add_update_user(email: str, password: str) -> User:
    # Check if the given user/password already exists or is valid.
    u = db_session.query(User).filter(User.email == email).first()
    if u is None:
        l.info(f"User %s not found in db. Adding a new entry...", email)
        salt = ''.join(random.choice(BASE62_ALPHABET) for i in range(16))
        hashed_pass = _hash_password(salt=salt, password=password)
        mqtt_ley = ''.join(random.choice(BASE62_ALPHABET) for i in range(16))
        u = User(email=email, salt=salt, password=hashed_pass, mqtt_key=mqtt_ley)
        db_session.add(u)
        db_session.commit()
    else:
        l.info(f"User %s already exists. Updating its password...", email)
        salt = u.salt
        hashed_pass = _hash_password(salt=salt, password=password)
        u.password = hashed_pass
        db_session.add(u)
        db_session.commit()
    return u


def main():
    args = parse_args()
    init_db()
    user = add_update_user(email=args.email, password=args.password)
    l.info(f"User: %s, mqtt_key: %s", user.email, user.mqtt_key)


if __name__ == '__main__':
    main()
