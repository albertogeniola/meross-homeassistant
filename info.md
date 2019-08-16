# Meross Custom Component
Based on pure-python library, this custom component enables full control on your meross devices. 

## Features
* Supports Meross power plugs, included power metering/electricity measure
* Supports light bulb switching and color setting
* Supports Garage Door openers
* Supports multi-channel power strips 
* Event driven: no bandwidth is wasted

## Requirements
Please note that the Meross devices are controlled via Meross Cloud. This means that homeassistant 
should have internet access to accomplish such task.

In order to enable this integration, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
meross_cloud:
  username: meross_username
  password: meross_password
```

## Be nice!
If you like the component, why don't you support me by buying me a beer or a coffe?
It would certainly motivate me to further improve this work.

[![Buy me a coffe!](https://www.buymeacoffee.com/assets/img/custom_images/black_img.png)](https://www.buymeacoffee.com/albertogeniola)

[![Beerpay](https://beerpay.io/albertogeniola/meross-homeassistant/badge.svg?style=beer-square)](https://beerpay.io/albertogeniola/meross-homeassistant)  [![Beerpay](https://beerpay.io/albertogeniola/meross-homeassistant/make-wish.svg?style=flat-square)](https://beerpay.io/albertogeniola/meross-homeassistant?focus=wish)