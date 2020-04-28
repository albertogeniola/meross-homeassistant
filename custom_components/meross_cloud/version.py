import logging


_LOGGER = logging.getLogger(__name__)


MEROSS_CLOUD_VERSION = "Unknown"
try:
    import json
    import os
    fname = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(fname, "rt") as f:
        data = json.load(f)
        _LOGGER.info("MerossCloudVersion: %s" % data.get("meross_cloud_version"))
        MEROSS_CLOUD_VERSION = data.get("meross_cloud_version")
except:
    _LOGGER.error("Failed to retrieve meross cloud version")
    MEROSS_CLOUD_VERSION = "Unknown"