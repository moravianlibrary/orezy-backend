
import logging


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stderr",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    # make sure uvicorn loggers propagate to root
    "loggers": {
        "uvicorn": {"level": "INFO", "propagate": True},
        "uvicorn.error": {"level": "INFO", "propagate": True},
        "uvicorn.access": {"level": "INFO", "propagate": True},
    },
}

def setup_logging():
    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger("uvicorn.error")
    logger.setLevel(logging.INFO)
    logger.info("Hello! Logging is set up.")
