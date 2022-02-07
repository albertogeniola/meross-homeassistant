#!/usr/bin/with-contenv bashio
# ==============================================================================
# Configures Meross service
# ==============================================================================

CONFIG_PATH=/data/options.json
DB_PATH=/data/database.db

# If the user has asked to reinit the db, remove it
REINIT_DB=$(bashio::config 'resetdb')
if [[ $REINIT_DB == true ]]; then
  if [[ -f $DB_PATH ]]; then
    bashio::log.warning "User configuration requires DB reinitialization. Removing previous DB data."
    rm $DB_PATH
  fi
fi

# Configure env-vars
ingress_entry=$(bashio::addon.ingress_entry)
sed -i "s#%%APIURL%%#${ingress_entry}#g" /var/www/assets/env.js

# Create logging directory for API Server
mkdir -p /var/log/broker

# Initializing DB
pushd /opt/custom_broker >/dev/null

ADMIN_EMAIL=$(jq --raw-output ".email" $CONFIG_PATH)
ADMIN_PASSWORD=$(jq --raw-output ".password" $CONFIG_PATH)

bashio::log.info "Setting up the database in $DB_PATH"
LOGIN_MEROSS=$(bashio::config 'federate_with_meross')
if [[ $LOGIN_MEROSS == true ]]; then
  python3 setup.py --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD" --federate-remote-broker
else
  python3 setup.py --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD"
fi

if [[ $? -ne 0 ]]; then
  bashio::log.error "Error when setting up the database file. Aborting."
  exit 1
else
  bashio::log.info "DB setup finished"
fi
popd >/dev/null