"""Tests for registry CLI commands."""

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest
from click.testing import CliRunner

from docvault.main import cli


class TestRegistryCommands:
    """Test registry-related commands."""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_project_manager(self):
        """Mock ProjectManager."""
        with patch("docvault.cli.registry_commands.ProjectManager") as mock:
            yield mock

    @pytest.fixture
    def mock_registry_manager(self):
        """Mock RegistryManager."""
        with patch("docvault.cli.registry_commands.RegistryManager") as mock:
            yield mock

    @pytest.fixture
    def sample_sources(self):
        """Sample documentation sources."""
        return [
            {
                "id": 1,
                "name": "react",
                "package_manager": "npm",
                "description": "React documentation",
                "homepage": "https://react.dev",
                "documentation_url": "https://react.dev/reference/react",
                "repository_url": "https://github.com/facebook/react",
            },
            {
                "id": 2,
                "name": "django",
                "package_manager": "pypi",
                "description": "Django web framework",
                "homepage": "https://www.djangoproject.com",
                "documentation_url": "https://docs.djangoproject.com",
                "repository_url": "https://github.com/django/django",
            },
        ]

    def test_registry_list_all(
        self, cli_runner, mock_project_manager, mock_registry_manager, sample_sources
    ):
        """Test listing all registry entries."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        mock_rm.list_sources = MagicMock(return_value=sample_sources)
        mock_registry_manager.return_value = mock_rm

        result = cli_runner.invoke(cli, ["registry", "list"])

        assert result.exit_code == 0
        assert "Documentation Registry" in result.output
        assert "react" in result.output
        assert "django" in result.output
        assert "npm" in result.output
        assert "pypi" in result.output

    def test_registry_list_filter(
        self, cli_runner, mock_project_manager, mock_registry_manager, sample_sources
    ):
        """Test listing with filter."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        # Return only matching source
        mock_rm.list_sources = MagicMock(return_value=[sample_sources[0]])
        mock_registry_manager.return_value = mock_rm

        result = cli_runner.invoke(cli, ["registry", "list", "--filter", "react"])

        assert result.exit_code == 0
        assert "react" in result.output
        assert "django" not in result.output
        mock_rm.list_sources.assert_called_once_with(filter_text="react")

    def test_registry_list_package_manager(
        self, cli_runner, mock_project_manager, mock_registry_manager, sample_sources
    ):
        """Test listing by package manager."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        # Return only pypi packages
        mock_rm.list_sources = MagicMock(return_value=[sample_sources[1]])
        mock_registry_manager.return_value = mock_rm

        result = cli_runner.invoke(
            cli, ["registry", "list", "--package-manager", "pypi"]
        )

        assert result.exit_code == 0
        assert "django" in result.output
        assert "react" not in result.output
        mock_rm.list_sources.assert_called_once_with(package_manager="pypi")

    def test_registry_list_empty(
        self, cli_runner, mock_project_manager, mock_registry_manager
    ):
        """Test listing when registry is empty."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        mock_rm.list_sources = MagicMock(return_value=[])
        mock_registry_manager.return_value = mock_rm

        result = cli_runner.invoke(cli, ["registry", "list"])

        assert result.exit_code == 0
        assert "No documentation sources found" in result.output

    def test_registry_add_success(
        self, cli_runner, mock_project_manager, mock_registry_manager
    ):
        """Test adding a new registry entry."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        mock_rm.add_source = MagicMock(return_value=True)
        mock_registry_manager.return_value = mock_rm

        result = cli_runner.invoke(
            cli,
            [
                "registry",
                "add",
                "vue",
                "npm",
                "--description",
                "Vue.js framework",
                "--homepage",
                "https://vuejs.org",
                "--docs",
                "https://vuejs.org/guide",
                "--repo",
                "https://github.com/vuejs/core",
            ],
        )

        assert result.exit_code == 0
        assert "Successfully added 'vue' to registry" in result.output

        # Verify add_source was called with correct arguments
        mock_rm.add_source.assert_called_once_with(
            name="vue",
            package_manager="npm",
            description="Vue.js framework",
            homepage="https://vuejs.org",
            documentation_url="https://vuejs.org/guide",
            repository_url="https://github.com/vuejs/core",
        )

    def test_registry_add_duplicate(
        self, cli_runner, mock_project_manager, mock_registry_manager
    ):
        """Test adding duplicate registry entry."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        mock_rm.add_source = MagicMock(side_effect=ValueError("Source already exists"))
        mock_registry_manager.return_value = mock_rm

        result = cli_runner.invoke(cli, ["registry", "add", "react", "npm"])

        assert result.exit_code == 1
        assert "Error" in result.output
        assert "Source already exists" in result.output

    def test_registry_remove_success(
        self, cli_runner, mock_project_manager, mock_registry_manager
    ):
        """Test removing a registry entry."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        mock_rm.remove_source = MagicMock(return_value=True)
        mock_registry_manager.return_value = mock_rm

        result = cli_runner.invoke(cli, ["registry", "remove", "react"])

        assert result.exit_code == 0
        assert "Successfully removed 'react' from registry" in result.output

    def test_registry_remove_not_found(
        self, cli_runner, mock_project_manager, mock_registry_manager
    ):
        """Test removing non-existent entry."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        mock_rm.remove_source = MagicMock(return_value=False)
        mock_registry_manager.return_value = mock_rm

        result = cli_runner.invoke(cli, ["registry", "remove", "nonexistent"])

        assert result.exit_code == 1
        assert "Source 'nonexistent' not found in registry" in result.output

    def test_registry_update_success(
        self, cli_runner, mock_project_manager, mock_registry_manager
    ):
        """Test updating a registry entry."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        mock_rm.update_source = MagicMock(return_value=True)
        mock_registry_manager.return_value = mock_rm

        result = cli_runner.invoke(
            cli,
            [
                "registry",
                "update",
                "react",
                "--description",
                "Updated React description",
                "--docs",
                "https://react.dev/updated",
            ],
        )

        assert result.exit_code == 0
        assert "Successfully updated 'react' in registry" in result.output

        # Verify update_source was called
        mock_rm.update_source.assert_called_once()
        call_args = mock_rm.update_source.call_args[1]
        assert call_args["description"] == "Updated React description"
        assert call_args["documentation_url"] == "https://react.dev/updated"

    def test_registry_update_not_found(
        self, cli_runner, mock_project_manager, mock_registry_manager
    ):
        """Test updating non-existent entry."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        mock_rm.update_source = MagicMock(return_value=False)
        mock_registry_manager.return_value = mock_rm

        result = cli_runner.invoke(
            cli, ["registry", "update", "nonexistent", "--description", "New desc"]
        )

        assert result.exit_code == 1
        assert "Source 'nonexistent' not found in registry" in result.output

    def test_registry_export_json(
        self, cli_runner, mock_project_manager, mock_registry_manager, sample_sources
    ):
        """Test exporting registry to JSON."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        mock_rm.export_registry = MagicMock(return_value=sample_sources)
        mock_registry_manager.return_value = mock_rm

        with patch("builtins.open", mock_open()) as mock_file:
            result = cli_runner.invoke(cli, ["registry", "export", "registry.json"])

            assert result.exit_code == 0
            assert "Successfully exported registry to registry.json" in result.output

            # Verify JSON was written
            mock_file.assert_called_once_with("registry.json", "w")
            written_data = ""
            for call in mock_file().write.call_args_list:
                written_data += call[0][0]

            parsed_data = json.loads(written_data)
            assert len(parsed_data) == 2
            assert parsed_data[0]["name"] == "react"

    def test_registry_export_csv(
        self, cli_runner, mock_project_manager, mock_registry_manager, sample_sources
    ):
        """Test exporting registry to CSV."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        mock_rm.export_registry = MagicMock(return_value=sample_sources)
        mock_registry_manager.return_value = mock_rm

        with patch("builtins.open", mock_open()) as mock_file:
            result = cli_runner.invoke(cli, ["registry", "export", "registry.csv"])

            assert result.exit_code == 0
            assert "Successfully exported registry to registry.csv" in result.output

            # Verify CSV header was written
            write_calls = mock_file().write.call_args_list
            assert any("name,package_manager" in str(call) for call in write_calls)

    def test_registry_import_json(
        self, cli_runner, mock_project_manager, mock_registry_manager, sample_sources
    ):
        """Test importing registry from JSON."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_rm = MagicMock()
        mock_rm.import_registry = MagicMock(return_value=(2, 0))
        mock_registry_manager.return_value = mock_rm

        json_data = json.dumps(sample_sources)
        with patch("builtins.open", mock_open(read_data=json_data)):
            with patch("pathlib.Path.exists", return_value=True):
                result = cli_runner.invoke(cli, ["registry", "import", "registry.json"])

                assert result.exit_code == 0
                assert "Successfully imported 2 sources" in result.output

    def test_registry_import_file_not_found(self, cli_runner, mock_project_manager):
        """Test importing from non-existent file."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        with patch("pathlib.Path.exists", return_value=False):
            result = cli_runner.invoke(cli, ["registry", "import", "nonexistent.json"])

            assert result.exit_code == 1
            assert "File not found: nonexistent.json" in result.output

    def test_registry_error_handling(self, cli_runner, mock_project_manager):
        """Test registry command error handling."""
        mock_project_manager.side_effect = Exception("Registry error")

        result = cli_runner.invoke(cli, ["registry", "list"])

        assert result.exit_code == 1
        assert "Error" in result.output
        assert "Registry error" in result.output
