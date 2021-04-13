from typing import Dict

from sqlalchemy import Column, String, BigInteger, Integer, DateTime
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import relationship
from database import Base
from model.enums import OnlineStatus
from sqlalchemy.inspection import inspect


class Serializer(object):

    def serialize(self):
        return {c: getattr(self, c) for c in inspect(self).attrs.keys()}

    @staticmethod
    def serialize_list(l):
        return [m.serialize() for m in l]


class User(Base, Serializer):
    __tablename__ = 'users'
    __table_args__ = {'sqlite_autoincrement': True}

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(64), unique=True)
    salt = Column(String(64))
    password = Column(String(64))
    mqtt_key = Column(String(64))
    owned_devices = relationship("Device", back_populates="owner_user")

    def __init__(self, email: str, salt: str, password: str, mqtt_key: str, *args, **kwargs):
        self.email = email
        self.salt = salt
        self.password = password
        self.mqtt_key = mqtt_key

    def __repr__(self):
        return '<User %r (%r)>' % (self.user_id, self.email)

    def serialize(self):
        d = Serializer.serialize(self)
        del d['password']
        del d['owned_devices']
        return d


class UserToken(Base, Serializer):
    __tablename__ = 'user_tokens'

    token = Column(String(32), primary_key=True)
    user_id = Column(String, ForeignKey('users.user_id'))
    user = relationship("User")

    def __init__(self, token: str, user_id: str, *args, **kwargs):
        self.token = token
        self.user_id = user_id

    def __repr__(self):
        return '<UserToken %r (%r)>' % (self.token, self.user_id)

    def serialize(self):
        d = Serializer.serialize(self)
        del d['user']
        return d


class Device(Base, Serializer):
    __tablename__ = 'devices'

    mac = Column(String(16), primary_key=True)
    uuid = Column(String(36), unique=True)
    online_status = Column(Enum(OnlineStatus))
    device_name = Column(String(255))
    # dev_icon_id
    bind_time = Column(BigInteger())
    device_type = Column(String(255))
    device_sub_type = Column(String(255))
    # channels # TODO
    # region
    firmware_version = Column(String(16))
    hardware_version = Column(String(16))
    # user_dev_icon
    # icon_type
    # skill_number
    domain = Column(String(255))
    reserved_domain = Column(String(255))

    user_id = Column(String, ForeignKey('users.user_id'))
    owner_user = relationship("User", back_populates="owned_devices")

    # Technical fields
    last_seen_time = Column(DateTime)

    def __init__(self, mac: str, *args, **kwargs):
        self.mac = mac

    def serialize(self):
        d = Serializer.serialize(self)
        del d['owner_user']
        d['online_status'] = self.online_status.name
        return d