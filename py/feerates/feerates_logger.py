import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from paths import LN

logger = logging.getLogger("feerates_logger")

fmt = "%(asctime)s: %(levelname)s: %(module)s: %(funcName)s: %(message)s"
formatter = logging.Formatter(fmt=fmt, datefmt='%Y-%m-%d %H:%M:%S')
logger.setLevel(logging.DEBUG)

# file handler. we use RotatingFileHandler since this logger may be used
# indefinitely (e.g. for the feerates dump process)
logfile = os.path.join(LN, "feerates.log")
file_handler = RotatingFileHandler(
    filename=logfile,
    maxBytes=50 * 1024 * 1024,  # 50 MB
    backupCount=1,
)
file_handler.setFormatter(formatter)
file_handler.setLevel("DEBUG")
logger.addHandler(file_handler)

# console handler
console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel("DEBUG")
logger.addHandler(console_handler)
