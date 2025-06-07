"""Logging utilities for DocVault."""

import logging
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from docvault import config


def setup_logging(
    level: str | None = None,
    log_file: str | None = None,
    quiet: bool = False,
    verbose: bool = False,
) -> None:
    """Set up logging configuration for DocVault.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        quiet: If True, only show errors
        verbose: If True, show debug messages
    """
    # Determine log level
    if quiet:
        log_level = logging.ERROR
    elif verbose:
        log_level = logging.DEBUG
    elif level:
        log_level = getattr(logging, level.upper(), logging.INFO)
    else:
        log_level = getattr(logging, config.LOG_LEVEL, logging.INFO)

    # Create formatters
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler with Rich
    console_handler = RichHandler(
        console=Console(stderr=True),
        show_time=False,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_suppress=[
            "click",
            "asyncio",
        ],
    )
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file or config.LOG_FILE:
        log_path = Path(log_file or config.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class UserFriendlyFormatter(logging.Formatter):
    """Custom formatter that shows user-friendly messages for common errors."""

    ERROR_MESSAGES = {
        "ConnectionError": (
            "Could not connect to the server. Please check your internet "
            "connection."
        ),
        "SSLError": (
            "SSL certificate verification failed. The website might be using a "
            "self-signed certificate."
        ),
        "TimeoutError": "Request timed out. The server might be slow or unresponsive.",
        "DNSLookupError": "Could not resolve the domain name. Please check the URL.",
        "HTTPError": "Server returned an error response.",
    }

    def format(self, record: logging.LogRecord) -> str:
        # For errors, try to provide a user-friendly message
        if record.levelno >= logging.ERROR and record.exc_info:
            exc_type = record.exc_info[0]
            if exc_type and exc_type.__name__ in self.ERROR_MESSAGES:
                record.msg = self.ERROR_MESSAGES[exc_type.__name__]
                record.exc_info = None  # Don't show stack trace

        return super().format(record)
