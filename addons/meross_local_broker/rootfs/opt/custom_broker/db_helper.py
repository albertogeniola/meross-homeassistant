from meross_iot.model.enums import OnlineStatus

from logger import get_logger
from typing import Optional, List

from database import db_session
from model.db_models import UserToken, Device, User, DeviceChannel, SubDevice, Event
from datetime import datetime

from model.enums import BridgeStatus, EventType

l = get_logger(__name__)


class DbHelper:
    def __init__(self):
        self._s = db_session

    def store_new_user_token(self, userid, token) -> UserToken:
        token = UserToken(user_id=userid, token=token)
        self._s.add(token)
        self._s.commit()
        return token

    def associate_user_device(self, userid: int, mac: str, uuid: str, device_client_id: str) -> None:
        # Check if a device with that MAC already exists. If so, update its user_id.
        # If not, create a new one
        d = self._s.query(Device).filter(Device.mac == mac).first()
        if d is None:
            d = Device(mac=mac)
        d.user_id = userid
        d.uuid = uuid
        d.client_id = device_client_id
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

    def find_user_owner_by_device_uuid(self, device_uuid: str) -> Optional[User]:
        dev = self._s.query(Device).filter(Device.uuid == device_uuid).first()
        if dev is None:
            return None
        return dev.owner_user

    def get_device_by_uuid(self, device_uuid: str) -> Optional[Device]:
        dev = self._s.query(Device).filter(Device.uuid == device_uuid).first()
        if dev is None:
            return None
        return dev

    def update_device(self, device: Device) -> Device:
        self._s.add(device)
        self._s.commit()
        return device

    def get_all_devices(self) -> List[Device]:
        return self._s.query(Device).all()

    def update_device_status(self, device_uuid: str, status: OnlineStatus) -> None:
        dev = self._s.query(Device).filter(Device.uuid == device_uuid).first()
        if dev is None:
            raise Exception("Device %s was not present into the database." % device_uuid)
        dev.online_status = status
        dev.last_seen_time = datetime.now()
        self._s.add(dev)
        self._s.commit()

    def update_device_channel(self, device_uuid: str, channel_id: int) -> DeviceChannel:
        dev = self._s.query(Device).filter(Device.uuid == device_uuid).first()
        if dev is None:
            raise Exception("Device %s was not present into the database." % device_uuid)

        channel = None
        for c in dev.channels:
            if c.channel_id == channel_id:
                l.debug("Channel %d already attached to device uuid %s: channel__id %s", channel_id, device_uuid,
                        c.device_channel_id)
                channel = c
                break

        # TODO: channel name/type update?

        if channel is None:
            l.info("Discovered channel index %d on device uuid %s", channel_id, device_uuid)
            channel = DeviceChannel()
            channel.channel_id = channel_id
            channel.device_uuid = device_uuid

            self._s.add(channel)
            self._s.commit()

        return channel

    def update_device_bridge_status(self, device_uuid: str, status: BridgeStatus):
        device = self.get_device_by_uuid(device_uuid=device_uuid)
        if device is None:
            raise Exception("Invalid device uuid")
        device.bridge_status = status
        self._s.add(device)
        self._s.commit()

    def bind_subdevice(self, subdevice_type: str, subdevice_id: str, hub_uuid: str) -> SubDevice:
        l.info("Binding subdevice %s to hub id %s", subdevice_id, hub_uuid)
        # Check if the subdevice exists. If so, update the existing one
        subdevice = self._s.query(SubDevice).filter(SubDevice.sub_device_id == subdevice_id).first()
        if subdevice is None:
            subdevice = SubDevice(subdevice_id=subdevice_id)
        subdevice.sub_device_type = subdevice_type
        subdevice.hub_uuid = hub_uuid
        self._s.add(subdevice)
        self._s.commit()
        return subdevice

    def unbind_subdevice(self, subdevice_id: str) -> None:
        l.info("Unbinding subdevice %s", subdevice_id)
        # Check if the subdevice exists. If so, update the existing one
        subdevice = self._s.query(SubDevice).filter(SubDevice.sub_device_id == subdevice_id).first()
        if subdevice is not None:
            self._s.delete(subdevice)
            self._s.commit()

    def get_all_subdevices(self) -> List[SubDevice]:
        return self._s.query(SubDevice).all()

    def get_subdevice_by_id(self, subdevice_id: str) -> Optional[SubDevice]:
        return self._s.query(SubDevice).filter(SubDevice.sub_device_id == subdevice_id).first()

    def update_subdevice(self, subdevice: SubDevice) -> SubDevice:
        self._s.add(subdevice)
        self._s.commit()
        return subdevice

    def reset_device_online_status(self) -> None:
        self._s.query(Device).update({Device.online_status: OnlineStatus.UNKNOWN})
        self._s.commit()

    def store_event(self, event_type: EventType, device_uuid: str = None, sub_device_id: str = None, user_id:str = None, details: str = None) -> Event:
        event = Event(event_type=event_type, device_uuid=device_uuid, sub_device_id=sub_device_id, user_id=user_id, details=details)
        self._s.add(event)
        self._s.commit()
        return event


dbhelper = DbHelper()
