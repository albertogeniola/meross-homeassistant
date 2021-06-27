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

Before installing this addon, it is important to understand **what this addon does** and **what it does not**.

To get there, know that Meross devices rely on a 3 tiers distributed architecture:

- Physical hardware devices (smart plugs/bulbs/power-strip/valves/...)
- Remote HTTP Api server
- Remote MQTT Api server

Each physical device connects to the MQTT server and sends/receives updates/commands to/from certain topics.
Users, via the Meross App, talks to the Meross HTTP server to register, login and enroll their Meross devices.
The Meross app, in turn, is also capable to talk to the physical devices via the MQTT server.

This addon re-implements both the MQTT and the HTTP API parts of the Meross ecosystem, allowing your Meross physical devices
to talk locally on the LAN to such components. This enables you to get rid of Meross limits as this local addon does not enforce any.

## Compatibility & tested environments

This addon has been tested on Homeassistant Docker environment, specifically on AMD64 VMWare virtual machine and on a
Raspberry PI 3 B+ (ARM arch). While it is possible to run it on embedded Homeassistand devices (raspberry PI, ODROID),
it is highly recommended to run it on X86/AMD64 CPU with at least 2 cores and 4Gb or RAM memory. Even though the
absorbed resources at runtime are much lower, the build phase of the Docker container requires high memory and CPU
power, as most of the software is compiled from scratch.

To give you an idea of what that means, consider that the installation phase on a **Raspberry Pi 3 B+ takes about
60 minutes** to complete, while only **3~5 minutes on a 4-cpu 4 Gb ram virtual machine**.

Run this addon on Intel NUC / X86 / AMD64 platform powered Homeassistant installations.

## Donate!

TBD
