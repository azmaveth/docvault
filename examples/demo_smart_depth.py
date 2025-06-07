#!/usr/bin/env python3
"""
Demonstration of smart depth detection in DocVault.

This script shows how the different depth strategies work when scraping documentation.
"""

import asyncio

from docvault.core.depth_analyzer import DepthAnalyzer, DepthStrategy


async def demo_depth_strategies():
    """Demonstrate different depth control strategies."""

    # Sample URLs for testing
    base_url = "https://docs.example.com/v2/"
    test_urls = [
        ("https://docs.example.com/v2/api/reference", "API Reference"),
        ("https://docs.example.com/v2/guide/tutorial", "Tutorial Guide"),
        ("https://docs.example.com/v2/blog/news", "Blog News"),
        ("https://docs.example.com/v2/about/careers", "Careers Page"),
        ("https://external.com/docs", "External Site"),
        ("https://docs.example.com/v3/api", "Different Version"),
        ("https://docs.example.com/v2/file.pdf", "PDF File"),
    ]

    # Test each strategy
    strategies = [
        DepthStrategy.AUTO,
        DepthStrategy.CONSERVATIVE,
        DepthStrategy.AGGRESSIVE,
        DepthStrategy.MANUAL,
    ]

    for strategy in strategies:
        print(f"\n{'=' * 60}")
        print(f"Testing {strategy.value.upper()} Strategy")
        print("=" * 60)

        analyzer = DepthAnalyzer(strategy)

        for url, description in test_urls:
            result = analyzer.analyze_url(url, base_url, current_depth=3)

            status = "✓ FOLLOW" if result.should_follow else "✗ SKIP"
            print(f"\n{status} {description}")
            print(f"  URL: {url}")
            print(f"  Priority: {result.priority:.2f}")
            print(f"  Reason: {result.reason}")
            if result.suggested_depth:
                print(f"  Suggested Depth: {result.suggested_depth}")

    # Demonstrate content analysis
    print(f"\n{'=' * 60}")
    print("Content Analysis Demo")
    print("=" * 60)

    analyzer = DepthAnalyzer(DepthStrategy.AUTO)

    # High quality documentation content
    good_content = """
    <html>
    <body>
    <h1>API Reference</h1>
    <h2>Parameters</h2>
    <pre><code>
    def process_data(input: str, options: dict) -> dict:
        '''Process input data with given options.

        Args:
            input: The input string to process
            options: Configuration options

        Returns:
            Processed data as dictionary
        '''
        pass
    </code></pre>
    <p>This function handles data processing with the following syntax...</p>
    </body>
    </html>
    """

    # Low quality content (navigation heavy)
    nav_content = """
    <html>
    <body>
    <h1>Site Map</h1>
    <a href="/page1">Page 1</a>
    <a href="/page2">Page 2</a>
    <a href="/page3">Page 3</a>
    <a href="/page4">Page 4</a>
    <a href="/page5">Page 5</a>
    <p>Choose a page from above.</p>
    </body>
    </html>
    """

    for content_type, content in [
        ("High Quality Docs", good_content),
        ("Navigation Heavy", nav_content),
    ]:
        scores = analyzer.analyze_content(content)
        should_continue, depth = analyzer.should_continue_crawling(scores, 3)

        print(f"\n{content_type}:")
        print(f"  Code Density: {scores['code_density']:.2f}")
        print(f"  API Indicators: {scores['api_indicators']:.2f}")
        print(f"  Navigation Ratio: {scores['navigation_ratio']:.2f}")
        print(f"  Overall Score: {scores['overall']:.2f}")
        print(f"  Continue Crawling: {'Yes' if should_continue else 'No'}")
        if should_continue:
            print(f"  Suggested Depth: {depth}")


async def demo_cli_usage():
    """Show example CLI commands with smart depth."""

    print(f"\n{'=' * 60}")
    print("CLI Usage Examples")
    print("=" * 60)

    examples = [
        (
            "Basic auto depth (smart detection):",
            "dv import https://docs.example.com --depth auto",
        ),
        (
            "Conservative strategy (high-confidence docs only):",
            "dv import https://docs.example.com --depth 5 --depth-strategy conservative",
        ),
        (
            "Aggressive strategy (follow most links):",
            "dv scrape https://api.example.com --depth aggressive",
        ),
        ("Traditional fixed depth:", "dv import https://docs.example.com --depth 3"),
        (
            "Override strategy for specific scrape:",
            "dv import https://docs.example.com --depth auto --depth-strategy manual",
        ),
    ]

    for description, command in examples:
        print(f"\n{description}")
        print(f"  $ {command}")


if __name__ == "__main__":
    print("DocVault Smart Depth Detection Demo")
    print("===================================")

    asyncio.run(demo_depth_strategies())
    asyncio.run(demo_cli_usage())

    print("\n\nKey Benefits:")
    print("- AUTO mode intelligently decides depth based on content quality")
    print("- CONSERVATIVE mode ensures only high-quality docs are scraped")
    print("- AGGRESSIVE mode captures more content with smart filtering")
    print("- MANUAL mode preserves traditional behavior")
    print("\nExternal links are always filtered regardless of strategy!")
