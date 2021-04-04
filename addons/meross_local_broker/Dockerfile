ARG BUILD_FROM=ghcr.io/hassio-addons/base/amd64:9.1.6
#ARG BUILD_FROM=homeassistant/amd64-base:latest

FROM ${BUILD_FROM}

# Versions
ENV HIVEMQ='b2043e7fcbd5897a3799869d42c6202122221fbc' \
    LIBWEBSOCKETS='3.1.0' \
    MOSQUITTO='2.0.10' \
    MOSQUITTO_GO_AUTH='1.5.0'

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Set workdir
WORKDIR /usr/src

# Copy the requirements.txt file
COPY rootfs/opt/custom_broker/requirements.txt requirements.txt

# Setup base
# hadolint ignore=DL3003
RUN apk update \
  && apk add --no-cache --virtual .build-dependencies \
    git \
    cmake \
    build-base \
    openssl-dev \
    libressl-dev \
    util-linux-dev \
    avahi-dev \
    python3-dev \
  \
  && apk add --no-cache \
    avahi \
    avahi-compat-libdns_sd \
    avahi-tools \
    dbus \
    bash \
    sqlite \
    sqlite-dev \
    curl \
    musl \
    openssl \
    pwgen \
    socat \
    python3 \
    py3-pip \
    nginx \
    go \
  \
  && pip3 install -r requirements.txt \
  \
  && git clone --branch "v${LIBWEBSOCKETS}" --depth=1 \
    https://github.com/warmcat/libwebsockets.git /tmp/libwebsockets \
  \
  && mkdir -p /tmp/libwebsockets/build \
  && cd /tmp/libwebsockets/build \
  && cmake .. \
    -DCMAKE_BUILD_TYPE=MinSizeRel \
    -DCMAKE_INSTALL_PREFIX=/usr \
    -DLWS_IPV6=OFF \
    -DLWS_WITHOUT_BUILTIN_GETIFADDRS=ON \
    -DLWS_WITHOUT_CLIENT=ON \
    -DLWS_WITHOUT_EXTENSIONS=ON \
    -DLWS_WITHOUT_TESTAPPS=ON \
    -DLWS_WITH_SHARED=OFF \
    -DLWS_WITH_ZIP_FOPS=OFF \
    -DLWS_WITH_ZLIB=OFF \
  && make \
  && make install \
  \
  && git clone --branch "v${MOSQUITTO}" --depth=1 \
      https://github.com/eclipse/mosquitto.git /tmp/mosquitto \
  \
  && cd /tmp/mosquitto \
  && make \
    WITH_ADNS=no \
    WITH_DOCS=no \
    WITH_MEMORY_TRACKING=no \
    WITH_TLS_PSK=no \
    WITH_WEBSOCKETS=yes \
    WITH_CJSON=no \
    WITH_CLIENTS=no \
    WITH_BROKER=yes \
    WITH_PLUGINS=yes \
    prefix=/usr \
    binary \
  && make WITH_DOCS=no WITH_CJSON=no install binary \
  \
  && cd /tmp \
  && git clone --depth 1 --branch "${MOSQUITTO_GO_AUTH}" \
        https://github.com/iegomez/mosquitto-go-auth.git \
  && cd mosquitto-go-auth \
  && make \
  && mkdir -p /usr/share/mosquitto \
  && cp /tmp/mosquitto-go-auth/pw /usr/share/mosquitto/pw \
  && cp /tmp/mosquitto-go-auth/go-auth.so /usr/share/mosquitto/go-auth.so \
  \
  && addgroup -S mosquitto \
  && adduser -S -D -H -h /var/empty -s /sbin/nologin \
    -G mosquitto -g mosquitto mosquitto \
  \
  && apk del --no-cache --purge .build-dependencies \
  && rm -fr \
    /etc/nginx \
    /opt/mosquitto.conf \
    /opt/acl \
    /tmp/*


WORKDIR /
COPY rootfs /
RUN chmod +x /usr/local/bin/*.sh

# Build arguments
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_REF
ARG BUILD_VERSION

LABEL io.hass.version="VERSION" io.hass.type="addon" io.hass.arch="armhf|aarch64|i386|amd64"
