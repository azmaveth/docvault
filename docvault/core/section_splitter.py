"""
Enhanced section-aware document splitting logic.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from bs4 import BeautifulSoup, NavigableString, Tag


@dataclass
class DocumentSection:
    """Represents a section with its content and metadata."""

    title: str
    level: int
    content: str
    path: str
    parent_path: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def parent_id_path(self) -> Optional[str]:
        """Get parent path from current path."""
        if not self.parent_path:
            parts = self.path.split(".")
            if len(parts) > 1:
                return ".".join(parts[:-1])
        return self.parent_path


class SectionSplitter:
    """
    Split documents into hierarchical sections based on headers.

    Supports both HTML and Markdown documents.
    """

    # Common section patterns in documentation
    COMMON_SECTIONS = {
        "overview": ["overview", "introduction", "getting started", "about"],
        "installation": ["installation", "install", "setup", "requirements"],
        "usage": ["usage", "examples", "quick start", "tutorial"],
        "api": ["api", "reference", "methods", "functions", "classes"],
        "configuration": ["configuration", "config", "settings", "options"],
        "faq": ["faq", "frequently asked questions", "troubleshooting"],
        "changelog": ["changelog", "release notes", "history", "versions"],
    }

    def __init__(self, max_section_size: int = 8000, min_section_size: int = 100):
        """
        Initialize the splitter.

        Args:
            max_section_size: Maximum size for a section in characters
            min_section_size: Minimum size to create a separate section
        """
        self.max_section_size = max_section_size
        self.min_section_size = min_section_size

    def split_document(
        self, content: str, content_type: str = "html"
    ) -> List[DocumentSection]:
        """
        Split a document into sections based on headers.

        Args:
            content: Document content (HTML or Markdown)
            content_type: Type of content ('html' or 'markdown')

        Returns:
            List of DocumentSection objects
        """
        if content_type == "markdown":
            return self._split_markdown(content)
        else:
            return self._split_html(content)

    def _split_html(self, html_content: str) -> List[DocumentSection]:
        """Split HTML document into sections."""
        soup = BeautifulSoup(html_content, "html.parser")
        sections = []

        # Find all headers
        headers = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

        if not headers:
            # No headers found, return entire content as one section
            return [
                DocumentSection(
                    title="Document",
                    level=1,
                    content=soup.get_text(strip=True),
                    path="1",
                )
            ]

        # Track section hierarchy
        section_counters = [0] * 6  # For h1-h6

        # Process each header and its content
        for header in headers:
            level = int(header.name[1])  # h1 -> 1, h2 -> 2, etc.
            title = header.get_text(strip=True)

            # Update section counters
            section_counters[level - 1] += 1
            # Reset deeper level counters
            for j in range(level, 6):
                section_counters[j] = 0

            # Build section path
            path_parts = []
            for j in range(level):
                if section_counters[j] > 0:
                    path_parts.append(str(section_counters[j]))
            path = ".".join(path_parts)

            # Get content between this header and the next
            content_elements = []
            current = header.next_sibling

            while current:
                # Stop at next header of same or higher level
                if isinstance(current, Tag) and current.name in [
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                ]:
                    next_level = int(current.name[1])
                    if next_level <= level:
                        break

                if isinstance(current, (Tag, NavigableString)):
                    text = (
                        current.get_text(strip=True)
                        if hasattr(current, "get_text")
                        else str(current).strip()
                    )
                    if text:
                        content_elements.append(text)

                current = current.next_sibling

            content = "\n".join(content_elements)

            # Determine parent path
            parent_path = None
            if len(path_parts) > 1:
                parent_path = ".".join(path_parts[:-1])

            # Create section
            section = DocumentSection(
                title=title,
                level=level,
                content=content,
                path=path,
                parent_path=parent_path,
                metadata=self._extract_metadata(title),
            )

            # Handle large sections by splitting them
            if len(content) > self.max_section_size:
                sections.extend(self._split_large_section(section))
            elif len(content) >= self.min_section_size or not content:
                # Include empty sections to maintain structure
                sections.append(section)

        return sections

    def _split_markdown(self, markdown_content: str) -> List[DocumentSection]:
        """Split Markdown document into sections."""
        lines = markdown_content.split("\n")
        sections = []

        # Track section hierarchy
        section_counters = [0] * 6  # For h1-h6
        current_section = None
        current_content = []

        for line in lines:
            # Check if line is a header
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)

            if header_match:
                # Save previous section if exists
                if current_section and (current_content or not current_section.content):
                    current_section.content = "\n".join(current_content).strip()
                    if (
                        len(current_section.content) >= self.min_section_size
                        or not current_section.content
                    ):
                        sections.append(current_section)

                # Parse new header
                level = len(header_match.group(1))
                title = header_match.group(2).strip()

                # Update section counters
                section_counters[level - 1] += 1
                # Reset deeper level counters
                for j in range(level, 6):
                    section_counters[j] = 0

                # Build section path
                path_parts = []
                for j in range(level):
                    if section_counters[j] > 0:
                        path_parts.append(str(section_counters[j]))
                path = ".".join(path_parts)

                # Determine parent path
                parent_path = None
                if len(path_parts) > 1:
                    parent_path = ".".join(path_parts[:-1])

                # Create new section
                current_section = DocumentSection(
                    title=title,
                    level=level,
                    content="",
                    path=path,
                    parent_path=parent_path,
                    metadata=self._extract_metadata(title),
                )
                current_content = []
            else:
                # Add line to current section content
                if current_section:
                    current_content.append(line)
                else:
                    # Content before first header
                    if not sections and line.strip():
                        # Create initial section for content before first header
                        current_section = DocumentSection(
                            title="Introduction", level=1, content="", path="1"
                        )
                        section_counters[0] = 1
                        current_content = [line]

        # Save last section
        if current_section:
            current_section.content = "\n".join(current_content).strip()
            if (
                len(current_section.content) >= self.min_section_size
                or not current_section.content
            ):
                sections.append(current_section)

        # Handle large sections
        final_sections = []
        for section in sections:
            if len(section.content) > self.max_section_size:
                final_sections.extend(self._split_large_section(section))
            else:
                final_sections.append(section)

        return final_sections

    def _split_large_section(self, section: DocumentSection) -> List[DocumentSection]:
        """
        Split a large section into smaller chunks while preserving structure.

        Args:
            section: The section to split

        Returns:
            List of smaller sections
        """
        chunks = []
        content = section.content

        # Try to split at paragraph boundaries
        paragraphs = content.split("\n\n")
        current_chunk = []
        current_size = 0
        chunk_index = 1

        for para in paragraphs:
            para_size = len(para)

            if current_size + para_size > self.max_section_size and current_chunk:
                # Create a chunk
                chunk_content = "\n\n".join(current_chunk)
                chunk_title = f"{section.title} (Part {chunk_index})"
                chunk_path = f"{section.path}.{chunk_index}"

                chunks.append(
                    DocumentSection(
                        title=chunk_title,
                        level=section.level,
                        content=chunk_content,
                        path=chunk_path,
                        parent_path=section.path,
                        metadata=section.metadata.copy(),
                    )
                )

                current_chunk = [para]
                current_size = para_size
                chunk_index += 1
            else:
                current_chunk.append(para)
                current_size += para_size

        # Add remaining content
        if current_chunk:
            chunk_content = "\n\n".join(current_chunk)
            if chunk_index > 1:
                chunk_title = f"{section.title} (Part {chunk_index})"
                chunk_path = f"{section.path}.{chunk_index}"
            else:
                # If only one chunk, keep original
                chunk_title = section.title
                chunk_path = section.path

            chunks.append(
                DocumentSection(
                    title=chunk_title,
                    level=section.level,
                    content=chunk_content,
                    path=chunk_path,
                    parent_path=(
                        section.parent_path if chunk_index == 1 else section.path
                    ),
                    metadata=section.metadata.copy(),
                )
            )

        return chunks

    def _extract_metadata(self, title: str) -> Dict[str, str]:
        """Extract metadata from section title."""
        metadata = {}
        title_lower = title.lower()

        # Identify section type
        for section_type, patterns in self.COMMON_SECTIONS.items():
            if any(pattern in title_lower for pattern in patterns):
                metadata["section_type"] = section_type
                break

        # Check for version numbers
        version_match = re.search(r"v?(\d+\.\d+(?:\.\d+)?)", title)
        if version_match:
            metadata["version"] = version_match.group(1)

        # Check for code/API indicators
        if any(
            indicator in title_lower
            for indicator in ["api", "function", "method", "class", "module"]
        ):
            metadata["content_type"] = "api_reference"
        elif any(
            indicator in title_lower for indicator in ["example", "tutorial", "guide"]
        ):
            metadata["content_type"] = "tutorial"
        elif any(
            indicator in title_lower for indicator in ["install", "setup", "config"]
        ):
            metadata["content_type"] = "setup"

        return metadata


def create_section_segments(
    document_id: int, sections: List[DocumentSection]
) -> List[Dict]:
    """
    Convert DocumentSection objects to segment dictionaries for storage.

    Args:
        document_id: ID of the parent document
        sections: List of DocumentSection objects

    Returns:
        List of segment dictionaries ready for database storage
    """
    segments = []

    # Create a mapping of paths to sections for parent lookup
    path_to_section = {s.path: s for s in sections}

    for section in sections:
        segment = {
            "document_id": document_id,
            "content": section.content,
            "section_title": section.title,
            "section_level": section.level,
            "section_path": section.path,
            "segment_type": section.metadata.get("content_type", "text"),
            "metadata": section.metadata,
        }

        segments.append(segment)

    return segments
