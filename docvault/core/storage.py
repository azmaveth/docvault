import hashlib
import os
import shutil
import subprocess

import html2text

from docvault import config
from docvault.utils.path_security import get_safe_path, validate_filename


def generate_filename(url: str) -> str:
    """Generate a unique filename from URL"""
    # Create a hash of the URL to avoid filesystem issues with long URLs
    url_hash = hashlib.md5(url.encode()).hexdigest()

    # Extract domain for better organization
    from urllib.parse import urlparse

    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace("www.", "")
    # Replace invalid filename characters
    domain = domain.replace(":", "_").replace("/", "_")

    return f"{domain}_{url_hash}"


def save_html(content: str, url: str) -> str:
    """Save HTML content to file"""
    filename_base = generate_filename(url)
    # Validate filename to prevent path traversal
    safe_filename = validate_filename(f"{filename_base}.html")
    # Get safe path within HTML storage directory
    html_path = get_safe_path(config.HTML_PATH, safe_filename, create_dirs=True)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)

    return str(html_path)


def save_markdown(content: str, url: str) -> str:
    """Save Markdown content to file"""
    filename_base = generate_filename(url)
    # Validate filename to prevent path traversal
    safe_filename = validate_filename(f"{filename_base}.md")
    # Get safe path within Markdown storage directory
    markdown_path = get_safe_path(config.MARKDOWN_PATH, safe_filename, create_dirs=True)

    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(content)

    return str(markdown_path)


def _render_with_glow(content: str) -> str:
    """Render markdown using Glow if available"""
    if not shutil.which("glow"):
        return content  # Fall back to basic rendering

    try:
        process = subprocess.Popen(
            ["glow", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate(input=content)
        if process.returncode == 0 and stdout:
            return stdout
        return content
    except Exception:
        return content


def _render_html(html_content: str) -> str:
    """Render HTML to plain text using html2text"""
    try:
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_tables = False
        h.body_width = 0  # Don't wrap text
        return h.handle(html_content)
    except Exception:
        return html_content


def read_html(document_path: str) -> str:
    """Read HTML content from file and render it as markdown"""
    with open(document_path, "r", encoding="utf-8") as f:
        content = f.read()
    return _render_html(content)


def read_markdown(document_path: str, render: bool = True) -> str:
    """Read Markdown content from file

    Args:
        document_path: Path to the markdown file
        render: If True, render markdown for display. If False, return raw content.
               Default is True for backward compatibility.

    Returns:
        str: The markdown content, either rendered or raw
    """
    with open(document_path, "r", encoding="utf-8") as f:
        content = f.read()

    if not render:
        return content

    # Try to render markdown with Glow
    return _render_with_glow(content)


def open_html_in_browser(document_path: str) -> bool:
    """Open HTML document in default browser"""
    import webbrowser

    try:
        webbrowser.open(f"file://{os.path.abspath(document_path)}")
        return True
    except Exception:
        return False
