"""Loggers setup and utilities"""
import logging
import sys


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG, stream=sys.stdout)


def get_logger(name: str):
    """Returns the a logger for the specific name and creates a new one if not available yet"""
    return logging.getLogger(name)


def set_logger_level(level):
    """Configures the root logging level"""
    logging.getLogger().setLevel(level)
