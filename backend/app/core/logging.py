import logging
import sys
from typing import Optional

from app.config import settings


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Configures the application logging system.

    Sets up structured, consistent logging for the entire application.
    Call this once at application startup in main.py.

    Args:
        log_level: Override the log level from settings.
                   If None, uses settings.LOG_LEVEL.
    """
    level_str = log_level or settings.LOG_LEVEL
    level = getattr(logging, level_str, logging.INFO)

    # --------------------------------------------------------------------------
    # LOG FORMAT
    # --------------------------------------------------------------------------
    # Development format: human-readable with colors (if supported)
    # Production format: structured for log aggregation tools
    # --------------------------------------------------------------------------

    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    # --------------------------------------------------------------------------
    # CONSOLE HANDLER
    # Writes log output to stdout (terminal in development, captured in production)
    # --------------------------------------------------------------------------

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(
        logging.Formatter(fmt=log_format, datefmt=date_format)
    )

    # --------------------------------------------------------------------------
    # ROOT LOGGER CONFIGURATION
    # All loggers in the application inherit from the root logger.
    # --------------------------------------------------------------------------

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers to avoid duplicate logs
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # --------------------------------------------------------------------------
    # SILENCE NOISY THIRD-PARTY LOGGERS
    # Some libraries log too much. Set them to WARNING to reduce noise.
    # --------------------------------------------------------------------------

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)

    # --------------------------------------------------------------------------
    # LOG STARTUP CONFIRMATION
    # --------------------------------------------------------------------------

    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured. level=%s app=%s version=%s debug=%s",
        level_str,
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.DEBUG,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger for use in any module.

    Convenience wrapper around logging.getLogger.
    Encourages consistent logger naming across the application.

    Usage:
        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("message")
    """
    return logging.getLogger(name)