import logging
import sys
import os
from app.core.config import get_settings


class CustomFormatter(logging.Formatter):
    cyan = "\x1b[36;20m"
    magenta = "\x1b[35;1m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    base_format = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )

    FORMATS = {
        logging.DEBUG: cyan + base_format + reset,
        logging.INFO: magenta + base_format + reset,
        logging.WARNING: yellow + base_format + reset,
        logging.ERROR: red + base_format + reset,
        logging.CRITICAL: bold_red + base_format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.base_format)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


logger = logging.getLogger("server")

# Set log level from environment variable, defaulting to INFO
# In a DEBUG environment (from settings), you might want to default to DEBUG
# but for simplicity here, we'll use LOG_LEVEL env var directly.
# try:
#     settings = get_settings()
#     default_level = "DEBUG" if settings.DEBUG else "ERROR"
# except Exception:
#     default_level = "INFO"

# LOG_LEVEL_STR = os.environ.get("LOG_LEVEL", default_level).upper()
LOG_LEVEL_STR = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)
logger.setLevel(LOG_LEVEL)

logger.handlers.clear()
logger.propagate = False

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(CustomFormatter())

logger.addHandler(console_handler)
