#!/usr/bin/with-contenv bashio

MQTT_MOSQUITTO_CONF_PATH=/etc/mosquitto/mosquitto.conf

bashio::log.info "Waiting for local dev server..."
bashio::net.wait_for 2002

bashio::log.info "Waiting for auth file..."
while [ ! -f /etc/mosquitto/auth.pw ]; do sleep 1; done
bashio::log.info "Waiting for acl file..."
while [ ! -f /etc/mosquitto/auth.acl ]; do sleep 1; done

bashio::log.info "Starting mosquitto..."
exec mosquitto -c $MQTT_MOSQUITTO_CONF_PATH
