"""
Tests for llms.txt functionality.
"""

import json
from unittest.mock import Mock

import pytest

from docvault.core.llms_txt import LLMsDocument, LLMsGenerator, LLMsParser
from docvault.db.operations_llms import (
    add_llms_txt_metadata,
    add_llms_txt_resource,
    get_llms_txt_metadata,
    get_llms_txt_resources,
    search_llms_txt_resources,
)

SAMPLE_LLMS_TXT = """# DocVault Documentation

> A powerful tool for managing and searching documentation

DocVault helps you collect, index, and search through documentation from various sources.

## Docs

- [Installation Guide](https://docvault.io/docs/install): Complete installation instructions
- [API Reference](https://docvault.io/docs/api): Detailed API documentation
- [CLI Usage](https://docvault.io/docs/cli): Command line interface guide

## Examples

- [Quick Start](https://docvault.io/examples/quickstart): Get started in 5 minutes
- [Advanced Search](https://docvault.io/examples/search): Complex search queries

## Optional

- [Contributing](https://docvault.io/contributing): How to contribute to the project
- [Changelog](https://docvault.io/changelog): Release notes and version history
"""


class TestLLMsParser:
    """Test the LLMs.txt parser."""

    def test_parse_complete_document(self):
        """Test parsing a complete llms.txt document."""
        parser = LLMsParser()
        doc = parser.parse(SAMPLE_LLMS_TXT, "https://example.com/llms.txt")

        assert doc.title == "DocVault Documentation"
        assert doc.summary == "A powerful tool for managing and searching documentation"
        assert "DocVault helps you" in doc.introduction
        assert "Docs" in doc.sections
        assert "Examples" in doc.sections
        assert "Optional" in doc.sections

        # Check Docs section
        docs_resources = doc.sections["Docs"]
        assert len(docs_resources) == 3
        assert docs_resources[0].title == "Installation Guide"
        assert docs_resources[0].url == "https://docvault.io/docs/install"
        assert docs_resources[0].description == "Complete installation instructions"
        assert not docs_resources[0].is_optional

        # Check Optional section
        optional_resources = doc.sections["Optional"]
        assert len(optional_resources) == 2
        assert optional_resources[0].is_optional

    def test_parse_minimal_document(self):
        """Test parsing a minimal llms.txt document."""
        minimal_txt = """# My Project

## Docs
- [README](./README.md)
"""
        parser = LLMsParser()
        doc = parser.parse(minimal_txt, "https://example.com/llms.txt")

        assert doc.title == "My Project"
        assert doc.summary is None
        assert doc.introduction is None
        assert len(doc.sections) == 1
        assert "Docs" in doc.sections

    def test_parse_with_relative_urls(self):
        """Test parsing with relative URLs."""
        relative_txt = """# Test Project

## Docs
- [Local Doc](./docs/guide.md): A local guide
- [Parent Doc](../README.md): Parent directory doc
"""
        parser = LLMsParser()
        doc = parser.parse(relative_txt, "https://example.com/project/llms.txt")

        # Check URL resolution
        docs = doc.sections["Docs"]
        assert docs[0].url == "https://example.com/project/docs/guide.md"
        assert docs[1].url == "https://example.com/README.md"

    def test_validate_valid_document(self):
        """Test validation of a valid document."""
        parser = LLMsParser()
        doc = parser.parse(SAMPLE_LLMS_TXT)

        is_valid, errors = parser.validate(doc)
        assert is_valid
        assert len(errors) == 0

    def test_validate_invalid_document(self):
        """Test validation of invalid documents."""
        parser = LLMsParser()

        # Missing title
        doc = LLMsDocument(title="", sections={"Docs": []})
        is_valid, errors = parser.validate(doc)
        assert not is_valid
        assert "Missing required H1 title" in errors

        # Empty document
        doc = LLMsDocument(title="Test")
        is_valid, errors = parser.validate(doc)
        assert not is_valid
        assert "Document has no content beyond title" in errors


class TestLLMsGenerator:
    """Test the LLMs.txt generator."""

    def test_generate_basic(self):
        """Test basic llms.txt generation."""
        generator = LLMsGenerator()
        documents = [
            {
                "title": "Installation",
                "url": "https://docs.example.com/install",
                "description": "How to install",
            },
            {
                "title": "API Guide",
                "url": "https://docs.example.com/api",
                "description": None,
            },
        ]

        content = generator.generate("My Project", documents, "A test project")

        assert "# My Project" in content
        assert "> A test project" in content
        assert "## Docs" in content
        assert (
            "- [Installation](https://docs.example.com/install): How to install"
            in content
        )
        assert "- [API Guide](https://docs.example.com/api)" in content
        assert "## Optional" in content

    def test_generate_without_optional(self):
        """Test generation without optional section."""
        generator = LLMsGenerator()
        documents = []

        content = generator.generate("Empty Project", documents, include_optional=False)

        assert "# Empty Project" in content
        assert "## Optional" not in content


