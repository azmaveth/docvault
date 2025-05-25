"""Tests for the smart depth detection feature."""

from unittest.mock import patch

import pytest

from docvault.core.depth_analyzer import DepthAnalyzer, DepthStrategy


class TestDepthAnalyzer:
    """Test cases for DepthAnalyzer class."""

    def test_init_with_strategy(self):
        """Test initialization with different strategies."""
        analyzer = DepthAnalyzer(DepthStrategy.AUTO)
        assert analyzer.strategy == DepthStrategy.AUTO

        analyzer = DepthAnalyzer(DepthStrategy.CONSERVATIVE)
        assert analyzer.strategy == DepthStrategy.CONSERVATIVE

    def test_analyze_url_external_domain(self):
        """Test that external domains are never followed."""
        analyzer = DepthAnalyzer()

        result = analyzer.analyze_url(
            "https://external.com/docs", "https://example.com/docs", 3
        )

        assert not result.should_follow
        assert result.reason == "External domain"
        assert result.priority == 0.0

    def test_analyze_url_skip_file_extensions(self):
        """Test that non-documentation file types are skipped."""
        analyzer = DepthAnalyzer()
        base_url = "https://example.com/docs"

        skip_urls = [
            "https://example.com/docs/file.pdf",
            "https://example.com/docs/archive.zip",
            "https://example.com/docs/image.png",
            "https://example.com/docs/video.mp4",
        ]

        for url in skip_urls:
            result = analyzer.analyze_url(url, base_url, 3)
            assert not result.should_follow
            assert "Non-documentation file type" in result.reason

    def test_analyze_url_documentation_patterns(self):
        """Test URL pattern recognition for documentation."""
        analyzer = DepthAnalyzer(DepthStrategy.AUTO)
        base_url = "https://example.com"

        # Documentation URLs should score high
        doc_urls = [
            "https://example.com/docs/api",
            "https://example.com/api/reference",
            "https://example.com/guide/tutorial",
            "https://example.com/documentation/manual",
            "https://example.com/learn/getting-started",
        ]

        for url in doc_urls:
            result = analyzer.analyze_url(url, base_url, 3)
            assert result.should_follow
            # Documentation URLs should have decent priority
            assert result.priority >= 0.5 or (
                result.priority >= 0.3 and "Uncertain" in result.reason
            )
            # The reason should indicate it's recognized as documentation or uncertain
            assert any(
                phrase in result.reason
                for phrase in ["Documentation URL pattern", "Uncertain"]
            )

    def test_analyze_url_non_documentation_patterns(self):
        """Test URL pattern recognition for non-documentation."""
        analyzer = DepthAnalyzer(DepthStrategy.AUTO)
        base_url = "https://example.com"

        # Non-documentation URLs should score low
        non_doc_urls = [
            "https://example.com/blog/news",
            "https://example.com/about/careers",
            "https://example.com/pricing",
            "https://example.com/contact",
            "https://example.com/support/forum",
        ]

        for url in non_doc_urls:
            result = analyzer.analyze_url(url, base_url, 3)
            if result.should_follow:
                # In AUTO mode, might still follow with low priority
                assert result.priority <= 0.3
            else:
                assert "Non-documentation URL pattern" in result.reason

    def test_analyze_url_version_consistency(self):
        """Test version consistency checking."""
        analyzer = DepthAnalyzer()

        # Same version should be consistent
        result = analyzer.analyze_url(
            "https://example.com/docs/v2/api", "https://example.com/docs/v2/guide", 3
        )
        assert result.should_follow  # Version consistent

        # Different versions should affect decision
        result = analyzer.analyze_url(
            "https://example.com/docs/v3/api", "https://example.com/docs/v2/guide", 3
        )
        # The version mismatch might affect the decision depending on strategy

    def test_conservative_strategy(self):
        """Test conservative strategy behavior."""
        analyzer = DepthAnalyzer(DepthStrategy.CONSERVATIVE)
        base_url = "https://example.com"

        # Only high-confidence documentation links should be followed
        # Use a URL that matches multiple patterns to get a higher score
        result = analyzer.analyze_url(
            "https://example.com/docs/api/reference",  # Matches /docs/, /api/, and gets bonus
            base_url,
            3,
        )
        assert result.should_follow
        assert result.priority > 0.7

        # Single pattern matches should not be followed in conservative mode
        result = analyzer.analyze_url("https://example.com/docs/page", base_url, 3)
        assert not result.should_follow

        # Uncertain links should not be followed
        result = analyzer.analyze_url("https://example.com/some/page", base_url, 3)
        assert not result.should_follow

    def test_aggressive_strategy(self):
        """Test aggressive strategy behavior."""
        analyzer = DepthAnalyzer(DepthStrategy.AGGRESSIVE)
        base_url = "https://example.com"

        # Most links should be followed unless clearly non-documentation
        result = analyzer.analyze_url("https://example.com/some/page", base_url, 3)
        assert result.should_follow

        # Only clearly non-documentation should be skipped
        # Use URL that matches multiple negative patterns to score below -0.5
        result = analyzer.analyze_url(
            "https://example.com/about/careers",  # Matches both /about/ and /careers/
            base_url,
            3,
        )
        assert not result.should_follow

    def test_manual_strategy(self):
        """Test manual strategy behavior."""
        analyzer = DepthAnalyzer(DepthStrategy.MANUAL)
        base_url = "https://example.com"

        # Should follow everything up to depth limit
        result = analyzer.analyze_url("https://example.com/anything", base_url, 3)
        assert result.should_follow
        assert result.reason == "Manual depth control"

        # Should not follow at depth 0
        result = analyzer.analyze_url("https://example.com/anything", base_url, 0)
        assert not result.should_follow

    def test_analyze_content_code_density(self):
        """Test content analysis for code density."""
        analyzer = DepthAnalyzer()

        # High code density content
        content_with_code = """
        <html>
        <body>
        <pre><code>
        def hello_world():
            print("Hello, World!")
        </code></pre>
        <p>This function prints a greeting.</p>
        <code>import sys</code>
        </body>
        </html>
        """

        scores = analyzer.analyze_content(content_with_code)
        assert scores["code_density"] > 0.0
        assert scores["overall"] > 0.0

    def test_analyze_content_api_indicators(self):
        """Test content analysis for API documentation indicators."""
        analyzer = DepthAnalyzer()

        # Content with API documentation indicators
        api_content = """
        <html>
        <body>
        <h2>Parameters</h2>
        <p>This method returns a string value.</p>
        <h3>Usage</h3>
        <p>Example syntax for this function.</p>
        <h3>Arguments</h3>
        <p>The function accepts the following options.</p>
        </body>
        </html>
        """

        scores = analyzer.analyze_content(api_content)
        assert scores["api_indicators"] > 0.0
        assert scores["overall"] > 0.0

    def test_should_continue_crawling(self):
        """Test crawling continuation decisions."""
        analyzer = DepthAnalyzer(DepthStrategy.AUTO)

        # High quality content should allow deeper crawling
        high_scores = {"overall": 0.8, "code_density": 0.9}
        should_continue, depth = analyzer.should_continue_crawling(high_scores, 2)
        assert should_continue
        assert depth >= 3

        # Low quality content should stop crawling
        low_scores = {"overall": 0.1, "code_density": 0.0}
        should_continue, depth = analyzer.should_continue_crawling(low_scores, 2)
        assert not should_continue
        assert depth == 0

    def test_prioritize_links(self):
        """Test link prioritization."""
        analyzer = DepthAnalyzer(DepthStrategy.AUTO)
        base_url = "https://example.com"

        links = [
            "https://example.com/blog/news",  # Low priority (-0.5 score)
            "https://example.com/docs/api/reference",  # High priority (0.9 score)
            "https://example.com/guide/tutorial",  # Medium priority (0.3 score)
            "https://example.com/about",  # Low priority (-0.5 score)
            "https://external.com/docs",  # Should be filtered out
        ]

        prioritized = analyzer.prioritize_links(links, base_url, 3, max_links=3)

        # Should return only 3 links (max_links), external filtered out
        assert len(prioritized) <= 3

        # The highest scoring documentation link should be first
        if len(prioritized) > 0:
            assert "/docs/api/reference" in prioritized[0]

        # External links should not be included
        assert not any("external.com" in link for link in prioritized)

        # Low priority links (blog, about) should be last or not included
        if len(prioritized) == 3:
            assert "/blog/news" not in prioritized[0] and "/about" not in prioritized[0]

    def test_extract_version(self):
        """Test version extraction from URLs."""
        analyzer = DepthAnalyzer()

        # Test various version patterns
        assert analyzer._extract_version("/docs/v1/api") == "/v1/"
        assert analyzer._extract_version("/docs/v2.0/guide") == "/v2.0/"
        assert analyzer._extract_version("/docs/3.1.4/reference") == "/3.1.4/"
        assert analyzer._extract_version("/docs/stable/api") == "/stable/"
        assert analyzer._extract_version("/docs/latest/guide") == "/latest/"
        assert analyzer._extract_version("/docs/api") is None

    def test_check_version_consistency(self):
        """Test version consistency checking between URLs."""
        analyzer = DepthAnalyzer()

        # Same versions
        assert analyzer._check_version_consistency("/docs/v1/api", "/docs/v1/guide")

        # No version in base, any version in URL is OK
        assert analyzer._check_version_consistency("/docs/api", "/docs/v1/guide")

        # Version in base, no version in URL is OK (inherits)
        assert analyzer._check_version_consistency("/docs/v1/api", "/docs/guide")

        # Different versions
        assert not analyzer._check_version_consistency("/docs/v1/api", "/docs/v2/guide")


class TestDepthAnalyzerIntegration:
    """Integration tests with WebScraper."""

    @pytest.mark.asyncio
    async def test_scraper_with_auto_depth(self):
        """Test scraper integration with auto depth strategy."""
        from docvault.core.scraper import WebScraper

        # Create scraper with auto depth strategy
        scraper = WebScraper(depth_strategy="auto")
        assert scraper.depth_strategy == DepthStrategy.AUTO
        assert scraper.depth_analyzer.strategy == DepthStrategy.AUTO

    @pytest.mark.asyncio
    async def test_scraper_depth_parameter_parsing(self):
        """Test that scraper correctly parses depth parameter."""
        from docvault.core.scraper import WebScraper

        scraper = WebScraper()

        # Mock the scraping process to test parameter handling
        with patch.object(scraper, "_safe_fetch_url") as mock_fetch:
            mock_fetch.return_value = ("<html><body>Test</body></html>", None)

            # The scrape_url method should handle "auto" as depth
            # This is a simplified test - in reality would need more mocking
            # Just verify the method accepts the parameter without error

            # Test that invalid strategies default to AUTO
            scraper_invalid = WebScraper(depth_strategy="invalid")
            assert scraper_invalid.depth_strategy == DepthStrategy.AUTO
