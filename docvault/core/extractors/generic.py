"""Generic content extractor for unspecified documentation types."""

from typing import Any, Dict, List

from bs4 import BeautifulSoup, Tag

from .base import BaseExtractor


class GenericExtractor(BaseExtractor):
    """Generic extractor for unknown documentation types."""

    def extract(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract content using generic patterns."""
        # Extract metadata
        metadata = self.extract_metadata(soup)

        # Extract main content
        content = self._extract_main_content(soup)

        # Extract code blocks
        code_blocks = self._extract_code_blocks(soup)
        if code_blocks:
            metadata["code_blocks"] = code_blocks

        # Extract tables
        tables = self._extract_tables(soup)
        if tables:
            metadata["tables"] = tables

        return {"content": content, "metadata": metadata}

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract the main content area."""
        # Try common content selectors
        content_selectors = [
            "main",
            "article",
            '[role="main"]',
            ".content",
            ".main",
            "#content",
            ".documentation",
            ".doc-content",
        ]

        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                return self._clean_content(content_elem)

        # Fallback to body
        body = soup.find("body")
        return self._clean_content(body) if body else ""

    def _extract_code_blocks(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract code blocks from the page."""
        code_blocks = []

        # Look for pre/code combinations
        for pre in soup.find_all("pre"):
            code = pre.find("code")
            if code:
                # Try to detect language
                language = None
                for cls in code.get("class", []):
                    if cls.startswith("language-"):
                        language = cls.replace("language-", "")
                        break

                code_blocks.append(
                    {
                        "type": "code",
                        "language": language,
                        "content": code.get_text(strip=True),
                    }
                )

        return code_blocks

    def _extract_tables(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract tables from the page."""
        tables = []

        for table in soup.find_all("table"):
            # Extract headers
            headers = []
            header_row = table.find("thead")
            if header_row:
                for th in header_row.find_all("th"):
                    headers.append(th.get_text(strip=True))
            else:
                # Try first row
                first_row = table.find("tr")
                if first_row:
                    for th in first_row.find_all("th"):
                        headers.append(th.get_text(strip=True))

            # Extract rows
            rows = []
            tbody = table.find("tbody") or table
            for tr in tbody.find_all("tr"):
                cells = []
                for td in tr.find_all(["td", "th"]):
                    cells.append(td.get_text(strip=True))
                if cells and (not headers or len(cells) == len(headers)):
                    rows.append(cells)

            if rows:
                tables.append({"headers": headers, "rows": rows})

        return tables

    def _clean_content(self, element: Tag) -> str:
        """Clean and convert HTML content to text."""
        if not element:
            return ""

        # Clone to avoid modifying original
        element = element.__copy__()

        # Remove script and style tags
        for tag in element(["script", "style"]):
            tag.decompose()

        # Remove navigation elements
        for nav in element.select("nav, aside, .sidebar, .navigation"):
            nav.decompose()

        # Convert to text
        text = element.get_text(separator="\n")

        # Clean up whitespace
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if line:
                lines.append(line)

        return "\n\n".join(lines)
