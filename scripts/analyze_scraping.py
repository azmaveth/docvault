#!/usr/bin/env python3
"""
Script to analyze scraping effectiveness for MCP specification website.
Compares different scraping methods and identifies issues.
"""

import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import aiohttp
import requests
from bs4 import BeautifulSoup

# Try to import selenium, but make it optional
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️  Selenium not available - skipping JavaScript analysis")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from docvault.core.doc_type_detector import DocTypeDetector
from docvault.core.extractors import GenericExtractor, MkDocsExtractor, SphinxExtractor
# from docvault.core.scraper import WebScraper  # Not used in analysis


class ScrapingAnalyzer:
    """Analyze different scraping methods for MCP specification."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.results = {}
        self.child_pages = set()

    async def analyze_all_methods(self):
        """Run all scraping methods and compare results."""
        print(f"🔍 Analyzing scraping methods for: {self.base_url}")

        # 1. Simple requests
        await self.analyze_requests_method()

        # 2. aiohttp (what DocVault uses)
        await self.analyze_aiohttp_method()

        # 3. Selenium (JavaScript-heavy sites)
        if SELENIUM_AVAILABLE:
            await self.analyze_selenium_method()
        else:
            self.results["selenium"] = {"error": "Selenium not available"}

        # 4. DocVault scraper
        await self.analyze_docvault_method()

        # 5. Find child pages
        await self.discover_child_pages()

        # 6. Analyze child pages
        await self.analyze_child_pages()

        # 7. Generate report
        self.generate_report()

    async def analyze_requests_method(self):
        """Analyze using simple requests library."""
        print("📡 Testing requests method...")
        try:
            response = requests.get(self.base_url, timeout=30)
            soup = BeautifulSoup(response.content, "html.parser")

            self.results["requests"] = {
                "status_code": response.status_code,
                "content_length": len(response.content),
                "title": soup.find("title").get_text() if soup.find("title") else None,
                "headings": [
                    h.get_text().strip() for h in soup.find_all(["h1", "h2", "h3"])
                ],
                "links": len(soup.find_all("a", href=True)),
                "code_blocks": len(soup.find_all(["pre", "code"])),
                "content_preview": soup.get_text()[:500],
                "has_navigation": bool(soup.find("nav")),
                "has_sidebar": bool(soup.find(["aside", ".sidebar", ".toc"])),
                "javascript_required": "application/javascript"
                in response.headers.get("content-type", ""),
            }
        except Exception as e:
            self.results["requests"] = {"error": str(e)}

    async def analyze_aiohttp_method(self):
        """Analyze using aiohttp (DocVault's method)."""
        print("🌐 Testing aiohttp method...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url) as response:
                    content = await response.text()
                    soup = BeautifulSoup(content, "html.parser")

                    self.results["aiohttp"] = {
                        "status_code": response.status,
                        "content_length": len(content),
                        "title": (
                            soup.find("title").get_text()
                            if soup.find("title")
                            else None
                        ),
                        "headings": [
                            h.get_text().strip()
                            for h in soup.find_all(["h1", "h2", "h3"])
                        ],
                        "links": len(soup.find_all("a", href=True)),
                        "code_blocks": len(soup.find_all(["pre", "code"])),
                        "content_preview": soup.get_text()[:500],
                        "has_navigation": bool(soup.find("nav")),
                        "has_sidebar": bool(soup.find(["aside", ".sidebar", ".toc"])),
                        "headers": dict(response.headers),
                    }
        except Exception as e:
            self.results["aiohttp"] = {"error": str(e)}

    async def analyze_selenium_method(self):
        """Analyze using Selenium for JavaScript-heavy content."""
        print("🤖 Testing Selenium method...")
        try:
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            driver = webdriver.Chrome(options=options)
            driver.get(self.base_url)

            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Get page source after JavaScript execution
            content = driver.page_source
            soup = BeautifulSoup(content, "html.parser")

            self.results["selenium"] = {
                "content_length": len(content),
                "title": driver.title,
                "headings": [
                    h.get_text().strip() for h in soup.find_all(["h1", "h2", "h3"])
                ],
                "links": len(soup.find_all("a", href=True)),
                "code_blocks": len(soup.find_all(["pre", "code"])),
                "content_preview": soup.get_text()[:500],
                "has_navigation": bool(soup.find("nav")),
                "has_sidebar": bool(soup.find(["aside", ".sidebar", ".toc"])),
                "dynamic_content": len(soup.find_all(attrs={"data-react": True})) > 0,
                "spa_indicators": any(
                    script.get("src", "").find("react") != -1
                    or script.get("src", "").find("vue") != -1
                    or script.get("src", "").find("angular") != -1
                    for script in soup.find_all("script")
                ),
            }

            driver.quit()
        except Exception as e:
            self.results["selenium"] = {"error": str(e)}

    async def analyze_docvault_method(self):
        """Analyze using DocVault's scraper."""
        print("📚 Testing DocVault method...")
        try:
            # First, detect documentation type
            detector = DocTypeDetector()

            # Get raw HTML for detection
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url) as response:
                    html_content = await response.text()

            doc_type, confidence = detector.detect(self.base_url, html_content)

            # Use appropriate extractor
            if doc_type.value == "mkdocs":
                extractor = MkDocsExtractor()
            elif doc_type.value == "sphinx":
                extractor = SphinxExtractor()
            else:
                extractor = GenericExtractor()

            soup = BeautifulSoup(html_content, "html.parser")

            # Fix the missing _extract_metadata method issue
            try:
                extraction_result = extractor.extract(soup, self.base_url)
            except AttributeError as e:
                if "_extract_metadata" in str(e):
                    # Fallback to basic extraction
                    extraction_result = {
                        "content": soup.get_text()[:1000],
                        "metadata": {
                            "title": (
                                soup.find("title").get_text()
                                if soup.find("title")
                                else "Unknown"
                            )
                        },
                    }
                else:
                    raise

            self.results["docvault"] = {
                "detected_type": doc_type.value,
                "detection_confidence": confidence,
                "extracted_content_length": len(extraction_result.get("content", "")),
                "metadata_keys": list(extraction_result.get("metadata", {}).keys()),
                "content_preview": extraction_result.get("content", "")[:500],
                "has_navigation": "navigation" in extraction_result.get("metadata", {}),
                "has_code_examples": "code_examples"
                in extraction_result.get("metadata", {}),
                "extractor_used": extractor.__class__.__name__,
            }

        except Exception as e:
            self.results["docvault"] = {"error": str(e)}

    async def discover_child_pages(self):
        """Discover child pages from the main page."""
        print("🔗 Discovering child pages...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url) as response:
                    content = await response.text()
                    soup = BeautifulSoup(content, "html.parser")

                    base_domain = urlparse(self.base_url).netloc

                    for link in soup.find_all("a", href=True):
                        href = link["href"]
                        full_url = urljoin(self.base_url, href)
                        parsed = urlparse(full_url)

                        # Only include same-domain links that look like documentation
                        if (
                            parsed.netloc == base_domain
                            and not href.startswith("#")
                            and not href.startswith("mailto:")
                            and not href.startswith("javascript:")
                            and full_url != self.base_url
                        ):
                            self.child_pages.add(full_url)

                    print(f"   Found {len(self.child_pages)} child pages")

        except Exception as e:
            print(f"   Error discovering child pages: {e}")

    async def analyze_child_pages(self, max_pages=5):
        """Analyze a sample of child pages."""
        print(f"📄 Analyzing {min(max_pages, len(self.child_pages))} child pages...")

        self.results["child_pages"] = {}

        for url in list(self.child_pages)[:max_pages]:
            print(f"   Analyzing: {url}")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        content = await response.text()
                        soup = BeautifulSoup(content, "html.parser")

                        self.results["child_pages"][url] = {
                            "status_code": response.status,
                            "title": (
                                soup.find("title").get_text()
                                if soup.find("title")
                                else None
                            ),
                            "headings": [
                                h.get_text().strip()
                                for h in soup.find_all(["h1", "h2", "h3"])
                            ],
                            "content_length": len(content),
                            "has_code": len(soup.find_all(["pre", "code"])) > 0,
                        }
            except Exception as e:
                self.results["child_pages"][url] = {"error": str(e)}

    def generate_report(self):
        """Generate a comprehensive analysis report."""
        print("\n" + "=" * 80)
        print("📊 SCRAPING ANALYSIS REPORT")
        print("=" * 80)

        # Compare methods
        methods = ["requests", "aiohttp", "selenium", "docvault"]

        print("\n🔍 METHOD COMPARISON:")
        print("-" * 40)

        for method in methods:
            result = self.results.get(method, {})
            if "error" in result:
                print(f"{method.upper()}: ❌ Error - {result['error']}")
                continue

            if method == "docvault":
                print(f"{method.upper()}:")
                print(f"  - Detected Type: {result.get('detected_type', 'unknown')}")
                print(f"  - Confidence: {result.get('detection_confidence', 0):.2f}")
                print(f"  - Extractor: {result.get('extractor_used', 'unknown')}")
                print(
                    f"  - Content Length: {result.get('extracted_content_length', 0)}"
                )
                print(f"  - Metadata Keys: {len(result.get('metadata_keys', []))}")
            else:
                print(f"{method.upper()}:")
                print(f"  - Status: {result.get('status_code', 'N/A')}")
                print(f"  - Content Length: {result.get('content_length', 0)}")
                print(f"  - Title: {result.get('title', 'None')[:50]}")
                print(f"  - Headings: {len(result.get('headings', []))}")
                print(f"  - Code Blocks: {result.get('code_blocks', 0)}")

        # Analyze discrepancies
        print("\n⚠️  POTENTIAL ISSUES:")
        print("-" * 40)

        issues = []

        # Compare content lengths
        lengths = {
            method: self.results.get(method, {}).get("content_length", 0)
            for method in ["requests", "aiohttp", "selenium"]
        }
        lengths["docvault"] = self.results.get("docvault", {}).get(
            "extracted_content_length", 0
        )

        max_length = max(lengths.values()) if lengths.values() else 0
        min_length = min(lengths.values()) if lengths.values() else 0

        if max_length > 0 and (max_length - min_length) / max_length > 0.3:
            issues.append(f"Significant content length variation: {lengths}")

        # Check for JavaScript requirements
        if (
            self.results.get("selenium", {}).get("content_length", 0)
            > self.results.get("aiohttp", {}).get("content_length", 0) * 1.5
        ):
            issues.append("Site likely requires JavaScript for full content")

        # Check DocVault detection
        docvault_result = self.results.get("docvault", {})
        if docvault_result.get("detection_confidence", 0) < 0.5:
            issues.append(
                f"Low detection confidence: {docvault_result.get('detection_confidence', 0):.2f}"
            )

        if not issues:
            print("✅ No major issues detected")
        else:
            for issue in issues:
                print(f"⚠️  {issue}")

        # Child pages analysis
        print(f"\n📄 CHILD PAGES ({len(self.child_pages)} total):")
        print("-" * 40)

        successful_child_pages = sum(
            1
            for result in self.results.get("child_pages", {}).values()
            if "error" not in result
        )

        print(f"✅ Successfully analyzed: {successful_child_pages}")
        print(
            f"❌ Failed to analyze: {len(self.results.get('child_pages', {})) - successful_child_pages}"
        )

        if self.results.get("child_pages"):
            avg_content_length = sum(
                result.get("content_length", 0)
                for result in self.results.get("child_pages", {}).values()
                if "error" not in result
            ) / max(successful_child_pages, 1)
            print(f"📊 Average content length: {avg_content_length:.0f} characters")

        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        print("-" * 40)

        recommendations = []

        if "Site likely requires JavaScript" in str(issues):
            recommendations.append(
                "Consider adding JavaScript rendering support (e.g., Playwright/Selenium)"
            )

        if docvault_result.get("detection_confidence", 1) < 0.7:
            recommendations.append(
                "Improve documentation type detection for this site type"
            )

        if len(self.results.get("child_pages", {})) > 10:
            recommendations.append(
                "Implement smart crawling limits for large documentation sites"
            )

        # Check for missing navigation
        nav_methods = sum(
            1
            for method in ["requests", "aiohttp", "selenium"]
            if self.results.get(method, {}).get("has_navigation", False)
        )

        if nav_methods == 0:
            recommendations.append("Site may have non-standard navigation structure")

        if not recommendations:
            recommendations.append("Scraping approach appears adequate for this site")

        for rec in recommendations:
            print(f"💡 {rec}")

        # Save detailed results
        output_file = Path(__file__).parent / "scraping_analysis_results.json"
        with open(output_file, "w") as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"\n📁 Detailed results saved to: {output_file}")


async def main():
    """Main function to run the analysis."""
    if len(sys.argv) != 2:
        print("Usage: python analyze_scraping.py <URL>")
        print(
            "Example: python analyze_scraping.py https://modelcontextprotocol.io/specification/2025-03-26"
        )
        sys.exit(1)

    url = sys.argv[1]
    analyzer = ScrapingAnalyzer(url)
    await analyzer.analyze_all_methods()


if __name__ == "__main__":
    asyncio.run(main())
