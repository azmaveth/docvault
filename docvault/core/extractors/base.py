"""
Base extractor class for content extraction.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from bs4 import BeautifulSoup


class BaseExtractor(ABC):
    """Base class for all content extractors."""

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the extractor.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

    @abstractmethod
    def extract(self, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        """
        Extract content from the parsed HTML.

        Args:
            soup: BeautifulSoup parsed HTML
            url: The source URL

        Returns:
            Dictionary with 'content' (markdown string) and 'metadata' (dict)
        """
        pass

    def extract_metadata(self, soup: BeautifulSoup) -> dict[str, Any]:
        """
        Extract metadata from the page.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Metadata dictionary
        """
        metadata = {}

        # Extract title
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text(strip=True)

        # Extract meta tags
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property")
            content = meta.get("content")
            if name and content:
                # Normalize common metadata fields
                if name == "description":
                    metadata["description"] = content
                elif name == "keywords":
                    metadata["keywords"] = content
                elif name == "author":
                    metadata["author"] = content
                else:
                    metadata[f"meta_{name}"] = content

        # Extract version if present
        version_selectors = [
            "div.version",
            "span.version",
            "select.version-select option[selected]",
        ]
        for selector in version_selectors:
            version_elem = soup.select_one(selector)
            if version_elem:
                metadata["version"] = version_elem.get_text(strip=True)
                break

        return metadata

    def clean_text(self, text: str) -> str:
        """
        Clean extracted text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)

        # Join with single newlines
        cleaned = "\n".join(cleaned_lines)

        # Remove multiple consecutive newlines
        while "\n\n\n" in cleaned:
            cleaned = cleaned.replace("\n\n\n", "\n\n")

        return cleaned.strip()

    def extract_code_blocks(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """
        Extract code blocks from the content.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            List of code block dictionaries
        """
        code_blocks = []

        # Common code block selectors
        selectors = self.config.get("code_selector", "pre, code").split(", ")

        for selector in selectors:
            for i, elem in enumerate(soup.select(selector)):
                code_text = elem.get_text(strip=True)
                if not code_text:
                    continue

                # Try to detect language
                language = None
                classes = elem.get("class", [])
                if isinstance(classes, str):
                    classes = [classes]

                for cls in classes:
                    if cls.startswith("language-"):
                        language = cls.replace("language-", "")
                        break
                    elif cls in ["python", "javascript", "java", "cpp", "go", "rust"]:
                        language = cls
                        break

                # Check parent for language hints
                if not language and elem.parent:
                    parent_classes = elem.parent.get("class", [])
                    if isinstance(parent_classes, str):
                        parent_classes = [parent_classes]
                    for cls in parent_classes:
                        if "highlight-" in cls:
                            language = cls.split("highlight-")[1]
                            break

                code_blocks.append(
                    {
                        "type": "code",
                        "content": code_text,
                        "language": language or "text",
                        "index": i,
                    }
                )

        return code_blocks

    def extract_sections(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """
        Extract sections based on headers.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            List of section dictionaries
        """
        sections = []
        headers = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

        for i, header in enumerate(headers):
            level = int(header.name[1])
            title = header.get_text(strip=True)

            # Get content between this header and the next
            content_parts = []
            current = header.next_sibling

            while current:
                # Stop at next header
                if hasattr(current, "name") and current.name in [
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                ]:
                    break

                if hasattr(current, "get_text"):
                    text = current.get_text(strip=True)
                    if text:
                        content_parts.append(text)
                elif isinstance(current, str):
                    text = current.strip()
                    if text:
                        content_parts.append(text)

                current = current.next_sibling

            content = "\n".join(content_parts)

            sections.append(
                {
                    "type": "section",
                    "title": title,
                    "level": level,
                    "content": self.clean_text(content),
                    "index": i,
                }
            )

        return sections

    def segment_content(
        self, segments: list[dict[str, Any]], max_size: int = 8000
    ) -> list[dict[str, Any]]:
        """
        Segment content into smaller chunks if needed.

        Args:
            segments: List of content segments
            max_size: Maximum size for each segment

        Returns:
            List of sized segments
        """
        sized_segments = []

        for segment in segments:
            content = segment.get("content", "")

            if len(content) <= max_size:
                sized_segments.append(segment)
            else:
                # Split large segments
                chunks = self._split_text(content, max_size)
                for i, chunk in enumerate(chunks):
                    chunk_segment = segment.copy()
                    chunk_segment["content"] = chunk
                    chunk_segment["chunk_index"] = i
                    chunk_segment["total_chunks"] = len(chunks)
                    sized_segments.append(chunk_segment)

        return sized_segments

    def _split_text(self, text: str, max_size: int) -> list[str]:
        """
        Split text into chunks of maximum size.

        Args:
            text: Text to split
            max_size: Maximum chunk size

        Returns:
            List of text chunks
        """
        # Try to split on paragraph boundaries
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para)

            if current_size + para_size > max_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size + 2  # Account for \n\n

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        # If we still have chunks that are too large, split them further
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= max_size:
                final_chunks.append(chunk)
            else:
                # Split on sentence boundaries
                sentences = chunk.split(". ")
                sub_chunks = []
                current_sub = []
                current_size = 0

                for sent in sentences:
                    sent_size = len(sent)
                    if current_size + sent_size > max_size and current_sub:
                        sub_chunks.append(". ".join(current_sub) + ".")
                        current_sub = [sent]
                        current_size = sent_size
                    else:
                        current_sub.append(sent)
                        current_size += sent_size + 2

                if current_sub:
                    sub_chunks.append(". ".join(current_sub))

                final_chunks.extend(sub_chunks)

        return final_chunks

    def _clean_content(self, element) -> str:
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
