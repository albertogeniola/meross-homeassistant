#!/bin/bash
docker build --build-arg BUILD_ARCH="amd64" --build-arg BUILD_FROM="ghcr.io/home-assistant/amd64-base-debian:buster" -t local/meross_local_broker "addons/meross_local_broker"
