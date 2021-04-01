#!/usr/bin/with-contenv bashio
# ==============================================================================
# Configure NGINX for use with Meross Local Broker
# ==============================================================================
ingress_entry=$(bashio::addon.ingress_entry)
ingress_interface=$(bashio::addon.ip_address)

sed -i "s#%%ingress_entry%%#${ingress_entry}#g" /etc/nginx/ingress.conf
sed -i "s/%%interface%%/${ingress_interface}/g" /etc/nginx/ingress.conf