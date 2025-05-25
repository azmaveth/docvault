"""Integration tests for CLI workflows."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from docvault.db import operations
from docvault.main import cli


class TestCLIIntegration:
    """Integration tests for complete CLI workflows."""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def temp_project_dir(self, tmp_path):
        """Create a temporary project directory."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        docvault_dir = project_dir / ".docvault"
        docvault_dir.mkdir()
        return project_dir

    @pytest.fixture
    def mock_scraper(self):
        """Mock scraper for consistent test results."""
        with patch("docvault.cli.commands.DocumentScraper") as mock:
            scraper_instance = MagicMock()
            scraper_instance.scrape_url = AsyncMock(
                return_value=(
                    1,  # doc_id
                    "Test Document",
                    "https://example.com",
                    [
                        {
                            "type": "text",
                            "content": "Test content",
                            "section_title": "Introduction",
                        },
                        {
                            "type": "code",
                            "content": "print('hello')",
                            "section_title": "Examples",
                        },
                    ],
                )
            )
            mock.return_value = scraper_instance
            yield scraper_instance

    @pytest.fixture
    def mock_embeddings(self):
        """Mock embedding generation."""
        with patch("docvault.cli.commands.generate_embeddings") as mock:
            mock.return_value = [0.1, 0.2, 0.3] * 128  # 384-dim vector
            yield mock

    def test_workflow_add_search_read(
        self, cli_runner, temp_project_dir, mock_scraper, mock_embeddings
    ):
        """Test complete workflow: add document, search, and read."""
        with patch("docvault.cli.commands.ProjectManager") as mock_pm_class:
            # Setup mock project manager
            mock_pm = MagicMock()
            mock_pm.docvault_dir = temp_project_dir / ".docvault"
            mock_pm.db_path = mock_pm.docvault_dir / "vault.db"
            mock_pm_class.return_value = mock_pm

            # Initialize database
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
                mock_pm.db_path = Path(tmp_db.name)
                operations.init_db(str(mock_pm.db_path))

                # Step 1: Add a document
                result = cli_runner.invoke(cli, ["add", "https://example.com"])
                assert result.exit_code == 0
                assert "Successfully added document" in result.output

                # Step 2: Index the document
                result = cli_runner.invoke(cli, ["index"])
                assert result.exit_code == 0

                # Step 3: Search for content
                with patch(
                    "docvault.cli.commands.operations.search_documents"
                ) as mock_search:
                    mock_search.return_value = [
                        {
                            "document_id": 1,
                            "segment_id": 1,
                            "title": "Test Document",
                            "content": "Test content",
                            "score": 0.95,
                        }
                    ]

                    result = cli_runner.invoke(cli, ["search", "test"])
                    assert result.exit_code == 0
                    assert "Test Document" in result.output
                    assert "Test content" in result.output

                # Step 4: Read the document
                with patch(
                    "docvault.cli.commands.operations.get_document_by_id"
                ) as mock_get_doc:
                    mock_get_doc.return_value = {
                        "id": 1,
                        "title": "Test Document",
                        "url": "https://example.com",
                        "content": "# Test Document\n\nTest content",
                    }

                    result = cli_runner.invoke(cli, ["read", "1"])
                    assert result.exit_code == 0
                    assert "Test Document" in result.output

                # Cleanup
                Path(tmp_db.name).unlink()

    def test_workflow_import_deps_and_search(self, cli_runner, temp_project_dir):
        """Test workflow: import dependencies and search for library docs."""
        with patch("docvault.cli.commands.ProjectManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm.docvault_dir = temp_project_dir / ".docvault"
            mock_pm_class.return_value = mock_pm

            # Create a package.json file
            package_json = temp_project_dir / "package.json"
            package_json.write_text(
                json.dumps({"dependencies": {"react": "^18.0.0", "axios": "^1.0.0"}})
            )

            # Step 1: Import dependencies
            with patch("docvault.cli.commands.LibraryManager") as mock_lm_class:
                mock_lm = MagicMock()
                mock_lm.add_documentation = MagicMock(return_value=True)
                mock_lm_class.return_value = mock_lm

                result = cli_runner.invoke(cli, ["import-deps", str(package_json)])
                assert result.exit_code == 0
                assert "Found 2 unique dependencies" in result.output

            # Step 2: Search for library documentation
            with patch(
                "docvault.cli.commands.operations.lookup_library_docs"
            ) as mock_lookup:
                mock_lookup.return_value = {
                    "name": "react",
                    "version": "18.0.0",
                    "documentation_url": "https://react.dev",
                    "description": "React library",
                }

                result = cli_runner.invoke(cli, ["search", "lib", "react"])
                assert result.exit_code == 0
                assert "react" in result.output

    def test_workflow_backup_and_restore(self, cli_runner, temp_project_dir):
        """Test workflow: create backup and restore."""
        with patch("docvault.cli.commands.ProjectManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm.docvault_dir = temp_project_dir / ".docvault"
            mock_pm.docvault_dir.exists.return_value = True
            mock_pm_class.return_value = mock_pm

            # Create some test data in docvault
            test_file = mock_pm.docvault_dir / "test.txt"
            test_file = temp_project_dir / ".docvault" / "test.txt"
            test_file.write_text("test data")

            # Step 1: Create backup
            backup_path = temp_project_dir / "backup.tar.gz"

            with patch("tarfile.open") as mock_tar:
                mock_tar_obj = MagicMock()
                mock_tar.__enter__.return_value = mock_tar_obj

                result = cli_runner.invoke(cli, ["backup", str(backup_path)])
                assert result.exit_code == 0
                assert "Backup created successfully" in result.output

            # Step 2: Simulate removing original data
            mock_pm.docvault_dir.exists.return_value = False

            # Step 3: Restore from backup
            with patch("tarfile.open") as mock_tar:
                mock_tar_obj = MagicMock()
                mock_tar.__enter__.return_value = mock_tar_obj

                with patch("pathlib.Path.exists", return_value=True):
                    result = cli_runner.invoke(cli, ["import-backup", str(backup_path)])
                    assert result.exit_code == 0
                    assert "Backup imported successfully" in result.output

    def test_workflow_registry_management(self, cli_runner, temp_project_dir):
        """Test workflow: manage documentation registry."""
        with patch("docvault.cli.registry_commands.ProjectManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm

            with patch(
                "docvault.cli.registry_commands.RegistryManager"
            ) as mock_rm_class:
                mock_rm = MagicMock()
                mock_rm_class.return_value = mock_rm

                # Step 1: Add sources to registry
                mock_rm.add_source = MagicMock(return_value=True)

                result = cli_runner.invoke(
                    cli,
                    [
                        "registry",
                        "add",
                        "vue",
                        "npm",
                        "--description",
                        "Vue.js framework",
                        "--docs",
                        "https://vuejs.org/guide",
                    ],
                )
                assert result.exit_code == 0

                # Step 2: List registry entries
                mock_rm.list_sources = MagicMock(
                    return_value=[
                        {
                            "id": 1,
                            "name": "vue",
                            "package_manager": "npm",
                            "description": "Vue.js framework",
                            "documentation_url": "https://vuejs.org/guide",
                        }
                    ]
                )

                result = cli_runner.invoke(cli, ["registry", "list"])
                assert result.exit_code == 0
                assert "vue" in result.output

                # Step 3: Export registry
                mock_rm.export_registry = MagicMock(return_value=mock_rm.list_sources())

                export_file = temp_project_dir / "registry.json"
                result = cli_runner.invoke(
                    cli, ["registry", "export", str(export_file)]
                )
                assert result.exit_code == 0

                # Step 4: Update registry entry
                mock_rm.update_source = MagicMock(return_value=True)

                result = cli_runner.invoke(
                    cli,
                    [
                        "registry",
                        "update",
                        "vue",
                        "--description",
                        "Vue.js 3 framework",
                    ],
                )
                assert result.exit_code == 0

    def test_workflow_config_and_init(self, cli_runner, temp_project_dir):
        """Test workflow: configure and initialize project."""
        with patch("docvault.cli.commands.ProjectManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm.docvault_dir = temp_project_dir / ".docvault"
            mock_pm.db_path = mock_pm.docvault_dir / "vault.db"
            mock_pm.config_file = mock_pm.docvault_dir / "config.json"
            mock_pm_class.return_value = mock_pm

            # Step 1: Initialize configuration
            mock_pm.config_file.exists.return_value = False
            mock_pm.save_config = MagicMock()

            result = cli_runner.invoke(cli, ["config", "--init"])
            assert result.exit_code == 0
            assert "Initialized new project configuration" in result.output

            # Step 2: Initialize database
            mock_pm.db_path.exists.return_value = False

            with patch("docvault.cli.commands.operations.init_db") as mock_init_db:
                result = cli_runner.invoke(cli, ["init"])
                assert result.exit_code == 0
                assert "Database initialized successfully" in result.output
                mock_init_db.assert_called_once()

            # Step 3: View configuration
            result = cli_runner.invoke(cli, ["config"])
            assert result.exit_code == 0
            assert "DocVault Configuration" in result.output

    def test_workflow_error_recovery(self, cli_runner, temp_project_dir):
        """Test workflow: error handling and recovery."""
        with patch("docvault.cli.commands.ProjectManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm.docvault_dir = temp_project_dir / ".docvault"
            mock_pm_class.return_value = mock_pm

            # Step 1: Try to add document with network error
            with patch("docvault.cli.commands.DocumentScraper") as mock_scraper_class:
                scraper = MagicMock()
                scraper.scrape_url = AsyncMock(side_effect=Exception("Network error"))
                mock_scraper_class.return_value = scraper

                result = cli_runner.invoke(cli, ["add", "https://example.com"])
                assert result.exit_code == 1
                assert "Error" in result.output

            # Step 2: List documents (should work despite previous error)
            with patch("docvault.cli.commands.operations.list_documents") as mock_list:
                mock_list.return_value = []

                result = cli_runner.invoke(cli, ["list"])
                assert result.exit_code == 0
                assert "No documents found" in result.output

            # Step 3: Try indexing with missing sqlite-vec
            with patch("docvault.cli.commands.operations.SQLITE_VEC_AVAILABLE", False):
                result = cli_runner.invoke(cli, ["index"])
                assert result.exit_code == 1
                assert "sqlite-vec extension is not available" in result.output
