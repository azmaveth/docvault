"""Console output utilities with logging integration."""

from typing import Optional

from rich.console import Console as RichConsole
from rich.table import Table

from docvault.utils.logging import get_logger

# Global console instance
_console = RichConsole()
logger = get_logger(__name__)


class LoggingConsole:
    """Console wrapper that logs messages in addition to printing them."""

    def __init__(self, console: Optional[RichConsole] = None):
        self.console = console or _console
        self.logger = get_logger("docvault.console")

    def print(self, *args, style: Optional[str] = None, **kwargs):
        """Print to console and log the message."""
        # Convert args to string
        message = " ".join(str(arg) for arg in args)

        # Log based on style
        if style and ("error" in style or "red" in style):
            self.logger.error(message)
        elif style and ("warning" in style or "yellow" in style):
            self.logger.warning(message)
        elif style and ("success" in style or "green" in style):
            self.logger.info(f"SUCCESS: {message}")
        else:
            self.logger.info(message)

        # Print to console
        self.console.print(*args, style=style, **kwargs)

    def error(self, message: str, **kwargs):
        """Print error message."""
        self.logger.error(message)
        self.console.print(f"❌ {message}", style="bold red", **kwargs)

    def warning(self, message: str, **kwargs):
        """Print warning message."""
        self.logger.warning(message)
        self.console.print(f"⚠️  {message}", style="yellow", **kwargs)

    def success(self, message: str, **kwargs):
        """Print success message."""
        self.logger.info(f"SUCCESS: {message}")
        self.console.print(f"✅ {message}", style="green", **kwargs)

    def info(self, message: str, **kwargs):
        """Print info message."""
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


# Global console instance with logging
console = LoggingConsole()
