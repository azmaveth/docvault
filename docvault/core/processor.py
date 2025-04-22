from typing import List, Optional, Tuple

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


def segment_markdown(markdown_content: str) -> List[Tuple[str, str]]:
    """
    Split markdown into segments for embedding
    Returns list of (segment_type, content) tuples
    """
    import re

    # Split by headers
    header_pattern = r"^(#{1,6})\s+(.+)$"
    segments = []
    current_segment = []
    current_type = "text"

    for line in markdown_content.split("\n"):
        header_match = re.match(header_pattern, line)

        if header_match:
            # Save previous segment if it exists
            if current_segment:
                segments.append((current_type, "\n".join(current_segment)))

            # Start new segment with header
            current_segment = [line]
            current_type = f"h{len(header_match.group(1))}"
        else:
            current_segment.append(line)

    # Add the last segment
    if current_segment:
        segments.append((current_type, "\n".join(current_segment)))

    # Further process to separate code blocks
    processed_segments = []
    code_block_pattern = r"```.*?\n(.*?)```"

    for segment_type, content in segments:
        # Find code blocks
        code_blocks = re.finditer(code_block_pattern, content, re.DOTALL)
        last_end = 0

        for match in code_blocks:
            # Add text before code block
            if match.start() > last_end:
                text_before = content[last_end : match.start()]
                if text_before.strip():
                    processed_segments.append((segment_type, text_before))

            # Add code block
            processed_segments.append(("code", match.group(1)))
            last_end = match.end()

        # Add remaining text
        if last_end < len(content):
            remaining = content[last_end:]
            if remaining.strip():
                processed_segments.append((segment_type, remaining))

    return processed_segments or [(current_type, markdown_content)]
