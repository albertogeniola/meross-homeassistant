#!/usr/bin/with-contenv bashio

CONFIG_PATH=/data/options.json
DB_PATH=/data/database.db
DB_SCHEMA_PATH=/opt/meross_api/schema.sql

# If the user has asked to reinit the db, remove it
REINIT_DB=$(jq "if .resetdb then .resetdb else 0 end" $CONFIG_PATH)
if [[ $REINIT_DB -eq 1 ]]; then
  if [[ -f $DB_PATH ]]; then
    bashio::log.warning "User configuration requires DB reinitialization. Removing previous DB data."
    rm $DB_PATH
  fi
fi


# If the DB does not exist, create it from scratch
bashio::log.info "Checking for local DB in $DB_PATH"
if [[ -f $DB_PATH ]]; then
  bashio::log.info "DB already exists."
else
  bashio::log.warning "DB does not exist. Creating..."
  sqlite3 $DB_PATH < $DB_SCHEMA_PATH
  if [[ $? -ne 0 ]]; then
    bashio::log.error "Error when creating the database file. Aborting."
    exit 1
  else
    bashio::log.info "DB created correctly"
  fi
fi


# Initializing DB
ADMIN_EMAIL=$(jq --raw-output ".email" $CONFIG_PATH)
ADMIN_PASSWORD=$(jq --raw-output ".password" $CONFIG_PATH)

# TODO: generate the following salts randomly
RANDOM_SALT=6LdesYrDAPJ3UrAz
RANDOM_MQTT_KEY=jHZJp06GX5RS3HdN

#RANDOM_SALT=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 16 | head -n 1)
#RANDOM_MQTT_KEY=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 16 | head -n 1)
HASHED_PASS=$(printf "$RANDOM_SALT$ADMIN_PASSWORD" | sha256sum | head -c 64)
sqlite3 $DB_PATH "INSERT INTO users(email,userid,salt,password,mqtt_key) VALUES(\"$ADMIN_EMAIL\",0,\"$RANDOM_SALT\", \"$HASHED_PASS\", \"$RANDOM_MQTT_KEY\") ON CONFLICT(email) DO UPDATE SET password=\"$HASHED_PASS\", salt=\"$RANDOM_SALT\";"

# Start flask
pushd /opt/meross_api
export FLASK_APP=http_api.py
python3 http_api.py
popd