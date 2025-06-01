"""Improved tests for search CLI commands using minimal mocking."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from docvault.main import cli
from tests.utils import create_test_document_in_db  # Import the fixture


class TestSearchCommand:
    """Test search commands with minimal mocking."""

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

            # Create some test documents
            self._create_test_data()
            yield

    def _create_test_data(self):
        """Create test documents in the database."""
        # Get the database path from the test project
        db_path = self.project.db_path

        # Create a few test documents
        self.doc1 = create_test_document_in_db(
            db_path,
            {
                "url": "https://docs.python.org",
                "title": "Python Documentation",
                "content": "Python is a programming language",
                "html_path": "/tmp/test1.html",
                "markdown_path": "/tmp/test1.md",
                "version": "3.12",
                "is_library_doc": True,
                "library_name": "python",
            },
        )

        self.doc2 = create_test_document_in_db(
            db_path,
            {
                "url": "https://docs.djangoproject.com",
                "title": "Django Documentation",
                "content": "Django is a web framework",
                "html_path": "/tmp/test2.html",
                "markdown_path": "/tmp/test2.md",
                "version": "4.2.0",
                "is_library_doc": True,
                "library_name": "django",
            },
        )

        self.doc3 = create_test_document_in_db(
            db_path,
            {
                "url": "https://example.com",
                "title": "Example Documentation",
                "content": "Example content for testing",
                "html_path": "/tmp/test3.html",
                "markdown_path": "/tmp/test3.md",
            },
        )

    def test_search_text_basic(self, cli_runner):
        """Test basic text search."""

        # Mock the search function to return results from our test data
        async def mock_search(
            query=None,
            limit=5,
            text_only=False,
            min_score=0.0,
            doc_filter=None,
            document_ids=None,
        ):
            # Simple mock that returns results if "python" is in query
            if query and "python" in query.lower():
                return [
                    {
                        "id": 1,
                        "document_id": 1,
                        "segment_id": 1,
                        "title": "Python Documentation",
                        "content": "Python is a programming language",
                        "score": 0.95,
                        "url": "https://docs.python.org",
                        "section_title": "Introduction",
                    }
                ]
            return []

        # Mock the search from embeddings module (as used by commands.py)
        with (
            patch(
                "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
            ),
            patch(
                "docvault.models.tags.get_document_tags", return_value=[]
            ),  # Mock tags as empty
            patch(
                "docvault.models.collections.get_document_collections", return_value=[]
            ),  # Mock collections
            patch(
                "docvault.db.operations_llms.get_llms_txt_metadata", return_value=None
            ),  # Mock llms metadata
        ):
            result = cli_runner.invoke(cli, ["search", "text", "python"])

            # Debug output
            if result.exit_code != 0:
                print(f"Exit code: {result.exit_code}")
                print(f"Output: {result.output}")
                print(f"Exception: {result.exception}")
                if result.exception:
                    import traceback

                    traceback.print_exception(
                        type(result.exception),
                        result.exception,
                        result.exception.__traceback__,
                    )

            assert result.exit_code == 0
            assert "Python Documentation" in result.output
            assert "programming language" in result.output

    def test_search_json_output(self, cli_runner):
        """Test search with JSON output format."""

        async def mock_search(
            query, limit=5, text_only=False, min_score=0.0, doc_filter=None
        ):
            return [
                {
                    "id": 1,
                    "document_id": 1,
                    "segment_id": 1,
                    "title": "Test Document",
                    "content": "Test content",
                    "score": 0.9,
                    "url": "https://example.com",
                }
            ]

        with (
            patch(
                "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
            ),
            patch("docvault.models.tags.get_document_tags", return_value=[]),
            patch(
                "docvault.models.collections.get_document_collections", return_value=[]
            ),
        ):
            result = cli_runner.invoke(
                cli, ["search", "text", "test", "--format", "json"]
            )

            assert result.exit_code == 0

            # Parse JSON output
            data = json.loads(result.output)
            assert data["status"] == "success"
            assert len(data["results"]) == 1

    def test_search_no_results(self, cli_runner):
        """Test search with no results."""

        async def mock_search(
            query, limit=5, text_only=False, min_score=0.0, doc_filter=None
        ):
            return []

        with (
            patch(
                "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
            ),
            patch("docvault.models.tags.get_document_tags", return_value=[]),
            patch(
                "docvault.models.collections.get_document_collections", return_value=[]
            ),
        ):
            result = cli_runner.invoke(cli, ["search", "text", "nonexistent"])

            assert result.exit_code == 0
            assert "No matching documents found" in result.output

    def test_search_with_limit(self, cli_runner):
        """Test search with custom limit."""
        call_count = 0

        async def mock_search(
            query, limit=5, text_only=False, min_score=0.0, doc_filter=None
        ):
            nonlocal call_count
            call_count += 1
            # Verify limit is passed correctly
            assert limit == 3
            return []

        with (
            patch(
                "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
            ),
            patch("docvault.models.tags.get_document_tags", return_value=[]),
            patch(
                "docvault.models.collections.get_document_collections", return_value=[]
            ),
        ):
            result = cli_runner.invoke(cli, ["search", "text", "test", "--limit", "3"])

            assert result.exit_code == 0
            assert call_count == 1

    def test_search_text_only(self, cli_runner):
        """Test text-only search mode."""

        async def mock_search(
            query, limit=5, text_only=False, min_score=0.0, doc_filter=None
        ):
            # Verify text_only flag is passed
            assert text_only is True
            return []

        with (
            patch(
                "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
            ),
            patch("docvault.models.tags.get_document_tags", return_value=[]),
            patch(
                "docvault.models.collections.get_document_collections", return_value=[]
            ),
        ):
            result = cli_runner.invoke(cli, ["search", "text", "test", "--text-only"])

            assert result.exit_code == 0

    def test_search_library(self, cli_runner):
        """Test library search command."""
        mock_result = [
            {
                "id": 1,
                "library_name": "django",
                "version": "4.2.0",
                "title": "Django Documentation",
                "url": "https://docs.djangoproject.com/en/4.2/",
                "resolved_version": "4.2.0",
                "scraped_at": "2024-05-24 10:00:00",
            }
        ]

        with patch(
            "docvault.core.library_manager.LibraryManager.get_library_docs",
            return_value=mock_result,
        ):
            result = cli_runner.invoke(cli, ["search", "lib", "django"])

            assert result.exit_code == 0
            assert "django" in result.output
            assert "4.2.0" in result.output

    def test_search_library_with_version(self, cli_runner):
        """Test library search with specific version."""
        mock_result = [
            {
                "id": 1,
                "library_name": "django",
                "version": "3.2.0",
                "title": "Django Documentation",
                "url": "https://docs.djangoproject.com/en/3.2/",
                "resolved_version": "3.2.0",
                "scraped_at": "2024-05-24 10:00:00",
            }
        ]

        with patch(
            "docvault.core.library_manager.LibraryManager.get_library_docs",
            return_value=mock_result,
        ):
            result = cli_runner.invoke(cli, ["search", "lib", "django@3.2"])

            assert result.exit_code == 0
            assert "django" in result.output
            assert "3.2" in result.output

    def test_default_search_behavior(self, cli_runner):
        """Test that default command is search."""

        async def mock_search(
            query, limit=5, text_only=False, min_score=0.0, doc_filter=None
        ):
            # Should search for "python"
            assert "python" in query
            return []

        with (
            patch(
                "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
            ),
            patch("docvault.models.tags.get_document_tags", return_value=[]),
            patch(
                "docvault.models.collections.get_document_collections", return_value=[]
            ),
        ):
            # "dv python" should default to search
            result = cli_runner.invoke(cli, ["python"])

            assert result.exit_code == 0
