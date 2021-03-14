#!/usr/bin/with-contenv bashio

MQTT_MOSQUITTO_CONF_PATH=/etc/mosquitto/mosquitto.conf

bashio::log.info "Waiting for local dev server..."
bashio::net.wait_for 2002

bashio::log.info "Starting mosquitto..."
mosquitto -c $MQTT_MOSQUITTO_CONF_PATH
bashio::log.warning "Mosquitto terminated."