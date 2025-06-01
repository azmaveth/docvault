"""Improved tests for document management CLI commands."""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from docvault.main import cli
from tests.utils import mock_app_initialization, temp_project


class TestDocumentCommands:
    """Test document management commands with minimal mocking."""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture(autouse=True)
    def setup_test_env(self, mock_app_initialization, temp_project):
        """Set up test environment."""
        self.project = temp_project

        # Mock ProjectManager to use our test project
        with patch("docvault.project.ProjectManager") as mock_pm:
            mock_pm.return_value = self.project
            yield

    @pytest.fixture
    def mock_documents(self):
        """Sample documents for testing."""
        return [
            {
                "id": 1,
                "title": "Test Document 1",
                "url": "https://example.com/doc1",
                "version": "latest",
                "scraped_at": "2024-05-24 10:00:00",
                "is_library_doc": False,
            },
            {
                "id": 2,
                "title": "Test Document 2",
                "url": "https://example.com/doc2",
                "version": "latest",
                "scraped_at": "2024-05-24 11:00:00",
                "is_library_doc": False,
            },
            {
                "id": 3,
                "title": "Test Document 3",
                "url": "https://example.com/doc3",
                "version": "latest",
                "scraped_at": "2024-05-24 12:00:00",
                "is_library_doc": False,
            },
        ]

    def test_list_documents(self, cli_runner, mock_documents):
        """Test listing all documents."""
        with (
            patch("docvault.db.operations.list_documents", return_value=mock_documents),
            patch(
                "docvault.models.tags.get_document_tags", return_value=[]
            ),  # Mock tags as empty
        ):
            result = cli_runner.invoke(cli, ["list"])

            assert result.exit_code == 0
            # Check that our test documents appear (they may be truncated in the table)
            assert "Test" in result.output
            assert "Docume" in result.output
            # Check the table structure is present
            assert "ID" in result.output
            assert "Title" in result.output
            assert "URL" in result.output

    def test_list_with_filter(self, cli_runner, mock_documents):
        """Test listing with filter."""
        with (
            patch(
                "docvault.db.operations.list_documents",
                return_value=mock_documents[1:2],
            ),
            patch(
                "docvault.models.tags.get_document_tags", return_value=[]
            ),  # Mock tags as empty
        ):
            result = cli_runner.invoke(cli, ["list", "--filter", "Document 2"])

            assert result.exit_code == 0
            # Check that document 2 appears (may be truncated)
            assert "2" in result.output and "Test" in result.output
            # Check that only one document is in the table (ID 2)
            assert "│ 2  │" in result.output  # ID column for doc 2
            assert "│ 1  │" not in result.output  # ID column for doc 1

    def test_list_with_limit(self, cli_runner, mock_documents):
        """Test listing with simulated limit (via mock)."""
        # The list command doesn't have a --limit flag, so we simulate it by returning fewer documents
        with (
            patch(
                "docvault.db.operations.list_documents", return_value=mock_documents[:2]
            ),
            patch(
                "docvault.models.tags.get_document_tags", return_value=[]
            ),  # Mock tags as empty
        ):
            result = cli_runner.invoke(cli, ["list"])

            assert result.exit_code == 0
            # Should only show first 2 documents (simulated limit)
            assert "│ 1" in result.output  # ID 1 in table
            assert "│ 2" in result.output  # ID 2 in table
            assert "│ 3" not in result.output  # ID 3 should not appear

    def test_read_document(self, cli_runner):
        """Test reading a document."""
        # This test uses mocks to be consistent with other tests in this class
        # For real database tests, see test_cli.py::test_read_command
        from unittest.mock import mock_open

        mock_doc = {
            "id": 1,
            "title": "Test Document",
            "url": "https://example.com/doc1",
            "html_path": "/tmp/test.html",
            "markdown_path": "/tmp/test.md",
            "version": "1.0",
            "scraped_at": "2024-01-01 00:00:00",
        }

        mock_content = "# Test Document\n\nThis is the content."

        with (
            patch("docvault.db.operations.get_document", return_value=mock_doc),
            patch("builtins.open", mock_open(read_data=mock_content)),
            patch("pathlib.Path.exists", return_value=True),
            patch("docvault.core.caching.get_cache_manager") as mock_cache_manager,
            patch(
                "docvault.db.operations_llms.get_llms_txt_metadata", return_value=None
            ),
            patch("docvault.models.tags.get_document_tags", return_value=[]),
            patch(
                "docvault.models.collections.get_document_collections", return_value=[]
            ),
        ):
            mock_cache_instance = Mock()
            mock_cache_instance.update_staleness_status.return_value = "FRESH"
            mock_cache_manager.return_value = mock_cache_instance

            result = cli_runner.invoke(cli, ["read", "1"])

            assert result.exit_code == 0
            assert "Test Document" in result.output
            assert "This is the content" in result.output

    def test_read_nonexistent_document(self, cli_runner):
        """Test reading non-existent document."""
        with patch("docvault.db.operations.get_document", return_value=None):
            result = cli_runner.invoke(cli, ["read", "999"])

            assert result.exit_code == 0
            assert "Document not found: 999" in result.output

    def test_remove_document(self, cli_runner):
        """Test removing a document."""
        # Mock the confirmation, document lookup, and database operations
        mock_doc = {
            "id": 1,
            "title": "Test Document",
            "url": "https://example.com",
            "html_path": None,
            "markdown_path": None,
        }
        with (
            patch("click.confirm", return_value=True),
            patch("docvault.db.operations.get_document", return_value=mock_doc),
            patch("docvault.db.operations.delete_document", return_value=True),
        ):
            result = cli_runner.invoke(cli, ["remove", "1"])

            assert result.exit_code == 0
            assert "Deleted 1 document(s)" in result.output

    def test_remove_with_force(self, cli_runner):
        """Test removing with --force flag."""
        mock_doc = {
            "id": 1,
            "title": "Test Document",
            "url": "https://example.com",
            "html_path": None,
            "markdown_path": None,
        }
        with (
            patch("docvault.db.operations.get_document", return_value=mock_doc),
            patch("docvault.db.operations.delete_document", return_value=True),
        ):
            result = cli_runner.invoke(cli, ["remove", "1", "--force"])

            assert result.exit_code == 0
            # Should not ask for confirmation
            assert "Deleted 1 document(s)" in result.output

    def test_remove_multiple_documents(self, cli_runner):
        """Test removing multiple documents."""
        doc_ids = "1,2"

        mock_doc = {
            "id": 1,
            "title": "Test Document",
            "url": "https://example.com",
            "html_path": None,
            "markdown_path": None,
        }

        with (
            patch("docvault.db.operations.get_document", return_value=mock_doc),
            patch("docvault.db.operations.delete_document", return_value=True),
        ):
            result = cli_runner.invoke(cli, ["remove", doc_ids, "--force"])

            assert result.exit_code == 0
            assert "2" in result.output or "multiple" in result.output.lower()

    def test_remove_range(self, cli_runner):
        """Test removing a range of documents."""
        mock_doc = {
            "id": 1,
            "title": "Test Document",
            "url": "https://example.com",
            "html_path": None,
            "markdown_path": None,
        }

        with (
            patch("docvault.db.operations.get_document", return_value=mock_doc),
            patch("docvault.db.operations.delete_document", return_value=True),
        ):
            result = cli_runner.invoke(cli, ["remove", "1-3", "--force"])

            assert result.exit_code == 0
            # Should indicate multiple documents were removed
            assert "3" in result.output or "multiple" in result.output.lower()

    def test_remove_abort(self, cli_runner):
        """Test aborting document removal."""
        mock_doc = {
            "id": 1,
            "title": "Test Document",
            "url": "https://example.com",
            "html_path": None,
            "markdown_path": None,
        }
        with (
            patch("docvault.db.operations.get_document", return_value=mock_doc),
            patch("click.confirm", return_value=False),
        ):
            result = cli_runner.invoke(cli, ["remove", "1"])

            assert result.exit_code == 0
            # Should indicate operation was cancelled
            assert "Deletion cancelled" in result.output
