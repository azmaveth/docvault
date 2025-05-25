"""Tests for document management CLI commands (list, read, remove)"""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from docvault.main import cli


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing"""
    return CliRunner()


@pytest.fixture
def mock_documents():
    """Mock document list"""
    return [
        {
            "id": 1,
            "url": "https://docs.python.org",
            "title": "Python Documentation",
            "version": "3.9",
            "scraped_at": "2024-05-24 10:00:00",
            "is_library_doc": True,
        },
        {
            "id": 2,
            "url": "https://example.com/tutorial",
            "title": "Example Tutorial",
            "version": "latest",
            "scraped_at": "2024-05-24 11:00:00",
            "is_library_doc": False,
        },
        {
            "id": 3,
            "url": "https://docs.pytest.org",
            "title": "pytest documentation",
            "version": "7.4.0",
            "scraped_at": "2024-05-24 12:00:00",
            "is_library_doc": True,
        },
    ]


class TestListCommand:
    """Test suite for list command"""

    def test_list_all_documents(self, cli_runner, mock_documents):
        """Test listing all documents"""
        with patch(
            "docvault.db.operations.list_documents", return_value=mock_documents
        ):
            result = cli_runner.invoke(cli, ["list"])

            assert result.exit_code == 0
            assert "Python Documentation" in result.output
            assert "Example Tutorial" in result.output
            assert "pytest documentation" in result.output
            assert "3" in result.output  # ID

    def test_list_with_filter(self, cli_runner, mock_documents):
        """Test listing with filter"""
        with patch(
            "docvault.db.operations.list_documents", return_value=mock_documents[:1]
        ):
            result = cli_runner.invoke(cli, ["list", "--filter", "python"])

            assert result.exit_code == 0
            assert "Python Documentation" in result.output
            assert "Example Tutorial" not in result.output

    def test_list_library_docs_only(self, cli_runner, mock_documents):
        """Test listing library documents only"""
        library_docs = [doc for doc in mock_documents if doc["is_library_doc"]]

        with patch("docvault.db.operations.list_documents", return_value=library_docs):
            result = cli_runner.invoke(cli, ["list", "--library"])

            assert result.exit_code == 0
            assert "Python Documentation" in result.output
            assert "pytest documentation" in result.output
            assert "Example Tutorial" not in result.output

    def test_list_with_limit(self, cli_runner, mock_documents):
        """Test listing with limit"""
        with patch(
            "docvault.db.operations.list_documents", return_value=mock_documents[:2]
        ):
            result = cli_runner.invoke(cli, ["list", "--limit", "2"])

            assert result.exit_code == 0
            # Should show only 2 documents
            assert result.output.count("https://") == 2

    def test_list_no_documents(self, cli_runner):
        """Test listing when no documents exist"""
        with patch("docvault.db.operations.list_documents", return_value=[]):
            result = cli_runner.invoke(cli, ["list"])

            assert result.exit_code == 0
            assert "No documents found" in result.output

    def test_list_error_handling(self, cli_runner):
        """Test list command error handling"""
        with patch(
            "docvault.db.operations.list_documents", side_effect=Exception("DB Error")
        ):
            result = cli_runner.invoke(cli, ["list"])

            assert result.exit_code != 0
            assert "Error" in result.output


class TestReadCommand:
    """Test suite for read command"""

    def test_read_markdown_default(self, cli_runner):
        """Test reading document in default markdown format"""
        mock_doc = {
            "id": 1,
            "title": "Test Document",
            "url": "https://example.com",
            "markdown_path": "/test/doc.md",
            "html_path": "/test/doc.html",
        }
        mock_content = "# Test Document\n\nThis is test content."

        with patch("docvault.db.operations.get_document", return_value=mock_doc):
            with patch(
                "docvault.core.storage.read_markdown", return_value=mock_content
            ):
                result = cli_runner.invoke(cli, ["read", "1"])

                assert result.exit_code == 0
                assert "Test Document" in result.output
                assert "This is test content" in result.output

    def test_read_raw_format(self, cli_runner):
        """Test reading document in raw format"""
        mock_doc = {
            "id": 1,
            "title": "Test",
            "url": "https://example.com",
            "markdown_path": "/test/doc.md",
        }
        mock_content = "# Raw Content"

        with patch("docvault.db.operations.get_document", return_value=mock_doc):
            with patch(
                "docvault.core.storage.read_markdown", return_value=mock_content
            ):
                with patch("click.echo_via_pager") as mock_pager:
                    result = cli_runner.invoke(cli, ["read", "1", "--raw"])

                    assert result.exit_code == 0
                    mock_pager.assert_called_once_with("# Raw Content")

    def test_read_html_browser(self, cli_runner):
        """Test reading document in browser"""
        mock_doc = {
            "id": 1,
            "title": "Test",
            "url": "https://example.com",
            "html_path": "/test/doc.html",
        }

        with patch("docvault.db.operations.get_document", return_value=mock_doc):
            with patch("docvault.core.storage.open_html_in_browser") as mock_browser:
                result = cli_runner.invoke(cli, ["read", "1", "--browser"])

                assert result.exit_code == 0
                mock_browser.assert_called_once_with("/test/doc.html")

    def test_read_nonexistent_document(self, cli_runner):
        """Test reading non-existent document"""
        with patch("docvault.db.operations.get_document", return_value=None):
            result = cli_runner.invoke(cli, ["read", "999"])

            assert result.exit_code != 0
            assert "Document not found" in result.output

    def test_read_missing_file(self, cli_runner):
        """Test reading document with missing file"""
        mock_doc = {
            "id": 1,
            "title": "Test",
            "url": "https://example.com",
            "markdown_path": "/test/missing.md",
        }

        with patch("docvault.db.operations.get_document", return_value=mock_doc):
            with patch(
                "docvault.core.storage.read_markdown", side_effect=FileNotFoundError
            ):
                result = cli_runner.invoke(cli, ["read", "1"])

                assert result.exit_code != 0
                assert "Error" in result.output


class TestRemoveCommand:
    """Test suite for remove command"""

    def test_remove_single_document(self, cli_runner):
        """Test removing single document"""
        mock_doc = {
            "id": 1,
            "title": "Test Document",
            "url": "https://example.com",
            "html_path": str(Path("/test/doc.html")),
            "markdown_path": str(Path("/test/doc.md")),
        }

        with patch("docvault.db.operations.get_document", return_value=mock_doc):
            with patch("docvault.db.operations.delete_document", return_value=True):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.unlink"):
                        # Test with force flag
                        result = cli_runner.invoke(cli, ["rm", "1", "--force"])

                        assert result.exit_code == 0
                        assert "Deleted" in result.output

    def test_remove_multiple_documents(self, cli_runner):
        """Test removing multiple documents"""

        def mock_get_doc(doc_id):
            return {
                "id": doc_id,
                "title": f"Document {doc_id}",
                "url": f"https://example.com/{doc_id}",
                "html_path": f"/test/doc{doc_id}.html",
                "markdown_path": f"/test/doc{doc_id}.md",
            }

        with patch("docvault.db.operations.get_document", side_effect=mock_get_doc):
            with patch("docvault.db.operations.delete_document", return_value=True):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.unlink"):
                        # Test comma-separated IDs
                        result = cli_runner.invoke(cli, ["rm", "1,2,3", "--force"])

                        assert result.exit_code == 0
                        assert "3" in result.output  # Should show count

    def test_remove_range_syntax(self, cli_runner):
        """Test removing documents with range syntax"""
        call_count = 0

        def mock_get_doc(doc_id):
            nonlocal call_count
            call_count += 1
            if doc_id <= 3:
                return {
                    "id": doc_id,
                    "title": f"Doc {doc_id}",
                    "url": f"https://example.com/{doc_id}",
                    "html_path": f"/test/{doc_id}.html",
                    "markdown_path": f"/test/{doc_id}.md",
                }
            return None

        with patch("docvault.db.operations.get_document", side_effect=mock_get_doc):
            with patch("docvault.db.operations.delete_document", return_value=True):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.unlink"):
                        result = cli_runner.invoke(cli, ["rm", "1-3", "--force"])

                        assert result.exit_code == 0
                        assert call_count == 3

    def test_remove_without_force(self, cli_runner):
        """Test remove command requires confirmation without force flag"""
        mock_doc = {"id": 1, "title": "Test", "url": "https://example.com"}

        with patch("docvault.db.operations.get_document", return_value=mock_doc):
            # Simulate user not confirming
            result = cli_runner.invoke(cli, ["rm", "1"], input="n\n")

            assert result.exit_code == 0
            assert "Confirm" in result.output or "cancelled" in result.output

    def test_remove_nonexistent_document(self, cli_runner):
        """Test removing non-existent document"""
        with patch("docvault.db.operations.get_document", return_value=None):
            result = cli_runner.invoke(cli, ["rm", "999", "--force"])

            assert result.exit_code == 0
            assert "not found" in result.output

    def test_remove_mixed_format(self, cli_runner):
        """Test removing with mixed ID format"""
        doc_ids = []

        def mock_get_doc(doc_id):
            doc_ids.append(doc_id)
            return {
                "id": doc_id,
                "title": f"Doc {doc_id}",
                "url": f"https://example.com/{doc_id}",
                "html_path": f"/test/{doc_id}.html",
                "markdown_path": f"/test/{doc_id}.md",
            }

        with patch("docvault.db.operations.get_document", side_effect=mock_get_doc):
            with patch("docvault.db.operations.delete_document", return_value=True):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.unlink"):
                        # Mix of single IDs and ranges
                        result = cli_runner.invoke(cli, ["rm", "1,3-5,7", "--force"])

                        assert result.exit_code == 0
                        assert sorted(doc_ids) == [1, 3, 4, 5, 7]
