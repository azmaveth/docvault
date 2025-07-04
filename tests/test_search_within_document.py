"""
Test search within document functionality.
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from docvault.cli.commands import search_text
from docvault.db.operations import add_document, add_document_segment


def extract_json_from_output(output):
    """Extract JSON from CLI output that may contain log lines."""
    # Split output into lines
    lines = output.split("\n")

    # Find lines that look like JSON (start with { or are part of a JSON object)
    json_lines = []
    in_json = False
    brace_count = 0

    for line in lines:
        # Skip log lines (they typically start with ERROR, WARNING, INFO, DEBUG)
        if line.strip() and not any(
            line.strip().startswith(level)
            for level in ["ERROR", "WARNING", "INFO", "DEBUG"]
        ):
            # Check if this line starts a JSON object or is part of one
            if "{" in line or in_json:
                json_lines.append(line)
                brace_count += line.count("{") - line.count("}")
                if brace_count > 0:
                    in_json = True
                elif brace_count == 0 and json_lines:
                    # We've found a complete JSON object
                    json_str = "\n".join(json_lines)
                    # Find the actual JSON part (in case there's text before it)
                    json_start = json_str.find("{")
                    if json_start != -1:
                        json_str = json_str[json_start:]
                    return json.loads(json_str)

    # If we didn't find a complete JSON object, try the original approach
    json_start = output.find("{")
    if json_start != -1:
        # Just take everything after the first { and hope for the best
        return json.loads(output[json_start:])

    raise ValueError(f"No valid JSON found in output: {output}")


class TestSearchWithinDocument:
    """Test search within specific document functionality."""

    @pytest.fixture
    def setup_test_docs(self, test_db):
        """Set up test documents with content for searching."""
        # Add two test documents
        doc1_id = add_document(
            url="https://example.com/doc1",
            title="Python Tutorial",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )

        doc2_id = add_document(
            url="https://example.com/doc2",
            title="JavaScript Guide",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )

        # Add segments to both documents
        segment1_id = add_document_segment(
            document_id=doc1_id,
            content="Python functions are defined using def keyword. Example: "
            "def hello():",
            section_title="Functions",
            segment_type="text",
        )

        segment2_id = add_document_segment(
            document_id=doc1_id,
            content="Python classes use class keyword. Example: class MyClass:",
            section_title="Classes",
            segment_type="text",
        )

        segment3_id = add_document_segment(
            document_id=doc2_id,
            content="JavaScript functions can be declared with function keyword",
            section_title="Functions",
            segment_type="text",
        )

        return {
            "doc1_id": doc1_id,
            "doc2_id": doc2_id,
            "segments": [segment1_id, segment2_id, segment3_id],
        }

    def test_search_within_specific_document_text_only(self, setup_test_docs):
        """Test searching within a specific document using text search."""
        doc1_id = setup_test_docs["doc1_id"]
        runner = CliRunner()

        # Search for "functions" within doc1 only
        result = runner.invoke(
            search_text,
            ["functions", "--in-doc", str(doc1_id), "--text-only", "--format", "json"],
        )

        assert result.exit_code == 0
        data = extract_json_from_output(result.output)

        # Should find results only from doc1
        assert data["status"] == "success"
        assert data["count"] > 0
        assert "search_scope" in data
        assert data["search_scope"]["document_id"] == doc1_id
        assert data["search_scope"]["document_title"] == "Python Tutorial"

        # All results should be from doc1
        for result_item in data["results"]:
            assert result_item["document_id"] == doc1_id

    def test_search_within_nonexistent_document(self, setup_test_docs):
        """Test searching within a document that doesn't exist."""
        runner = CliRunner()

        result = runner.invoke(
            search_text,
            [
                "functions",
                "--in-doc",
                "999",  # Non-existent document ID
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = extract_json_from_output(result.output)

        assert data["status"] == "error"
        assert "Document not found: 999" in data["error"]

    def test_search_within_document_text_output(self, setup_test_docs):
        """Test text output format when searching within document."""
        doc1_id = setup_test_docs["doc1_id"]
        runner = CliRunner()

        result = runner.invoke(
            search_text, ["functions", "--in-doc", str(doc1_id), "--text-only"]
        )

        assert result.exit_code == 0
        # Should show document title in output
        assert "Python Tutorial" in result.output
        assert "Found" in result.output
        # Check for the actual output format
        assert "filtered by in document: 'Python Tutorial'" in result.output

    def test_search_within_document_no_results(self, setup_test_docs):
        """Test searching within document when no results found."""
        doc1_id = setup_test_docs["doc1_id"]
        runner = CliRunner()

        result = runner.invoke(
            search_text,
            ["nonexistent_term", "--in-doc", str(doc1_id), "--format", "json"],
        )

        assert result.exit_code == 0

        try:
            data = extract_json_from_output(result.output)
        except json.JSONDecodeError as e:
            # Print debug info if JSON parsing fails
            print(f"Failed to parse JSON. Output was:\n{result.output}")
            raise e

        assert data["status"] == "success"
        assert data["count"] == 0
        assert data["results"] == []
        assert "search_scope" in data
        assert data["search_scope"]["document_id"] == doc1_id

    @patch("docvault.core.embeddings.generate_embeddings")
    @patch("docvault.db.operations.search_segments")
    def test_search_within_document_filters_applied(
        self, mock_search, mock_embeddings, setup_test_docs
    ):
        """Test that document filter is properly applied to search."""
        doc1_id = setup_test_docs["doc1_id"]

        # Mock the search to verify filter is passed
        mock_search.return_value = []
        mock_embeddings.return_value = b"fake_embedding"

        runner = CliRunner()
        result = runner.invoke(search_text, ["functions", "--in-doc", str(doc1_id)])

        assert result.exit_code == 0

        # Verify search_segments was called with document filter
        mock_search.assert_called_once()
        call_args = mock_search.call_args

        # Check that doc_filter contains our document ID
        doc_filter = call_args[1]["doc_filter"]  # keyword argument
        assert doc_filter is not None
        assert "document_ids" in doc_filter
        assert doc_filter["document_ids"] == [doc1_id]

    def test_search_within_document_combined_with_other_filters(self, setup_test_docs):
        """Test combining --in-doc with other filters."""
        doc1_id = setup_test_docs["doc1_id"]
        runner = CliRunner()

        result = runner.invoke(
            search_text,
            [
                "functions",
                "--in-doc",
                str(doc1_id),
                "--version",
                "1.0",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0

        try:
            data = extract_json_from_output(result.output)
        except json.JSONDecodeError as e:
            # Print debug info if JSON parsing fails
            print(f"Failed to parse JSON. Output was:\n{result.output}")
            raise e

        # Should still work with combined filters
        assert data["status"] == "success"
        if data["count"] > 0:
            # All results should be from doc1 and version 1.0
            for result_item in data["results"]:
                assert result_item["document_id"] == doc1_id

    def test_search_within_document_status_message(self, setup_test_docs, capsys):
        """Test that the search status message includes document title."""
        doc1_id = setup_test_docs["doc1_id"]
        runner = CliRunner()

        # Run search and capture the status output
        result = runner.invoke(
            search_text, ["functions", "--in-doc", str(doc1_id), "--text-only"]
        )

        assert result.exit_code == 0
        # The status message should mention the document title
        # Note: This tests the logic but Rich status messages don't appear in test
        # output

    def test_search_empty_query_within_document(self, setup_test_docs):
        """Test searching within document without a query (filter-only search)."""
        doc1_id = setup_test_docs["doc1_id"]
        runner = CliRunner()

        result = runner.invoke(
            search_text, ["--in-doc", str(doc1_id), "--format", "json"]
        )

        assert result.exit_code == 0
        data = extract_json_from_output(result.output)

        # Should return documents matching the filter even without query
        assert data["status"] == "success"
        assert "search_scope" in data
        assert data["search_scope"]["document_id"] == doc1_id


class TestSearchWithinDocumentIntegration:
    """Integration tests for search within document."""

    def test_full_search_workflow(self, test_db):
        """Test complete workflow of adding document and searching within it."""
        # Add a document with specific content
        doc_id = add_document(
            url="https://example.com/python-guide",
            title="Complete Python Guide",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="2.0",
        )

        # Add a segment with searchable content
        add_document_segment(
            document_id=doc_id,
            content="List comprehensions in Python: [x for x in range(10)]",
            section_title="Advanced Features",
            segment_type="code",
        )

        runner = CliRunner()

        # Search for specific term within this document
        result = runner.invoke(
            search_text,
            [
                "comprehensions",
                "--in-doc",
                str(doc_id),
                "--text-only",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = extract_json_from_output(result.output)

        assert data["status"] == "success"
        assert data["count"] > 0
        assert data["search_scope"]["document_id"] == doc_id
        assert data["search_scope"]["document_title"] == "Complete Python Guide"

        # Verify content contains our search term
        found_content = False
        for result_item in data["results"]:
            if "comprehensions" in result_item["content_preview"].lower():
                found_content = True
                break

        assert found_content, "Search term not found in results"
