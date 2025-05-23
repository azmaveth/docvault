from typing import Any, Dict, List, Optional

import html2text
from bs4 import BeautifulSoup


def html_to_markdown(html_content: str) -> str:
    """Convert HTML to Markdown"""
    h2t = html2text.HTML2Text()
    h2t.ignore_links = False
    h2t.ignore_images = False
    h2t.ignore_tables = False
    h2t.ignore_emphasis = False
    h2t.body_width = 0  # Don't wrap text

    # Pre-process HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()

    # Convert to markdown
    markdown = h2t.handle(str(soup))

    return markdown


def extract_title(html_content: str) -> Optional[str]:
    """Extract title from HTML"""
    soup = BeautifulSoup(html_content, "html.parser")
    title_tag = soup.find("title")

    if title_tag:
        return title_tag.text.strip()

    # Try h1 if no title
    h1_tag = soup.find("h1")
    if h1_tag:
        return h1_tag.text.strip()

    return None


def segment_markdown(markdown_content: str) -> List[Dict[str, Any]]:
    """
    Split markdown into segments with section hierarchy information.

    Returns:
        List of segment dictionaries with the following keys:
        - type: Segment type ('h1', 'h2', ..., 'h6', 'text', 'code')
        - content: The content of the segment
        - section_title: Title of the current section (for non-header segments)
        - section_level: Nesting level of the current section (1-6 for headers, 0 for text/code)
        - section_path: Path-like string representing the section hierarchy (e.g., '1.2.3')
    """
    import re
    from typing import Any, Dict, List, Optional

    class Section:
        def __init__(
            self,
            level: int,
            title: str,
            position: int,
            parent: Optional["Section"] = None,
        ):
            self.level = level
            self.title = title
            self.position = position
            self.parent = parent
            self.children: List["Section"] = []
            self.counter = 1

            if parent:
                parent.children.append(self)
                # Find siblings to determine counter
                siblings = [s for s in parent.children if s.level == level]
                if len(siblings) > 1:
                    self.counter = len(siblings)

        def get_path(self) -> str:
            """Get the section path as a string (e.g., '1.2.3')."""
            if not self.parent:
                return str(self.counter)
            return f"{self.parent.get_path()}.{self.counter}"

    # Split by headers
    header_pattern = r"^(#{1,6})\s+(.+)$"
    segments: List[Dict[str, Any]] = []
    current_segment = []
    current_type = "text"
    current_section: Optional[Section] = None

    lines = markdown_content.split("\n")

    for i, line in enumerate(lines):
        header_match = re.match(header_pattern, line)

        if header_match:
            # Save previous segment if it exists
            if current_segment:
                segments.append(
                    {
                        "type": current_type,
                        "content": "\n".join(current_segment),
                        "section_title": (
                            current_section.title if current_section else "Introduction"
                        ),
                        "section_level": (
                            current_section.level if current_section else 0
                        ),
                        "section_path": (
                            current_section.get_path() if current_section else ""
                        ),
                    }
                )

            # Create new section
            level = len(header_match.group(1))
            title = header_match.group(2).strip()

            # Find the appropriate parent section
            parent = current_section
            while parent and parent.level >= level:
                parent = parent.parent

            current_section = Section(level, title, i, parent)

            # Start new segment with header
            current_segment = [line]
            current_type = f"h{level}"
        else:
            current_segment.append(line)

    # Add the last segment
    if current_segment:
        segments.append(
            {
                "type": current_type,
                "content": "\n".join(current_segment),
                "section_title": (
                    current_section.title if current_section else "Introduction"
                ),
                "section_level": current_section.level if current_section else 0,
                "section_path": current_section.get_path() if current_section else "",
            }
        )

    # Further process to separate code blocks and handle section inheritance
    processed_segments: List[Dict[str, Any]] = []
    code_block_pattern = r"```.*?\n(.*?)```"

    for segment in segments:
        segment_type = segment["type"]
        content = segment["content"]

        # Find code blocks
        code_blocks = list(re.finditer(code_block_pattern, content, re.DOTALL))

        if not code_blocks:
            # No code blocks, add the segment as is
            processed_segments.append(segment)
            continue

        # Process text around code blocks
        last_end = 0
        for match in code_blocks:
            # Add text before code block
            if match.start() > last_end:
                text_before = content[last_end : match.start()].strip()
                if text_before:
                    processed_segments.append(
                        {
                            **segment,
                            "type": segment_type,
                            "content": text_before,
                        }
                    )

            # Add code block with same section info
            code_content = match.group(1).strip()
            if code_content:
                processed_segments.append(
                    {
                        **segment,
                        "type": "code",
                        "content": code_content,
                    }
                )

            last_end = match.end()

        # Add remaining text after last code block
        if last_end < len(content):
            remaining = content[last_end:].strip()
            if remaining:
                processed_segments.append(
                    {
                        **segment,
                        "type": segment_type,
                        "content": remaining,
                    }
                )

    return processed_segments or [(current_type, markdown_content)]
