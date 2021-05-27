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

# If auth-plugin is not installed, build it now
if [[ ! -f go-auth.so ]]; then
  echo "Auth Plugin file missing. Building it now."
  build_auth_plugin
fi

# Generate keys
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 3600 -batch -nodes -key ca.key -out ca.crt
openssl genrsa -out server.key 2048
openssl req -new -batch -out server.csr -key server.key
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 360

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
