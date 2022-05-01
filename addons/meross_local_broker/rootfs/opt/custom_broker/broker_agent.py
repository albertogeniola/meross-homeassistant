import argparse
import json
import logging
import re
import ssl
import time
import uuid
from datetime import datetime
from threading import RLock
from typing import Dict, List

import paho.mqtt.client as mqtt
from expiringdict import ExpiringDict
from meross_iot.model.enums import OnlineStatus

from broker_bridge import BrokerDeviceBridge
from database import init_db
from db_helper import dbhelper
from logger import get_logger, set_logger_level
from model.db_models import Device
from protocol import _build_mqtt_message

CLIENT_ID = 'broker_agent'
APPLIANCE_MESSAGE_TOPICS = '/appliance/+/publish'
APPLIANCE_SUBSCRIBE_TOPIC = '/appliance/+/subscribe'
NAT_TOPIC = '/_nat_/#'
DISCONNECTION_TOPIC = '$SYS/client-disconnections'
AGENT_TOPIC = '/_agent'

l = get_logger(__name__)

APPLIANCE_PUBLISH_TOPIC_RE = re.compile("/appliance/([a-zA-Z0-9]+)/publish")
APPLIANCE_SUBSCRIBE_TOPIC_RE = re.compile("/appliance/([a-zA-Z0-9]+)/subscribe")
DISCONNECTION_TOPIC_RE = re.compile("^\$SYS/client-disconnections$")
_NAT_RE = re.compile("/_nat_/([a-zA-Z0-9\-]+)")
_CLIENTID_RE = re.compile('^fmware:([a-zA-Z0-9]+)_[a-zA-Z0-9]+$')
_DEVICE_UPDATE_CACHE_INTERVAL_SECONDS = 60


def parse_args():
    parser = argparse.ArgumentParser(description='MQTT Broker Agent')
    parser.add_argument('--port', type=int, help='MQTT server port', default=2001)
    parser.add_argument('--host', type=str, help='MQTT server hostname', default='localhost')
    parser.add_argument('--username', type=str, required=True, help='MQTT username')
    parser.add_argument('--password', type=str, required=True, help='MQTT password')
    parser.add_argument('--debug', dest='debug', action='store_true', help='When set, prints debug messages')
    parser.add_argument('--cert-ca', required=True, type=str, help='Path to the root CA certificate path')
    parser.add_argument('--enable-bridging', action="store_true", help='When set, enabled Meross Broker bridging')
    parser.set_defaults(debug=False)
    parser.set_defaults(enable_bridging=False)
    return parser.parse_args()


def guess_subdevice_type(subdevices_data: Dict):
    if 'mts100v3' in subdevices_data:
        return 'mts100v3'
    elif 'ms100' in subdevices_data:
        return 'ms100'
    else:
        l.warning('Could not identify subdevice type from subdevice data: %s', str(subdevices_data))
        return 'unknown'


