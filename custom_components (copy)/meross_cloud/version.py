import logging


_LOGGER = logging.getLogger(__name__)


MEROSS_CLOUD_VERSION = "Unknown"
try:
    import json
    import os
    fname = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(fname, "rt") as f:
        data = json.load(f)
        version = "unknown"
        for r in data.get("requirements"):
            if r.index("meross-iot==")==0:
                version = r.split("==")[1]
                break
        _LOGGER.info(f"MerossCloudVersion: {version}")
        MEROSS_CLOUD_VERSION = version
except:
    _LOGGER.error("Failed to retrieve meross cloud version")
    MEROSS_CLOUD_VERSION = "Unknown"
