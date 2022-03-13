#!/usr/bin/with-contenv bashio
# ==============================================================================
# Configures Meross service
# ==============================================================================

DB_PATH=/data/database.db

# If the user has asked to reinit the db, remove it
REINIT_DB=${reinit_db:-false}
if [[ $REINIT_DB == "true" ]]; then
  if [[ -f $DB_PATH ]]; then
    bashio::log.warning "User configuration requires DB reinitialization. Removing previous DB data."
    rm $DB_PATH
  fi
fi

# Configure env-vars
ingress_entry=$(bashio::addon.ingress_entry)
sed -i "s#%%APIURL%%#${ingress_entry}#g" /var/www/assets/env.js

# Initializing DB
pushd /opt/custom_broker >/dev/null

bashio::log.info "Setting up the database in $DB_PATH"
python3 setup.py

if [[ $? -ne 0 ]]; then
  bashio::log.error "Error when setting up the database file. Aborting."
  exit 1
else
  bashio::log.info "DB setup finished"
fi
popd >/dev/null

# Prepare log dir
mkdir -p /var/log/api
chown nobody:nogroup /var/log/api
chmod 02755 /var/log/api