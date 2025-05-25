"""Tests for the serve CLI command."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from docvault.main import cli


class TestServeCommand:
    """Test the serve command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_project_manager(self):
        """Mock ProjectManager."""
        with patch("docvault.cli.commands.ProjectManager") as mock:
            yield mock

    @pytest.fixture
    def mock_server(self):
        """Mock MCP server."""
        with patch("docvault.cli.commands.DocVaultMCPServer") as mock:
            yield mock

    def test_serve_stdio_mode(self, cli_runner, mock_project_manager, mock_server):
        """Test serving in stdio mode."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_server_instance = MagicMock()
        mock_server_instance.run_stdio = AsyncMock()
        mock_server.return_value = mock_server_instance

        # Mock asyncio.run to prevent actual async execution
        with patch("asyncio.run") as mock_run:
            result = cli_runner.invoke(cli, ["serve"])

            assert result.exit_code == 0
            mock_server.assert_called_once_with(mock_pm)
            mock_run.assert_called_once()
            # Check that run_stdio was set up to be called
            coro = mock_run.call_args[0][0]
            assert hasattr(coro, "__name__") or hasattr(coro, "__qualname__")

    def test_serve_sse_mode(self, cli_runner, mock_project_manager, mock_server):
        """Test serving in SSE mode."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_server_instance = MagicMock()
        mock_server_instance.run_sse = AsyncMock()
        mock_server.return_value = mock_server_instance

        with patch("asyncio.run") as mock_run:
            result = cli_runner.invoke(cli, ["serve", "--transport", "sse"])

            assert result.exit_code == 0
            mock_server.assert_called_once_with(mock_pm)
            mock_run.assert_called_once()

    def test_serve_custom_host_port(
        self, cli_runner, mock_project_manager, mock_server
    ):
        """Test serving with custom host and port."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_server_instance = MagicMock()
        mock_server_instance.run_sse = AsyncMock()
        mock_server.return_value = mock_server_instance

        with patch("asyncio.run") as mock_run:
            result = cli_runner.invoke(
                cli,
                ["serve", "--transport", "sse", "--host", "0.0.0.0", "--port", "8080"],
            )

            assert result.exit_code == 0
            # Verify the server was created
            mock_server.assert_called_once_with(mock_pm)
            # Verify asyncio.run was called
            mock_run.assert_called_once()

            # Get the coroutine that was passed to asyncio.run
            _coro = mock_run.call_args[0][0]
            # The host/port would be passed to run_sse in the actual coroutine

    def test_serve_invalid_transport(self, cli_runner):
        """Test serving with invalid transport."""
        result = cli_runner.invoke(cli, ["serve", "--transport", "invalid"])

        assert result.exit_code == 2
        assert "Invalid value for '--transport'" in result.output

    def test_serve_keyboard_interrupt(
        self, cli_runner, mock_project_manager, mock_server
    ):
        """Test handling keyboard interrupt."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_server_instance = MagicMock()
        mock_server_instance.run_stdio = AsyncMock()
        mock_server.return_value = mock_server_instance

        with patch("asyncio.run") as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            result = cli_runner.invoke(cli, ["serve"])

            assert result.exit_code == 0
            assert "Server stopped by user" in result.output

    def test_serve_error_handling(self, cli_runner, mock_project_manager, mock_server):
        """Test serve command error handling."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_server.side_effect = Exception("Server error")

        result = cli_runner.invoke(cli, ["serve"])

        assert result.exit_code == 1
        assert "Failed to start server" in result.output
        assert "Server error" in result.output

    def test_serve_with_debug_logging(
        self, cli_runner, mock_project_manager, mock_server
    ):
        """Test serving with debug logging enabled."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_server_instance = MagicMock()
        mock_server_instance.run_stdio = AsyncMock()
        mock_server.return_value = mock_server_instance

        with patch("asyncio.run"):
            result = cli_runner.invoke(cli, ["--debug", "serve"])

            assert result.exit_code == 0
            mock_server.assert_called_once()

    def test_serve_stdio_info_message(
        self, cli_runner, mock_project_manager, mock_server
    ):
        """Test stdio mode shows correct info message."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_server_instance = MagicMock()
        mock_server_instance.run_stdio = AsyncMock()
        mock_server.return_value = mock_server_instance

        with patch("asyncio.run"):
            result = cli_runner.invoke(cli, ["serve", "--transport", "stdio"])

            assert result.exit_code == 0
            assert "Starting MCP server in stdio mode" in result.output

    def test_serve_sse_info_message(
        self, cli_runner, mock_project_manager, mock_server
    ):
        """Test SSE mode shows correct info message."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_server_instance = MagicMock()
        mock_server_instance.run_sse = AsyncMock()
        mock_server.return_value = mock_server_instance

        with patch("asyncio.run"):
            result = cli_runner.invoke(
                cli,
                [
                    "serve",
                    "--transport",
                    "sse",
                    "--host",
                    "localhost",
                    "--port",
                    "5000",
                ],
            )

            assert result.exit_code == 0
            assert "Starting MCP server in SSE mode on localhost:5000" in result.output
