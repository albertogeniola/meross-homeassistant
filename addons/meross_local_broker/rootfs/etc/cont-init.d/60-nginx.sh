#!/usr/bin/with-contenv bashio
# ==============================================================================
# Configure NGINX for use with Meross Local Broker
# ==============================================================================
ingress_entry=$(bashio::addon.ingress_entry)
ingress_interface=$(bashio::addon.ip_address)

# Safe defaults
if [[ $ingress_interface = "" ]]; then
    ingress_interface="0.0.0.0"
fi

if [[ $ingress_entry = "" ]]; then
    ingress_entry="/"
fi

sed -i "s#%%ingress_entry%%#${ingress_entry}#g" /etc/nginx/ingress.conf
sed -i "s/%%interface%%/${ingress_interface}/g" /etc/nginx/ingress.conf

# Prepare log dir
mkdir -p /var/log/nginx
chown nobody:nogroup /var/log/nginx
chmod 02755 /var/log/nginx