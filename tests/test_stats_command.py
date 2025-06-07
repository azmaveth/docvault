"""Tests for the stats command."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from docvault.main import cli
from tests.utils import mock_app_initialization


@pytest.fixture
def runner():
    """Create a CliRunner instance."""
    return CliRunner()


@pytest.fixture
def cli_runner():
    """Create a CliRunner instance (alias for consistency)."""
    return CliRunner()


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        db_path = temp_path / "test.db"
        storage_path = temp_path / "storage"
        storage_path.mkdir()

        # Create some dummy files in storage
        for i in range(5):
            file_path = storage_path / f"doc_{i}.md"
            file_path.write_text(f"# Document {i}\nThis is test content.")

        with patch("docvault.config.DB_PATH", str(db_path)):
            with patch("docvault.config.STORAGE_PATH", str(storage_path)):
                # Initialize the database schema
                from docvault.db.schema import initialize_database

                initialize_database(force_recreate=True)
                yield db_path, storage_path


def test_stats_command_help(runner, mock_app_initialization):
    """Test stats command help output."""
    result = runner.invoke(cli, ["stats", "--help"])
    assert result.exit_code == 0
    assert "Show database statistics" in result.output
    assert "--format" in result.output
    assert "--verbose" in result.output


def test_stats_command_empty_database(runner, temp_db, mock_app_initialization):
    """Test stats command with empty database."""
    result = runner.invoke(cli, ["stats"])
    assert result.exit_code == 0

    # Check for expected sections
    assert "DocVault Statistics" in result.output
    assert "Database Information" in result.output
    assert "Document Statistics" in result.output
    assert "Vector Search Status" in result.output
    assert "Documentation Sources" in result.output

    # Check for empty database indicators
    assert "Total Documents" in result.output
    assert "0" in result.output  # Should show 0 documents
    assert "No documents in vault" in result.output


def test_stats_command_json_format(runner, temp_db, mock_app_initialization):
    """Test stats command with JSON output format."""
    result = runner.invoke(cli, ["stats", "--format", "json"])
    assert result.exit_code == 0

    # Parse JSON output
    # Find the JSON part (after log messages)
    json_start = result.output.find("{")
    if json_start == -1:
        pytest.fail("No JSON output found")

    json_output = result.output[json_start:]
    stats = json.loads(json_output)

    # Verify JSON structure
    assert "database_size_mb" in stats
    assert "storage_size_mb" in stats
    assert "document_count" in stats
    assert "segment_count" in stats
    assert "vector_search_enabled" in stats
    assert "documentation_sources" in stats

    # Check values
    assert stats["document_count"] == 0
    assert stats["storage_file_count"] == 5  # We created 5 files
    assert isinstance(stats["documentation_sources"], list)


def test_stats_command_verbose(runner, temp_db, mock_app_initialization):
    """Test stats command with verbose flag."""
    result = runner.invoke(cli, ["stats", "--verbose"])
    assert result.exit_code == 0

    # Verbose mode should show more details
    assert "DocVault Statistics" in result.output

    # In verbose mode with empty database, it might not show document details
    # but should still complete successfully


def test_stats_command_with_documents(runner, temp_db, mock_app_initialization):
    """Test stats command with documents in database."""
    db_path, storage_path = temp_db

    # Manually insert a test document
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Insert a document
    cursor.execute(
        """
        INSERT INTO documents (title, url, version, scraped_at)
        VALUES ('Test Document', 'https://example.com/doc', 'latest', datetime('now'))
    """
    )
    doc_id = cursor.lastrowid

    # Insert a segment
    cursor.execute(
        """
        INSERT INTO document_segments (document_id, content, segment_type,
                                        section_title)
        VALUES (?, 'Test content for the document', 'text', 'Introduction')
    """,
        (doc_id,),
    )

    conn.commit()
    conn.close()

    # Now run stats
    result = runner.invoke(cli, ["stats"])
    assert result.exit_code == 0

    # Should show 1 document
    assert "Total Documents" in result.output
    assert "1" in result.output  # Should show 1 document

    # Recent Documents section appears when there are documents
    if "Recent Documents" in result.output:
        assert "Test Document" in result.output


def test_stats_command_database_error(runner, mock_app_initialization):
    """Test stats command when database is not accessible."""
    with patch("docvault.config.DB_PATH", "/nonexistent/path/db.db"):
        with patch("docvault.config.STORAGE_PATH", "/nonexistent/storage"):
            result = runner.invoke(cli, ["stats"])
            # Should still work but show 0 sizes
            assert result.exit_code == 0
            assert "0.0 MB" in result.output
