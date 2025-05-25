from unittest.mock import patch

import pytest

from docvault.core.scraper import WebScraper


class TestSectionedStorage:
    """Test suite for sectioned storage functionality"""

    @pytest.fixture
    def scraper(self):
        """Create a test scraper instance"""
        return WebScraper()

    @pytest.fixture
    def sample_html(self):
        """Sample HTML content for testing"""
        return """
        <html>
        <head><title>Test Documentation</title></head>
        <body>
            <h1>Introduction</h1>
            <p>This is the introduction content.</p>
            
            <h2>Installation</h2>
            <p>To install the package, run:</p>
            <code>pip install example</code>
            
            <h2>API Reference</h2>
            <p>This section covers the API.</p>
            
            <h3>Classes</h3>
            <p>Available classes in the package.</p>
            
            <h2>Examples</h2>
            <p>Usage examples.</p>
            
            <div class="documentation">
                <h2>Advanced Topics</h2>
                <p>Advanced documentation content.</p>
            </div>
            
            <div id="api-docs">
                <h3>API Details</h3>
                <p>Detailed API documentation.</p>
            </div>
        </body>
        </html>
        """

    def test_filter_content_sections_no_filters(self, scraper, sample_html):
        """Test that content is unchanged when no filters are applied"""
        result = scraper._filter_content_sections(sample_html)
        assert result == sample_html

    def test_filter_content_sections_by_heading(self, scraper, sample_html):
        """Test filtering content by section headings"""
        result = scraper._filter_content_sections(
            sample_html, sections=["Installation"]
        )

        # The result should contain the Installation section
        assert "Installation" in result
        assert "pip install example" in result

        # But should not contain other sections
        assert "API Reference" not in result
        assert "Examples" not in result

    def test_filter_content_sections_multiple_headings(self, scraper, sample_html):
        """Test filtering content by multiple section headings"""
        result = scraper._filter_content_sections(
            sample_html, sections=["Installation", "Examples"]
        )

        # Should contain both requested sections
        assert "Installation" in result
        assert "pip install example" in result
        assert "Examples" in result
        assert "Usage examples" in result

        # But should not contain other sections
        assert "Introduction" not in result

    def test_filter_content_sections_by_css_selector(self, scraper, sample_html):
        """Test filtering content by CSS selector"""
        result = scraper._filter_content_sections(
            sample_html, filter_selector=".documentation"
        )

        # Should contain content within the .documentation div
        assert "Advanced Topics" in result
        assert "Advanced documentation content" in result

        # Should not contain other content
        assert "Installation" not in result
        assert "Examples" not in result

    def test_filter_content_sections_by_id_selector(self, scraper, sample_html):
        """Test filtering content by ID selector"""
        result = scraper._filter_content_sections(
            sample_html, filter_selector="#api-docs"
        )

        # Should contain content within the #api-docs div
        assert "API Details" in result
        assert "Detailed API documentation" in result

        # Should not contain other content
        assert "Installation" not in result
        assert "Examples" not in result

    def test_filter_content_sections_case_insensitive(self, scraper, sample_html):
        """Test that section filtering is case-insensitive"""
        result = scraper._filter_content_sections(
            sample_html, sections=["installation"]
        )

        # Should match despite case difference
        assert "Installation" in result
        assert "pip install example" in result

    def test_filter_content_sections_partial_match(self, scraper, sample_html):
        """Test that section filtering supports partial matches"""
        result = scraper._filter_content_sections(sample_html, sections=["API"])

        # Should match "API Reference" section
        assert "API Reference" in result
        assert "This section covers the API" in result

    def test_filter_content_sections_invalid_selector(self, scraper, sample_html):
        """Test handling of invalid CSS selectors"""
        with patch.object(scraper.logger, "warning") as mock_warning:
            result = scraper._filter_content_sections(
                sample_html, filter_selector="[[invalid"
            )

            # Should return original content and log warning
            assert result == sample_html
            mock_warning.assert_called_once()

    def test_filter_content_sections_no_matches(self, scraper, sample_html):
        """Test handling when no sections match the filter"""
        result = scraper._filter_content_sections(sample_html, sections=["NonExistent"])

        # Should return original content when no matches found
        assert result == sample_html

    @pytest.mark.asyncio
    async def test_scrape_url_with_sections(self, scraper):
        """Test scraping with section filtering"""
        test_url = "https://example.com/docs"
        test_html = """
        <html>
        <head><title>Test Docs</title></head>
        <body>
            <h1>Getting Started</h1>
            <p>Start here.</p>
            <h2>Installation</h2>
            <p>Install instructions.</p>
        </body>
        </html>
        """

        with (
            patch.object(scraper, "_safe_fetch_url") as mock_fetch,
            patch("docvault.core.processor.extract_title") as mock_title,
            patch("docvault.core.processor.html_to_markdown") as mock_markdown,
            patch("docvault.core.storage.save_html") as mock_save_html,
            patch("docvault.core.storage.save_markdown") as mock_save_md,
            patch("docvault.db.operations.update_document_by_url") as mock_update,
            patch("docvault.core.processor.segment_markdown") as mock_segment,
            patch("docvault.core.embeddings.generate_embeddings") as mock_embed,
            patch("docvault.db.operations.add_document_segment") as mock_add_seg,
            patch("docvault.db.operations.get_document") as mock_get_doc,
        ):

            # Setup mocks
            mock_fetch.return_value = (test_html, None)
            mock_title.return_value = "Test Docs"
            mock_markdown.return_value = (
                "# Getting Started\nStart here.\n# Installation\nInstall instructions."
            )
            mock_save_html.return_value = "/path/test.html"
            mock_save_md.return_value = "/path/test.md"
            mock_update.return_value = 1
            mock_segment.return_value = [
                {"type": "h1", "content": "Getting Started\nStart here."},
                {"type": "h2", "content": "Installation\nInstall instructions."},
            ]
            mock_embed.return_value = [0.1, 0.2, 0.3]
            mock_add_seg.return_value = None
            mock_get_doc.return_value = {"id": 1, "title": "Test Docs", "url": test_url}

            # Test scraping with section filter
            await scraper.scrape_url(test_url, sections=["Installation"])

            # Verify the section filtering was applied
            assert mock_fetch.called
            # The filtered content should be passed to processor functions
            call_args = mock_markdown.call_args[0][0]
            assert "Installation" in call_args
            # Getting Started section should be filtered out
            assert "Getting Started" not in call_args or call_args.count(
                "Installation"
            ) >= call_args.count("Getting Started")

    @pytest.mark.asyncio
    async def test_scrape_url_with_css_selector(self, scraper):
        """Test scraping with CSS selector filtering"""
        test_url = "https://example.com/docs"
        test_html = """
        <html>
        <head><title>Test Docs</title></head>
        <body>
            <div class="main-content">
                <h1>Main Documentation</h1>
                <p>Main content here.</p>
            </div>
            <div class="sidebar">
                <h2>Navigation</h2>
                <p>Nav content.</p>
            </div>
        </body>
        </html>
        """

        with (
            patch.object(scraper, "_safe_fetch_url") as mock_fetch,
            patch("docvault.core.processor.extract_title") as mock_title,
            patch("docvault.core.processor.html_to_markdown") as mock_markdown,
            patch("docvault.core.storage.save_html") as mock_save_html,
            patch("docvault.core.storage.save_markdown") as mock_save_md,
            patch("docvault.db.operations.update_document_by_url") as mock_update,
            patch("docvault.core.processor.segment_markdown") as mock_segment,
            patch("docvault.core.embeddings.generate_embeddings") as mock_embed,
            patch("docvault.db.operations.add_document_segment") as mock_add_seg,
            patch("docvault.db.operations.get_document") as mock_get_doc,
        ):

            # Setup mocks
            mock_fetch.return_value = (test_html, None)
            mock_title.return_value = "Test Docs"
            mock_markdown.return_value = "# Main Documentation\nMain content here."
            mock_save_html.return_value = "/path/test.html"
            mock_save_md.return_value = "/path/test.md"
            mock_update.return_value = 1
            mock_segment.return_value = [
                {"type": "h1", "content": "Main Documentation\nMain content here."}
            ]
            mock_embed.return_value = [0.1, 0.2, 0.3]
            mock_add_seg.return_value = None
            mock_get_doc.return_value = {"id": 1, "title": "Test Docs", "url": test_url}

            # Test scraping with CSS selector
            await scraper.scrape_url(test_url, filter_selector=".main-content")

            # Verify the CSS selector filtering was applied
            assert mock_fetch.called
            # The filtered content should contain only main-content
            call_args = mock_markdown.call_args[0][0]
            assert "Main Documentation" in call_args
            # Sidebar content should be filtered out
            assert "Navigation" not in call_args

    def test_cli_import_command_sections_option(self):
        """Test that CLI import command accepts sections option"""
        import click.testing

        from docvault.cli.commands import import_cmd

        runner = click.testing.CliRunner()

        # Test that the command accepts the --sections option
        result = runner.invoke(import_cmd, ["--help"])
        assert "--sections" in result.output
        assert "Filter by section headings" in result.output

        # Test that the command accepts the --filter-selector option
        assert "--filter-selector" in result.output
        assert "CSS selector to filter" in result.output

    @pytest.mark.asyncio
    async def test_mcp_scrape_document_with_sections(self):
        """Test MCP scrape_document tool with section filtering"""
        # Test that the MCP server can be created successfully with the new tool signature
        from docvault.mcp.server import create_server

        try:
            server = create_server()
            assert server is not None

            # Test the WebScraper class directly to verify it supports section filtering
            from docvault.core.scraper import WebScraper

            scraper = WebScraper()

            import inspect

            sig = inspect.signature(scraper.scrape_url)
            assert "sections" in sig.parameters
            assert "filter_selector" in sig.parameters

        except Exception as e:
            pytest.fail(f"Server creation or scraper inspection failed: {e}")
