"""Next.js documentation extractor for client-side rendered content."""

import json
import re
from typing import Any, List, Optional

from bs4 import BeautifulSoup, Tag

from .base import BaseExtractor


class NextJSExtractor(BaseExtractor):
    """Extractor for Next.js-based documentation sites with MDX content."""

    def extract(self, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        """
        Extract content from Next.js documentation site.

        Args:
            soup: BeautifulSoup parsed HTML
            url: The source URL

        Returns:
            Dictionary with 'content' (markdown string) and 'metadata' (dict)
        """
        # Extract metadata from HTML head
        metadata = self.extract_metadata(soup)

        # Try to extract from __NEXT_DATA__ first
        next_data_content = self._extract_from_next_data(soup)

        if next_data_content:
            content = next_data_content["content"]
            metadata.update(next_data_content["metadata"])

            # Also extract static content and combine if it adds value
            static_content = self._extract_static_content(soup)
            if static_content and len(static_content) > len(content) * 0.5:
                # If static content is substantial, combine it
                combined_content = (
                    f"{content}\n\n## Additional Content\n\n{static_content}"
                )
                content = combined_content
                metadata["combined_extraction"] = True
        else:
            # Fallback to static content extraction
            content = self._extract_static_content(soup)
            metadata["extraction_method"] = "static_fallback"

        # Extract additional structured content
        code_blocks = self._extract_code_blocks(soup)
        if code_blocks:
            metadata["code_blocks"] = code_blocks

        # Extract navigation structure if available
        navigation = self._extract_navigation_structure(soup)
        if navigation:
            metadata["navigation"] = navigation

        return {"content": content, "metadata": metadata}

    def _extract_from_next_data(self, soup: BeautifulSoup) -> dict[str, Any] | None:
        """
        Extract content from __NEXT_DATA__ script.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Dictionary with content and metadata or None if extraction fails
        """
        # Find __NEXT_DATA__ script
        next_data_script = soup.find("script", {"id": "__NEXT_DATA__"})
        if not next_data_script or not next_data_script.string:
            return None

        try:
            next_data = json.loads(next_data_script.string)
            page_props = next_data.get("props", {}).get("pageProps", {})

            content_parts = []
            metadata = {"extraction_method": "next_data"}

            # Extract MDX source
            mdx_content = self._extract_mdx_content(page_props)
            if mdx_content:
                content_parts.append(mdx_content["content"])
                metadata.update(mdx_content["metadata"])

            # Extract table of contents
            toc = self._extract_table_of_contents(page_props)
            if toc:
                metadata["table_of_contents"] = toc

            # Extract code examples
            code_examples = self._extract_code_examples(page_props)
            if code_examples:
                metadata["code_examples"] = code_examples

            # Extract page metadata
            page_metadata = page_props.get("pageMetadata", {})
            if page_metadata:
                metadata["page_title"] = page_metadata.get("title")
                metadata["page_description"] = page_metadata.get("description")

            # Combine all content
            final_content = "\n\n".join(filter(None, content_parts))

            if final_content:
                return {"content": self.clean_text(final_content), "metadata": metadata}

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Log the error but don't fail completely
            metadata = {
                "extraction_method": "next_data_failed",
                "extraction_error": str(e),
            }

        return None

    def _extract_mdx_content(self, page_props: dict[str, Any]) -> dict[str, Any] | None:
        """
        Extract content from MDX source.

        Args:
            page_props: Page properties from Next.js data

        Returns:
            Dictionary with content and metadata or None
        """
        mdx_source = page_props.get("mdxSource", {})
        if not mdx_source:
            return None

        content_parts = []
        metadata = {}

        # Try to extract from compiled source
        compiled_source = mdx_source.get("compiledSource", "")
        if compiled_source:
            extracted_text = self._extract_text_from_compiled_mdx(compiled_source)
            if extracted_text:
                content_parts.append(extracted_text)

        # Extract frontmatter
        frontmatter = mdx_source.get("frontmatter", {})
        if frontmatter:
            metadata["frontmatter"] = frontmatter
            if "title" in frontmatter:
                content_parts.insert(0, f"# {frontmatter['title']}")

        # Extract scope data if available
        scope = mdx_source.get("scope", {})
        if scope:
            metadata["mdx_scope"] = scope

        if content_parts:
            return {"content": "\n\n".join(content_parts), "metadata": metadata}

        return None

    def _extract_text_from_compiled_mdx(self, compiled_source: str) -> str:
        """
        Extract readable text from compiled MDX JavaScript.

        Args:
            compiled_source: Compiled MDX JavaScript code

        Returns:
            Extracted text content
        """
        # This is complex because MDX compiles to React components
        # We need to extract string literals that contain actual content

        content_strings = []

        # Look for children properties with string content
        children_patterns = [
            r'children:\s*"([^"]*)"',  # Single string children
            r"children:\s*\[(.*?)\]",  # Array children (more complex)
        ]

        # Extract simple children strings
        children_matches = re.findall(children_patterns[0], compiled_source)
        for match in children_matches:
            try:
                # Unescape the string
                unescaped = match.encode().decode("unicode_escape")
                if self._is_content_string(unescaped):
                    content_strings.append(unescaped)
            except (UnicodeDecodeError, UnicodeError):
                continue

        # Look for JSX component content with specific patterns
        jsx_patterns = [
            r'_jsx\([^,]+,\s*{\s*children:\s*"([^"]+)"',  # JSX with children
            r"_jsxs\([^,]+,\s*{\s*children:\s*\[(.*?)\]",  # JSX with array children
        ]

        for pattern in jsx_patterns:
            matches = re.findall(pattern, compiled_source, re.DOTALL)
            for match in matches:
                if isinstance(match, str):
                    try:
                        unescaped = match.encode().decode("unicode_escape")
                        if self._is_content_string(unescaped):
                            content_strings.append(unescaped)
                    except (UnicodeDecodeError, UnicodeError):
                        continue

        # Pattern to match all string literals in quotes (fallback)
        string_patterns = [
            r'"((?:[^"\\]|\\.)*)"\s*[,})\]]',  # Double quoted strings
        ]

        for pattern in string_patterns:
            matches = re.findall(pattern, compiled_source)
            for match in matches:
                # Unescape the string
                try:
                    unescaped = match.encode().decode("unicode_escape")
                    # Filter for strings that look like content
                    if self._is_content_string(unescaped):
                        content_strings.append(unescaped)
                except (UnicodeDecodeError, UnicodeError):
                    # Skip strings that can't be properly decoded
                    continue

        # Look for Heading components
        heading_pattern = (
            r'_jsx\(Heading,\s*{\s*level:\s*"(\d+)",.*?children:\s*"([^"]+)"'
        )
        heading_matches = re.findall(heading_pattern, compiled_source)
        for level, text in heading_matches:
            if text and len(text) > 2:
                heading_prefix = "#" * min(int(level), 6)
                content_strings.append(f"{heading_prefix} {text}")

        # Look for multiline string content spread across lines
        multiline_pattern = r'"([^"]*(?:\\n[^"]*)+)"'
        multiline_matches = re.findall(multiline_pattern, compiled_source)
        for match in multiline_matches:
            try:
                unescaped = match.encode().decode("unicode_escape")
                # Clean up the content
                clean_content = unescaped.replace("\\n", "\n").strip()
                if len(clean_content) > 50 and "\n" in clean_content:
                    content_strings.append(clean_content)
            except (UnicodeDecodeError, UnicodeError):
                continue

        # Remove duplicates while preserving order
        seen = set()
        unique_strings = []
        for s in content_strings:
            normalized = s.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_strings.append(normalized)

        return "\n\n".join(unique_strings)

    def _is_content_string(self, text: str) -> bool:
        """
        Check if a string looks like documentation content.

        Args:
            text: String to check

        Returns:
            True if it looks like content, False otherwise
        """
        # Filter criteria for content strings
        return (
            len(text) >= 5  # Minimum length (reduced for titles)
            and not text.startswith("_")  # Not internal variables
            and not text.startswith("function")  # Not function code
            and not text.startswith("const")  # Not variable declarations
            and not text.startswith("import")  # Not imports
            and not re.match(r"^[A-Z_]+$", text)  # Not constants
            and not re.match(r"^[a-z]+\([^)]*\)$", text)  # Not function calls
            and not re.search(
                r"\w+\(.*\);?$", text
            )  # Not code calls like "console.log(...)"
            and text.count('"') < 3  # Not nested quotes
            and not text.startswith("http")  # Not URLs
            and (
                # Has punctuation OR contains spaces OR looks like a title
                "." in text
                or "," in text
                or "!" in text
                or "?" in text
                or " " in text  # Multi-word content
                or (
                    len(text) > 3
                    and len(text) <= 20
                    and text[0].isupper()
                    and text.isalnum()
                    and not text.isupper()
                )  # Title-like (reasonable length, starts with capital, not all caps)
            )
        )

    def _extract_table_of_contents(
        self, page_props: dict[str, Any]
    ) -> list[dict[str, Any]] | None:
        """
        Extract table of contents from page properties.

        Args:
            page_props: Page properties from Next.js data

        Returns:
            List of TOC entries or None
        """
        mdx_extracts = page_props.get("mdxExtracts", {})
        toc = mdx_extracts.get("tableOfContents", [])

        if toc and isinstance(toc, list):
            # Clean up and structure the TOC
            structured_toc = []
            for item in toc:
                if isinstance(item, dict):
                    toc_entry = {
                        "title": item.get("title", ""),
                        "slug": item.get("slug", ""),
                        "depth": item.get("depth", 1),
                    }
                    if "children" in item:
                        toc_entry["children"] = item["children"]
                    structured_toc.append(toc_entry)

            return structured_toc if structured_toc else None

        return None

    def _extract_code_examples(
        self, page_props: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Extract code examples from page properties.

        Args:
            page_props: Page properties from Next.js data

        Returns:
            Code examples dictionary or None
        """
        mdx_extracts = page_props.get("mdxExtracts", {})
        code_examples = mdx_extracts.get("codeExamples", {})

        if code_examples and isinstance(code_examples, dict):
            return code_examples

        return None

    def _extract_static_content(self, soup: BeautifulSoup) -> str:
        """
        Fallback method to extract static content when Next.js data isn't available.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Extracted text content
        """
        # Try common Next.js content selectors
        content_selectors = [
            "main",
            "div#__next",
            "div[data-reactroot]",
            "article",
            "div.content",
        ]

        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                return self._clean_static_content(content_elem)

        # Final fallback to body
        body = soup.find("body")
        return self._clean_static_content(body) if body else ""

    def _clean_static_content(self, element: Tag) -> str:
        """
        Clean static HTML content for text extraction.

        Args:
            element: BeautifulSoup element

        Returns:
            Cleaned text content
        """
        if not element:
            return ""

        # Clone to avoid modifying original
        element = element.__copy__()

        # Remove script and style tags
        for tag in element(["script", "style", "noscript"]):
            tag.decompose()

        # Remove navigation elements that aren't content
        for nav in element.select("nav, aside, .sidebar, .navigation, header, footer"):
            # Keep if it looks like a content navigation (TOC)
            nav_text = nav.get_text(strip=True)
            if len(nav_text) < 500 or not any(
                word in nav_text.lower() for word in ["contents", "overview", "guide"]
            ):
                nav.decompose()

        # Convert to text
        text = element.get_text(separator="\n")
        return self.clean_text(text)

    def _extract_navigation_structure(
        self, soup: BeautifulSoup
    ) -> list[dict[str, Any]] | None:
        """
        Extract navigation structure from the page.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Navigation structure or None
        """
        nav_elements = soup.find_all("nav")
        navigation = []

        for nav in nav_elements:
            # Look for navigation links
            links = nav.find_all("a", href=True)
            if len(links) > 3:  # Has multiple links, likely a navigation
                nav_items = []
                for link in links[:20]:  # Limit to prevent too much data
                    text = link.get_text(strip=True)
                    href = link.get("href")
                    if text and href:
                        nav_items.append({"title": text, "href": href})

                if nav_items:
                    navigation.append({"type": "navigation", "items": nav_items})

        return navigation if navigation else None

    def _extract_code_blocks(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """
        Extract code blocks from static HTML.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            List of code block dictionaries
        """
        code_blocks = []

        # Look for pre/code combinations
        for pre in soup.find_all("pre"):
            code = pre.find("code") or pre
            code_text = code.get_text(strip=True)

            if not code_text or len(code_text) < 10:
                continue

            # Try to detect language
            language = None
            for cls in code.get("class", []):
                if cls.startswith("language-"):
                    language = cls.replace("language-", "")
                    break

            code_blocks.append(
                {
                    "type": "code",
                    "language": language or "text",
                    "content": code_text,
                }
            )

        return code_blocks
