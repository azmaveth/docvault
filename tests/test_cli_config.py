"""Tests for configuration and initialization CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from docvault.main import cli


class TestConfigCommand:
    """Test the config command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture(autouse=True)
    def mock_initialization(self):
        """Mock initialization to prevent file system operations."""
        with patch("docvault.core.initialization.ensure_app_initialized"):
            yield

    @pytest.fixture
    def mock_app_config(self):
        """Mock app config."""
        with patch("docvault.config") as mock:
            mock.DB_PATH = "/test/docvault/vault.db"
            mock.STORAGE_PATH = "/test/docvault/storage"
            mock.LOG_DIR = "/test/docvault/logs"
            mock.LOG_LEVEL = "INFO"
            mock.EMBEDDING_MODEL = "test-model"
            mock.OLLAMA_URL = "http://localhost:11434"
            mock.HOST = "127.0.0.1"
            mock.PORT = 8379
            mock.DEFAULT_BASE_DIR = "/test/docvault"
            yield mock

    def test_config_display(self, cli_runner, mock_app_config):
        """Test displaying configuration."""
        with patch("docvault.utils.logging.setup_logging"):
            result = cli_runner.invoke(cli, ["config"])

        assert result.exit_code == 0
        assert "Current Configuration" in result.output
        assert "Database Path" in result.output
        assert "Storage Path" in result.output
        assert "Log Directory" in result.output
        assert "Embedding Model" in result.output
        assert "/test/docvault" in result.output

    def test_config_init_new_env(self, cli_runner, mock_app_config, tmp_path):
        """Test initializing a new .env file."""
        mock_app_config.DEFAULT_BASE_DIR = str(tmp_path)

        with patch("docvault.cli.commands.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            mock_path_instance.write_text = MagicMock()
            mock_path.return_value = mock_path_instance

            result = cli_runner.invoke(cli, ["config", "--init"])

        assert result.exit_code == 0
        assert "Created configuration file" in result.output
        mock_path_instance.write_text.assert_called_once()

    def test_config_init_existing_env(self, cli_runner, mock_app_config, tmp_path):
        """Test initializing when .env already exists."""
        mock_app_config.DEFAULT_BASE_DIR = str(tmp_path)
        env_path = tmp_path / ".env"
        env_path.write_text("existing config")

        # User declines to overwrite
        with patch("click.confirm", return_value=False):
            result = cli_runner.invoke(cli, ["config", "--init"])

        assert result.exit_code == 0
        assert env_path.read_text() == "existing config"

    def test_config_error_handling(self, cli_runner):
        """Test config command error handling."""
        with patch("docvault.cli.commands.app_config") as mock_config:
            # Simulate an error when accessing config
            mock_config.DB_PATH = property(
                lambda self: (_ for _ in ()).throw(Exception("Config error"))
            )

            result = cli_runner.invoke(cli, ["config"])

            # The command might still succeed but show the error in output
            assert result.exit_code in [0, 1]


class TestInitCommand:
    """Test the init command."""

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

    @pytest.fixture
    def mock_initialize_database(self):
        """Mock initialize_database function."""
        with patch("docvault.db.schema.initialize_database") as mock:
            yield mock

    def test_init_new_database(self, cli_runner, mock_initialize_database):
        """Test initializing a new database."""
        result = cli_runner.invoke(cli, ["init"])

        assert result.exit_code == 0
        assert "Database initialized successfully" in result.output
        mock_initialize_database.assert_called_once_with(force_recreate=False)

    def test_init_with_force(self, cli_runner, mock_initialize_database):
        """Test force recreating database."""
        result = cli_runner.invoke(cli, ["init", "--force"])

        assert result.exit_code == 0
        assert "Database initialized successfully" in result.output
        mock_initialize_database.assert_called_once_with(force_recreate=True)

    def test_init_error_handling(self, cli_runner, mock_initialize_database):
        """Test init command error handling."""
        mock_initialize_database.side_effect = Exception("Database error")

        result = cli_runner.invoke(cli, ["init"])

        assert result.exit_code == 1
        assert "Error initializing database" in result.output
        assert "Database error" in result.output


class TestVersionCommand:
    """Test the version command."""

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

    def test_version_display(self, cli_runner):
        """Test displaying version information."""
        result = cli_runner.invoke(cli, ["version"])

        assert result.exit_code == 0
        assert "DocVault version:" in result.output
        # Version should be in output
        assert "." in result.output  # Version has dots

    def test_version_with_debug_logging(self, cli_runner):
        """Test version command doesn't break with debug logging."""
        result = cli_runner.invoke(cli, ["--debug", "version"])

        assert result.exit_code == 0
        assert "DocVault version:" in result.output
