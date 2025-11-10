"""Logger configuration for the QA system."""

import logging
import sys
from datetime import datetime

# Create logs directory
import os
os.makedirs("logs", exist_ok=True)


def setup_logging(log_level: str = "INFO"):
    """Set up comprehensive logging."""

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    simple_formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    # File handler - general logs
    file_handler = logging.FileHandler(
        f"logs/app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    # File handler - errors only
    error_handler = logging.FileHandler(f"logs/errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)

    return logger


# Get logger instance
logger = logging.getLogger(__name__)

