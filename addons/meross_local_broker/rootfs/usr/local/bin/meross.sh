#!/usr/bin/with-contenv bashio

pushd /opt/meross_api >/dev/null

# Start flask
export FLASK_APP=http_api.py
export FLASK_ENV=development
export FLASK_DEBUG=0
bashio::log.info "Starting flask..."
flask run --host=0.0.0.0 --port=2002
bashio::log.warning "Flask terminated."

popd >/dev/null