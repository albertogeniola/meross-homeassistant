import argparse
import asyncio
import logging
import sys
import ssl
from contextlib import AsyncExitStack, asynccontextmanager

from asyncio_mqtt import Client, MqttError


CLIENT_ID = 'broker_agent'
APPLIANCE_MESSAGES = '/appliance/+/publish'

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


async def mqtt_message_handler(hostname, port, username, password, cert_ca_path):
    async with AsyncExitStack() as stack:
        # Keep track of the asyncio tasks that we create, so that
        # we can cancel them on exit
        tasks = set()
        stack.push_async_callback(cancel_tasks, tasks)

        # Connect to the MQTT broker
        context = ssl.create_default_context(cafile=cert_ca_path)
        context.check_hostname = False
        #context.set_ciphers(None)
        context.verify_mode = ssl.CERT_REQUIRED
        client = Client(hostname=hostname,
                          port=port,
                          username=username,
                          password=password,
                          clean_session=True,
                          tls_context=context)
        await stack.enter_async_context(client)

        topic_filters = (
            APPLIANCE_MESSAGES,
            #"#" # More topics
        )

        for topic_filter in topic_filters:
            # Log all messages that matches the filter
            manager = client.filtered_messages(topic_filter)
            messages = await stack.enter_async_context(manager)
            task = asyncio.create_task(handle_relevant_messages(messages))
            tasks.add(task)

        # Messages that doesn't match a filter will get logged here
        messages = await stack.enter_async_context(client.unfiltered_messages())
        task = asyncio.create_task(handle_unknown_messages(messages))
        tasks.add(task)

        # Subscribe to topic(s)
        await client.subscribe(APPLIANCE_MESSAGES)
        await asyncio.gather(*tasks)


async def handle_relevant_messages(messages):
    async for message in messages:
        print("Known: {s}" % message.payload.decode())


async def handle_unknown_messages(messages):
    async for message in messages:
        print("Unknown: {s}" % message.payload.decode())


async def cancel_tasks(tasks):
    for task in tasks:
        if task.done():
            continue
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def main():
    args = parse_args()
    if args.debug:
        handler.setLevel(logging.DEBUG)
        l.setLevel(logging.DEBUG)

    reconnect_interval = 10  # [seconds]
    while True:
        try:
            l.warning("Connecting to broker")
            await mqtt_message_handler(hostname=args.host,
                               port=args.port,
                               username=args.username,
                               password=args.password,
                               cert_ca_path=args.cert_ca)
        except MqttError as error:
            l.exception(f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
        finally:
            await asyncio.sleep(reconnect_interval)


if __name__ == '__main__':
    asyncio.run(main())
