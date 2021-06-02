# Merosss Local Broker Addon

This addon aims at implementing a full Meross Broker (both MQTT and HTTP components) within HomeAssistant.

The main advantage of running a local broker is that you can workaround the HTTP/MQTT limits imposed by the
Meross Cloud. This becomes particularly necessary when running an high number of Meross devices:
as Homeassistant aggressively polls device status, Meross Cloud team might ban HA users.

## Disclaimer

Meross does not officially support this integration, neither provides OpenSource/API specs.
This component, and all the others around the Meross python ecosystem, has been developed by applying
protocol inspection and guessing. Thus, expect this addon/component to be unstable: at any time Meross might
change their internals and break the logic within this addon.

## Features

TBD

## Donate

TBD
