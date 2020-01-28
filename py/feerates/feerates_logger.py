import os

from utils import setup_logging

ln = os.path.expandvars("$LN")

logger = setup_logging(
    logger_name="feerates_logger",
    filename=os.path.join(ln, "feerates.log"),
)
