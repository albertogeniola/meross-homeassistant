from typing import Dict, Optional

from meross_iot.model.enums import OnlineStatus
from sqlalchemy import Column, String, BigInteger, Integer, DateTime
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import relationship
from database import Base
from sqlalchemy.inspection import inspect

from model.enums import BridgeStatus, EventType


class Serializer(object):

    def serialize(self):
        return {c: getattr(self, c) for c in inspect(self).attrs.keys()}

    @staticmethod
    def serialize_list(l):
        return [m.serialize() for m in l]


class User(Base, Serializer):
    __tablename__ = 'users'
    __table_args__ = {'sqlite_autoincrement': True}

    user_id = Column(Integer, primary_key=True)
    email = Column(String(64), unique=True, autoincrement=True)
    salt = Column(String(64))
    password = Column(String(64))
    mqtt_key = Column(String(64))
    owned_devices = relationship("Device", back_populates="owner_user")

    def __init__(self, email: str, salt: str, password: str, mqtt_key: str, user_id: Optional[int], *args, **kwargs):
        self.email = email
        self.salt = salt
        self.password = password
        self.mqtt_key = mqtt_key
        self.user_id = user_id

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
    child_subdevices = relationship("SubDevice", back_populates="parent_device")

    # Technical fields
    last_seen_time = Column(DateTime)
    bridge_status = Column(Enum(BridgeStatus), default=BridgeStatus.DISCONNECTED)

    def __init__(self, mac: str, *args, **kwargs):
        self.mac = mac

    def serialize(self):
        d = Serializer.serialize(self)
        del d['owner_user']
        d['online_status'] = self.online_status.value
        d['user_email'] = self.owner_user.email
        d['channels'] = DeviceChannel.serialize_list(self.channels)
        d['child_subdevices'] = SubDevice.serialize_list(self.child_subdevices)
        d['bridge_status'] = self.bridge_status.name
        return d


class SubDevice(Base, Serializer):
    __tablename__ = 'subdevices'

    sub_device_id = Column(String(16), primary_key=True)
    true_id = Column(String(8))
    sub_device_type = Column(String(16))
    sub_device_vendor = Column(String(16))
    sub_device_name = Column(String(255))
    sub_device_icon_id = Column(String(16))

    hub_uuid = Column(String, ForeignKey('devices.uuid'))
    parent_device = relationship("Device", back_populates="child_subdevices")

    def __init__(self, subdevice_id: str, *args, **kwargs):
        self.sub_device_id = subdevice_id

    def serialize(self):
        d = Serializer.serialize(self)
        del d['parent_device']
        return d


class Event(Base, Serializer):
    __tablename__ = 'events'
    __table_args__ = {'sqlite_autoincrement': True}
    
    event_id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(Enum(EventType), nullable=False)
    device_uuid = Column(String, nullable=True)
    sub_device_id = Column(String, nullable=True)
    user_id = Column(String, nullable=True)
    details = Column(String, nullable=True)
    