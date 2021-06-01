#!/bin/bash

function build_auth_plugin () {
  # Install Mosquitto
  sudo apt-get install -y cmake libc-ares-dev libssl-dev openssllibc-ares2 openssl uuid uuid-dev libwebsockets-dev
  wget http://mosquitto.org/files/source/mosquitto-2.0.9.tar.gz
  tar xzvf mosquitto-2.0.9.tar.gz
  pushd mosquitto-2.0.9 || exit
  sudo make install WITH_WEBSOCKETS=yes WITH_CJSON=no
  sudo groupadd mosquitto
  sudo useradd -s /sbin/nologin mosquitto -g mosquitto -d /var/lib/mosquitto
  sudo mkdir -p /var/log/mosquitto/ /var/lib/mosquitto/
  sudo chown -R mosquitto:mosquitto /var/log/mosquitto/
  sudo chown -R mosquitto:mosquitto /var/lib/mosquitto/
  if [[ -d /tmp/mosquitto-go-auth ]]; then
    sudo rm -R /tmp/mosquitto-go-auth
  fi
  popd
  rm -rf xzvf mosquitto-2.0.9.tar.gz

  # Install GO
  wget https://dl.google.com/go/go1.13.8.linux-amd64.tar.gz
  sudo tar -C /usr/local -xzf go1.13.8.linux-amd64.tar.gz
  sudo rm /usr/bin/go
  ln -s /usr/local/go/bin/go /usr/bin/go
  rm go1.13.8.linux-amd64.tar.gz

  # Make plugin
  git clone https://github.com/iegomez/mosquitto-go-auth.git --branch 1.6.0 /tmp/mosquitto-go-auth
  pushd /tmp/mosquitto-go-auth || exit
  sudo go version
  sudo make
  popd

  cp /tmp/mosquitto-go-auth/pw pw
  cp /tmp/mosquitto-go-auth/go-auth.so go-auth.so
  rm -fr /tmp/mosquitto-go-auth
}

function setup_certs() {
  MQTT_CERTS_FOLDER_PATH=./certs
  MQTT_CA_KEY_PATH="$MQTT_CERTS_FOLDER_PATH/ca.key"
  MQTT_CA_CRT_PATH="$MQTT_CERTS_FOLDER_PATH/ca.crt"
  MQTT_SERVER_KEY_PATH="$MQTT_CERTS_FOLDER_PATH/server.key"
  MQTT_SERVER_CRT_PATH="$MQTT_CERTS_FOLDER_PATH/server.crt"
  MQTT_CA_KEY_SECRET=notasecret
  MQTT_CA_CONFIG_PATH=./ca.conf
  MQTT_SERVER_CONFIG_PATH=./server.conf

  # Generate mosquitto certificates
  echo "Checking for RSA keys..."
  if [[ ! -d $MQTT_CERTS_FOLDER_PATH ]]; then
    mkdir -p $MQTT_CERTS_FOLDER_PATH
  fi
  if [[ ! -f $MQTT_CA_KEY_PATH ]] || [[ ! -f $MQTT_CA_CRT_PATH ]] || [[ ! -f $MQTT_SERVER_KEY_PATH ]] || [[ ! -f $MQTT_SERVER_CRT_PATH ]]; then
    echo "One or more certificate files are not present on the system. Generating certificates from scratch..."
    rm -R $MQTT_CERTS_FOLDER_PATH
    mkdir -p $MQTT_CERTS_FOLDER_PATH

    openssl genrsa -des3 -out $MQTT_CA_KEY_PATH -passout pass:$MQTT_CA_KEY_SECRET 2048
    openssl req -new -x509 -days 3600 -key $MQTT_CA_KEY_PATH -out $MQTT_CA_CRT_PATH -passin pass:$MQTT_CA_KEY_SECRET -config $MQTT_CA_CONFIG_PATH
    openssl genrsa -out $MQTT_SERVER_KEY_PATH 2048
    openssl req -new -out /tmp/server.csr -key $MQTT_SERVER_KEY_PATH -config $MQTT_SERVER_CONFIG_PATH
    openssl x509 -req -in /tmp/server.csr -CA $MQTT_CA_CRT_PATH -CAkey $MQTT_CA_KEY_PATH -CAcreateserial -out $MQTT_SERVER_CRT_PATH -days 3600 -passin pass:$MQTT_CA_KEY_SECRET
  else
    echo "All certificate files seems present."
  fi

  # Align permissions
  echo "Aligning permissions for certificates"
  chown -vR mosquitto:mosquitto ./
}

# If auth-plugin is not installed, build it now
if [[ ! -f go-auth.so ]]; then
  echo "Auth Plugin file missing. Building it now."
  build_auth_plugin
fi


# Create auth files
AGENT_USERNAME="admin"
AGENT_PASSWORD="admin"
AGENT_PBKDF2=$(./pw -p $AGENT_PASSWORD)
echo "$AGENT_USERNAME:$AGENT_PBKDF2">./auth.pw
cat <<EOF > ./auth.acl
user $AGENT_USERNAME
topic write #
topic read #
EOF

# Start mosquitto
echo "Starting mosquitto."
mosquitto -c mosquitto.conf
