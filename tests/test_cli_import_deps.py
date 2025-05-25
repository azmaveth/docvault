"""Tests for the import-deps CLI command."""

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest
from click.testing import CliRunner

from docvault.main import cli


class TestImportDepsCommand:
    """Test the import-deps command."""

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
    def mock_library_manager(self):
        """Mock LibraryManager."""
        with patch("docvault.core.library_manager.LibraryManager") as mock:
            yield mock

    @pytest.fixture
    def sample_package_json(self):
        """Sample package.json content."""
        return {
            "dependencies": {
                "react": "^18.2.0",
                "axios": "~1.4.0",
                "@mui/material": "5.14.0",
            },
            "devDependencies": {"typescript": "^5.0.0", "jest": "29.5.0"},
        }

    @pytest.fixture
    def sample_requirements_txt(self):
        """Sample requirements.txt content."""
        return """
# Main dependencies
django==4.2.0
requests>=2.28.0,<3.0.0
numpy~=1.24.0

# Dev dependencies
pytest==7.3.1
black>=23.0.0

# Comments should be ignored
"""

    @pytest.fixture
    def sample_pyproject_toml(self):
        """Sample pyproject.toml content."""
        return """
[project]
dependencies = [
    "fastapi>=0.100.0",
    "pydantic~=2.0",
    "uvicorn[standard]"
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "mypy==1.4.0"
]

[tool.poetry.dependencies]
python = "^3.11"
sqlalchemy = "^2.0.0"
"""

    def test_import_deps_package_json(
        self,
        cli_runner,
        mock_project_manager,
        mock_library_manager,
        sample_package_json,
    ):
        """Test importing from package.json."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_lm = MagicMock()
        mock_lm.add_documentation = MagicMock(return_value=True)
        mock_library_manager.return_value = mock_lm

        # Create a temp package.json file
        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_package_json))
        ):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.is_file", return_value=True):
                    result = cli_runner.invoke(cli, ["import-deps", "package.json"])

        assert result.exit_code == 0
        assert "Found 5 unique dependencies" in result.output
        assert "Successfully added documentation for 5 packages" in result.output

        # Verify all packages were processed
        expected_packages = ["react", "axios", "@mui/material", "typescript", "jest"]
        for package in expected_packages:
            assert any(
                package in str(call)
                for call in mock_lm.add_documentation.call_args_list
            )

    def test_import_deps_requirements_txt(
        self,
        cli_runner,
        mock_project_manager,
        mock_library_manager,
        sample_requirements_txt,
    ):
        """Test importing from requirements.txt."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_lm = MagicMock()
        mock_lm.add_documentation = MagicMock(return_value=True)
        mock_library_manager.return_value = mock_lm

        with patch("builtins.open", mock_open(read_data=sample_requirements_txt)):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.is_file", return_value=True):
                    result = cli_runner.invoke(cli, ["import-deps", "requirements.txt"])

        assert result.exit_code == 0
        assert "Found 5 unique dependencies" in result.output

        # Verify packages were processed
        expected_packages = ["django", "requests", "numpy", "pytest", "black"]
        for package in expected_packages:
            assert any(
                package in str(call)
                for call in mock_lm.add_documentation.call_args_list
            )

    def test_import_deps_pyproject_toml(
        self,
        cli_runner,
        mock_project_manager,
        mock_library_manager,
        sample_pyproject_toml,
    ):
        """Test importing from pyproject.toml."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_lm = MagicMock()
        mock_lm.add_documentation = MagicMock(return_value=True)
        mock_library_manager.return_value = mock_lm

        with patch("builtins.open", mock_open(read_data=sample_pyproject_toml)):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.is_file", return_value=True):
                    result = cli_runner.invoke(cli, ["import-deps", "pyproject.toml"])

        assert result.exit_code == 0
        # Should find dependencies from both [project] and [tool.poetry]
        assert "unique dependencies" in result.output

    def test_import_deps_include_dev(
        self,
        cli_runner,
        mock_project_manager,
        mock_library_manager,
        sample_package_json,
    ):
        """Test including dev dependencies."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_lm = MagicMock()
        mock_lm.add_documentation = MagicMock(return_value=True)
        mock_library_manager.return_value = mock_lm

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_package_json))
        ):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.is_file", return_value=True):
                    result = cli_runner.invoke(
                        cli, ["import-deps", "package.json", "--include-dev"]
                    )

        assert result.exit_code == 0
        # Dev dependencies should be included
        assert any(
            "typescript" in str(call)
            for call in mock_lm.add_documentation.call_args_list
        )

    def test_import_deps_production_only(
        self,
        cli_runner,
        mock_project_manager,
        mock_library_manager,
        sample_package_json,
    ):
        """Test production dependencies only."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_lm = MagicMock()
        mock_lm.add_documentation = MagicMock(return_value=True)
        mock_library_manager.return_value = mock_lm

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_package_json))
        ):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.is_file", return_value=True):
                    result = cli_runner.invoke(
                        cli, ["import-deps", "package.json", "--production"]
                    )

        assert result.exit_code == 0
        # Should only include production dependencies
        assert "Found 3 unique dependencies" in result.output

    def test_import_deps_file_not_found(self, cli_runner, mock_project_manager):
        """Test handling missing dependency file."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        with patch("pathlib.Path.exists", return_value=False):
            result = cli_runner.invoke(cli, ["import-deps", "nonexistent.json"])

        assert result.exit_code == 1
        assert "File not found: nonexistent.json" in result.output

    def test_import_deps_unsupported_format(self, cli_runner, mock_project_manager):
        """Test handling unsupported file format."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.is_file", return_value=True):
                result = cli_runner.invoke(cli, ["import-deps", "unknown.xyz"])

        assert result.exit_code == 1
        assert "Unsupported file type" in result.output

    def test_import_deps_parse_error(
        self, cli_runner, mock_project_manager, mock_library_manager
    ):
        """Test handling parse errors."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_lm = MagicMock()
        mock_library_manager.return_value = mock_lm

        with patch("builtins.open", mock_open(read_data="invalid json {")):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.is_file", return_value=True):
                    result = cli_runner.invoke(cli, ["import-deps", "package.json"])

        assert result.exit_code == 1
        assert "Failed to parse" in result.output

    def test_import_deps_add_documentation_failure(
        self,
        cli_runner,
        mock_project_manager,
        mock_library_manager,
        sample_package_json,
    ):
        """Test handling documentation addition failures."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_lm = MagicMock()
        # First call succeeds, rest fail
        mock_lm.add_documentation = MagicMock(
            side_effect=[True, False, False, False, False]
        )
        mock_library_manager.return_value = mock_lm

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_package_json))
        ):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.is_file", return_value=True):
                    result = cli_runner.invoke(cli, ["import-deps", "package.json"])

        assert result.exit_code == 0
        assert "Successfully added documentation for 1 packages" in result.output
        assert "Failed to add documentation for 4 packages" in result.output

    def test_import_deps_version_handling(
        self, cli_runner, mock_project_manager, mock_library_manager
    ):
        """Test proper version parsing."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        mock_lm = MagicMock()
        mock_lm.add_documentation = MagicMock(return_value=True)
        mock_library_manager.return_value = mock_lm

        deps = {
            "dependencies": {
                "package1": "^1.2.3",
                "package2": "~4.5.6",
                "package3": ">=7.8.9",
                "package4": "1.0.0 - 2.0.0",
                "package5": "latest",
            }
        }

        with patch("builtins.open", mock_open(read_data=json.dumps(deps))):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.is_file", return_value=True):
                    result = cli_runner.invoke(cli, ["import-deps", "package.json"])

        assert result.exit_code == 0

        # Check version parsing
        calls = mock_lm.add_documentation.call_args_list
        assert any("1.2.3" in str(call) for call in calls)
        assert any("4.5.6" in str(call) for call in calls)
        assert any("7.8.9" in str(call) for call in calls)
