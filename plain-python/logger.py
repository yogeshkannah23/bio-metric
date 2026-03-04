"""
Logging — three rotating file loggers used across the application.
"""

import os
import logging
from logging.handlers import RotatingFileHandler

import config

os.makedirs(config.LOGS_DIRECTORY, exist_ok=True)


def _make_logger(name, log_file, level=logging.INFO):
    fmt = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
    h = RotatingFileHandler(
        os.path.join(config.LOGS_DIRECTORY, log_file),
        maxBytes=10 * 1024 * 1024, backupCount=10
    )
    h.setFormatter(fmt)
    lg = logging.getLogger(name)
    lg.setLevel(level)
    if not lg.handlers:
        lg.addHandler(h)
    return lg


error_logger   = _make_logger('adms_error',   'adms_error.log',  logging.ERROR)
info_logger    = _make_logger('adms_info',    'adms_logs.log')
checkin_logger = _make_logger('adms_checkin', 'adms_checkin.log')
