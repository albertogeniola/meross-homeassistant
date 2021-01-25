import json
import logging

from shared import BaseDictPayload

_LOGGER = logging.getLogger(__name__)


class HttpSubdeviceInfo(BaseDictPayload):
    def __init__(self,
                 sub_device_id: str,
                 true_id: str,
                 sub_device_type: str,
                 sub_device_vendor: str,
                 sub_device_name: str,
                 sub_device_icon_id: str,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.sub_device_id = sub_device_id
        self.true_id = true_id
        self.sub_device_type = sub_device_type
        self.sub_device_vendor = sub_device_vendor
        self.sub_device_name = sub_device_name
        self.sub_device_icon_id = sub_device_icon_id

    def __repr__(self):
        return json.dumps(self.__dict__)

    def __str__(self):
        basic_info = f"{self.sub_device_name} ({self.sub_device_type}, ID {self.sub_device_id}, TRUE-ID {self.true_id})"
        return basic_info
