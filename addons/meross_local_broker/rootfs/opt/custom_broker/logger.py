"""Loggers setup and utilities"""
import logging
import sys
from logging.handlers import RotatingFileHandler


# Configure main logger, specifying logging format and default handlers.
# 128K log file, rotating on a single file.
logging.basicConfig(format='%(asctime)s:%(name)s:%(levelname)s:%(message)s',
                    level=logging.DEBUG, stream=sys.stdout)
fileHandler = RotatingFileHandler(
    filename="/var/log/broker/api.log", maxBytes=131072, backupCount=1)
logging.getLogger().addHandler(fileHandler)


def get_logger(name: str):
    """Returns the a logger for the specific name and creates a new one if not available yet"""
    return logging.getLogger(name)


def set_logger_level(level):
    """Configures the root logging level"""
    logging.getLogger().setLevel(level)
