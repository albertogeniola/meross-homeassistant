#!/usr/bin/with-contenv bashio

pushd /opt/custom_broker >/dev/null

# Start flask
export FLASK_APP=http_api.py
debug=$(bashio::config 'debug_mode')

if [[ $debug == true ]]; then
  bashio::log.info "Setting flask debug flags"
  export FLASK_ENV=development
  export FLASK_DEBUG=1
else
  bashio::log.info "Setting flask production flags"
  export FLASK_ENV=production
  export FLASK_DEBUG=0
fi

bashio::log.info "Starting flask..."
flask run --host=0.0.0.0 --port=2002
bashio::log.warning "Flask terminated."

popd >/dev/null