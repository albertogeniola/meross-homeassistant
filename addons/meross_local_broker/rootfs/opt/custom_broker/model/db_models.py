from typing import Dict

from meross_iot.model.enums import OnlineStatus
from sqlalchemy import Column, String, BigInteger, Integer, DateTime
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import relationship
from database import Base
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

    email = Column(String(64), primary_key=True, unique=True)
    user_id = Column(Integer, unique=True)
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


class DeviceChannel(Base, Serializer):
    __tablename__ = 'channels'
    __table_args__ = {'sqlite_autoincrement': True}

    device_channel_id = Column(Integer, primary_key=True, autoincrement=True)
    device_uuid = Column(String, ForeignKey('devices.uuid'))
    channel_id = Column(Integer)
    device = relationship("Device", back_populates="channels")

    def serialize(self):
        d = Serializer.serialize(self)
        del d['device']
        return d


class Device(Base, Serializer):
    __tablename__ = 'devices'

    mac = Column(String(16), primary_key=True)
    uuid = Column(String(36), unique=True)
    online_status = Column(Enum(OnlineStatus))
    dev_name = Column(String(255))
    dev_icon_id = Column(String(255))
    bind_time = Column(BigInteger())
    device_type = Column(String(255))
    sub_type = Column(String(255))
    channels = relationship("DeviceChannel", back_populates="device")
    region = Column(String(255))
    fmware_version = Column(String(16))
    hdware_version = Column(String(16))
    user_dev_icon = Column(String(64))
    icon_type = Column(String(64))
    skill_number = Column(String(64))
    domain = Column(String(255))
    reserved_domain = Column(String(255))

    local_ip = Column(String(16))
    client_id = Column(String(255))

    user_id = Column(String, ForeignKey('users.user_id'))
    owner_user = relationship("User", back_populates="owned_devices")

    # Technical fields
    last_seen_time = Column(DateTime)

    def __init__(self, mac: str, *args, **kwargs):
        self.mac = mac

    def serialize(self):
        d = Serializer.serialize(self)
        del d['owner_user']
        d['online_status'] = self.online_status.value
        d['user_email'] = self.owner_user.email
        d['channels'] = DeviceChannel.serialize_list(self.channels)
        return d
