#!/usr/bin/with-contenv bashio
# ==============================================================================
# Configures the Avahi daemon
# ==============================================================================
# shellcheck disable=SC1091

readonly AVAHI_CONFIG='/etc/avahi/avahi-daemon.conf'
declare interfaces
declare hostname

# Remove some problematic Avahi service files
rm -f /etc/avahi/services/*

# Prepare log dir
mkdir -p /var/log/avahi
chown nobody:nogroup /var/log/avahi
chmod 02755 /var/log/avahi