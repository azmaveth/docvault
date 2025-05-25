"""Tests for search CLI commands"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from docvault.main import cli


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing"""
    return CliRunner()


@pytest.fixture
def mock_search_results():
    """Mock search results"""
    return [
        {
            "id": 1,
            "document_id": 1,
            "content": "Python is a programming language",
            "segment_type": "text",
            "title": "Python Documentation",
            "url": "https://docs.python.org",
            "score": 0.95,
            "section_title": "Introduction",
            "section_level": 1,
        },
        {
            "id": 2,
            "document_id": 1,
            "content": "Python supports multiple programming paradigms",
            "segment_type": "text",
            "title": "Python Documentation",
            "url": "https://docs.python.org",
            "score": 0.85,
            "section_title": "Features",
            "section_level": 2,
        },
    ]


class TestSearchCommand:
    """Test suite for search commands"""

    def test_search_text_basic(self, cli_runner, mock_search_results):
        """Test basic text search"""

        async def mock_search(query, limit=5, text_only=False):
            return mock_search_results

        with patch(
            "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
        ):
            result = cli_runner.invoke(cli, ["search", "text", "python"])

            assert result.exit_code == 0
            assert "Python Documentation" in result.output
            assert "Introduction" in result.output
            assert "Features" in result.output

    def test_search_with_limit(self, cli_runner, mock_search_results):
        """Test search with custom limit"""

        async def mock_search(query, limit=5, text_only=False):
            return mock_search_results[:limit]

        with patch(
            "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
        ):
            result = cli_runner.invoke(
                cli, ["search", "text", "python", "--limit", "1"]
            )

            assert result.exit_code == 0
            assert "Introduction" in result.output
            assert "Features" not in result.output  # Limited to 1 result

    def test_search_text_only(self, cli_runner, mock_search_results):
        """Test text-only search"""

        async def mock_search(query, limit=5, text_only=False):
            assert text_only is True
            return mock_search_results

        with patch(
            "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
        ):
            result = cli_runner.invoke(cli, ["search", "text", "python", "--text-only"])

            assert result.exit_code == 0

    def test_search_json_format(self, cli_runner, mock_search_results):
        """Test search with JSON output format"""

        async def mock_search(query, limit=5, text_only=False):
            return mock_search_results

        with patch(
            "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
        ):
            result = cli_runner.invoke(
                cli, ["search", "text", "python", "--format", "json"]
            )

            assert result.exit_code == 0
            # Parse JSON output
            output_data = json.loads(result.output)
            assert output_data["status"] == "success"
            assert output_data["count"] == 2
            assert len(output_data["results"]) == 2
            assert output_data["results"][0]["title"] == "Python Documentation"

    def test_search_no_results(self, cli_runner):
        """Test search with no results"""

        async def mock_search(query, limit=5, text_only=False):
            return []

        with patch(
            "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
        ):
            result = cli_runner.invoke(cli, ["search", "text", "nonexistent"])

            assert result.exit_code == 0
            assert "No matching documents found" in result.output

    def test_search_with_filters(self, cli_runner, mock_search_results):
        """Test search with various filters"""

        async def mock_search(query, limit=5, text_only=False, **kwargs):
            return mock_search_results

        with patch(
            "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
        ):
            # Test with library filter
            result = cli_runner.invoke(cli, ["search", "text", "python", "--library"])
            assert result.exit_code == 0

            # Test with version filter
            result = cli_runner.invoke(
                cli, ["search", "text", "python", "--version", "3.9"]
            )
            assert result.exit_code == 0

            # Test with title filter
            result = cli_runner.invoke(
                cli, ["search", "text", "python", "--title-contains", "Doc"]
            )
            assert result.exit_code == 0

    def test_search_timeout(self, cli_runner):
        """Test search with timeout"""
        import asyncio

        async def mock_search(query, limit=5, text_only=False):
            raise asyncio.TimeoutError()

        with patch(
            "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
        ):
            result = cli_runner.invoke(
                cli, ["search", "text", "python", "--timeout", "1"]
            )

            assert result.exit_code == 0
            assert "timed out" in result.output

    def test_search_error_handling(self, cli_runner):
        """Test search error handling"""

        async def mock_search(query, limit=5, text_only=False):
            raise Exception("Database error")

        with patch(
            "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
        ):
            result = cli_runner.invoke(cli, ["search", "text", "python"])

            assert result.exit_code == 0
            assert (
                "Error" in result.output
                or "No matching documents found" in result.output
            )

    def test_default_search_behavior(self, cli_runner, mock_search_results):
        """Test default search (without subcommand)"""

        async def mock_search(query, limit=5, text_only=False):
            return mock_search_results

        with patch(
            "docvault.core.embeddings.search", AsyncMock(side_effect=mock_search)
        ):
            # Test that "dv python" defaults to search
            result = cli_runner.invoke(cli, ["python"])

            assert result.exit_code == 0
            assert "Python Documentation" in result.output


