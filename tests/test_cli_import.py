"""Improved tests for import/add CLI commands using minimal mocking."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from docvault.main import cli
from tests.utils import create_test_document_in_db


class TestImportCommand:
    """Test the import/add command with minimal mocking."""

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
    def mock_scraper_success(self):
        """Mock successful document scraping."""

        async def mock_scrape(
            url,
            depth=1,
            max_links=10,
            strict_path=True,
            force_update=False,
            sections=None,
            **kwargs,
        ):
            # Return realistic scraping result as a dictionary
            return {
                "id": 1,
                "title": "Test Document",
                "url": url,
                "segments": [
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
            }

        with patch("docvault.core.scraper.get_scraper") as mock_get:
            scraper = MagicMock()
            scraper.scrape_url = AsyncMock(side_effect=mock_scrape)
            # Mock stats for the import command
            scraper.stats = {
                "pages_scraped": 1,
                "pages_skipped": 0,
                "segments_created": 2,
            }
            mock_get.return_value = scraper
            yield scraper

    def test_import_success(self, cli_runner, mock_scraper_success):
        """Test successful document import."""
        result = cli_runner.invoke(cli, ["add", "https://example.com"])

        assert result.exit_code == 0
        assert "Successfully imported" in result.output
        assert "Test Document" in result.output

    def test_import_with_depth(self, cli_runner, mock_scraper_success):
        """Test import with custom depth."""
        result = cli_runner.invoke(cli, ["add", "https://example.com", "--depth", "3"])

        assert result.exit_code == 0
        assert "Successfully imported" in result.output

        # Verify the scraper was called with correct depth
        mock_scraper_success.scrape_url.assert_called_once()
        call_kwargs = mock_scraper_success.scrape_url.call_args[1]
        assert call_kwargs["depth"] == 3

    def test_import_network_error(self, cli_runner):
        """Test handling of network errors."""

        async def mock_scrape_error(*args, **kwargs):

            # Use a simple message in the OSError instead of complex construction
            raise OSError("Cannot connect to host example.com")

        with patch("docvault.core.scraper.get_scraper") as mock_get:
            scraper = MagicMock()
            scraper.scrape_url = AsyncMock(side_effect=mock_scrape_error)
            mock_get.return_value = scraper

            result = cli_runner.invoke(cli, ["add", "https://example.com"])

            assert result.exit_code == 0  # Command handles errors gracefully
            assert (
                "Cannot connect" in result.output or "network" in result.output.lower()
            )

    def test_import_invalid_url(self, cli_runner):
        """Test import with invalid URL."""
        result = cli_runner.invoke(cli, ["add", "not-a-valid-url"])

        assert result.exit_code == 1  # Command should fail with invalid URL
        assert "Invalid URL format" in result.output

    def test_import_with_update_flag(self, cli_runner, mock_scraper_success):
        """Test import with --update flag."""
        # First, create an existing document
        create_test_document_in_db(
            self.project.db_path,
            {"title": "Old Document", "url": "https://example.com"},
        )

        # Now try to import with update flag
        result = cli_runner.invoke(cli, ["add", "https://example.com", "--update"])

        assert result.exit_code == 0
        assert "Successfully imported" in result.output

        # Verify force_update was passed
        call_kwargs = mock_scraper_success.scrape_url.call_args[1]
        assert call_kwargs.get("force_update") is True

    def test_import_timeout(self, cli_runner):
        """Test handling of timeout errors."""

        async def mock_scrape_timeout(*args, **kwargs):
            raise asyncio.TimeoutError("Request timed out")

        with patch("docvault.core.scraper.get_scraper") as mock_get:
            scraper = MagicMock()
            scraper.scrape_url = AsyncMock(side_effect=mock_scrape_timeout)
            mock_get.return_value = scraper

            result = cli_runner.invoke(cli, ["add", "https://example.com"])

            assert result.exit_code == 0
            assert (
                "Request timed out" in result.output
                or "timed out" in result.output.lower()
            )

    def test_import_quiet_mode(self, cli_runner, mock_scraper_success):
        """Test import in quiet mode."""
        result = cli_runner.invoke(cli, ["add", "https://example.com", "--quiet"])

        assert result.exit_code == 0
        # In quiet mode, output should still show results but no progress messages
        assert "Successfully imported" in result.output
        # Should not have the initial "Importing" message
        assert "🌐 Importing" not in result.output
