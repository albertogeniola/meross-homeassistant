import json
import random
import string
import time
from _md5 import md5


def _build_mqtt_message(method: str, namespace: str, payload: dict, dev_key: str):
    # Generate a random 16 byte string
    randomstring = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(16))

    # Hash it as md5
    md5_hash = md5()
    md5_hash.update(randomstring.encode('utf8'))
    messageId = md5_hash.hexdigest().lower()
    timestamp = int(round(time.time()))

    # Hash the messageId, the key and the timestamp
    md5_hash = md5()
    strtohash = "%s%s%s" % (messageId, dev_key, timestamp)
    md5_hash.update(strtohash.encode("utf8"))
    signature = md5_hash.hexdigest().lower()

    data = {
        "header":
            {
                "from": "/_agent",
                "messageId": messageId,  # Example: "122e3e47835fefcd8aaf22d13ce21859"
                "method": method,  # Example: "GET",
                "namespace": namespace,  # Example: "Appliance.System.All",
                "payloadVersion": 1,
                "sign": signature,  # Example: "b4236ac6fb399e70c3d61e98fcb68b74",
                "timestamp": timestamp,
                'triggerSrc': 'Agent'
            },
        "payload": payload
    }
    strdata = json.dumps(data)
    return strdata.encode("utf-8"), messageId