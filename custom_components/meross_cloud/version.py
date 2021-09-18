import logging
from meross_iot.utilities.misc import current_version

_LOGGER = logging.getLogger(__name__)

MEROSS_IOT_VERSION = current_version()
MEROSS_INTEGRATION_VERSION = "N/A"
try:
    import json
    import os
    fname = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(fname, "rt") as f:
        data = json.load(f)
        MEROSS_INTEGRATION_VERSION = data.get("version")
except:
    _LOGGER.error("Failed to retrieve integration version")

_LOGGER.info(f"MerossIot Version: {MEROSS_IOT_VERSION}")
_LOGGER.info(f"Integration Version: {MEROSS_INTEGRATION_VERSION}")