"""
Sphinx documentation extractor.
"""

import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from .base import BaseExtractor


class SphinxExtractor(BaseExtractor):
    """Extractor specialized for Sphinx documentation."""

    def extract(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Extract content from Sphinx documentation.

        Args:
            soup: BeautifulSoup parsed HTML
            url: The source URL

        Returns:
            Dictionary with 'content' (markdown string) and 'metadata' (dict)
        """
        # Extract metadata
        metadata = self.extract_metadata(soup)

        # Find main content area
        content_area = soup.select_one("div.body") or soup.select_one("div.document")
        if not content_area:
            content_area = soup.body or soup

        # Convert content to markdown
        content = self._convert_to_markdown(content_area)

        # Extract additional structured data for metadata
        if self.config.get("extract_api_signatures", True):
            api_elements = self._extract_api_elements(content_area, metadata)
            if api_elements:
                metadata["api_elements"] = api_elements

        # Extract code examples
        code_examples = self._extract_code_examples(content_area, metadata)
        if code_examples:
            metadata["code_examples"] = code_examples

        # Extract warnings and notes
        admonitions = self._extract_admonitions(content_area, metadata)
        if admonitions:
            metadata["admonitions"] = admonitions

        return {"content": content, "metadata": metadata}

    def extract_navigation(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Extract Sphinx navigation/TOC.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Navigation structure or None
        """
        # Look for Sphinx sidebar
        sidebar = soup.select_one("div.sphinxsidebar") or soup.select_one(
            "div.sphinxsidebarwrapper"
        )

        if sidebar:
            toc = self._extract_toc_tree(sidebar)
            if toc:
                return toc

        # Look for inline toctree
        toctree = soup.select_one("div.toctree-wrapper")
        if toctree:
            return self._extract_toc_tree(toctree)

        return None

    def _extract_api_elements(
        self, content: BeautifulSoup, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract API documentation elements."""
        segments = []

        # API element selectors
        api_selectors = self.config.get(
            "api_selector",
            "dl.class, dl.function, dl.method, dl.attribute, dl.exception, dl.module",
        ).split(", ")

        for selector in api_selectors:
            for elem in content.select(selector):
                # Extract signature
                sig_elem = elem.select_one("dt")
                if not sig_elem:
                    continue

                # Get the API type
                api_type = selector.split(".")[-1]

                # Extract name
                name_elem = sig_elem.select_one("span.sig-name, code.descname")
                name = name_elem.get_text(strip=True) if name_elem else "Unknown"

                # Extract full signature
                signature = self._clean_signature(sig_elem.get_text(strip=True))

                # Extract description
                desc_elem = elem.select_one("dd")
                description = desc_elem.get_text(strip=True) if desc_elem else ""

                # Extract parameters if present
                params = self._extract_parameters(desc_elem) if desc_elem else []

                # Extract return type
                return_info = (
                    self._extract_return_info(desc_elem) if desc_elem else None
                )

                segments.append(
                    {
                        "type": "api",
                        "api_type": api_type,
                        "name": name,
                        "signature": signature,
                        "description": self.clean_text(description),
                        "parameters": params,
                        "return_info": return_info,
                        "metadata": metadata,
                    }
                )

        return segments

    def _extract_sphinx_sections(
        self, content: BeautifulSoup, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract regular content sections."""
        segments = []

        # Find all section divs
        sections = content.select("div.section, section")

        if not sections:
            # Fall back to header-based extraction
            return self.extract_sections(content)

        for section in sections:
            # Get section ID and title
            section_id = section.get("id", "")

            # Find section header
            header = section.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            if not header:
                continue

            title = header.get_text(strip=True)
            level = int(header.name[1])

            # Extract section content
            content_parts = []
            for elem in section.children:
                if elem == header:
                    continue
                if (
                    hasattr(elem, "name")
                    and elem.name in ["div"]
                    and "section" in elem.get("class", [])
                ):
                    # Skip nested sections
                    continue
                if hasattr(elem, "get_text"):
                    text = elem.get_text(strip=True)
                    if text:
                        content_parts.append(text)

            content_text = "\n".join(content_parts)

            segments.append(
                {
                    "type": "section",
                    "id": section_id,
                    "title": title,
                    "level": level,
                    "content": self.clean_text(content_text),
                    "metadata": metadata,
                }
            )

        return segments

    def _extract_code_examples(
        self, content: BeautifulSoup, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract code examples with language detection."""
        segments = []

        # Sphinx code block selectors
        code_selectors = [
            "div.highlight pre",
            "pre.literal-block",
            "div.doctest-block",
        ]

        for selector in code_selectors:
            for elem in content.select(selector):
                code_text = elem.get_text(strip=True)
                if not code_text:
                    continue

                # Detect language from parent div classes
                language = "text"
                parent = elem.parent
                if parent and parent.name == "div":
                    classes = parent.get("class", [])
                    for cls in classes:
                        if cls.startswith("highlight-"):
                            language = cls.replace("highlight-", "")
                            break

                # Check if it's a doctest
                if "doctest" in selector or ">>>" in code_text:
                    language = "python-doctest"

                segments.append(
                    {
                        "type": "code_example",
                        "language": language,
                        "content": code_text,
                        "metadata": metadata,
                    }
                )

        return segments

    def _extract_admonitions(
        self, content: BeautifulSoup, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract warnings, notes, and other admonitions."""
        segments = []

        # Sphinx admonition classes
        admonition_types = [
            "warning",
            "note",
            "tip",
            "important",
            "caution",
            "danger",
            "error",
            "hint",
            "attention",
            "seealso",
        ]

        for admon_type in admonition_types:
            for elem in content.select(
                f"div.{admon_type}, div.admonition.{admon_type}"
            ):
                # Get title
                title_elem = elem.select_one("p.admonition-title")
                title = (
                    title_elem.get_text(strip=True)
                    if title_elem
                    else admon_type.title()
                )

                # Get content
                content_text = elem.get_text(strip=True)
                if title_elem:
                    content_text = content_text.replace(title, "", 1).strip()

                segments.append(
                    {
                        "type": "admonition",
                        "admonition_type": admon_type,
                        "title": title,
                        "content": self.clean_text(content_text),
                        "metadata": metadata,
                    }
                )

        return segments

    def _extract_toc_tree(self, toc_elem: BeautifulSoup) -> Dict[str, Any]:
        """Extract table of contents tree."""
        links = []

        for link in toc_elem.find_all("a", href=True):
            # Get nesting level based on parent list depth
            level = 0
            parent = link.parent
            while parent and parent != toc_elem:
                if parent.name in ["ul", "ol"]:
                    level += 1
                parent = parent.parent

            links.append(
                {
                    "text": link.get_text(strip=True),
                    "href": link["href"],
                    "level": level,
                }
            )

        return {
            "type": "navigation",
            "structure": "tree",
            "links": links,
        }

    def _clean_signature(self, signature: str) -> str:
        """Clean API signature text."""
        # Remove extra whitespace
        signature = " ".join(signature.split())

        # Remove permalink symbols
        signature = re.sub(r"¶\s*$", "", signature)

        return signature.strip()

    def _extract_parameters(self, desc_elem: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract parameter information from description."""
        params = []

        # Look for parameter list
        param_list = desc_elem.select_one("dl.field-list")
        if not param_list:
            return params

        # Extract each parameter
        for field in param_list.select("dt"):
            param_name = field.get_text(strip=True)

            # Get parameter description
            desc = field.find_next_sibling("dd")
            param_desc = desc.get_text(strip=True) if desc else ""

            # Parse parameter name and type
            match = re.match(r"(\w+)\s*\((.*?)\)", param_name)
            if match:
                name, param_type = match.groups()
                params.append(
                    {
                        "name": name,
                        "type": param_type,
                        "description": param_desc,
                    }
                )
            else:
                params.append(
                    {
                        "name": param_name,
                        "description": param_desc,
                    }
                )

        return params

    def _extract_return_info(
        self, desc_elem: BeautifulSoup
    ) -> Optional[Dict[str, str]]:
        """Extract return type information."""
        # Look for return type in field list
        field_list = desc_elem.select_one("dl.field-list")
        if not field_list:
            return None

        for field in field_list.select("dt"):
            if "return" in field.get_text(strip=True).lower():
                desc = field.find_next_sibling("dd")
                if desc:
                    return {
                        "type": field.get_text(strip=True),
                        "description": desc.get_text(strip=True),
                    }

        return None

    def _convert_to_markdown(self, content_area: BeautifulSoup) -> str:
        """
        Convert Sphinx HTML content to Markdown.

        Args:
            content_area: BeautifulSoup element containing the content

        Returns:
            Markdown formatted string
        """
        # Import markdown converter
        import html2text

        # Remove navigation elements
        for nav in content_area.select(
            "div.sphinxsidebar, div.navigation, div.related"
        ):
            nav.decompose()

        # Configure html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.body_width = 0  # Don't wrap lines

        # Convert to markdown
        markdown = h.handle(str(content_area))

        # Clean up excessive whitespace
        lines = markdown.split("\n")
        cleaned_lines = []
        empty_count = 0

        for line in lines:
            if line.strip():
                cleaned_lines.append(line)
                empty_count = 0
            else:
                empty_count += 1
                if empty_count <= 2:  # Allow max 2 consecutive empty lines
                    cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()
