import logging
import os
import sys


def get_logger(name):
    ch = logging.StreamHandler(sys.stdout)
    log_level_name = os.environ['LOG_LEVEL'] if 'LOG_LEVEL' in os.environ else 'DEBUG'
    log_level = getattr(logging, log_level_name.upper())
    ch.setLevel(log_level)
    formatter = logging.Formatter('timestamp:%(asctime)s level:%(levelname)s name:%(name)s message:%(message)s',
                                  datefmt="%Y-%m-%dT%H:%M:%S%z")
    ch.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.handlers = []
    logger.addHandler(ch)
    logger.setLevel(logging.DEBUG)
    return logger


def format_logger_with_id(logger, id_name, id_val):
    formatter = logging.Formatter(f'corr_id:{id_name}:{id_val} timestamp:%(asctime)s level:%(levelname)s' +
                                  ' name:%(name)s message:%(message)s', datefmt="%Y-%m-%dT%H:%M:%S%z")
    logger.handlers[0].setFormatter(formatter)
    return logger
