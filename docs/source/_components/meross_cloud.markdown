---
layout: page
title: "Meross devices platform"
description: "Instructions on how to integrate Meross devices into Home Assistant."
date: 2019-06-16 09:00
sidebar: true
comments: false
sharing: true
footer: true
logo: meross.png
ha_category:
  - Switch
  - Light
  - Cover
ha_iot_class: Cloud Push
ha_release: "0.94.3"
---

The `meross` platform allows you to control the state of your [Meross devices](https://www.meross.com/).

The list of tested and fully supported devices is the following:
- MSL120
- MSS110
- MSS210
- MSS310
- MSS310h
- MSS425e
- MSS530h
- MSG100

Please note that the integration might be working also with unlisted Meross devices.
If you own any Meross plug, give it a try even if it's not listed.


In order to enable this integration, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
meross_cloud:
  username: meross_username
  password: meross_password
```

{% configuration %}
username:
  description: The username of your Meross account. It's the email you use to login into the Meross app
  required: true
  type: string
password:
  description: The password of your Meross account. It's the one you use to login into the Meross app.
  required: true
  type: string
{% endconfiguration %}
