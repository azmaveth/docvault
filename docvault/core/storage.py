import hashlib
import os

from docvault import config


def generate_filename(url: str) -> str:
    """Generate a unique filename from URL"""
    # Create a hash of the URL to avoid filesystem issues with long URLs
    url_hash = hashlib.md5(url.encode()).hexdigest()

    # Extract domain for better organization
    from urllib.parse import urlparse

    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace("www.", "")

    return f"{domain}_{url_hash}"


def save_html(content: str, url: str) -> str:
    """Save HTML content to file"""
    filename_base = generate_filename(url)
    html_path = config.HTML_PATH / f"{filename_base}.html"

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)

    return str(html_path)


def save_markdown(content: str, url: str) -> str:
    """Save Markdown content to file"""
    filename_base = generate_filename(url)
    markdown_path = config.MARKDOWN_PATH / f"{filename_base}.md"

    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(content)

    return str(markdown_path)


def read_html(document_path: str) -> str:
    """Read HTML content from file"""
    with open(document_path, "r", encoding="utf-8") as f:
        return f.read()


def read_markdown(document_path: str) -> str:
    """Read Markdown content from file"""
    with open(document_path, "r", encoding="utf-8") as f:
        return f.read()


def open_html_in_browser(document_path: str) -> bool:
    """Open HTML document in default browser"""
    import webbrowser

    try:
        webbrowser.open(f"file://{os.path.abspath(document_path)}")
        return True
    except Exception:
        return False
