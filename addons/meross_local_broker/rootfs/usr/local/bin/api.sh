#!/usr/bin/with-contenv bashio
pushd /opt/custom_broker >/dev/null

debug=${debug_mode:-false}

# Start flask
bashio::log.info "Starting flask..."
if [[ $debug == "true" ]]; then
  bashio::log.info "Setting flask debug flags"
  export ENABLE_DEBUG=True
  export DEBUG_PORT=${debug_port:-10001}
  python3 -m debugpy --listen 0.0.0.0:$DEBUG_PORT ./http_api.py
else
  bashio::log.info "Setting flask production flags"
  export ENABLE_DEBUG=False
  python3 ./http_api.py
fi

popd >/dev/null