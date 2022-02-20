#!/usr/bin/with-contenv bashio
# ==============================================================================
# Configures the Avahi daemon
# ==============================================================================
# shellcheck disable=SC1091

# Prepare log dir
mkdir -p /var/log/broker
chown nobody:nogroup /var/log/broker
chmod 02755 /var/log/broker