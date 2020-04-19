#!/bin/bash

# Run isort on the entire source
pip install isort
isort -rc custom_components/meross_cloud

# Clean the dist directory
rm -vR dist
mkdir dist

# zip the meross_cloud sources
pushd custom_components
zip -r ../dist/meross_cloud.zip meross_cloud
popd
