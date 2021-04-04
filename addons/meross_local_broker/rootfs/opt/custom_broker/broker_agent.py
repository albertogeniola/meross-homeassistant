import argparse
import logging
import sys
import ssl
import paho.mqtt.client as mqtt
import time
import re

from database import init_db
from db_helper import dbhelper
from model.enums import OnlineStatus

CLIENT_ID = 'broker_agent'
APPLIANCE_MESSAGE_TOPICS = '/appliance/+/publish'

l = logging.getLogger()
l.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - BROKER: %(message)s')
handler.setFormatter(formatter)
l.addHandler(handler)

APPLIANCE_PUBLISH_TOPIC_RE = re.compile("/appliance/([a-zA-Z0-9]+)/publish")


def parse_args():
    parser = argparse.ArgumentParser(description='MQTT Broker Agent')
    parser.add_argument('--port', type=int, help='MQTT server port', default=2001)
    parser.add_argument('--host', type=str, help='MQTT server hostname', default='localhost')
    parser.add_argument('--username', type=str, required=True, help='MQTT username')
    parser.add_argument('--password', type=str, required=True, help='MQTT password')
    parser.add_argument('--debug', dest='debug', action='store_true', help='When set, prints debug messages')
    parser.add_argument('--cert-ca', required=True, type=str, help='Path to the root CA certificate path')
    parser.set_defaults(debug=False)
    return parser.parse_args()


class Broker:
    def __init__(self,
                 hostname: str,
                 port: int,
                 username: str,
                 password: str,
                 cert_ca: str):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.cert_ca = cert_ca
        self.c = mqtt.Client(client_id="broker", clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
        self.c.username_pw_set(username=self.username, password=self.password)

        context = ssl.create_default_context(cafile=self.cert_ca)
        context.check_hostname = False
        # context.set_ciphers(None)
        context.verify_mode = ssl.CERT_REQUIRED
        self.c.tls_set_context(context)

        self.c.on_connect = self._on_connect
        self.c.on_disconnect = self._on_disconnect
        self.c.on_message = self._on_message

    def setup(self):
        l.debug("Connecting as %s : %s", self.username, self.password)
        self.c.connect(host=self.hostname, port=self.port)
        # l.debug("Starting mqtt thread loop")
        # self.c.loop_start()

    def _on_connect(self, client, userdata, rc, other):
        l.debug("Connected to broker, rc=%s", str(rc))
        self.c.subscribe(APPLIANCE_MESSAGE_TOPICS)

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        l.debug("Subscribed to relevant topics")

    def _on_message(self, client, userdata, msg):
        l.debug(f"Received message from topic {msg.topic}: {str(msg.payload)}")
        self._handle_message(topic=msg.topic, payload=msg.payload)

    def _on_unsubscribe(self, *args, **kwargs):
        l.debug("Unsubscribed")

    def _on_disconnect(self, client, userdata, rc):
        l.debug("Disconnection detected. Reason: %s" % str(rc))

        # If the client disconnected explicitly
        if rc == mqtt.MQTT_ERR_SUCCESS:
            pass
        else:
            # Otherwise, if the disconnection was not intentional, we probably had a connection drop.
            l.warning("Client has been disconnected. Connection will be re-attempted.")

    def setdown(self):
        l.info("Disconnecting from mqtt broker")
        self.c.disconnect()
        l.debug("Stopping the MQTT looper.")
        self.c.loop_stop(True)
        l.info("MQTT Client has fully disconnected.")

    def _handle_message(self, topic, payload):
        try:
            # Extract the device_uuid from he topic
            match = APPLIANCE_PUBLISH_TOPIC_RE.fullmatch(topic)
            if match is None:
                l.warning("Skipped message against topic %s.", topic)
                return

            # If the message comes from a known device, update its online status


            # Find the USER-ID assigned to the given device
            device_uuid = match.group(1)
            user = dbhelper.find_user_owner_by_device_uuid(device_uuid)
            if user is None:
                l.warning("No user associated to device UUID %s, message will be skipped.", device_uuid)
                return
            l.debug("Forwarding message for device %s to user %s", device_uuid, user)
            self.c.publish(topic=f"/app/{user.user_id}/subscribe", payload=payload)

        except Exception as ex:
            l.exception("An error occurred while handling message %s received on topic %s", str(payload), str(topic))


class OnlineStatusManager:
    def __init__(self):
        self._online_dev_status={}

    def notify_device_online(self, uuid: str):
        old_status = self._online_dev_status.get(uuid)
        if old_status is None:
            dbhelper.update_device_status(device_uuid=uuid, status=OnlineStatus.ONLINE)
            self._online_dev_status[uuid] = OnlineStatus.ONLINE
        


def main():
    args = parse_args()
    if args.debug:
        handler.setLevel(logging.DEBUG)
        l.setLevel(logging.DEBUG)

    # Init or setup DB
    init_db()

    b = Broker(hostname=args.host, port=args.port, username=args.username, password=args.password, cert_ca=args.cert_ca)

    reconnect_interval = 10  # [seconds]
    while True:
        try:
            b.setup()
            b.c.loop_forever()

        except KeyboardInterrupt as ex:
            l.warning("Keyboard interrupt received, exiting.")
            b.setdown()
            break
        except Exception as ex:
            l.exception("An unhandled error occurred")
            b.setdown()
            time.sleep(reconnect_interval)


if __name__ == '__main__':
    main()
