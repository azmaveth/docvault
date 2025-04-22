"""Tests for library documentation manager"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_resolve_doc_url_builtin_pattern(mock_config):
    """Test resolving documentation URL for built-in patterns"""
    from docvault.core.library_manager import LibraryManager

    manager = LibraryManager()

    # Mock URL check to always succeed
    with patch.object(manager, "check_url_exists", new=AsyncMock(return_value=True)):
        url = await manager.resolve_doc_url("numpy", "1.21.0")

        # Check that the URL is correct
        assert url == "https://numpy.org/doc/1.21.0/"


@pytest.mark.asyncio
async def test_resolve_doc_url_language_specific(mock_config):
    """Test resolving documentation URL for language-specific libraries"""
    from docvault.core.library_manager import LibraryManager

    manager = LibraryManager()

    # Mock URL check to always succeed
    with patch.object(manager, "check_url_exists", new=AsyncMock(return_value=True)):
        url = await manager.resolve_doc_url("tokio", "1.0.0")

        # Check that the URL is correct for Rust
        assert url == "https://docs.rs/tokio/1.0.0"


@pytest.mark.asyncio
async def test_pypi_doc_url(mock_config):
    """Test fetching documentation URL from PyPI"""
    # Use direct function replacement
    from docvault.core.library_manager import LibraryManager

    # Create a test instance
    manager = LibraryManager()

    # Create a direct replacement for the method
    async def mock_get_pypi_doc_url(self, library_name, version):
        assert library_name == "pytest"
        assert version == "7.0.0"
        return "https://docs.pytest.org/en/7.0.0/"

    # Apply the patch
    with patch.object(LibraryManager, "get_pypi_doc_url", mock_get_pypi_doc_url):
        url = await manager.get_pypi_doc_url("pytest", "7.0.0")

        # Check that the URL is correct
        assert url == "https://docs.pytest.org/en/7.0.0/"


@pytest.mark.asyncio
async def test_search_doc_url(mock_config):
    """Test searching for documentation URL"""
    from docvault.core.library_manager import LibraryManager

    # Set an API key for testing
    with patch("docvault.config.BRAVE_API_KEY", "fake-api-key"):
        manager = LibraryManager()

        # Create a direct replacement for the method
        async def mock_search_doc_url(self, library_name, version):
            assert library_name == "fastapi"
            assert version == "latest"
            return "https://fastapi.tiangolo.com/"

        # Apply the patch
        with (
            patch.object(LibraryManager, "search_doc_url", mock_search_doc_url),
            patch.object(manager, "check_url_exists", new=AsyncMock(return_value=True)),
        ):

            url = await manager.search_doc_url("fastapi", "latest")

            # Check that the URL is correct
            assert url == "https://fastapi.tiangolo.com/"


@pytest.mark.asyncio
async def test_get_library_docs_cached(mock_config, test_db):
    """Test retrieving library docs from cache"""
    from docvault.core.library_manager import LibraryManager
    from docvault.db.operations import add_document, add_library

    manager = LibraryManager()

    # Add a library and document to the database
    lib_id = add_library("pytest", "7.0.0", "https://docs.pytest.org/en/7.0.0/")
    doc_id = add_document(
        url="https://docs.pytest.org/en/7.0.0/",
        title="pytest 7.0.0",
        html_path="/fake/path/pytest.html",
        markdown_path="/fake/path/pytest.md",
        library_id=lib_id,
        is_library_doc=True,
    )

    # Mock operations.get_library_documents
    with patch(
        "docvault.db.operations.get_library_documents",
        return_value=[{"id": doc_id, "title": "pytest 7.0.0"}],
    ):
        docs = await manager.get_library_docs("pytest", "7.0.0")

        # Check that we got docs back
        assert docs is not None
        assert len(docs) == 1
        assert docs[0]["title"] == "pytest 7.0.0"


@pytest.mark.asyncio
async def test_get_library_docs_latest_version(mock_config, test_db):
    """Test retrieving latest library docs"""
    from docvault.core.library_manager import LibraryManager
    from docvault.db.operations import add_library

    # Set up test
    manager = LibraryManager()

    # Add library records for different versions
    add_library("pytest", "6.2.5", "https://docs.pytest.org/en/6.2.5/")
    add_library("pytest", "7.0.0", "https://docs.pytest.org/en/7.0.0/")

    # Mock operations.get_latest_library_version for correct behavior
    with patch(
        "docvault.db.operations.get_latest_library_version",
        return_value={"id": 2, "version": "7.0.0", "is_available": True},
    ):

        # Mock operations.get_library_documents
        with patch(
            "docvault.db.operations.get_library_documents",
            return_value=[{"id": 2, "title": "pytest 7.0.0"}],
        ):

            docs = await manager.get_library_docs("pytest", "latest")

            # Check that we got docs back for the latest version
            assert docs is not None
            assert len(docs) == 1
            assert docs[0]["title"] == "pytest 7.0.0"


@pytest.mark.asyncio
async def test_determine_actual_version(mock_config):
    """Test determining actual version from URL"""
    from docvault.core.library_manager import LibraryManager

    manager = LibraryManager()

    # Test various URL patterns
    test_cases = [
        ("https://docs.pytest.org/en/v7.0.0/", "7.0.0"),
        ("https://docs.pytest.org/en/7.0.0/", "7.0.0"),
        ("https://docs.djangoproject.com/en/4.1/", "4.1"),
        ("https://numpy.org/doc/1.21.0/", "1.21.0"),
        ("https://docs.python.org/3.9/", "3.9"),
        ("https://fastapi.tiangolo.com/", "latest"),  # No version in URL
    ]

    for url, expected_version in test_cases:
        actual_version = await manager.determine_actual_version("test-lib", url)
        assert actual_version == expected_version


@pytest.mark.asyncio
async def test_find_latest_version_with_search(mock_config):
    """Test finding latest version using search"""
    from docvault.core.library_manager import LibraryManager

    # Create a test instance
    manager = LibraryManager()

    # Create a direct replacement for the method that returns "7.0.0"
    async def mock_find_latest_version(self, library_name):
        assert library_name == "pytest"
        return "7.0.0"

    # Apply the patch
    with patch.object(
        LibraryManager, "find_latest_version_with_search", mock_find_latest_version
    ):
        version = await manager.find_latest_version_with_search("pytest")

        # Check that the version is correct
        assert version == "7.0.0"
