"""Base test class for CLI tests with common fixtures."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner


class BaseCLITest:
    """Base test class with common fixtures for CLI tests."""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture(autouse=True)
    def mock_initialization(self):
        """Mock initialization to prevent file system operations."""
        with patch("docvault.core.initialization.ensure_app_initialized"):
            with patch("docvault.utils.logging.setup_logging"):
                yield