class Broker:
    def __init__(self,
                 hostname: str,
                 port: int,
                 username: str,
                 password: str,
                 cert_ca: str,
                 enable_bridging: bool):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.cert_ca = cert_ca
        self.bridging_enabled = enable_bridging
        self.c = mqtt.Client(client_id="broker", clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
        self.c.username_pw_set(username=self.username, password=self.password)

        context = ssl.create_default_context(cafile=self.cert_ca)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED
        self.c.tls_set_context(context)

        self.c.on_connect = self._on_connect
        self.c.on_disconnect = self._on_disconnect
        self.c.on_message = self._on_message
        self.c.on_subscribe = self._on_subscribe
        self._lock = RLock()
        self._devices_sys_info_timestamp = {}
        self._bridges = {}

        self._nat_table = ExpiringDict(max_age_seconds=30, max_len=50000)

    def setup(self):
        l.debug("Connecting as %s : %s", self.username, self.password)
        self.c.connect(host=self.hostname, port=self.port)

    def _on_connect(self, client, userdata, rc, other):
        l.debug("Connected to broker, rc=%s", str(rc))
        self.c.subscribe(
            [(NAT_TOPIC, 2), (APPLIANCE_MESSAGE_TOPICS, 2), (DISCONNECTION_TOPIC, 2), (APPLIANCE_SUBSCRIBE_TOPIC, 2),
             (AGENT_TOPIC, 2)])

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        l.debug("Subscribed to relevant topics")
        l.info("Re-loading connected device status.")
        self._issue_devices_discovery()

    def _on_message(self, client, userdata, msg):
        l.debug(f"Local MQTT: received message on topic {msg.topic}: {str(msg.payload)}")
        self._handle_message(topic=msg.topic, payload=msg.payload)

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

    def _issue_devices_discovery(self) -> None:
        devices = dbhelper.get_all_devices()
        for d in devices:
            self._issue_device_get_all(device_uuid=d.uuid)

    def _issue_device_get_all(self, device_uuid: str) -> None:
        device = dbhelper.get_device_by_uuid(device_uuid=device_uuid)
        msg, message_id = _build_mqtt_message(method="GET",
                                              namespace="Appliance.System.All",
                                              payload={},
                                              dev_key=device.owner_user.mqtt_key)
        self.c.publish(topic=f"/appliance/{device_uuid}/subscribe", payload=msg)

    def _handle_device_publication(self, device_uuid: str, topic: str, payload: dict):
        # If the message comes from a known device, update its online status
        dbhelper.update_device_status(device_uuid=device_uuid, status=OnlineStatus.ONLINE)

        user = dbhelper.find_user_owner_by_device_uuid(device_uuid)
        if user is None:
            l.warning("No user associated to device UUID %s, message will be skipped.", device_uuid)
            return

        # If this is the first time we see this device or if its cached info is old, update its channel status
        last_update_ts = self._devices_sys_info_timestamp.get(device_uuid)
        if last_update_ts is None or (datetime.now() - last_update_ts).seconds > _DEVICE_UPDATE_CACHE_INTERVAL_SECONDS:
            l.info("Update required for device %s Issuing SystemAll command to discover its channels "
                   "and supplementary data", device_uuid)
            self._issue_device_get_all(device_uuid)

        # For subdevices, we need to intercept BIND and UNBIND events as they are the only messages that carry the
        # subdevice_type information.
        # If the event is a Hub Bind/Unbind event, handle it accordingly
        if payload.get('header', {}).get('namespace', {}) == 'Appliance.Hub.Bind':
            for d in payload.get('payload').get('bind'):
                dbhelper.bind_subdevice(subdevice_type=d.get('deviceType'),
                                        subdevice_id=d.get('id'),
                                        hub_uuid=device_uuid)

        if payload.get('header', {}).get('namespace', {}) == 'Appliance.Hub.Unbind':
            for d in payload.get('payload').get('bind'):
                dbhelper.unbind_subdevice(subdevice_id=d.get('id'))

        # Some devices require the broker to acknowledge their binding message in order to complete the process.
        if payload.get('header', {}).get('namespace', {}) == 'Appliance.Control.Bind' \
            and payload.get('header', {}).get('method', {}) == 'SET':
            bind_ack, message_id = _build_mqtt_message(method='SETACK', namespace='Appliance.Control.Bind', header_from='/cloud/hook/subscribe', payload={}, dev_key=user.mqtt_key)
            self.c.publish(topic=f"/appliance/{device_uuid}/subscribe", payload=bind_ack)

        # Forward the device push notification to the app channel
        l.debug("Local MQTT -> Local MQTT: forwarding push notification received from device %s to user %s",
                device_uuid, user)
        self.c.publish(topic=f"/app/{user.user_id}/subscribe", payload=json.dumps(payload))

        # In case there is a bridged remote connection, forward the event to the remote broker as well
        if self.bridging_enabled:
            self._forward_message_to_remote(bridge_uuid=device_uuid, topic=topic,
                                            payload=json.dumps(payload).encode("utf8"))

    def _handle_message_to_agent(self, topic: str, payload: dict) -> None:
        # Try to guess the channels from the system_all payload
        namespace = payload.get('header', {}).get('namespace', None)
        method = payload.get('header', {}).get('method', None)
        from_appliance = payload.get('header', {}).get('from', None)

        if namespace == 'Appliance.System.All' and method == 'GETACK':
            # Retrieve appliance uuid
            match = APPLIANCE_PUBLISH_TOPIC_RE.fullmatch(from_appliance)
            appliance_uuid = match.group(1)

            # Retrieve system_all info
            system = payload.get('payload', {}).get('all', {}).get('system', None)
            if system is None:
                l.warning("Missing or invalid payload Appliance.System.All payload: could not find system attribute")
                return

            # Update device info
            hardware = system.get('hardware')
            firmware = system.get('firmware')
            time = system.get('time')
            online = system.get('online')
            device = dbhelper.get_device_by_uuid(device_uuid=appliance_uuid)
            device.device_type = hardware.get('type')
            device.sub_type = hardware.get('subType')
            device.hdware_version = hardware.get('version')
            device.fmware_version = firmware.get('version')
            device.domain = f"{firmware.get('server')}:{firmware.get('port')}"
            device.online_status = OnlineStatus(online.get('status'))
            device.local_ip = firmware.get('innerIp')
            dbhelper.update_device(device)

            digest = payload.get('payload', {}).get('all', {}).get('digest', None)
            if digest is None:
                l.warning("Missing or invalid payload Appliance.System.All payload: could not find digest attribute")
            else:
                hub_data = digest.get("hub")
                if hub_data is not None:
                    subdevices_data = hub_data.get('subdevice', [])
                    self._update_hub_subdevices(hub_device=device, subdevices_data=subdevices_data)

                # Guess channels and Store Appliance info on DB
                togglex_switches = digest.get('togglex')
                # TODO: implement other channel guessing
                # light_switches = digest.get('light')
                # spray_switches = digest.get('spray')

                # Guess by togglex
                if togglex_switches is not None and len(togglex_switches) > 0:
                    l.debug("Guessing channels via togglex")
                    for d in togglex_switches:
                        channel_id = d.get('channel')
                        dbhelper.update_device_channel(device_uuid=appliance_uuid, channel_id=channel_id)
                # Guess by "light"
                # elif light_switches is not None:
                #     pass
                #
                # # Guess by "spray"
                # elif spray_switches is not None:
                #     pass
                else:
                    l.warning("Could not guess the channels for device uuid %s", appliance_uuid)

            # Update the last update timestamp
            ts = datetime.now()
            l.info("Setting last update timestamp to %s for device %s", ts, appliance_uuid)
            self._devices_sys_info_timestamp[device.uuid] = ts

            if self.bridging_enabled:
                self._get_or_create_bridge(device_uuid=device.uuid)

    def _handle_device_disconnected(self, payload: dict) -> None:
        if payload.get("event") != "disconnect":
            l.warning("Invalid or unhandled event received: %s", payload.get("event"))
            return
        data = payload.get("data")
        client_id = data.get("client_id")
        username = data.get("username")
        address = data.get("address")
        reason = data.get("reason")
        l.debug("Broker reported client %s (username: %s, ip: %s) disconnected for reason %s", client_id, username,
                address, str(reason))

        # Only proceed if the client-id belongs to a hw device
        device_match = _CLIENTID_RE.fullmatch(client_id)
        if device_match:
            uuid = device_match.group(1)
            dbhelper.update_device_status(device_uuid=uuid, status=OnlineStatus.OFFLINE)
            l.info("Device %s has disconnected from broker", uuid)

            # Clear last timestamp update
            if uuid in self._devices_sys_info_timestamp:
                del self._devices_sys_info_timestamp[uuid]

            # Stop the corresponding bridge
            bridge = self._bridges.get(uuid)
            if bridge is not None:
                l.debug("Stopping and Removing device MQTT-Bridge: %s", uuid)
                bridge.stop()
                del self._bridges[uuid]
            else:
                l.debug("No MQTT Bridge found for device %s, nothing to stop.", uuid)

    def _handle_message(self, topic: str, payload: bytes):
        try:
            # TODO: Implement message signature checks.
            #  For now, we trust the message regardless of its signature.

            # Handling DISCONNECTION control messages
            disconnection_match = DISCONNECTION_TOPIC_RE.match(topic)
            if disconnection_match is not None:
                p = json.loads(payload)
                self._handle_device_disconnected(payload=p)
                return

            # Handling NATTED messages if bridging is enabled
            if self.bridging_enabled:
                match = _NAT_RE.fullmatch(topic)
                if match is not None:
                    nat_table_index = match.group(1)
                    nat_entry = self._nat_table.get(nat_table_index)
                    if nat_entry is None:
                        l.error("Invalid _NAT_ address received. Message will be discarded.")
                        return
                    original_topic = nat_entry.get("original_from_attribute")
                    originating_bridge_uuid = nat_entry.get("originating_bridge_uuid")
                    #p = json.loads(payload)
                    #p['header']['from'] = original_topic
                    #original_payload = json.dumps(p).encode('utf8')
                    self._forward_message_to_remote(topic=original_topic, payload=payload,
                                                    bridge_uuid=originating_bridge_uuid)
                    return

            # Handling messages pushed to APPLIANCE publication topics
            match = APPLIANCE_PUBLISH_TOPIC_RE.fullmatch(topic)
            if match is not None:
                device_uuid = match.group(1)
                p = json.loads(payload)
                self._handle_device_publication(device_uuid=device_uuid, topic=topic, payload=p)
                return

            # Handling messages pushed to /_agent dedicated topic
            if topic == AGENT_TOPIC:
                p = json.loads(payload)
                self._handle_message_to_agent(topic=topic, payload=p)
                return

        except Exception as ex:
            l.exception("An error occurred while handling message %s received on topic %s", str(payload), str(topic))

    def _get_or_create_bridge(self, device_uuid: str) -> BrokerDeviceBridge:
        bridge: BrokerDeviceBridge = self._bridges.get(device_uuid)
        if bridge is None:
            l.info("Creating MQTT bridge for device %s", device_uuid)
            # Retrieve device info
            device = dbhelper.get_device_by_uuid(device_uuid=device_uuid)
            bridge = BrokerDeviceBridge(broker=self,
                                        device_uuid=device_uuid,
                                        device_client_id=device.client_id,
                                        meross_device_mac=device.mac,
                                        meross_user_id=str(device.user_id),
                                        meross_key=device.owner_user.mqtt_key)
            bridge.start()
            self._bridges[device_uuid] = bridge
        return bridge

    def forward_device_command_locally(self, topic: str, payload: bytes, originating_bridge_uuid: str):
        # When a device receives a command from Meross Cloud, we need to forward it to the local broker.
        # In order to send back the ACK to that command, we apply masquerading NAT, so that we can later
        # intercept the responses to such messages and forward them to the remote broker
        with self._lock:
            message_data = json.loads(payload)
            from_attribute = message_data.get('header', {}).get('from', None)

            # Generate nat entry and store the original "address" into the nat table
            rand_uuid = str(uuid.uuid4())
            nat_entry = f"/_nat_/{rand_uuid}"
            self._nat_table[rand_uuid] = {
                "original_from_attribute": from_attribute,
                "originating_bridge_uuid": originating_bridge_uuid
            }

            # Replace the original address with the natted one and submit the message locally
            message_data['header']['from'] = nat_entry
            newdata = json.dumps(message_data).encode('utf8')
            l.debug("Device Bridge (%s) -> Local MQTT, topic: %s, message: %s", originating_bridge_uuid, str(topic),
                    str(newdata))
            self.c.publish(topic=topic, payload=newdata)

    def _forward_message_to_remote(self, topic: str, payload: bytearray, bridge_uuid: str):
        bridge = self._get_or_create_bridge(device_uuid=bridge_uuid)
        if bridge is not None:
            bridge.send_message(topic=topic, payload=payload)
        else:
            l.debug("Bridge creation failed for device %s", bridge_uuid)

    def _update_hub_subdevices(self, hub_device: Device, subdevices_data: List[Dict]) -> None:
        l.debug("Updating subdevices for hub %s (%s)", hub_device.uuid, hub_device.dev_name)
        # Add newly discovered subdevices
        for d in subdevices_data:
            subdevice_id = d.get('id')
            subdevice_type = guess_subdevice_type(d)
            subdevice = dbhelper.get_subdevice_by_id(subdevice_id)
            if subdevice is None:
                l.info("Found new subdevice %s belonging to hub %s (%s)", subdevice_id, hub_device.uuid,
                       hub_device.dev_name)
                subdevice = dbhelper.bind_subdevice(subdevice_type=subdevice_type, subdevice_id=subdevice_id,
                                                    hub_uuid=hub_device.uuid)
            if (subdevice.sub_device_type is None or subdevice.sub_device_type == 'unknown') and subdevice_type is not None:
                l.warning("Subdevice %s was of unknown, but from update data looks like an %s."
                          "From now on, this subdevice is treated as an %s.", subdevice_id,
                          subdevice_type, subdevice_type)
                subdevice.sub_device_type = subdevice_type
                dbhelper.update_subdevice(subdevice)

        # Remove old subdevices that were not listed any longer
        current_devices_ids = {x.get('id') for x in subdevices_data}
        for d in hub_device.child_subdevices:
            if d.sub_device_id not in current_devices_ids:
                l.warning("Removing subdevice %s from hub %s (%s)", d.sub_device_id, hub_device.uuid,
                          hub_device.dev_name)
                dbhelper.unbind_subdevice(subdevice_id=d.sub_device_id)


def main():
    # Parse Args
    args = parse_args()
    if args.debug:
        set_logger_level(logging.DEBUG)

    # Init or setup DB
    init_db()

    # Set all devices to unknown online status
    dbhelper.reset_device_online_status()

    b = Broker(hostname=args.host,
               port=args.port,
               username=args.username,
               password=args.password,
               cert_ca=args.cert_ca,
               enable_bridging=args.enable_bridging)

    reconnect_interval = 10  # [seconds]
    while True:
        try:
            b.setup()

            while True:
                # Every 60 seconds, issue a full device discovery
                b.c.loop(timeout=60, max_packets=-1)
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
