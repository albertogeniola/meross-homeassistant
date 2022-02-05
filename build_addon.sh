#!/bin/bash
#docker run --rm --privileged -v "$(pwd)":/docker \
#    -i albertogeniola/{arch}-meross_homeassistant_broker \
#    hassioaddons/build-env:latest --tag-latest \
#    --push --all -t addons/meross_local_broker \
#    --maintainer "Alberto Geniola <albertogeniola@gmail.com>"
#
# docker buildx create --use
# Onliner to build a multi-arch image.
# TODO: Test if really works with Raspberry PI
#docker buildx build --push --platform linux/arm/v7,linux/arm64/v8,linux/amd64,linux/i386 --tag albertogeniola/meross_homeassistant_broker:0.0.1-alpha1 .

addon_path=addons/meross_local_broker
repository=albertogeniola
image=meross_homeassistant_broker
version=0.0.1-alpha1


#armhf: "ghcr.io/home-assistant/armhf-base-debian:buster"
#armv7: "ghcr.io/home-assistant/armv7-base-debin:buster"
#i386: "ghcr.io/home-assistant/i386-base-debian:buster"

build_image() {
    build_arch=$1
    build_from=$2
    build_platform=$3
    result_image="${repository}/${build_arch}-${image}:${version}"
    echo ""
    echo "############################"
    echo "Building ${result_image}..."
    echo "############################"
    docker buildx build -t "${result_image}" \
    --push \
    --platform "${build_platform}" \
    --build-arg "BUILD_FROM=${build_from}" \
    --build-arg "BUILD_VERSION=${version}" \
    --build-arg "BUILD_ARCH=${build_arch}" ${addon_path}
}

# Build ARM64
build_image "aarch64" "ghcr.io/home-assistant/aarch64-base-debian:buster" "linux/arm64"
# Build AMD64
build_image "amd64" "ghcr.io/home-assistant/amd64-base-debian:buster" "linux/amd64"
# Build i386
build_image "i386" "ghcr.io/home-assistant/i386-base-debian:buster" "linux/i386"

# Build ARM
#build_image "armv7" "ghcr.io/home-assistant/armv7-base-debian:buster" "linux/arm/v7"
# Build ARMHF
#build_image "armhf" "ghcr.io/home-assistant/armhf-base-debian:buster" "linux/arm/v7"
