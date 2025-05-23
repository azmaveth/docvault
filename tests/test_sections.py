"""Tests for document sections functionality."""

import os
import sqlite3
import tempfile

from docvault import config
from docvault.db import (
    add_document,
    add_document_segment,
    get_document_sections,
    initialize_database,
)

# Schema for testing
TEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    version TEXT,
    title TEXT,
    html_path TEXT,
    markdown_path TEXT,
    content_hash TEXT,
    library_id INTEGER,
    is_library_doc BOOLEAN DEFAULT 0,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (library_id) REFERENCES libraries(id)
);

CREATE TABLE IF NOT EXISTS document_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB,
    segment_type TEXT,
    position INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    section_title TEXT,
    section_level INTEGER DEFAULT 1,
    section_path TEXT,
    parent_segment_id INTEGER,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_segment_id) REFERENCES document_segments(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def setup_test_db(db_path):
    """Set up a test database with the required schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the schema
    cursor.executescript(TEST_SCHEMA)

    # Set the schema version to 1 to skip migrations
    cursor.execute("INSERT INTO schema_version (version) VALUES (1)")

    conn.commit()
    conn.close()


def test_add_document_with_sections():
    """Test adding a document with sections."""
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Set up the test database
        original_db_path = config.DB_PATH
        config.DB_PATH = db_path

        # Set up the test database with our schema
        setup_test_db(db_path)

        # Initialize the database
        initialize_database()

        # Add a test document
        doc_id = add_document(
            url="https://example.com/test",
            title="Test Document",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
        )

        # Add document sections
        intro_id = add_document_segment(
            document_id=doc_id,
            content="Introduction",
            segment_type="h1",
            section_title="Introduction",
            section_level=1,
            section_path="1",
        )

        section1_id = add_document_segment(
            document_id=doc_id,
            content="Section 1",
            segment_type="h2",
            section_title="First Section",
            section_level=2,
            section_path="1.1",
            parent_segment_id=intro_id,
        )

        # Add content to the section
        add_document_segment(
            document_id=doc_id,
            content="This is some content in section 1.",
            segment_type="text",
            section_title="First Section",
            section_level=2,
            section_path="1.1",
            parent_segment_id=section1_id,
        )

        # Get the document sections
        sections = get_document_sections(doc_id)

        # Verify the sections
        assert len(sections) == 3, "Should have 3 segments (h1, h2, text)"
        assert sections[0]["section_title"] == "Introduction"
        assert sections[1]["section_title"] == "First Section"
        assert sections[1]["parent_segment_id"] == intro_id

    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)
        config.DB_PATH = original_db_path


def test_migration_adds_section_columns():
    """Test that the migration adds section-related columns."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Set up the test database
        original_db_path = config.DB_PATH
        config.DB_PATH = db_path

        # Create a connection directly to set up the initial schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create the initial schema (without section columns)
        cursor.execute(
            """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            version TEXT,
            title TEXT,
            html_path TEXT,
            markdown_path TEXT,
            content_hash TEXT,
            library_id INTEGER,
            is_library_doc BOOLEAN DEFAULT 0,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (library_id) REFERENCES libraries(id)
        )
        """
        )

        cursor.execute(
            """
        CREATE TABLE document_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB,
            segment_type TEXT,
            position INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
        """
        )

        # Create the schema version table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        # Add a test document
        cursor.execute(
            """
            INSERT INTO documents (url, title, html_path, markdown_path)
            VALUES (?, ?, ?, ?)
            """,
            (
                "https://example.com/test",
                "Test Document",
                "/tmp/test.html",
                "/tmp/test.md",
            ),
        )
        doc_id = cursor.lastrowid

        # Add a segment without section info
        cursor.execute(
            """
            INSERT INTO document_segments (document_id, content, segment_type, position)
            VALUES (?, ?, ?, ?)
            """,
            (doc_id, "Test content", "text", 0),
        )

        conn.commit()
        conn.close()

        # Now run the migrations
        from docvault.db.migrations.migrations import migrate_schema

        assert migrate_schema(), "Migration failed"

        # Verify the columns were added
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check that the columns exist
        cursor.execute("PRAGMA table_info(document_segments)")
        columns = [row[1] for row in cursor.fetchall()]

        assert "section_title" in columns
        assert "section_level" in columns
        assert "section_path" in columns
        assert "parent_segment_id" in columns

        # Check that the existing segment has default section values
        cursor.execute(
            "SELECT section_title, section_level, section_path FROM document_segments"
        )
        row = cursor.fetchone()
        assert row[0] == "Introduction"  # Default section title
        assert row[1] == 1  # Default section level
        assert row[2] == "0"  # Default section path

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
        config.DB_PATH = original_db_path
