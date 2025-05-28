"""Common fixtures for DocVault tests"""

import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

# Import shared fixtures from utils
from .utils import mock_app_initialization, temp_project


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    # Cleanup after tests
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_db_path(temp_dir):
    """Create a temporary database path"""
    return temp_dir / "docvault_test.db"


@pytest.fixture
def mock_config(temp_dir, temp_db_path, monkeypatch):
    """Mock configuration for tests"""
    # Set up temporary paths for testing
    storage_path = temp_dir / "storage"
    storage_path.mkdir(exist_ok=True)
    log_dir = temp_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    # Mock config values
    monkeypatch.setattr("docvault.config.DB_PATH", str(temp_db_path))
    monkeypatch.setattr("docvault.config.STORAGE_PATH", str(storage_path))
    monkeypatch.setattr("docvault.config.LOG_DIR", str(log_dir))
    monkeypatch.setattr("docvault.config.LOG_FILE", str(log_dir / "docvault_test.log"))
    monkeypatch.setattr("docvault.config.EMBEDDING_MODEL", "fake-embedding-model")
    monkeypatch.setattr("docvault.config.OLLAMA_URL", "http://localhost:11434")


@pytest.fixture
def test_db(temp_db_path, mock_config):
    """Set up a test database with schema"""
    # Import here to use the mocked config
    from docvault.db.schema import initialize_database

    # Initialize the database
    initialize_database(force_recreate=True)

    # Return connection for test use
    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    yield conn

    # Close and clean up
    conn.close()
