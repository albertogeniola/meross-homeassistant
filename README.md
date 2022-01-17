[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
![Build](https://img.shields.io/azure-devops/build/albertogeniola/c4128d1b-c23c-418d-95c5-2de061954ee5/3/master?style=for-the-badge)

# Meross HomeAssistant component
A full-featured Homeassistant component to drive Meross devices. 
This component is based on the underlying MerossIot library available [here](https://github.com/albertogeniola/MerossIot).

## :new: :rocket: Local-Only Addon under development :rocket:
I had promised to the community that I would have focused my development efforts in the local-addon, and... so I am doing :)
As already mentioned many times, the reason why it takes so much time is because everything done here is the result of hours 
and hours of procotol inspection sessions, reverse engineering and [hacking](https://en.wikipedia.org/wiki/Hacker_culture). 

Just to rise the hype, here there are some screens of the on-going development addon, which is 75% completed:
<img src="https://user-images.githubusercontent.com/4648843/117581720-9d2bb080-b0fe-11eb-802e-1f360d7c3c04.png" alt="Log Screenshot" width=250/>
<img src="https://user-images.githubusercontent.com/4648843/117581724-9e5cdd80-b0fe-11eb-9822-a1cc4363a929.png" alt="Info Screenshot" width=250/>
<img src="https://user-images.githubusercontent.com/4648843/117581904-aa956a80-b0ff-11eb-926c-132614eb9bda.png" alt="WebUi Screenshot" width=250/>


### What is the local-addon?
Meross Plugin has gained great success and popularity among the HomeAssistant users. However, the Meross engineers are imposing
new limits on their MQTT broker system, which cause problems to the HA users who want to implement aggressive polling or have
more than 10 devices connected to HA. For this reason, I am working on a new HomeAssistant addon, namely "Meross Local Addon", 
which aims at re-implementing the Meross MQTT Broker and HTTP API layer locally to the addon. This would basically allow users
to rely only on LAN-local connection, using HomeAssistant as command center. 

As you can imagine, there is a huge work behind that: first I need to reverse-engineer the Meross protocols, then I need to 
implement any "logic-layer" implemented on Meross Systems on the new addon I am developing and, eventually, I have to make
sure that everything works together. That means that I am not able to spend much time in solving issues that may arise in 
the meantime, and for that I apologize. If you like this project and you want to support me, please consider donating:
that motivates me and helps me buy _more ram_ which is absolutely necessary when developing on a virtualized environment.

## Installation & configuration
You can install this component in two ways: via HACS or manually.
HACS is a nice community-maintained components manager, which allows you to install git-hub hosted components in a few clicks.
If you have already HACS installed on your HomeAssistant, it's better to go with that.
On the other hand, if you don't have HACS installed or if you don't plan to install it, then you can use manual installation.

### Option A: Installing via HACS
If you have HACS, well, it's piece of cake! 
Just search for "Meross" (Full name is Meross Cloud IoT) in the default repository of HACS and it'll show up.
Click on Install. When the installation completes, **you must restart homeassistant** in order to make it work.
As soon as HomeAssistant is restarted, you can proceed with __component setup__.

### Option B: Classic installation (custom_component)
1. Download the latest zip release archive from [here](https://github.com/albertogeniola/meross-homeassistant/releases/latest)
1. Unzip/copy the meross_cloud directory within the `custom_components` directory of your homeassistant installation.
The `custom_components` directory resides within your homeassistant configuration directory.
Usually, the configuration directory is within your home (`~/.homeassistant/`).
In other words, the configuration directory of homeassistant is where the config.yaml file is located.
After a correct installation, your configuration directory should look like the following.
    ```
    └── ...
    └── configuration.yaml
    └── secrects.yaml
    └── custom_components
        └── meross_cloud
            └── __init__.py
            └── common.py
            └── cover.py
            └── ...
    ```

    **Note**: if the custom_components directory does not exist, you need to create it.

After copy-pasting the meross_cloud directory into the custom_components folder, you need to restart HomeAssistant.
As soon as HomeAssistant is restarted, you can proceed with __component setup__.

### Component setup    
Once the component has been installed, you need to configure it in order to make it work.
To do so, navigate to "Configuration -> Integrations -> Add Integration" and look for "Meross Cloud IoT".
As soon as you add it, you'll be asked to configure it. 
The following table summarizes the fields that the wizard will require you to fill in:

|  Field Name                      | Example Value           | Description                                             | 
|----------------------------------|-------------------------|---------------------------------------------------------|
| HTTP Api Endpoint                | https://iot.meross.com  | Is the HTTP(s) API endpoint used by the Meross Manager. This might vary in accordance with your country | 
| Email Address                    | johndoe@gmail.com       | Your Meross account username/email. If connecting to the official Meross cloud, use the same from the Meross App |
| Password                         | R4nd0mS3cret            | Your Meross account password. If connecting to the official Meross cloud, use the same from the Meross App |
| Skip MQTT certificate validation | True (Checked)          | Configures MQTT certificate validation. When unchecked it requires a valid certificate to be exposed from the Meross Server. If checked, it skips the MQTT certificate validation. If connecting to the official Meross cloud, you can uncheck this. When connecting to local-lan or custom MQTT brokers, you might want to check this. |

The following animation shows an example of component configuration
[![Installation via web UI](https://raw.githubusercontent.com/albertogeniola/meross-homeassistant/master/docs/source/images/components/meross_cloud/install-via-webui.gif)](https://raw.githubusercontent.com/albertogeniola/meross-homeassistant/master/docs/source/images/components/meross_cloud/install-via-webui.gif)

## Features
### Massive support
This library supports all the Meross devices currently exposed by the Meross IoT library.
In particular Bulbs, Switches, Garage Door Openers and Smart Valves/Thermostat are fully supported and perfectly integrated with HomeAssistant.

<details>
    <summary>Have a look a the screenshots below...</summary>

<img src="docs/source/images/components/meross_cloud/general-ui.png" alt="User interface" width=400> 
<img src="docs/source/images/components/meross_cloud/bulb-control.png" alt="Controlling the light bulb" width=400> 
<img src="docs/source/images/components/meross_cloud/garage-control.png" alt="Controlling the garage opener" width=400> 
<img src="docs/source/images/components/meross_cloud/sensor.png" alt="Power sensor feedbacks" width=400> 
<img src="docs/source/images/components/meross_cloud/switch-control.png" alt="Controlling switches" width=400> 
</details>
 
### Efficiency and adoption of Homeassistant best practices
Since I'm aiming at making this component part of the official HA repo, I've put a lot of effort into following 
HomeAssistant best practices, in particular:
- Asynchronous functions when possible;
- No polling: the library is event-based. It saves bandwidth and makes the UI much more reactive.
- Robust to disconnection: the library handles network disruption;
- Lovelace notification: supports UI persistent event notification;
- PEP8 code styling


## Supporting my work
By buying me a coffee, not only you make my development more efficient, but also motivate me to further improve 
my work. On the other hand, buying me a beer will certainly make me happier: **a toast to you, supporter**!
In case you are a pro and a strong opensource supporter, you might also consider [sponsoring my GitHub work](https://github.com/sponsors/albertogeniola).

[![Buy me a coffe!](https://www.buymeacoffee.com/assets/img/custom_images/black_img.png)](https://www.buymeacoffee.com/albertogeniola)

