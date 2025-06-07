"""
LLMs.txt parser and handler for DocVault.

This module provides functionality to parse, validate, and work with llms.txt files
according to the specification at https://llmstxt.org/
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse


@dataclass
class LLMsResource:
    """Represents a resource link in an llms.txt file."""

    title: str
    url: str
    description: str | None = None
    is_optional: bool = False


@dataclass
class LLMsDocument:
    """Represents a parsed llms.txt document."""

    title: str
    summary: str | None = None
    introduction: str | None = None
    sections: dict[str, list[LLMsResource]] = field(default_factory=dict)
    raw_content: str = ""
    source_url: str | None = None


class LLMsParser:
    """Parser for llms.txt files."""

    def __init__(self):
        self.link_pattern = re.compile(
            r"^\s*-\s*\[([^\]]+)\]\(([^)]+)\)(?:\s*:\s*(.*))?$"
        )
        self.header_pattern = re.compile(r"^#+\s+(.+)$")

    def parse(self, content: str, source_url: str | None = None) -> LLMsDocument:
        """
        Parse an llms.txt file content.

        Args:
            content: The raw text content of the llms.txt file
            source_url: Optional URL where the llms.txt was found

        Returns:
            Parsed LLMsDocument object
        """
        lines = content.strip().split("\n")
        doc = LLMsDocument(title="", raw_content=content, source_url=source_url)

        current_section = None
        current_section_resources = []
        in_summary = False
        intro_lines = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                if in_summary:
                    in_summary = False
                i += 1
                continue

            # Check for title (H1)
            if line.startswith("# ") and not doc.title:
                doc.title = line[2:].strip()
                i += 1
                continue

            # Check for summary (blockquote)
            if line.startswith(">") and not doc.summary:
                summary_lines = []
                while i < len(lines) and lines[i].strip().startswith(">"):
                    summary_lines.append(lines[i].strip()[1:].strip())
                    i += 1
                doc.summary = " ".join(summary_lines)
                continue

            # Check for section headers
            header_match = self.header_pattern.match(line)
            if header_match:
                # Save previous section if exists
                if current_section and current_section_resources:
                    doc.sections[current_section] = current_section_resources

                current_section = header_match.group(1).strip()
                current_section_resources = []
                i += 1
                continue

            # Check for resource links
            link_match = self.link_pattern.match(line)
            if link_match:
                title = link_match.group(1).strip()
                url = link_match.group(2).strip()
                description = (
                    link_match.group(3).strip() if link_match.group(3) else None
                )

                # Resolve relative URLs if source_url is provided
                if source_url and not urlparse(url).scheme:
                    url = urljoin(source_url, url)

                resource = LLMsResource(
                    title=title,
                    url=url,
                    description=description,
                    is_optional=current_section
                    and "optional" in current_section.lower(),
                )
                current_section_resources.append(resource)
                i += 1
                continue

            # If we're not in a section yet and it's not a special line, it's intro
            if not current_section and not doc.introduction:
                intro_lines.append(line)

            i += 1

        # Save final section
        if current_section and current_section_resources:
            doc.sections[current_section] = current_section_resources

        # Set introduction
        if intro_lines:
            doc.introduction = "\n".join(intro_lines).strip()

        return doc

    def validate(self, doc: LLMsDocument) -> tuple[bool, list[str]]:
        """
        Validate an LLMsDocument according to the specification.

        Args:
            doc: The document to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Title is required
        if not doc.title:
            errors.append("Missing required H1 title")

        # Check for at least some content
        if not doc.sections and not doc.introduction and not doc.summary:
            errors.append("Document has no content beyond title")

        # Validate URLs in resources
        for section, resources in doc.sections.items():
            for resource in resources:
                if not resource.url:
                    errors.append(
                        f"Resource '{resource.title}' in section '{section}' has no URL"
                    )

        return len(errors) == 0, errors


class LLMsGenerator:
    """Generate llms.txt content from DocVault documents."""

    def generate(
        self,
        title: str,
        documents: list[dict],
        summary: str | None = None,
        include_optional: bool = True,
    ) -> str:
        """
        Generate llms.txt content from a collection of documents.

        Args:
            title: The main title for the llms.txt file
            documents: List of document dictionaries with 'title', 'url', 'description'
            summary: Optional summary for the project
            include_optional: Whether to include optional sections

        Returns:
            Generated llms.txt content
        """
        lines = []

        # Title
        lines.append(f"# {title}")
        lines.append("")

        # Summary
        if summary:
            lines.append(f"> {summary}")
            lines.append("")

        # Introduction
        lines.append(f"This is the documentation collection for {title}.")
        lines.append("")

        # Main docs section
        if documents:
            lines.append("## Docs")
            lines.append("")

            for doc in documents:
                link = f"- [{doc['title']}]({doc['url']})"
                if doc.get("description"):
                    link += f": {doc['description']}"
                lines.append(link)

            lines.append("")

        # Optional section placeholder
        if include_optional:
            lines.append("## Optional")
            lines.append("")
            lines.append(
                "- [Additional Resources](/resources): Extended documentation and "
                "examples"
            )
            lines.append("")

        return "\n".join(lines)


def detect_llms_txt(url: str) -> str | None:
    """
    Detect if a website has an llms.txt file.

    Args:
        url: The base URL of the website

    Returns:
        URL of the llms.txt file if found, None otherwise
    """
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    llms_url = urljoin(base_url, "/llms.txt")

    # This would need actual HTTP checking in the scraper
    # For now, just return the constructed URL
    return llms_url
