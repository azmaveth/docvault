"""
Documentation type detection for specialized content extraction.
"""

import re
from enum import Enum

from bs4 import BeautifulSoup


class DocType(Enum):
    """Supported documentation types."""

    SPHINX = "sphinx"
    MKDOCS = "mkdocs"
    OPENAPI = "openapi"
    SWAGGER = "swagger"
    READTHEDOCS = "readthedocs"
    GITHUB = "github"
    NEXTJS = "nextjs"
    GENERIC = "generic"


class DocTypeDetector:
    """Detect documentation type from HTML content and URL patterns."""

    # URL patterns that indicate documentation type
    URL_PATTERNS = {
        DocType.READTHEDOCS: [
            r"\.readthedocs\.io",
            r"readthedocs\.org",
        ],
        DocType.GITHUB: [
            r"github\.com/[^/]+/[^/]+/(blob|tree|wiki)",
            r"raw\.githubusercontent\.com",
        ],
        DocType.SWAGGER: [
            r"/swagger",
            r"/api-docs",
            r"/swagger-ui",
        ],
        DocType.OPENAPI: [
            r"/openapi",
            r"/api/v\d+/docs",
        ],
    }

    # HTML signatures that indicate documentation type
    HTML_SIGNATURES = {
        DocType.SPHINX: [
            ("meta", {"name": "generator", "content": re.compile(r"Sphinx", re.I)}),
            ("div", {"class": re.compile(r"sphinx", re.I)}),
            ("link", {"href": re.compile(r"_static/pygments\.css")}),
            ("script", {"src": re.compile(r"_static/sphinx")}),
        ],
        DocType.MKDOCS: [
            ("meta", {"name": "generator", "content": re.compile(r"MkDocs", re.I)}),
            ("nav", {"class": re.compile(r"md-header")}),
            ("div", {"class": re.compile(r"mkdocs", re.I)}),
            ("link", {"href": re.compile(r"assets/stylesheets/main\.")}),
        ],
        DocType.OPENAPI: [
            ("div", {"id": "swagger-ui"}),
            ("script", {"src": re.compile(r"swagger-ui")}),
            ("link", {"href": re.compile(r"swagger-ui\.css")}),
        ],
        DocType.READTHEDOCS: [
            ("div", {"class": "rst-content"}),
            ("div", {"class": "wy-nav-content"}),
            ("nav", {"data-toggle": "wy-nav-shift"}),
        ],
        DocType.NEXTJS: [
            ("script", {"id": "__NEXT_DATA__"}),
            ("script", {"src": re.compile(r"/_next/")}),
            ("meta", {"name": "generator", "content": re.compile(r"Next\.js", re.I)}),
            ("div", {"id": "__next"}),
        ],
    }

    # Content patterns that indicate documentation type
    CONTENT_PATTERNS = {
        DocType.SPHINX: [
            r'<div class="toctree-wrapper',
            r'<dl class="(class|function|method|attribute)"',
            r'<span class="sig-name descname"',
        ],
        DocType.MKDOCS: [
            r'<div class="md-sidebar',
            r'<article class="md-content__inner',
            r'<nav class="md-nav',
        ],
        DocType.OPENAPI: [
            r'"openapi":\s*"3\.',
            r'"swagger":\s*"2\.',
            r'"paths":\s*{',
            r'"definitions":\s*{',
        ],
        DocType.NEXTJS: [
            r'"props":\s*{\s*"pageProps"',
            r'"mdxSource":\s*{',
            r'"compiledSource":\s*"',
            r"__NEXT_DATA__",
        ],
    }

    def __init__(self):
        """Initialize the detector."""
        self._cache = {}

    def detect(self, url: str, html_content: str) -> tuple[DocType, float]:
        """
        Detect documentation type from URL and HTML content.

        Args:
            url: The URL of the documentation
            html_content: The HTML content of the page

        Returns:
            Tuple of (DocType, confidence_score)
        """
        # Check cache first
        cache_key = f"{url}:{hash(html_content[:1000])}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        scores = {}

        # Check URL patterns
        url_type = self._detect_by_url(url)
        if url_type:
            scores[url_type] = scores.get(url_type, 0) + 0.5

        # Parse HTML
        soup = BeautifulSoup(html_content, "html.parser")

        # Check HTML signatures
        html_type = self._detect_by_html_signatures(soup)
        if html_type:
            scores[html_type] = scores.get(html_type, 0) + 0.7

        # Check content patterns
        content_type = self._detect_by_content_patterns(html_content)
        if content_type:
            scores[content_type] = scores.get(content_type, 0) + 0.3

        # Check specific indicators
        if self._is_api_documentation(soup, html_content):
            for api_type in [DocType.OPENAPI, DocType.SWAGGER]:
                scores[api_type] = scores.get(api_type, 0) + 0.2

        # Determine the best match
        if scores:
            best_type = max(scores.items(), key=lambda x: x[1])
            result = (best_type[0], min(best_type[1], 1.0))
        else:
            result = (DocType.GENERIC, 0.0)

        # Cache the result
        self._cache[cache_key] = result
        return result

    def _detect_by_url(self, url: str) -> DocType | None:
        """Detect documentation type by URL patterns."""
        url_lower = url.lower()

        for doc_type, patterns in self.URL_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return doc_type

        return None

    def _detect_by_html_signatures(self, soup: BeautifulSoup) -> DocType | None:
        """Detect documentation type by HTML signatures."""
        for doc_type, signatures in self.HTML_SIGNATURES.items():
            matches = 0
            for tag_name, attrs in signatures:
                if soup.find(tag_name, attrs=attrs):
                    matches += 1

            # If we have multiple matches, it's likely this type
            if matches >= 2:
                return doc_type

        return None

    def _detect_by_content_patterns(self, html_content: str) -> DocType | None:
        """Detect documentation type by content patterns."""
        for doc_type, patterns in self.CONTENT_PATTERNS.items():
            matches = 0
            for pattern in patterns:
                if re.search(pattern, html_content, re.IGNORECASE):
                    matches += 1

            # If we have multiple matches, it's likely this type
            if matches >= 2:
                return doc_type

        return None

    def _is_api_documentation(self, soup: BeautifulSoup, html_content: str) -> bool:
        """Check if this appears to be API documentation."""
        api_indicators = [
            # Common API doc elements
            soup.find("div", class_=re.compile(r"endpoint|operation|api-method")),
            soup.find(
                "span", class_=re.compile(r"http-method|method-(get|post|put|delete)")
            ),
            # OpenAPI/Swagger specific
            "swagger" in html_content.lower(),
            "openapi" in html_content.lower(),
            "/api/v" in html_content,
            # API response examples
            bool(soup.find("pre", string=re.compile(r'^\s*{\s*"', re.MULTILINE))),
            bool(re.search(r'"responses":\s*{', html_content)),
        ]

        # If we have multiple indicators, it's likely API documentation
        return sum(bool(indicator) for indicator in api_indicators) >= 3

    def get_extractor_config(self, doc_type: DocType) -> dict[str, any]:
        """
        Get configuration for specialized extractors based on doc type.

        Args:
            doc_type: The detected documentation type

        Returns:
            Configuration dictionary for the extractor
        """
        configs = {
            DocType.SPHINX: {
                "content_selector": "div.body, div.document",
                "navigation_selector": "div.sphinxsidebar, div.toctree-wrapper",
                "code_selector": "div.highlight pre, pre.literal-block",
                "api_selector": "dl.class, dl.function, dl.method",
                "title_selector": "h1, div.section > h1",
                "extract_api_signatures": True,
                "preserve_hierarchy": True,
            },
            DocType.MKDOCS: {
                "content_selector": "article.md-content__inner, div.content",
                "navigation_selector": "nav.md-nav, div.md-sidebar",
                "code_selector": "pre code, div.codehilite pre",
                "title_selector": "h1.md-header__title, article h1",
                "extract_tabs": True,
                "preserve_admonitions": True,
            },
            DocType.OPENAPI: {
                "extract_json": True,
                "parse_endpoints": True,
                "extract_schemas": True,
                "group_by_tags": True,
                "include_examples": True,
            },
            DocType.READTHEDOCS: {
                "content_selector": "div.rst-content, div.wy-nav-content",
                "navigation_selector": "div.wy-menu, div.toctree-wrapper",
                "code_selector": "div.highlight pre, pre.literal-block",
                "api_selector": "dl.class, dl.function, dl.method, dl.describe",
                "warning_selector": "div.admonition",
                "preserve_hierarchy": True,
            },
            DocType.GITHUB: {
                "content_selector": "article, div.markdown-body, div.wiki-body",
                "code_selector": "pre code, div.highlight pre",
                "extract_readme": True,
                "follow_doc_links": True,
                "max_depth": 2,
            },
            DocType.NEXTJS: {
                "parse_next_data": True,
                "extract_mdx_source": True,
                "extract_page_props": True,
                "content_selector": "main, div#__next",
                "fallback_to_static": True,
                "extract_table_of_contents": True,
                "extract_code_examples": True,
            },
            DocType.GENERIC: {
                "content_selector": "main, article, div.content, body",
                "code_selector": "pre, code",
                "navigation_selector": "nav, aside",
                "title_selector": "h1, h2",
            },
        }

        return configs.get(doc_type, configs[DocType.GENERIC])

    def get_content_patterns(self, doc_type: DocType) -> dict[str, list[str]]:
        """
        Get content patterns to look for based on doc type.

        Args:
            doc_type: The detected documentation type

        Returns:
            Dictionary of pattern categories and their patterns
        """
        patterns = {
            DocType.SPHINX: {
                "api_elements": [
                    "dl.class",
                    "dl.function",
                    "dl.method",
                    "dl.attribute",
                    "dl.exception",
                    "dl.module",
                    "dl.data",
                ],
                "navigation": ["div.toctree-wrapper", "div.sphinxsidebarwrapper"],
                "examples": ["div.highlight-python", "div.doctest-block"],
                "warnings": ["div.warning", "div.note", "div.admonition"],
            },
            DocType.MKDOCS: {
                "api_elements": ["div.doc-class", "div.doc-function"],
                "navigation": ["nav.md-nav--primary", "div.md-sidebar--primary"],
                "examples": ["div.codehilite", "pre.codehilite"],
                "tabs": ["div.tabbed-set", "div.superfences-tabs"],
            },
            DocType.OPENAPI: {
                "endpoints": ["div.opblock", "div.operation"],
                "schemas": ["div.model-box", "section.models"],
                "examples": ["div.example", "pre.microlight"],
                "parameters": ["table.parameters", "div.parameter"],
            },
        }

        return patterns.get(
            doc_type,
            {
                "content": ["p", "div", "section"],
                "code": ["pre", "code"],
                "navigation": ["nav", "aside"],
            },
        )
