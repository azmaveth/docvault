"""Shared test utilities and fixtures for DocVault tests."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from docvault.db.schema import initialize_database


class TestProjectManager:
    """Test project manager that uses temporary directories."""

    def __init__(self, temp_dir):
        self.temp_dir = Path(temp_dir)
        self.docvault_dir = self.temp_dir / ".docvault"
        self.db_path = self.docvault_dir / "docvault.db"
        self.config_file = self.docvault_dir / "config.json"
        self.registry_path = self.docvault_dir / "registry.json"
        self.env_file = self.temp_dir / ".env"

        # Create directories
        self.docvault_dir.mkdir(parents=True, exist_ok=True)

    def initialize_test_db(self):
        """Initialize a test database."""
        # Temporarily override the DB path
        import docvault.config as config

        original_db_path = config.DB_PATH
        config.DB_PATH = str(self.db_path)

        try:
            initialize_database(force_recreate=True)
        finally:
            config.DB_PATH = original_db_path

    def get_db_path(self):
        """Get database path."""
        return str(self.db_path)


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory with initialized database."""
    project = TestProjectManager(tmp_path)
    project.initialize_test_db()
    return project


@pytest.fixture
def mock_app_initialization():
    """Mock app initialization to prevent file system operations."""
    with patch("docvault.core.initialization.ensure_app_initialized"):
        with patch("docvault.utils.logging.setup_logging"):
            # Also mock the config to use temp directories
            with patch("docvault.config.DEFAULT_BASE_DIR", new=tempfile.gettempdir()):
                yield


@pytest.fixture
def mock_embeddings():
    """Mock embedding generation with realistic vectors."""
    import numpy as np

    def generate_mock_embedding(text):
        # Generate consistent embeddings based on text hash
        seed = hash(text) % 2**32
        np.random.seed(seed)
        return np.random.rand(384).astype(np.float32)

    with patch("docvault.core.embeddings.generate_embeddings") as mock:
        mock.side_effect = generate_mock_embedding
        yield mock


@pytest.fixture
def sample_document():
    """Create a sample document for testing."""
    return {
        "id": 1,
        "title": "Test Documentation",
        "url": "https://example.com/docs",
        "content": "# Test Documentation\n\nThis is test content.",
        "segments": [
            {
                "type": "text",
                "content": "This is test content.",
                "section_title": "Introduction",
            },
            {
                "type": "code",
                "content": "print('Hello, World!')",
                "section_title": "Examples",
            },
        ],
    }


@pytest.fixture
def sample_search_results():
    """Create sample search results."""
    return [
        {
            "id": 1,
            "document_id": 1,
            "segment_id": 1,
            "title": "Python Documentation",
            "content": "Python is a programming language",
            "score": 0.95,
            "url": "https://docs.python.org",
        },
        {
            "id": 2,
            "document_id": 1,
            "segment_id": 2,
            "title": "Python Documentation",
            "content": "Python supports multiple programming paradigms",
            "score": 0.85,
            "url": "https://docs.python.org",
        },
    ]


def create_test_document_in_db(db_path, document):
    """Helper to create a test document in the database."""
    import sqlite3

    # Convert Path to string if necessary
    if hasattr(db_path, "__fspath__"):
        db_path = str(db_path)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Insert document
        cursor.execute(
            """
            INSERT INTO documents (title, url, version, scraped_at)
            VALUES (?, ?, ?, datetime('now'))
        """,
            (document["title"], document["url"], document.get("version", "latest")),
        )

        doc_id = cursor.lastrowid

        # Insert segments if provided
        if "segments" in document:
            for segment in document["segments"]:
                cursor.execute(
                    """
                    INSERT INTO document_segments (
                        document_id, content, segment_type, section_title
                    ) VALUES (?, ?, ?, ?)
                """,
                    (
                        doc_id,
                        segment.get("content", ""),
                        segment.get("type", "text"),
                        segment.get("section_title"),
                    ),
                )

        conn.commit()
        return doc_id


class MockAsyncContextManager:
    """Mock async context manager for testing."""

    def __init__(self, return_value=None):
        self.return_value = return_value

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    def __call__(self, *args, **kwargs):
        return self.return_value
