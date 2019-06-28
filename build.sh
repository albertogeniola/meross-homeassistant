# Run isort on the entire source
pip install isort
isort -rc custom_components/meross_cloud

# Clean the dist directory
rm -vR dist
mkdir dist

# zip the meross_cloud sources
zip -r dist/meross_cloud.zip custom_components/meross_cloud