class TestSearchLibCommand:
    """Test suite for library search command"""

    def test_search_lib_basic(self, cli_runner):
        """Test basic library search"""
        mock_docs = [
            {
                "id": 1,
                "url": "https://docs.pytest.org",
                "title": "pytest documentation",
                "resolved_version": "7.4.0",
            }
        ]

        async def mock_get_library_docs(name, version=None, verbose=False):
            return mock_docs

        with patch(
            "docvault.core.library_manager.LibraryManager.get_library_docs",
            AsyncMock(side_effect=mock_get_library_docs),
        ):
            result = cli_runner.invoke(cli, ["search", "lib", "pytest"])

            assert result.exit_code == 0
            assert "pytest documentation" in result.output
            assert "7.4.0" in result.output

    def test_search_lib_with_version(self, cli_runner):
        """Test library search with specific version"""
        mock_docs = [
            {
                "id": 1,
                "url": "https://docs.pytest.org/en/6.0.0",
                "title": "pytest 6.0.0 documentation",
                "resolved_version": "6.0.0",
            }
        ]

        async def mock_get_library_docs(name, version=None, verbose=False):
            assert version == "6.0.0"
            return mock_docs

        with patch(
            "docvault.core.library_manager.LibraryManager.get_library_docs",
            AsyncMock(side_effect=mock_get_library_docs),
        ):
            result = cli_runner.invoke(
                cli, ["search", "lib", "pytest", "--version", "6.0.0"]
            )

            assert result.exit_code == 0
            assert "6.0.0" in result.output

    def test_search_lib_json_format(self, cli_runner):
        """Test library search with JSON output"""
        mock_docs = [
            {
                "id": 1,
                "url": "https://docs.pytest.org",
                "title": "pytest documentation",
                "resolved_version": "7.4.0",
                "description": "Testing framework",
            }
        ]

        async def mock_get_library_docs(name, version=None, verbose=False):
            return mock_docs

        with patch(
            "docvault.core.library_manager.LibraryManager.get_library_docs",
            AsyncMock(side_effect=mock_get_library_docs),
        ):
            result = cli_runner.invoke(
                cli, ["search", "lib", "pytest", "--format", "json"]
            )

            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert output_data["status"] == "success"
            assert output_data["library"] == "pytest"
            assert len(output_data["results"]) == 1

    def test_search_lib_no_results(self, cli_runner):
        """Test library search with no results"""

        async def mock_get_library_docs(name, version=None, verbose=False):
            return []

        with patch(
            "docvault.core.library_manager.LibraryManager.get_library_docs",
            AsyncMock(side_effect=mock_get_library_docs),
        ):
            result = cli_runner.invoke(cli, ["search", "lib", "nonexistent"])

            assert result.exit_code == 0
            assert "No documentation found" in result.output

    def test_lib_as_direct_command(self, cli_runner):
        """Test 'dv lib pytest' as direct command"""
        mock_docs = [{"id": 1, "url": "https://docs.pytest.org", "title": "pytest"}]

        async def mock_get_library_docs(name, version=None, verbose=False):
            return mock_docs

        with patch(
            "docvault.core.library_manager.LibraryManager.get_library_docs",
            AsyncMock(side_effect=mock_get_library_docs),
        ):
            result = cli_runner.invoke(cli, ["lib", "pytest"])

            assert result.exit_code == 0
            assert "pytest" in result.output
