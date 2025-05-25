"""Tests for import/add CLI commands"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from docvault.main import cli


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing"""
    return CliRunner()


@pytest.fixture
def mock_scraper():
    """Mock scraper with stats"""
    scraper = MagicMock()
    scraper.stats = {"pages_scraped": 1, "pages_skipped": 0, "segments_created": 5}
    return scraper


class TestImportCommand:
    """Test suite for import/add commands"""

    def test_import_success(self, cli_runner, mock_scraper):
        """Test successful document import"""
        mock_document = {
            "id": 1,
            "title": "Test Documentation",
            "url": "https://example.com/docs",
        }
        mock_scraper.scrape_url = AsyncMock(return_value=mock_document)

        with patch("docvault.core.scraper.get_scraper", return_value=mock_scraper):
            result = cli_runner.invoke(cli, ["add", "https://example.com/docs"])

            assert result.exit_code == 0
            assert "Successfully imported" in result.output
            assert "Test Documentation" in result.output

    def test_import_with_depth(self, cli_runner, mock_scraper):
        """Test import with depth parameter"""
        mock_document = {"id": 1, "title": "Test", "url": "https://example.com"}
        mock_scraper.scrape_url = AsyncMock(return_value=mock_document)

        with patch("docvault.core.scraper.get_scraper", return_value=mock_scraper):
            result = cli_runner.invoke(
                cli, ["add", "https://example.com", "--depth", "3"]
            )

            assert result.exit_code == 0
            # Verify depth was passed
            mock_scraper.scrape_url.assert_called_once()
            call_args = mock_scraper.scrape_url.call_args
            assert call_args[0][1] == 3  # depth argument

    def test_import_with_update_flag(self, cli_runner, mock_scraper):
        """Test import with update flag"""
        mock_document = {"id": 2, "title": "Updated Doc", "url": "https://example.com"}
        mock_scraper.scrape_url = AsyncMock(return_value=mock_document)

        with patch("docvault.core.scraper.get_scraper", return_value=mock_scraper):
            result = cli_runner.invoke(cli, ["add", "https://example.com", "--update"])

            assert result.exit_code == 0
            # Verify force_update was passed
            call_kwargs = mock_scraper.scrape_url.call_args.kwargs
            assert call_kwargs.get("force_update") is True

    def test_import_invalid_url(self, cli_runner):
        """Test import with invalid URL"""
        result = cli_runner.invoke(cli, ["add", "not-a-valid-url"])

        assert result.exit_code != 0
        assert "Invalid URL format" in result.output

    def test_import_network_error(self, cli_runner, mock_scraper):
        """Test import with network error"""
        import aiohttp

        mock_scraper.scrape_url = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                connection_key=None, os_error=OSError("Cannot connect to host")
            )
        )

        with patch("docvault.core.scraper.get_scraper", return_value=mock_scraper):
            result = cli_runner.invoke(cli, ["add", "https://example.com"])

            assert result.exit_code != 0
            assert "Could not connect" in result.output

    def test_import_timeout_error(self, cli_runner, mock_scraper):
        """Test import with timeout error"""
        mock_scraper.scrape_url = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("docvault.core.scraper.get_scraper", return_value=mock_scraper):
            result = cli_runner.invoke(cli, ["add", "https://example.com"])

            assert result.exit_code != 0
            assert "timed out" in result.output

    def test_import_404_error(self, cli_runner, mock_scraper):
        """Test import with 404 error"""
        mock_scraper.scrape_url = AsyncMock(
            side_effect=ValueError(
                "Failed to fetch URL: https://example.com. Reason: 404 Not Found"
            )
        )

        with patch("docvault.core.scraper.get_scraper", return_value=mock_scraper):
            result = cli_runner.invoke(cli, ["add", "https://example.com"])

            assert result.exit_code != 0
            assert "404" in result.output

    def test_import_ssl_error(self, cli_runner, mock_scraper):
        """Test import with SSL error"""
        import ssl

        mock_scraper.scrape_url = AsyncMock(
            side_effect=ssl.SSLError("SSL: CERTIFICATE_VERIFY_FAILED")
        )

        with patch("docvault.core.scraper.get_scraper", return_value=mock_scraper):
            result = cli_runner.invoke(cli, ["add", "https://example.com"])

            assert result.exit_code != 0
            assert "SSL certificate verification failed" in result.output

    def test_import_quiet_mode(self, cli_runner, mock_scraper):
        """Test import in quiet mode"""
        mock_document = {"id": 1, "title": "Test", "url": "https://example.com"}
        mock_scraper.scrape_url = AsyncMock(return_value=mock_document)

        with patch("docvault.core.scraper.get_scraper", return_value=mock_scraper):
            result = cli_runner.invoke(cli, ["add", "https://example.com", "--quiet"])

            assert result.exit_code == 0
            # In quiet mode, output should be minimal
            assert "Next steps:" not in result.output

    def test_import_max_links(self, cli_runner, mock_scraper):
        """Test import with max-links parameter"""
        mock_document = {"id": 1, "title": "Test", "url": "https://example.com"}
        mock_scraper.scrape_url = AsyncMock(return_value=mock_document)

        with patch("docvault.core.scraper.get_scraper", return_value=mock_scraper):
            result = cli_runner.invoke(
                cli, ["add", "https://example.com", "--max-links", "10"]
            )

            assert result.exit_code == 0
            # Verify max_links was passed
            call_kwargs = mock_scraper.scrape_url.call_args.kwargs
            assert call_kwargs.get("max_links") == 10

    def test_import_no_strict_path(self, cli_runner, mock_scraper):
        """Test import with --no-strict-path flag"""
        mock_document = {"id": 1, "title": "Test", "url": "https://example.com"}
        mock_scraper.scrape_url = AsyncMock(return_value=mock_document)

        with patch("docvault.core.scraper.get_scraper", return_value=mock_scraper):
            result = cli_runner.invoke(
                cli, ["add", "https://example.com", "--no-strict-path"]
            )

            assert result.exit_code == 0
            # Verify strict_path was set to False
            call_kwargs = mock_scraper.scrape_url.call_args.kwargs
            assert call_kwargs.get("strict_path") is False
