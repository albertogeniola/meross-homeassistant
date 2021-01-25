ARG BUILD_FROM=homeassistant/amd64-base:latest
FROM $BUILD_FROM

ENV LANG C.UTF-8

# Install mosquitto + auth plugin
WORKDIR /usr/src
RUN apk add --no-cache \
        bash \
        sqlite \
        sqlite-dev \
        curl \
        mosquitto \
        musl \
        openssl \
        pwgen \
        socat \
    && apk add --no-cache --virtual .build-dependencies \
        build-base \
        curl-dev \
        git \
        mosquitto-dev \
        openssl-dev \
    \
    && git clone --depth 1 \
        https://github.com/pvizeli/mosquitto-auth-plug \
    && cd mosquitto-auth-plug \
    && cp config.mk.in config.mk && \
    sed -i "s/BACKEND_CDB ?= no/BACKEND_CDB = no/" config.mk && \
    sed -i "s/BACKEND_MYSQL ?= yes/BACKEND_MYSQL = no/" config.mk && \
    sed -i "s/BACKEND_SQLITE ?= no/BACKEND_SQLITE = yes/" config.mk && \
    sed -i "s/BACKEND_REDIS ?= no/BACKEND_REDIS = no/" config.mk && \
    sed -i "s/BACKEND_POSTGRES ?= no/BACKEND_POSTGRES = no/" config.mk && \
    sed -i "s/BACKEND_LDAP ?= no/BACKEND_LDAP = no/" config.mk && \
    sed -i "s/BACKEND_HTTP ?= no/BACKEND_HTTP = no/" config.mk && \
    sed -i "s/BACKEND_JWT ?= no/BACKEND_JWT = no/" config.mk && \
    sed -i "s/BACKEND_MONGO ?= no/BACKEND_MONGO = no/" config.mk && \
    sed -i "s/BACKEND_FILES ?= no/BACKEND_FILES = no/" config.mk && \
    sed -i "s/BACKEND_MEMCACHED ?= no/BACKEND_MEMCACHED = no/" config.mk && \
    sed -i "s/MOSQUITTO_SRC =/MOSQUITTO_SRC = ..\//" config.mk && \
    cat config.mk \
    && make \
    && mkdir -p /usr/share/mosquitto \
    && cp -f auth-plug.so /usr/share/mosquitto \
    \
    && apk del .build-dependencies \
    && rm -fr /usr/src/mosquitto-auth-plug

WORKDIR /
COPY rootfs /

COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh
ENTRYPOINT ["/app/run.sh"]

LABEL io.hass.version="VERSION" io.hass.type="addon" io.hass.arch="armhf|aarch64|i386|amd64"
