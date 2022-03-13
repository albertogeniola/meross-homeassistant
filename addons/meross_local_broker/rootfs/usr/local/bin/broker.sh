#!/usr/bin/with-contenv bashio

CONFIG_PATH=/data/options.json

pushd /opt/custom_broker >/dev/null

# Setup debug flag
debug=${debug_mode:-false}
if [[ $debug == "true" ]]; then
  bashio::log.info "Starting broker agent with debug flag"
  debug="--debug"
else
  debug=""
fi

#bridging=$(bashio::config 'federate_with_meross')
#if [[ $bridging == true ]]; then
#  bashio::log.info "Enabling Meross bridging"
#  bridging="--enable-bridging"
#else
#  bridging=""
#fi

# Generate a random password for agent user
AGENT_USERNAME="_agent"
AGENT_PASSWORD=$(openssl rand -base64 32)
AGENT_PBKDF2=$(/usr/share/mosquitto/pw -p $AGENT_PASSWORD)
echo "$AGENT_USERNAME:$AGENT_PBKDF2">/etc/mosquitto/auth.pw

# Grant to the _agent user permissions to:
# - read from /appliance/+/publish
# - write to /app/+/subscribe
#echo -e "user $AGENT_USERNAME\ntopic read /appliance/+/publish\ntopic write /app/+/subscribe">/etc/mosquitto/auth.acl
echo -e "user $AGENT_USERNAME\ntopic readwrite #">/etc/mosquitto/auth.acl

# Wait until mqtt is ready is available
bashio::log.info "Waiting MQTT server..."
bashio::net.wait_for 2001

python3 broker_agent.py --port 2001 --host localhost --username "$AGENT_USERNAME" --password "$AGENT_PASSWORD" --cert-ca "/data/mqtt/certs/ca.crt" $debug

popd >/dev/null