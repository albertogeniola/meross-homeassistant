import argparse
from datetime import datetime
from logger import get_logger
import string
import sys
import ssl
from _md5 import md5
import random
import paho.mqtt.client as mqtt
import time
import re
import json
from threading import RLock

from database import init_db
from db_helper import dbhelper
from model.enums import OnlineStatus


APPLIANCE_SUBSCRIBE_TOPIC = '/appliance/+/subscribe'
l = get_logger(__name__)


class BrokerDeviceBridge:
    def __init__(self,
                 broker,
                 device_client_id: str,
                 meross_device_mac: str,
                 meross_user_id: str,
                 meross_key: str,
                 meross_mqtt_server: str = "iot.meross.com",
                 meross_mqtt_port: int = 2001):

        self._l = RLock()
        self._broker_ref = broker
        self._c = mqtt.Client(client_id=device_client_id, clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
        self._connected = False

        self.hostname = meross_mqtt_server
        self.port = meross_mqtt_port
        self.username = meross_device_mac
        md5_hash = md5()
        strtohash = f"{meross_device_mac}{meross_key}"
        md5_hash.update(strtohash.encode("utf8"))
        pwdhash = md5_hash.hexdigest().lower()
        self.password = f"{meross_user_id}_{pwdhash}"
        self.c = mqtt.Client(client_id="broker", clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
        self.c.username_pw_set(username=self.username, password=self.password)

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED
        self.c.tls_set_context(context)

        self.c.on_connect = self._on_connect
        self.c.on_disconnect = self._on_disconnect
        self.c.on_message = self._on_message

    def start(self):
        self._c.connect(host=self.hostname, port=self.port)
        self._c.loop_start()

    def stop(self):
        self._c.loop_stop(force=True)

    def _on_connect(self, client, userdata, rc, other):
        l.debug("Connected to Meross Iot network rc=%s", str(rc))
        self._connected = True

        # Subscribe to the remote Meross MQTT Broker
        client.subscribe(topic=APPLIANCE_SUBSCRIBE_TOPIC, qos=0)

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        l.debug("Subscribed to Meross Iot topic.")

    def _on_message(self, client, userdata, msg):
        # Forward the message to the local broker
        l.debug("Received message %s from Meross Remote Broker on topic %s", str(msg.payload), str(msg.topic))
        self._broker_ref.forward_device_command_locally(topic=msg.topic, payload=msg.payload)

    def _on_unsubscribe(self, *args, **kwargs):
        pass

    def _on_disconnect(self, client, userdata, rc):
        l.debug("Disconnected result code " + str(rc))
        self._connected = False
        # TODO: intercept wrong password?
        # client.loop_stop()

    def send_message(self, topic: str, payload: bytearray):
        with self._l:
            l.debug("Sending message %s to Meross Remote Broker on topic %s", str(payload), str(topic))
            self._c.publish(topic=topic, payload=payload)
