"""
A lumberjack deals with logs.
"""
import os
import logging
import logging.config
from logging import Logger

from service.packages.lumberjack.SensitiveDataFilter import SensitiveDataFilter

LOGGER_DEFAULT_NAME = "AppLogger"

if os.getenv("LOG_LEVEL"):
    level = logging.getLevelName(int(os.getenv("LOG_LEVEL")))
else:
    # Default log level to INFO
    level = logging.getLevelName(20)


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"sensitive_data_filter": {"()": SensitiveDataFilter}},
    "formatters": {
        "json": {
            # dd.* fields (ITPP-375): ddtrace log-trace correlation. With DD_LOGS_INJECTION=true the
            # tracer populates these; when tracing is off they render null (JsonFormatter uses
            # record.__dict__.get, so absent fields don't raise) — prod-safe.
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s - %(dd.service)s - %(dd.env)s - %(dd.version)s - %(dd.trace_id)s - %(dd.span_id)s",
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        }
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json",
            "filters": ["sensitive_data_filter"],
        }
    },
    "loggers": {
        LOGGER_DEFAULT_NAME: {"handlers": ["stdout"], "level": level},
        "tortoise.db_client": {
            "handlers": ["stdout"],
            "level": "INFO",
        },
        "tortoise": {
            "handlers": ["stdout"],
            "level": "INFO",
        },
    },
}


def get_logger() -> Logger:
    """
    Returns our default AppLogger class.

    Returns:
        Logger
    """
    logging.config.dictConfig(LOGGING)
    return logging.getLogger(LOGGER_DEFAULT_NAME)
