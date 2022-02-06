#!/bin/bash
# docker run --rm --network host -p 2003:2001/tcp -p 2004:2002/tcp -v "$(pwd)/.local_debug/data":/data local/meross_local_broker
docker run --rm -p 8099:8099/tcp -p 2003:2001/tcp -p 2004:2002/tcp -v "$(pwd)/.local_debug/data":/data local/meross_local_broker
