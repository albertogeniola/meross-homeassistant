#!/bin/bash

# Generate mosquitto certificates
pushd /etc/mosquitto/certs
openssl genrsa -des3 -out ca.key -passout pass:notasecret 2048
openssl req -new -x509 -days 3600 -key ca.key -out ca.crt -passin pass:notasecret -config ca.conf
openssl genrsa -out server.key 2048
openssl req -new -out server.csr -key server.key -config server.conf
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 3600 -passin pass:notasecret
popd

mosquitto -c /etc/mosquitto/mosquitto.conf