class TestLLMsDatabaseOperations:
    """Test database operations for llms.txt."""

    @pytest.fixture
    def test_db(self, tmp_path, monkeypatch):
        """Create a test database."""
        db_path = tmp_path / "test.db"
        monkeypatch.setattr("docvault.config.DB_PATH", str(db_path))

        # Initialize database
        from docvault.db.schema import init_db

        init_db()

        # Apply migrations
        from docvault.db.migrations import migrate_schema

        migrate_schema()

        return db_path

    def test_add_llms_metadata(self, test_db):
        """Test adding llms.txt metadata."""
        # First create a document
        from docvault.db.operations import add_document

        doc_id = add_document(
            url="https://example.com",
            title="Test Doc",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            has_llms_txt=True,
            llms_txt_url="https://example.com/llms.txt",
        )

        # Add metadata
        sections_json = json.dumps(
            {"Docs": [{"title": "Guide", "url": "https://example.com/guide"}]}
        )

        metadata_id = add_llms_txt_metadata(
            document_id=doc_id,
            llms_title="Test Project",
            llms_summary="A test project",
            llms_introduction="This is a test",
            llms_sections=sections_json,
        )

        assert metadata_id > 0

        # Verify retrieval
        metadata = get_llms_txt_metadata(doc_id)
        assert metadata is not None
        assert metadata["llms_title"] == "Test Project"
        assert metadata["llms_summary"] == "A test project"

    def test_add_llms_resources(self, test_db):
        """Test adding llms.txt resources."""
        from docvault.db.operations import add_document

        doc_id = add_document(
            url="https://example.com",
            title="Test Doc",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
        )

        # Add resources
        resource_id = add_llms_txt_resource(
            document_id=doc_id,
            section="Docs",
            title="Installation Guide",
            url="https://example.com/install",
            description="How to install",
            is_optional=False,
        )

        assert resource_id > 0

        # Verify retrieval
        resources = get_llms_txt_resources(doc_id)
        assert len(resources) == 1
        assert resources[0]["title"] == "Installation Guide"
        assert resources[0]["section"] == "Docs"

    def test_search_llms_resources(self, test_db):
        """Test searching llms.txt resources."""
        from docvault.db.operations import add_document

        # Create documents
        doc1_id = add_document(
            url="https://example1.com",
            title="Project 1",
            html_path="/tmp/test1.html",
            markdown_path="/tmp/test1.md",
        )

        doc2_id = add_document(
            url="https://example2.com",
            title="Project 2",
            html_path="/tmp/test2.html",
            markdown_path="/tmp/test2.md",
        )

        # Add resources
        add_llms_txt_resource(
            doc1_id, "Docs", "Installation Guide", "url1", "How to install"
        )
        add_llms_txt_resource(doc1_id, "Docs", "API Reference", "url2", "API docs")
        add_llms_txt_resource(doc2_id, "Docs", "Quick Install", "url3", "Fast setup")

        # Search for "install"
        results = search_llms_txt_resources("install")
        assert len(results) == 2

        # Verify results contain both matches
        titles = [r["title"] for r in results]
        assert "Installation Guide" in titles
        assert "Quick Install" in titles


class TestLLMsScraperIntegration:
    """Test llms.txt integration with the scraper."""

    @pytest.mark.asyncio
    async def test_scraper_detects_llms_txt(self, monkeypatch):
        """Test that scraper detects and processes llms.txt files."""
        from docvault.core.scraper import WebScraper

        # Mock the fetch responses
        async def mock_fetch(self, url):
            if url.endswith("/llms.txt"):
                return SAMPLE_LLMS_TXT, None
            else:
                return "<html><body>Test page</body></html>", None

        monkeypatch.setattr(WebScraper, "_fetch_url", mock_fetch)

        # Mock database operations
        mock_add_doc = Mock(return_value=1)
        mock_add_segment = Mock(return_value=1)
        mock_add_metadata = Mock()
        mock_add_resource = Mock()

        monkeypatch.setattr(
            "docvault.db.operations.update_document_by_url", mock_add_doc
        )
        monkeypatch.setattr(
            "docvault.db.operations.add_document_segment", mock_add_segment
        )
        monkeypatch.setattr(
            "docvault.db.operations_llms.add_llms_txt_metadata", mock_add_metadata
        )
        monkeypatch.setattr(
            "docvault.db.operations_llms.add_llms_txt_resource", mock_add_resource
        )

        # Mock embeddings
        async def mock_embeddings(text):
            return b"\x00" * 1536  # Mock embedding

        monkeypatch.setattr(
            "docvault.core.embeddings.generate_embeddings", mock_embeddings
        )

        # Run scraper
        scraper = WebScraper()
        await scraper.scrape("https://example.com", depth=1)

        # Verify llms.txt was detected
        assert mock_add_doc.called
        call_kwargs = mock_add_doc.call_args.kwargs
        assert call_kwargs.get("has_llms_txt") is True
        assert call_kwargs.get("llms_txt_url") == "https://example.com/llms.txt"

        # Verify metadata was stored
        assert mock_add_metadata.called
        metadata_call = mock_add_metadata.call_args
        assert metadata_call.kwargs["llms_title"] == "DocVault Documentation"

        # Verify resources were stored
        assert mock_add_resource.called
        assert mock_add_resource.call_count >= 5  # At least 5 resources in sample
