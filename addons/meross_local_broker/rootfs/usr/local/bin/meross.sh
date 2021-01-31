#!/usr/bin/with-contenv bashio

CONFIG_PATH=/data/options.json
DB_PATH=/data/database.db
DB_SCHEMA_PATH=/opt/meross_api/schema.sql
MQTT_CERTS_FOLDER_PATH=/data/mqtt/certs
MQTT_CA_KEY_PATH="$MQTT_CERTS_FOLDER_PATH/ca.key"
MQTT_CA_CRT_PATH="$MQTT_CERTS_FOLDER_PATH/ca.crt"
MQTT_SERVER_KEY_PATH="$MQTT_CERTS_FOLDER_PATH/server.key"
MQTT_SERVER_CRT_PATH="$MQTT_CERTS_FOLDER_PATH/server.crt"
MQTT_CA_KEY_SECRET=notasecret
MQTT_CA_CONFIG_PATH=/etc/mosquitto/certs/ca.conf
MQTT_SERVER_CONFIG_PATH=/etc/mosquitto/certs/server.conf
MQTT_MOSQUITTO_CONF_PATH=/etc/mosquitto/mosquitto.conf


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

# Generate mosquitto certificates
bashio::log.info "Checking for RSA keys..."
if [[ ! -d $MQTT_CERTS_FOLDER_PATH ]]; then
  mkdir -p $MQTT_CERTS_FOLDER_PATH
fi
if [[ ! -f $MQTT_CA_KEY_PATH ]] || [[ ! -f $MQTT_CA_CRT_PATH ]] || [[ ! -f $MQTT_SERVER_KEY_PATH ]] || [[ ! -f $MQTT_SERVER_CRT_PATH ]]; then
  bashio::log.warning "One or more certificate files are not present on the system. Generating certificates from scratch..."
  rm -R $MQTT_CERTS_FOLDER_PATH
  mkdir -p $MQTT_CERTS_FOLDER_PATH
else
  bashio::log.info "All certificate files seems present."
fi


openssl genrsa -des3 -out $MQTT_CA_KEY_PATH -passout pass:$MQTT_CA_KEY_SECRET 2048
openssl req -new -x509 -days 3600 -key $MQTT_CA_KEY_PATH -out $MQTT_CA_CRT_PATH -passin pass:$MQTT_CA_KEY_SECRET -config $MQTT_CA_CONFIG_PATH
openssl genrsa -out $MQTT_SERVER_KEY_PATH 2048
openssl req -new -out /tmp/server.csr -key $MQTT_SERVER_KEY_PATH -config $MQTT_SERVER_CONFIG_PATH
openssl x509 -req -in /tmp/server.csr -CA $MQTT_CA_CRT_PATH -CAkey $MQTT_CA_KEY_PATH -CAcreateserial -out $MQTT_SERVER_CRT_PATH -days 3600 -passin pass:$MQTT_CA_KEY_SECRET


# Start flask
pushd /opt/meross_api
export FLASK_APP=http_api.py
python3 http_api.py &
popd

mosquitto -c $MQTT_MOSQUITTO_CONF_PATH