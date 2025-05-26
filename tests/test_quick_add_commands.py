"""Test quick add commands for package managers."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from docvault.cli.quick_add_commands import (
    add_package_manager,
    create_quick_add_command,
    quick_add_package,
)


class TestQuickAddCommands:
    """Test quick add command functionality."""

    @pytest.fixture
    def mock_library_manager(self):
        """Mock library manager."""
        with patch("docvault.cli.quick_add_commands.LibraryManager") as mock:
            manager = mock.return_value
            manager.get_library_docs = AsyncMock()
            yield manager

    @pytest.fixture
    def mock_registry(self):
        """Mock registry functions."""
        with (
            patch(
                "docvault.cli.quick_add_commands.list_documentation_sources"
            ) as mock_sources,
            patch("docvault.cli.quick_add_commands.find_library") as mock_library,
            patch("docvault.cli.quick_add_commands.add_library_entry") as mock_add,
        ):

            # Mock documentation source
            source = MagicMock()
            source.id = 1
            source.name = "PyPI"
            source.package_manager = "pypi"
            mock_sources.return_value = [source]

            # Mock library lookup (not found by default)
            mock_library.return_value = None

            yield {
                "sources": mock_sources,
                "library": mock_library,
                "add": mock_add,
            }

    @pytest.mark.asyncio
    async def test_quick_add_package_success(self, mock_library_manager, mock_registry):
        """Test successful package addition."""
        # Mock successful documentation fetch
        mock_library_manager.get_library_docs.return_value = [
            {
                "id": 1,
                "title": "Requests Documentation",
                "url": "https://docs.python-requests.org/",
            }
        ]

        result = await quick_add_package("pypi", "requests")

        assert result is not None
        assert result["id"] == 1
        assert result["title"] == "Requests Documentation"

        # Verify library was added to registry
        mock_registry["add"].assert_called_once()

    @pytest.mark.asyncio
    async def test_quick_add_package_not_found(
        self, mock_library_manager, mock_registry
    ):
        """Test package not found."""
        # Mock library not found
        from docvault.core.exceptions import LibraryNotFoundError

        mock_library_manager.get_library_docs.side_effect = LibraryNotFoundError(
            "Not found"
        )

        result = await quick_add_package("pypi", "nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_quick_add_package_already_exists(
        self, mock_library_manager, mock_registry
    ):
        """Test package already exists without force."""
        # Mock library already exists
        mock_registry["library"].return_value = {"id": 1, "name": "requests"}

        # Mock successful documentation fetch
        mock_library_manager.get_library_docs.return_value = [
            {
                "id": 1,
                "title": "Requests Documentation",
                "url": "https://docs.python-requests.org/",
            }
        ]

        result = await quick_add_package("pypi", "requests", force=False)

        # Should return existing doc without adding to registry
        assert result is not None
        mock_registry["add"].assert_not_called()

    def test_add_pypi_command(self, mock_library_manager, mock_registry):
        """Test add-pypi command."""
        runner = CliRunner()

        # Create the command
        cmd = create_quick_add_command("pypi", "PyPI")

        # Mock successful documentation fetch
        mock_library_manager.get_library_docs.return_value = [
            {
                "id": 1,
                "title": "Requests Documentation",
                "url": "https://docs.python-requests.org/",
            }
        ]

        result = runner.invoke(cmd, ["requests"])

        assert result.exit_code == 0
        assert "Successfully added requests documentation from PyPI" in result.output
        assert "Document ID: 1" in result.output

    def test_add_npm_command_with_version(self, mock_library_manager, mock_registry):
        """Test add-npm command with version."""
        runner = CliRunner()

        # Update mock for npm
        source = MagicMock()
        source.id = 2
        source.name = "npm"
        source.package_manager = "npm"
        mock_registry["sources"].return_value = [source]

        # Create the command
        cmd = create_quick_add_command("npm", "npm")

        # Mock successful documentation fetch
        mock_library_manager.get_library_docs.return_value = [
            {
                "id": 2,
                "title": "Express Documentation",
                "url": "https://expressjs.com/",
            }
        ]

        result = runner.invoke(cmd, ["express", "--version", "4.18.0"])

        assert result.exit_code == 0
        assert "Successfully added express documentation from npm" in result.output

    def test_add_pm_command_success(self, mock_library_manager, mock_registry):
        """Test add-pm command with correct syntax."""
        runner = CliRunner()

        # Mock successful documentation fetch
        mock_library_manager.get_library_docs.return_value = [
            {
                "id": 1,
                "title": "Requests Documentation",
                "url": "https://docs.python-requests.org/",
            }
        ]

        result = runner.invoke(add_package_manager, ["pypi:requests"])

        assert result.exit_code == 0
        assert "Successfully added requests documentation from PyPI" in result.output

    def test_add_pm_command_invalid_syntax(self):
        """Test add-pm command with invalid syntax."""
        runner = CliRunner()

        result = runner.invoke(add_package_manager, ["requests"])

        assert result.exit_code == 0  # Click doesn't exit with error by default
        assert "Invalid format" in result.output
        assert "Use 'pm:package' syntax" in result.output

    def test_add_pm_command_unknown_pm(self):
        """Test add-pm command with unknown package manager."""
        runner = CliRunner()

        result = runner.invoke(add_package_manager, ["unknown:package"])

        assert result.exit_code == 0
        assert "Unknown package manager 'unknown'" in result.output

    def test_add_pm_command_json_output(self, mock_library_manager, mock_registry):
        """Test add-pm command with JSON output."""
        runner = CliRunner()

        # Mock successful documentation fetch
        mock_library_manager.get_library_docs.return_value = [
            {
                "id": 1,
                "title": "Requests Documentation",
                "url": "https://docs.python-requests.org/",
            }
        ]

        result = runner.invoke(
            add_package_manager, ["pypi:requests", "--format", "json"]
        )

        assert result.exit_code == 0

        # Parse JSON output
        output = json.loads(result.output)
        assert output["status"] == "success"
        assert output["package"] == "requests"
        assert output["package_manager"] == "PyPI"
        assert output["document"]["id"] == 1

    def test_add_command_force_refetch(self, mock_library_manager, mock_registry):
        """Test force refetch of existing package."""
        runner = CliRunner()

        # Mock library already exists
        mock_registry["library"].return_value = {"id": 1, "name": "requests"}

        # Create the command
        cmd = create_quick_add_command("pypi", "PyPI")

        # Mock successful documentation fetch
        mock_library_manager.get_library_docs.return_value = [
            {
                "id": 2,  # New ID
                "title": "Requests Documentation (Updated)",
                "url": "https://docs.python-requests.org/",
            }
        ]

        result = runner.invoke(cmd, ["requests", "--force"])

        assert result.exit_code == 0
        assert "Successfully added requests documentation" in result.output

        # Should add to registry even though it exists
        mock_registry["add"].assert_called_once()

    def test_registry_not_configured(self, mock_registry):
        """Test when package manager is not configured."""
        runner = CliRunner()

        # Mock no documentation source
        mock_registry["sources"].return_value = []

        # Create the command
        cmd = create_quick_add_command("pypi", "PyPI")

        result = runner.invoke(cmd, ["requests"])

        assert result.exit_code == 0
        assert "Package manager 'pypi' not configured" in result.output
        assert "Run 'dv registry populate'" in result.output
