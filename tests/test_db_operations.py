"""Tests for database operations"""

import datetime

import numpy as np
import pytest


@pytest.fixture
def sample_doc(test_db):
    """Create a sample document in the database"""
    cursor = test_db.cursor()
    cursor.execute(
        """
    INSERT INTO documents 
    (url, title, html_path, markdown_path, version, content_hash, scraped_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            "https://example.com/test",
            "Test Document",
            "/path/to/html",
            "/path/to/markdown",
            "v1.0.0",
            "abc123hash",
            datetime.datetime.now(),
        ),
    )
    doc_id = cursor.lastrowid
    test_db.commit()
    return doc_id


def test_add_document(test_db, mock_config):
    """Test adding a document to the database"""
    from docvault.db.operations import add_document

    # Test data
    url = "https://example.com/page"
    title = "Example Page"
    html_path = "/tmp/example.html"
    md_path = "/tmp/example.md"

    # Add document
    version = "v2.1.0"
    content_hash = "cafebabedeadbeef"
    doc_id = add_document(
        url, title, html_path, md_path, version=version, content_hash=content_hash
    )

    # Verify document was added
    cursor = test_db.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    doc = cursor.fetchone()

    assert doc is not None
    assert doc["url"] == url
    assert doc["title"] == title
    assert doc["html_path"] == html_path
    assert doc["markdown_path"] == md_path
    assert doc["version"] == version
    assert doc["content_hash"] == content_hash


def test_get_document(test_db, sample_doc, mock_config):
    """Test retrieving a document by ID"""
    from docvault.db.operations import get_document

    # Get the test document
    doc = get_document(sample_doc)

    assert doc is not None
    assert doc["id"] == sample_doc
    assert doc["url"] == "https://example.com/test"
    assert doc["title"] == "Test Document"


def test_delete_document(test_db, sample_doc, mock_config):
    """Test deleting a document"""
    from docvault.db.operations import delete_document, get_document

    # Verify document exists
    doc = get_document(sample_doc)
    assert doc is not None

    # Delete the document
    result = delete_document(sample_doc)
    assert result is True

    # Verify document was deleted
    doc = get_document(sample_doc)
    assert doc is None


def test_add_document_segment(test_db, sample_doc, mock_config):
    """Test adding a segment to a document"""
    from docvault.db.operations import add_document_segment

    # Test data
    content = "This is a test segment."
    embedding = np.random.rand(384).astype(np.float32).tobytes()

    # Add segment
    segment_id = add_document_segment(
        sample_doc, content, embedding, segment_type="text", position=1
    )

    # Verify segment was added
    cursor = test_db.cursor()
    cursor.execute("SELECT * FROM document_segments WHERE id = ?", (segment_id,))
    segment = cursor.fetchone()

    assert segment is not None
    assert segment["document_id"] == sample_doc
    assert segment["content"] == content
    assert segment["segment_type"] == "text"
    assert segment["position"] == 1


def test_list_documents(test_db, mock_config):
    """Test listing documents"""
    from docvault.db.operations import add_document, list_documents

    # Add multiple documents
    add_document(
        "https://example.com/1",
        "Test 1",
        "/tmp/1.html",
        "/tmp/1.md",
        version="v1",
        content_hash="hash1",
    )
    add_document(
        "https://example.com/2",
        "Test 2",
        "/tmp/2.html",
        "/tmp/2.md",
        version="v2",
        content_hash="hash2",
    )
    add_document(
        "https://example.com/3",
        "Test 3",
        "/tmp/3.html",
        "/tmp/3.md",
        version="v3",
        content_hash="hash3",
    )

    # List documents
    docs = list_documents(limit=10)

    assert len(docs) == 3
    assert docs[0]["title"] == "Test 3"  # Most recently added first
    assert docs[0]["version"] == "v3"
    assert docs[0]["content_hash"] == "hash3"
    assert docs[1]["title"] == "Test 2"
    assert docs[1]["version"] == "v2"
    assert docs[1]["content_hash"] == "hash2"
    assert docs[2]["title"] == "Test 1"
    assert docs[2]["version"] == "v1"
    assert docs[2]["content_hash"] == "hash1"

    # Test filtering
    filtered_docs = list_documents(filter_text="Test 2")
    assert len(filtered_docs) == 1
    assert filtered_docs[0]["title"] == "Test 2"


def test_library_operations(test_db, mock_config):
    """Test library-related database operations"""
    from docvault.db.operations import (
        add_library,
        get_latest_library_version,
        get_library,
    )

    # Add a library
    add_library("pytest", "6.2.5", "https://docs.pytest.org/en/6.2.5/")
    # Get the library
    lib = get_library("pytest", "6.2.5")

    assert lib is not None
    assert lib["name"] == "pytest"
    assert lib["version"] == "6.2.5"
    assert lib["doc_url"] == "https://docs.pytest.org/en/6.2.5/"
    assert lib["is_available"] == 1  # SQLite stores booleans as 1/0

    # Add another version
    add_library("pytest", "7.0.0", "https://docs.pytest.org/en/7.0.0/")

    # Get latest version
    latest = get_latest_library_version("pytest")

    assert latest is not None
    assert latest["name"] == "pytest"
    assert latest["version"] == "7.0.0"  # Should pick the newer version
