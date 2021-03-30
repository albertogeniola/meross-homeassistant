ARG BUILD_FROM=homeassistant/amd64-base:latest
#ARG BUILD_FROM=hassioaddons/base:2.1.2
FROM $BUILD_FROM

ENV LANG C.UTF-8

# Install mosquitto + auth plugin
WORKDIR /usr/src
COPY rootfs/opt/custom_broker/requirements.txt requirements.txt
RUN apk add --no-cache --virtual .build-dependencies \
        avahi-dev \
        build-base \
        curl-dev \
        git \
        mosquitto-dev \
        openssl-dev \
        python3-dev \
    && apk add --no-cache \
        avahi \
        avahi-compat-libdns_sd \
        avahi-tools \
        dbus \
        bash \
        sqlite \
        sqlite-dev \
        curl \
        mosquitto \
        musl \
        openssl \
        pwgen \
        socat \
        python3 \
        py3-pip \
        nginx \
    && pip3 install -r requirements.txt \
    && git clone --depth 1 --branch 0.1.5 \
        https://github.com/albertogeniola/mosquitto-auth-plug \
    && cd mosquitto-auth-plug \
    && cp config.mk.in config.mk && \
    sed -i "s/BACKEND_CDB ?= no/BACKEND_CDB = no/" config.mk && \
    sed -i "s/BACKEND_MYSQL ?= yes/BACKEND_MYSQL = no/" config.mk && \
    sed -i "s/BACKEND_SQLITE ?= no/BACKEND_SQLITE = no/" config.mk && \
    sed -i "s/BACKEND_REDIS ?= no/BACKEND_REDIS = no/" config.mk && \
    sed -i "s/BACKEND_POSTGRES ?= no/BACKEND_POSTGRES = no/" config.mk && \
    sed -i "s/BACKEND_LDAP ?= no/BACKEND_LDAP = no/" config.mk && \
    sed -i "s/BACKEND_HTTP ?= no/BACKEND_HTTP = yes/" config.mk && \
    sed -i "s/BACKEND_JWT ?= no/BACKEND_JWT = no/" config.mk && \
    sed -i "s/BACKEND_MONGO ?= no/BACKEND_MONGO = no/" config.mk && \
    sed -i "s/BACKEND_FILES ?= no/BACKEND_FILES = yes/" config.mk && \
    sed -i "s/BACKEND_MEMCACHED ?= no/BACKEND_MEMCACHED = no/" config.mk && \
    sed -i "s/MOSQUITTO_SRC =/MOSQUITTO_SRC = ..\//" config.mk && \
    cat config.mk \
    && make \
    && mkdir -p /usr/share/mosquitto \
    && cp -f auth-plug.so /usr/share/mosquitto \
    && cp -f np /usr/local/bin \
    && apk del .build-dependencies \
    && rm -fr /usr/src/mosquitto-auth-plug \
    && mkdir -p /run/nginx

WORKDIR /
COPY rootfs /
RUN chmod +x /usr/local/bin/*.sh

LABEL io.hass.version="VERSION" io.hass.type="addon" io.hass.arch="armhf|aarch64|i386|amd64"
