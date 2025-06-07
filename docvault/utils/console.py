"""Console output utilities with logging integration and terminal sanitization."""

import os
from typing import Optional

from rich.console import Console as RichConsole
from rich.table import Table

from docvault.utils.logging import get_logger
from docvault.utils.terminal_sanitizer import (
    contains_suspicious_sequences,
    sanitize_output,
)

# Global console instance
_console = RichConsole()
logger = get_logger(__name__)


class LoggingConsole:
    """Console wrapper that logs messages and sanitizes output."""

    def __init__(self, console: RichConsole | None = None, sanitize: bool = True):
        self.console = console or _console
        self.logger = get_logger("docvault.console")
        # Enable sanitization by default, can be disabled via env var
        self.sanitize = sanitize and os.getenv("DOCVAULT_DISABLE_SANITIZATION") != "1"

    def print(self, *args, style: str | None = None, **kwargs):
        """Print to console and log the message with sanitization."""
        # Convert args to string and sanitize if needed
        sanitized_args = []
        suspicious = False

        for arg in args:
            # Special handling for Rich Table objects
            if isinstance(arg, Table):
                # Rich tables should be passed through without conversion
                sanitized_args.append(arg)
            else:
                arg_str = str(arg)
                if self.sanitize and contains_suspicious_sequences(arg_str):
                    suspicious = True
                    arg_str = sanitize_output(arg_str)
                sanitized_args.append(arg_str)

        # Build message for logging (skip Table objects)
        message_parts = []
        for arg in sanitized_args:
            if not isinstance(arg, Table):
                message_parts.append(str(arg))
        message = " ".join(message_parts) if message_parts else "<table output>"

        # Log warning if suspicious sequences were found
        if suspicious:
            self.logger.warning(
                "Suspicious terminal sequences detected and removed from output"
            )

        # Log based on style (only if we have non-table content)
        if message != "<table output>":
            if style and ("error" in style or "red" in style):
                self.logger.error(message)
            elif style and ("warning" in style or "yellow" in style):
                self.logger.warning(message)
            elif style and ("success" in style or "green" in style):
                self.logger.info(f"SUCCESS: {message}")
            else:
                self.logger.info(message)

        # Print sanitized content to console
        self.console.print(*sanitized_args, style=style, **kwargs)

    def error(self, message: str, **kwargs):
        """Print error message with sanitization."""
        if self.sanitize:
            message = sanitize_output(message)
        self.logger.error(message)
        self.console.print(f"❌ {message}", style="bold red", **kwargs)

    def warning(self, message: str, **kwargs):
        """Print warning message with sanitization."""
        if self.sanitize:
            message = sanitize_output(message)
        self.logger.warning(message)
        self.console.print(f"⚠️  {message}", style="yellow", **kwargs)

    def success(self, message: str, **kwargs):
        """Print success message with sanitization."""
        if self.sanitize:
            message = sanitize_output(message)
        self.logger.info(f"SUCCESS: {message}")
        self.console.print(f"✅ {message}", style="green", **kwargs)

    def info(self, message: str, **kwargs):
        """Print info message with sanitization."""
        if self.sanitize:
            message = sanitize_output(message)
        self.logger.info(message)
        self.console.print(message, **kwargs)

    def status(self, *args, **kwargs):
        """Create a status context."""
        return self.console.status(*args, **kwargs)

    def print_table(self, table: Table):
        """Print a Rich table."""
        self.console.print(table)

    def rule(self, *args, **kwargs):
        """Print a rule."""
        self.console.rule(*args, **kwargs)

    def print_exception(self, **kwargs):
        """Print exception traceback."""
        self.console.print_exception(**kwargs)

    def __getattr__(self, name):
        """Forward missing attributes to the underlying Rich console."""
        return getattr(self.console, name)

    def __enter__(self):
        """Context manager entry."""
        if hasattr(self.console, "__enter__"):
            return self.console.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if hasattr(self.console, "__exit__"):
            return self.console.__exit__(exc_type, exc_val, exc_tb)
        return None


# Global console instance with logging
console = LoggingConsole()
