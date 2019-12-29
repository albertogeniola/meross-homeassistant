# Constants
DOMAIN = 'meross_cloud'
ATTR_CONFIG = "config"
MANAGER = 'manager'
MEROSS_MANAGER = "%s.%s" % (DOMAIN, MANAGER)
SENSORS = 'sensors'
HA_SWITCH = 'switch'
HA_LIGHT = 'light'
HA_SENSOR = 'sensor'
HA_COVER = 'cover'
HA_CLIMATE = 'climate'
MEROSS_PLATFORMS = (HA_LIGHT, HA_SWITCH, HA_COVER, HA_SENSOR, HA_CLIMATE)


def calculate_switch_id(uuid: str, channel: int):
    return "%s:%s:%d" % (HA_SWITCH, uuid, channel)


def calculate_sensor_id(uuid: str):
    return "%s:%s" % (HA_SENSOR, uuid)


def calculate_gerage_door_opener_id(uuid: str, channel: int):
    return "%s:%s:%d" % (HA_COVER, uuid, channel)


def dismiss_notification(hass, notification_id):
    hass.async_create_task(
        hass.services.async_call(domain='persistent_notification', service='dismiss', service_data={
            'notification_id': "%s.%s" % (DOMAIN, notification_id)})
    )


def notify_error(hass, notification_id, title, message):
    hass.async_create_task(
        hass.services.async_call(domain='persistent_notification', service='create', service_data={
                                           'title': title,
                                           'message': message,
                                           'notification_id': "%s.%s" % (DOMAIN, notification_id)})
    )
