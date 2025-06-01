"""
Tests for section navigation functionality.
"""

import json

import pytest
from click.testing import CliRunner

from docvault.cli.section_commands import sections
from docvault.core.section_navigator import (
    SectionNavigator,
    get_section_content,
)
from docvault.core.section_splitter import (
    SectionSplitter,
)
from docvault.db.operations import add_document, add_document_segment, get_connection


class TestSectionNavigator:
    """Test section navigation functionality."""

    @pytest.fixture
    def setup_test_document(self, test_db):
        """Create a test document with hierarchical sections."""
        # Add document
        doc_id = add_document(
            url="https://example.com/test-doc",
            title="Test Documentation",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )

        # Add sections in hierarchical structure
        segments = [
            {
                "document_id": doc_id,
                "content": "Introduction to the library",
                "section_title": "Introduction",
                "section_level": 1,
                "section_path": "1",
                "parent_segment_id": None,
            },
            {
                "document_id": doc_id,
                "content": "How to install the library",
                "section_title": "Installation",
                "section_level": 1,
                "section_path": "2",
                "parent_segment_id": None,
            },
            {
                "document_id": doc_id,
                "content": "Install using pip",
                "section_title": "Using pip",
                "section_level": 2,
                "section_path": "2.1",
                "parent_segment_id": None,  # Will be updated
            },
            {
                "document_id": doc_id,
                "content": "Install from source",
                "section_title": "From source",
                "section_level": 2,
                "section_path": "2.2",
                "parent_segment_id": None,  # Will be updated
            },
            {
                "document_id": doc_id,
                "content": "API documentation",
                "section_title": "API Reference",
                "section_level": 1,
                "section_path": "3",
                "parent_segment_id": None,
            },
            {
                "document_id": doc_id,
                "content": "Core functions",
                "section_title": "Functions",
                "section_level": 2,
                "section_path": "3.1",
                "parent_segment_id": None,  # Will be updated
            },
        ]

        # Insert segments and track IDs
        ids = {}
        for segment in segments:
            seg_id = add_document_segment(**segment)
            ids[segment["section_path"]] = seg_id

        # Update parent relationships
        with get_connection() as conn:
            conn.execute(
                "UPDATE document_segments SET parent_segment_id = ? WHERE id = ?",
                (ids["2"], ids["2.1"]),
            )
            conn.execute(
                "UPDATE document_segments SET parent_segment_id = ? WHERE id = ?",
                (ids["2"], ids["2.2"]),
            )
            conn.execute(
                "UPDATE document_segments SET parent_segment_id = ? WHERE id = ?",
                (ids["3"], ids["3.1"]),
            )
            conn.commit()

        return doc_id, ids

    def test_get_table_of_contents(self, setup_test_document):
        """Test generating table of contents."""
        doc_id, ids = setup_test_document

        navigator = SectionNavigator(doc_id)
        toc = navigator.get_table_of_contents()

        # Should have 3 root sections
        assert len(toc) == 3
        assert toc[0].section_title == "Introduction"
        assert toc[1].section_title == "Installation"
        assert toc[2].section_title == "API Reference"

        # Check hierarchy
        assert len(toc[1].children) == 2
        assert toc[1].children[0].section_title == "Using pip"
        assert toc[1].children[1].section_title == "From source"

        assert len(toc[2].children) == 1
        assert toc[2].children[0].section_title == "Functions"

    def test_get_section_by_path(self, setup_test_document):
        """Test retrieving section by path."""
        doc_id, _ = setup_test_document

        navigator = SectionNavigator(doc_id)

        # Test valid paths
        section = navigator.get_section_by_path("2.1")
        assert section is not None
        assert section.section_title == "Using pip"
        assert section.section_path == "2.1"

        # Test invalid path
        section = navigator.get_section_by_path("9.9")
        assert section is None

    def test_get_section_children(self, setup_test_document):
        """Test getting section children."""
        doc_id, ids = setup_test_document

        navigator = SectionNavigator(doc_id)

        # Get children of Installation section
        children = navigator.get_section_children(ids["2"])
        assert len(children) == 2
        assert children[0].section_title == "Using pip"
        assert children[1].section_title == "From source"

        # Leaf section should have no children
        children = navigator.get_section_children(ids["2.1"])
        assert len(children) == 0

    def test_get_section_ancestors(self, setup_test_document):
        """Test getting section ancestors."""
        doc_id, ids = setup_test_document

        navigator = SectionNavigator(doc_id)

        # Get ancestors of "Using pip" section
        ancestors = navigator.get_section_ancestors(ids["2.1"])
        assert len(ancestors) == 1
        assert ancestors[0].section_title == "Installation"

        # Root section should have no ancestors
        ancestors = navigator.get_section_ancestors(ids["1"])
        assert len(ancestors) == 0

    def test_get_section_siblings(self, setup_test_document):
        """Test getting section siblings."""
        doc_id, ids = setup_test_document

        navigator = SectionNavigator(doc_id)

        # Get siblings of "Using pip" section
        siblings = navigator.get_section_siblings(ids["2.1"])
        assert len(siblings) == 1
        assert siblings[0].section_title == "From source"

        # Get siblings of root section
        siblings = navigator.get_section_siblings(ids["1"])
        assert len(siblings) == 2
        assert siblings[0].section_title == "Installation"
        assert siblings[1].section_title == "API Reference"

    def test_find_sections_by_title(self, setup_test_document):
        """Test finding sections by title pattern."""
        doc_id, _ = setup_test_document

        navigator = SectionNavigator(doc_id)

        # Find sections containing "install"
        matches = navigator.find_sections_by_title("install")
        assert len(matches) == 1
        assert matches[0].section_title == "Installation"

        # Case insensitive search
        matches = navigator.find_sections_by_title("API")
        assert len(matches) == 1
        assert matches[0].section_title == "API Reference"

        # No matches
        matches = navigator.find_sections_by_title("nonexistent")
        assert len(matches) == 0

    def test_get_section_content(self, setup_test_document):
        """Test getting section content with children."""
        doc_id, _ = setup_test_document

        # Get Installation section with children
        content = get_section_content(doc_id, "2")
        assert content is not None
        assert content["title"] == "Installation"
        assert len(content["segments"]) == 3  # Parent + 2 children

        # Verify content includes children
        titles = [s["title"] for s in content["segments"]]
        assert "Installation" in titles
        assert "Using pip" in titles
        assert "From source" in titles


