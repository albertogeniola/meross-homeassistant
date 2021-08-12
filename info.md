# Meross Custom Component
Based on pure-python library, this custom component enables full control on your meross devices. 

## Features
* Supports the majority of Meross devices on the market: from power plugs to light bulbs to temp/humidity sensors
* Fully async architecture that makes this integration run fast and lightweight 
* Event driven: updates are based on push notification rather than polling when possible 
* Auto discovery of new meross devices
* Auto-reconnect in case of connection drop
* Configurable API rate limits

## Requirements
Please note that the Meross devices are controlled via Meross Cloud. This means that homeassistant 
*must have* internet access to accomplish such task. You also need an account for the Meross cloud: 
you should reuse the one from your meross app.

## Configuration
Once installed, you should set up the Meross Cloud component to connect to the Meross Cloud service.
Just navigate to _settings -> Integrations, click "add" and then select "Meross Cloud IoT". 
A pop-up will appear, asking for the Meross API endpoint to use and your Meross credentials.

The official meross cloud server is __https://iot.meross.com__ (it is pre-filled by default).
The following animation shows how to do that.

<a href="https://raw.githubusercontent.com/albertogeniola/meross-homeassistant/master/docs/source/images/components/meross_cloud/install-via-webui.gif">
<img src="https://raw.githubusercontent.com/albertogeniola/meross-homeassistant/master/docs/source/images/components/meross_cloud/install-via-webui.gif" alt="Installation via web-ui" width=400>
</a>

### API rate limit
Meross does implement strict API rate limits. 
When connecting an more than 5 Meross sensors/devices to HomeAssistant via this integration, 
the Meross security team might request you to release/decrease the API calling frequency.
Therefore, you should avoid using high-frequency polling scripts/automations with Meross devices. 
As last resort, you can configure/tune the API rate limits via the CONFIGURATION section of this integration.
Be advised that the API rate limiter might "delay" commands or abort them.

## Updating from old 0.3.X.X versions
Before updting to version 1.X from older legacy versions, you need to take some steps to ensure everything will work.
1. Remove the Meross component integration
1. Remove all the Meross Devices / Entities (Settings -> Etntities -> _select all meross ones_ -> Delete )
1. Remove all Lovelace cards for old Meross devices 
1. Reboot HA
1. Install latest 1.X Meross integration using HACS or you preferred installation method
1. Set it up as explained in _Configuration_ paragraph
1. Enjoy!

## Be nice!
If you like the component, why don't you support me by buying me a beer or a coffe?
It would certainly motivate me to further improve this work. [Sponsor me on GitHub](https://github.com/sponsors/albertogeniola)!

Or, if you prefer, buy me some coffe for further improve this component even more. 
[![Buy me a coffe!](https://www.buymeacoffee.com/assets/img/custom_images/black_img.png)](https://www.buymeacoffee.com/albertogeniola)
