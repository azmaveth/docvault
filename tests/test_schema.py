"""Tests for database schema initialization"""

import sqlite3
from unittest.mock import patch


def test_initialize_database(mock_config, temp_db_path):
    """Test database initialization"""
    from docvault.db.schema import initialize_database

    # Initialize the database
    success = initialize_database(force_recreate=True)

    # Verify database was created
    assert success is True
    assert temp_db_path.exists()

    # Check tables were created
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()

    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    table_names = [table[0] for table in tables]

    # Check for required tables
    assert "documents" in table_names
    assert "document_segments" in table_names
    assert "libraries" in table_names

    # Check table schemas
    cursor.execute("PRAGMA table_info(documents)")
    document_columns = cursor.fetchall()
    document_column_names = [col[1] for col in document_columns]

    assert "id" in document_column_names
    assert "url" in document_column_names
    assert "title" in document_column_names
    assert "html_path" in document_column_names
    assert "markdown_path" in document_column_names
    assert "library_id" in document_column_names
    assert "is_library_doc" in document_column_names

    cursor.execute("PRAGMA table_info(document_segments)")
    segment_columns = cursor.fetchall()
    segment_column_names = [col[1] for col in segment_columns]

    assert "id" in segment_column_names
    assert "document_id" in segment_column_names
    assert "content" in segment_column_names
    assert "embedding" in segment_column_names

    cursor.execute("PRAGMA table_info(libraries)")
    library_columns = cursor.fetchall()
    library_column_names = [col[1] for col in library_columns]

    assert "id" in library_column_names
    assert "name" in library_column_names
    assert "version" in library_column_names
    assert "doc_url" in library_column_names
    assert "is_available" in library_column_names

    conn.close()


def test_vector_extension_handling(mock_config, temp_db_path):
    """Test handling of sqlite-vec extension"""
    from docvault.db.schema import initialize_database

    # Patch importlib directly to simulate ImportError
    with patch("importlib.import_module", side_effect=ImportError):
        # Should not raise error even if extension is not available
        success = initialize_database(force_recreate=True)
        assert success is True