class TestSectionSplitter:
    """Test section splitting functionality."""

    def test_split_markdown_simple(self):
        """Test splitting simple markdown document."""
        markdown = """# Introduction
This is the intro.

## Getting Started
How to begin.

### Prerequisites
What you need.

## Installation
How to install.
"""

        splitter = SectionSplitter(min_section_size=0)
        sections = splitter.split_document(markdown, content_type="markdown")

        assert len(sections) == 4
        assert sections[0].title == "Introduction"
        assert sections[0].path == "1"
        assert sections[0].level == 1

        assert sections[1].title == "Getting Started"
        assert sections[1].path == "1.1"
        assert sections[1].level == 2

        assert sections[2].title == "Prerequisites"
        assert sections[2].path == "1.1.1"
        assert sections[2].level == 3
        assert sections[2].parent_path == "1.1"

        assert sections[3].title == "Installation"
        assert sections[3].path == "1.2"
        assert sections[3].level == 2

    def test_split_html_simple(self):
        """Test splitting simple HTML document."""
        html = """
        <h1>Introduction</h1>
        <p>This is the intro.</p>
        
        <h2>Getting Started</h2>
        <p>How to begin.</p>
        
        <h3>Prerequisites</h3>
        <p>What you need.</p>
        
        <h2>Installation</h2>
        <p>How to install.</p>
        """

        splitter = SectionSplitter(min_section_size=0)
        sections = splitter.split_document(html, content_type="html")

        assert len(sections) == 4
        assert sections[0].title == "Introduction"
        assert sections[1].title == "Getting Started"
        assert sections[2].title == "Prerequisites"
        assert sections[3].title == "Installation"

    def test_split_large_section(self):
        """Test splitting large sections."""
        # Create a large section
        large_content = "This is a paragraph.\n\n" * 500  # ~10KB
        markdown = f"""# Large Section
{large_content}

# Next Section
Small content.
"""

        splitter = SectionSplitter(max_section_size=5000, min_section_size=0)
        sections = splitter.split_document(markdown, content_type="markdown")

        # Should split the large section
        large_sections = [s for s in sections if "Large Section" in s.title]
        assert len(large_sections) > 1
        assert "Part" in large_sections[1].title

        # Small section should not be split
        small_sections = [s for s in sections if s.title == "Next Section"]
        assert len(small_sections) == 1

    def test_extract_metadata(self):
        """Test metadata extraction from titles."""
        splitter = SectionSplitter(min_section_size=0)

        # Test section type detection
        metadata = splitter._extract_metadata("Installation Guide")
        assert metadata.get("section_type") == "installation"
        assert (
            metadata.get("content_type") == "tutorial"
        )  # 'Guide' matches tutorial pattern

        metadata = splitter._extract_metadata("API Reference v2.1.0")
        assert metadata.get("section_type") == "api"
        assert metadata.get("version") == "2.1.0"
        assert metadata.get("content_type") == "api_reference"

        metadata = splitter._extract_metadata("Tutorial: Getting Started")
        assert metadata.get("content_type") == "tutorial"

    def test_content_before_first_header(self):
        """Test handling content before first header."""
        markdown = """Some introductory text here.
More intro content.

# First Header
Header content.
"""

        splitter = SectionSplitter(min_section_size=0)
        sections = splitter.split_document(markdown, content_type="markdown")

        assert len(sections) == 2
        assert sections[0].title == "Introduction"
        assert "introductory text" in sections[0].content
        assert sections[1].title == "First Header"


