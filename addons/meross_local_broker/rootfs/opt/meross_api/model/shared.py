import logging
import re

_LOGGER = logging.getLogger(__name__)


camel_pat = re.compile(r'([A-Z])')
under_pat = re.compile(r'_([a-z])')


def _camel_to_underscore(key):
    return camel_pat.sub(lambda x: '_' + x.group(1).lower(), key)


def _underscore_to_camel(key):
    return under_pat.sub(lambda x: x.group(1).upper(), key)


class BaseDictPayload(object):
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def from_dict(cls, json_dict: dict):
        # Transform the camel-case notation into a more pythonian case
        new_dict = {_camel_to_underscore(key): value for (key, value) in json_dict.items()}
        obj = cls(**new_dict)
        return obj

    def to_dict(self) -> dict:
        res = {}
        for k, v in vars(self).items():
            new_key = _underscore_to_camel(k)
            res[new_key] = v
        return res
