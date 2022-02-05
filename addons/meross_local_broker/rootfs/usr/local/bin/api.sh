#!/usr/bin/with-contenv bashio

pushd /opt/custom_broker >/dev/null

# Start flask
debug=$(bashio::config 'debug_mode')
debug_port=$(bashio::addon.port 10001)

bashio::log.info "Starting flask..."
if [[ $debug == true ]]; then
  bashio::log.info "Setting flask debug flags"
  export ENABLE_DEBUG=True
  export DEBUG_PORT=$debug_port
  python3 -m debugpy --listen 0.0.0.0:$debug_port ./http_api.py
else
  bashio::log.info "Setting flask production flags"
  export ENABLE_DEBUG=False
  python3 ./http_api.py
fi

bashio::log.warning "Flask terminated."

popd >/dev/null