"""Improved tests for configuration and initialization commands."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from docvault.main import cli


class TestConfigInitCommands:
    """Test configuration and initialization commands."""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture(autouse=True)
    def setup_test_env(self, mock_app_initialization):
        """Set up test environment."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Mock the default base directory
        with patch("docvault.config.DEFAULT_BASE_DIR", self.temp_dir):
            yield

        # Cleanup
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_config_display(self, cli_runner):
        """Test displaying configuration."""
        result = cli_runner.invoke(cli, ["config"])

        assert result.exit_code == 0
        assert "Current Configuration" in result.output
        assert "Database Path" in result.output
        assert "Storage Path" in result.output

    def test_config_init_new(self, cli_runner):
        """Test initializing new configuration."""
        env_path = self.temp_path / ".env"

        # Ensure .env doesn't exist
        env_path.unlink(missing_ok=True)

        result = cli_runner.invoke(cli, ["config", "--init"])

        assert result.exit_code == 0
        assert "Created configuration file" in result.output
        assert env_path.exists()

        # Check content
        content = env_path.read_text()
        assert "DOCVAULT_DB_PATH" in content
        assert "OLLAMA_URL" in content

    def test_config_init_existing_confirm(self, cli_runner):
        """Test initializing when config exists and user confirms."""
        env_path = self.temp_path / ".env"
        env_path.write_text("# Existing config")

        # Mock user confirmation
        with patch("click.confirm", return_value=True):
            result = cli_runner.invoke(cli, ["config", "--init"])

        assert result.exit_code == 0
        assert "Created configuration file" in result.output

        # Check that file was overwritten
        content = env_path.read_text()
        assert "DOCVAULT_DB_PATH" in content

    def test_config_init_existing_abort(self, cli_runner):
        """Test initializing when config exists and user aborts."""
        env_path = self.temp_path / ".env"
        original_content = "# Existing config"
        env_path.write_text(original_content)

        # Mock user declining
        with patch("click.confirm", return_value=False):
            result = cli_runner.invoke(cli, ["config", "--init"])

        assert result.exit_code == 0
        # File should not be changed
        assert env_path.read_text() == original_content

    def test_init_database(self, cli_runner):
        """Test database initialization."""
        db_path = self.temp_path / ".docvault" / "docvault.db"

        # Ensure database doesn't exist
        db_path.unlink(missing_ok=True)

        result = cli_runner.invoke(cli, ["init"])

        assert result.exit_code == 0
        assert "Database initialized successfully" in result.output

    def test_init_database_force(self, cli_runner):
        """Test force database initialization."""
        db_path = self.temp_path / ".docvault" / "docvault.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a dummy file to simulate existing database
        db_path.write_text("dummy")

        result = cli_runner.invoke(cli, ["init", "--force"])

        assert result.exit_code == 0
        assert "Database initialized successfully" in result.output

    def test_version_command(self, cli_runner):
        """Test version display."""
        result = cli_runner.invoke(cli, ["version"])

        assert result.exit_code == 0
        assert "DocVault version" in result.output
        # Version should contain dots (e.g., 0.3.2)
        assert "." in result.output
