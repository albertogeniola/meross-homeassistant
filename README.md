[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

# Meross HomeAssistant component
A full featured Homeassistant component to drive Meross devices. 
This component is based on the underlying MerossIot library available [here](https://github.com/albertogeniola/MerossIot).

## Towards Homeassistant official integration
My personal goal is to make this component fully compliant with Homeassistant, so 
that it may be added as the official library to handle Meross devices. 
However, before pushing a PullRequest to the official Homeassistant repository, I would like to share it to some users.
In this way we can test it massively, check it for any bug and make it **robust enough** to be seamlessly integrated 
with Homeassistant.

For now, the component has been integrated as a custom component into [HACS](https://custom-components.github.io/hacs/).

## Installation & configuration
If you have HACS, well, it's a peace of cake! Just search for "Meross" (Full name is Meross Cloud IoT) in the default repository of HACS and It'll show up!

Install it as you would do with any homeassistant custom component:
1. Download the latest zip release archive from [here](https://github.com/albertogeniola/meross-homeassistant/releases/download/0.1a/meross_cloud.zip) (or clone the git master branch)
1. Unzip/copy the meross_cloud direcotry within the `custom_components` directory of your homeassistant installation.
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
1. Setup your meross cloud credentials. Edit/create the `secrets.yaml` file,
 which is located within the config directory as well. Add the following:
 
     ```
    meross_username: my_meross_email@domain.com
    meross_password: my_meross_password
    ```
    
    Where  my_meross_email@domain.com is your Meross account email and my_meross_password is the associated password. 
 
1. Enable the component by editing the configuration.yaml file (within the config directory as well).
Edit it by adding the following lines:
    ```
    meross_cloud:
      username: !secret meross_username
      password: !secret meross_password
    ```
    **Note!** In this case you do not need to replace meross_username and meross_password. 
Those are place holders that homeassistant automatically replaces by looking at the secrets.yaml file. 

1. Reboot hassio
1. Congrats! You're all set!

## Features
### Massive support
This library supports all the Meross devices currently exposed by the Meross IoT library.
In particular Bulbs, Switches and Garage Door Openers are fully supported and perfectly integrated with HomeAssistant.

Have a look a the screenshots below...

<img src="docs/source/images/components/meross_cloud/general-ui.png" alt="User interface" width=400> 
<img src="docs/source/images/components/meross_cloud/bulb-control.png" alt="Controlling the light bulb" width=400> 
<img src="docs/source/images/components/meross_cloud/garage-control.png" alt="Controlling the garage opener" width=400> 
<img src="docs/source/images/components/meross_cloud/sensor.png" alt="Power sensor feedbacks" width=400> 
<img src="docs/source/images/components/meross_cloud/switch-control.png" alt="Controlling switches" width=400> 

 
### Efficiency and adoption of Homeassistant best practices
Since I'm aiming at making this component part of the official HA repo, I've put a lot of effort following 
HomeAssistant best practices, in particular:
- Asynchronous functions when possible;
- No polling: the library is event-based. It saves bandwidth and makes the UI much more reactive.
- Robust to disconnection: the library handles network disruption;
- Lovelace notification: supports UI persistent event notification;
- PEP8 code styling

## What's next?
- Automated test
- CI/CD & GitHub release
- Feedback collection
- Refactor and improvements based on feedbacks

## Support on Beerpay
By buying me a coffee, not only you make my development more efficient, but also motivate me to further improve 
my work. On the other hand, buying me a beer will certainly make me happier: **a toast to you, supporter**!

[![Buy me a coffe!](https://www.buymeacoffee.com/assets/img/custom_images/black_img.png)](https://www.buymeacoffee.com/albertogeniola)

[![Beerpay](https://beerpay.io/albertogeniola/meross-homeassistant/badge.svg?style=beer-square)](https://beerpay.io/albertogeniola/meross-homeassistant)  [![Beerpay](https://beerpay.io/albertogeniola/meross-homeassistant/make-wish.svg?style=flat-square)](https://beerpay.io/albertogeniola/meross-homeassistant?focus=wish)
