from typing import Optional

from database import db_session
from model.db_models import UserToken, Device, User


class DbHelper:
    def __init__(self):
        self._s = db_session

    def store_new_user_token(self, userid, token) -> UserToken:
        token = UserToken(user_id=userid, token=token)
        self._s.add(token)
        self._s.commit()
        return token

    def associate_user_device(self, userid: int, mac: str) -> None:
        # Check if a device with that MAC already exists. If so, update its user_id.
        # If not, create a new one
        d = self._s.query(Device).filter(Device.mac == mac).first()
        if d is None:
            d = Device(mac=mac)
        d.user_id = userid
        self._s.add(d)
        self._s.commit()

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self._s.query(User).filter(User.email == email).first()

    def remove_user_token(self, token: str) -> None:
        token = self._s.query(UserToken).get(token)
        if token is not None:
            self._s.delete(token)
            self._s.commit()

    def get_user_by_id(self, userid: int) -> Optional[User]:
        return self._s.query(User).filter(User.user_id == userid).first()

    def get_user_by_token(self, token: str) -> Optional[User]:
        ut = self._s.query(UserToken).filter(UserToken.token == token).first()
        if ut is None:
            return None
        return ut.user


dbhelper = DbHelper()
