sudo docker build -t meross_offline_broker --build-arg BUILD_FROM=alpine:3.13.0 ..
sudo docker run --rm -v /tmp/my_test_data:/data -p 127.0.0.1:2001:2001/tcp meross_offline_broker