class TestSectionCLI:
    """Test section CLI commands."""

    @pytest.fixture
    def setup_cli_test(self, test_db):
        """Setup for CLI tests."""
        # Add document
        doc_id = add_document(
            url="https://example.com/test-doc",
            title="Test Documentation",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )

        # Add sections in hierarchical structure
        segments = [
            {
                "document_id": doc_id,
                "content": "Introduction to the library",
                "section_title": "Introduction",
                "section_level": 1,
                "section_path": "1",
                "parent_segment_id": None,
            },
            {
                "document_id": doc_id,
                "content": "How to install the library",
                "section_title": "Installation",
                "section_level": 1,
                "section_path": "2",
                "parent_segment_id": None,
            },
            {
                "document_id": doc_id,
                "content": "Install using pip",
                "section_title": "Using pip",
                "section_level": 2,
                "section_path": "2.1",
                "parent_segment_id": None,  # Will be updated
            },
            {
                "document_id": doc_id,
                "content": "Install from source",
                "section_title": "From source",
                "section_level": 2,
                "section_path": "2.2",
                "parent_segment_id": None,  # Will be updated
            },
            {
                "document_id": doc_id,
                "content": "API documentation",
                "section_title": "API Reference",
                "section_level": 1,
                "section_path": "3",
                "parent_segment_id": None,
            },
            {
                "document_id": doc_id,
                "content": "Core functions",
                "section_title": "Functions",
                "section_level": 2,
                "section_path": "3.1",
                "parent_segment_id": None,  # Will be updated
            },
        ]

        # Insert segments and track IDs
        ids = {}
        for segment in segments:
            seg_id = add_document_segment(**segment)
            ids[segment["section_path"]] = seg_id

        # Update parent relationships
        with get_connection() as conn:
            conn.execute(
                "UPDATE document_segments SET parent_segment_id = ? WHERE id = ?",
                (ids["2"], ids["2.1"]),
            )
            conn.execute(
                "UPDATE document_segments SET parent_segment_id = ? WHERE id = ?",
                (ids["2"], ids["2.2"]),
            )
            conn.execute(
                "UPDATE document_segments SET parent_segment_id = ? WHERE id = ?",
                (ids["3"], ids["3.1"]),
            )
            conn.commit()

        return doc_id, ids

    def test_toc_command_tree_format(self, setup_cli_test):
        """Test table of contents command with tree format."""
        doc_id, _ = setup_cli_test

        runner = CliRunner()
        result = runner.invoke(sections, ["toc", str(doc_id)])

        assert result.exit_code == 0
        assert "Test Documentation" in result.output
        assert "Introduction" in result.output
        assert "Installation" in result.output
        assert "Using pip" in result.output

    def test_toc_command_json_format(self, setup_cli_test):
        """Test table of contents command with JSON format."""
        doc_id, _ = setup_cli_test

        runner = CliRunner()
        result = runner.invoke(sections, ["toc", str(doc_id), "--format", "json"])

        assert result.exit_code == 0

        # Parse JSON output
        toc_data = json.loads(result.output)
        assert len(toc_data) == 3
        assert toc_data[0]["title"] == "Introduction"
        assert len(toc_data[1]["children"]) == 2

    def test_read_section_command(self, setup_cli_test):
        """Test reading a specific section."""
        doc_id, _ = setup_cli_test

        runner = CliRunner()
        result = runner.invoke(sections, ["read", str(doc_id), "2.1"])

        assert result.exit_code == 0
        assert "Using pip" in result.output
        assert "Install using pip" in result.output

    def test_find_sections_command(self, setup_cli_test):
        """Test finding sections by title."""
        doc_id, _ = setup_cli_test

        runner = CliRunner()
        result = runner.invoke(sections, ["find", str(doc_id), "install"])

        assert result.exit_code == 0
        assert "Found 1 sections" in result.output
        assert "Installation" in result.output

    def test_navigate_command(self, setup_cli_test):
        """Test section navigation command."""
        doc_id, ids = setup_cli_test

        runner = CliRunner()

        # Test showing children
        result = runner.invoke(
            sections, ["navigate", str(doc_id), str(ids["2"]), "--show", "children"]
        )

        assert result.exit_code == 0
        assert "Child sections:" in result.output
        assert "Using pip" in result.output
        assert "From source" in result.output

    def test_invalid_document_id(self, mock_app_initialization):
        """Test commands with invalid document ID."""
        from unittest.mock import MagicMock, patch

        runner = CliRunner()

        # Mock database operations
        with (
            patch("docvault.db.operations.get_document", return_value=None),
            patch("docvault.db.operations.get_connection") as mock_get_conn,
        ):
            # Mock the connection context manager
            mock_conn = MagicMock()
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            mock_get_conn.return_value.__exit__.return_value = None

            result = runner.invoke(sections, ["toc", "99999"])

        assert result.exit_code == 0
        assert "Document 99999 not found" in result.output

    def test_invalid_section_path(self, setup_cli_test):
        """Test reading invalid section path."""
        doc_id, _ = setup_cli_test

        runner = CliRunner()
        result = runner.invoke(sections, ["read", str(doc_id), "9.9.9"])

        assert result.exit_code == 0
        assert "Section 9.9.9 not found" in result.output
