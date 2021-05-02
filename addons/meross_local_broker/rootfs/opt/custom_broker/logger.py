import logging
import sys


logging.basicConfig(format='%(asctime)s:%(name)s:%(levelname)s:%(message)s', level=logging.DEBUG, stream=sys.stdout)


def get_logger(name: str):
    return logging.getLogger(name)