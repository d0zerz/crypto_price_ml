import logging
import os
from logging.handlers import RotatingFileHandler
import sys


def configure_logging(log_dir=None, log_level=logging.INFO, logfile=None):
    """
    Configure logging for the application.

    Args:
        log_dir: Directory to store log files. If None, only console logging is configured.
        log_level: The logging level to use (default: logging.INFO)
    """
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    # Ensure stdout uses UTF-8 encoding
    sys.stdout.reconfigure(encoding='utf-8')

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if log_dir is provided)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, logfile),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Suppress overly verbose loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return root_logger
