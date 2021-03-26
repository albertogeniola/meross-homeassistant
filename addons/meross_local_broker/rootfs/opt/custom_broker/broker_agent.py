import argparse
import logging
import sys
import ssl
import paho.mqtt.client as mqtt
from threading import Event
import time

CLIENT_ID = 'broker_agent'
APPLIANCE_MESSAGE_TOPICS = '/appliance/+/publish'

l = logging.getLogger()
l.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - BROKER: %(message)s')
handler.setFormatter(formatter)
l.addHandler(handler)


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
        self._connected_and_subscribed = Event()

        context = ssl.create_default_context(cafile=self.cert_ca)
        context.check_hostname = False
        self.c.tls_set_context(context)

        self.c.on_connect = self._on_connect
        self.c.on_disconnect = self._on_disconnect
        self.c.on_message = self._on_message

    def setup(self, timeout=None):
        self.c.connect(host=self.hostname, port=self.port)

        # l.debug("Starting mqtt thread loop")
        # self.c.loop_start()

        l.debug("Waiting for connect+subscribe")
        res = self._connected_and_subscribed.wait(timeout=timeout)
        if timeout is not None and not res:
            raise TimeoutError("Connection and subscription to the broker timeout")

        l.info("Connection to remote broker successful")

    def _on_connect(self, client, userdata, rc, other):
        l.debug("Connected to broker, rc=%s", str(rc))
        self.c.subscribe(APPLIANCE_MESSAGE_TOPICS)

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        l.debug("Subscribed to relevant topics")
        self._connected_and_subscribed.set()
        self._connected_and_subscribed.clear()

    def _on_message(self, client, userdata, msg):
        l.debug("Received message: %s", str(msg))

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
        self._connected_and_subscribed.clear()
        l.info("MQTT Client has fully disconnected.")


def main():
    args = parse_args()
    if args.debug:
        handler.setLevel(logging.DEBUG)
        l.setLevel(logging.DEBUG)

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
