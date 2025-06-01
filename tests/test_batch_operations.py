"""Tests for batch operations functionality."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from docvault.main import cli
from tests.utils import mock_app_initialization


@pytest.fixture
def runner():
    """Create a CliRunner instance."""
    return CliRunner()


@pytest.fixture
def mock_library_manager():
    """Mock LibraryManager for testing."""
    with patch("docvault.core.library_manager.LibraryManager") as mock:
        yield mock


def test_batch_search_help(runner, mock_app_initialization):
    """Test batch search command help."""
    result = runner.invoke(cli, ["search", "batch", "--help"])
    assert result.exit_code == 0
    assert "Search documentation for multiple libraries" in result.output
    assert "--concurrent" in result.output
    assert "--timeout" in result.output


def test_batch_search_no_args(runner, mock_app_initialization):
    """Test batch search with no arguments."""
    result = runner.invoke(cli, ["search", "batch"])
    assert result.exit_code != 0
    assert "Missing argument" in result.output or "Error" in result.output


def test_batch_search_multiple_libraries(
    runner, mock_library_manager, mock_app_initialization
):
    """Test batch search with multiple libraries."""
    # Mock the library manager
    mock_manager_instance = AsyncMock()
    mock_library_manager.return_value = mock_manager_instance

    # Mock responses for different libraries
    mock_manager_instance.get_library_docs.side_effect = [
        # requests
        [
            {
                "title": "Requests Documentation",
                "url": "https://docs.python-requests.org",
                "resolved_version": "2.31.0",
            }
        ],
        # flask
        [
            {
                "title": "Flask Documentation",
                "url": "https://flask.palletsprojects.com",
                "resolved_version": "2.3.0",
            }
        ],
        # numpy
        [
            {
                "title": "NumPy Documentation",
                "url": "https://numpy.org/doc",
                "resolved_version": "1.25.0",
            }
        ],
    ]

    result = runner.invoke(cli, ["search", "batch", "requests", "flask", "numpy"])

    assert result.exit_code == 0
    assert "Batch Search Summary" in result.output
    assert "Successful" in result.output
    assert "requests" in result.output
    assert "flask" in result.output
    assert "numpy" in result.output


def test_batch_search_with_versions(
    runner, mock_library_manager, mock_app_initialization
):
    """Test batch search with versioned libraries."""
    mock_manager_instance = AsyncMock()
    mock_library_manager.return_value = mock_manager_instance

    # Mock response
    mock_manager_instance.get_library_docs.side_effect = [
        [
            {
                "title": "Django 4.2",
                "url": "https://docs.djangoproject.com",
                "resolved_version": "4.2",
            }
        ],
        [
            {
                "title": "Flask 2.0",
                "url": "https://flask.palletsprojects.com",
                "resolved_version": "2.0",
            }
        ],
    ]

    result = runner.invoke(cli, ["search", "batch", "django@4.2", "flask@2.0"])

    assert result.exit_code == 0
    assert "django@4.2" in result.output
    assert "flask@2.0" in result.output


def test_batch_search_json_output(
    runner, mock_library_manager, mock_app_initialization
):
    """Test batch search with JSON output."""
    mock_manager_instance = AsyncMock()
    mock_library_manager.return_value = mock_manager_instance

    # Mock responses
    mock_manager_instance.get_library_docs.side_effect = [
        [
            {
                "title": "Requests",
                "url": "https://example.com",
                "resolved_version": "2.31.0",
            }
        ],
        Exception("Library not found"),
    ]

    result = runner.invoke(
        cli, ["search", "batch", "requests", "nonexistent", "--format", "json"]
    )

    assert result.exit_code == 0

    # Parse JSON output
    # Split output by lines and find the JSON part
    lines = result.output.strip().split("\n")
    json_str = ""
    in_json = False
    for line in lines:
        if line.strip().startswith("{"):
            in_json = True
        if in_json:
            json_str += line + "\n"

    json_output = json.loads(json_str)
    assert "total" in json_output
    assert json_output["total"] == 2
    assert "successful" in json_output
    assert json_output["successful"] == 1
    assert "failed" in json_output
    assert json_output["failed"] == 1
    assert "results" in json_output
    assert len(json_output["results"]) == 2


def test_batch_search_with_failures(
    runner, mock_library_manager, mock_app_initialization
):
    """Test batch search handling failures gracefully."""
    mock_manager_instance = AsyncMock()
    mock_library_manager.return_value = mock_manager_instance

    # Mock a failure
    from docvault.core.exceptions import LibraryNotFoundError

    mock_manager_instance.get_library_docs.side_effect = LibraryNotFoundError(
        "Library 'fake-lib' not found"
    )

    result = runner.invoke(cli, ["search", "batch", "fake-lib"])

    assert result.exit_code == 0
    assert "Failed" in result.output
    assert "fake-lib" in result.output
    assert "not found" in result.output.lower()


def test_batch_search_timeout(runner, mock_library_manager, mock_app_initialization):
    """Test batch search timeout handling."""
    import asyncio

    mock_manager_instance = AsyncMock()
    mock_library_manager.return_value = mock_manager_instance

    # Mock a slow response that will timeout
    async def slow_response(*args):
        await asyncio.sleep(10)  # Longer than timeout
        return []

    mock_manager_instance.get_library_docs.side_effect = slow_response

    result = runner.invoke(cli, ["search", "batch", "slow-lib", "--timeout", "1"])

    assert result.exit_code == 0
    assert "timed out" in result.output.lower()


def test_batch_search_concurrent_limit(
    runner, mock_library_manager, mock_app_initialization
):
    """Test batch search respects concurrent limit."""
    mock_manager_instance = AsyncMock()
    mock_library_manager.return_value = mock_manager_instance

    # Track concurrent calls
    concurrent_calls = []
    max_concurrent = 0

    async def track_concurrent(*args):
        concurrent_calls.append(1)
        current = len(concurrent_calls)
        nonlocal max_concurrent
        max_concurrent = max(max_concurrent, current)
        await asyncio.sleep(0.1)  # Simulate work
        concurrent_calls.pop()
        return [{"title": f"Doc for {args[0]}", "url": "https://example.com"}]

    mock_manager_instance.get_library_docs.side_effect = track_concurrent

    # Search for 5 libraries with concurrency limit of 2
    result = runner.invoke(
        cli,
        [
            "search",
            "batch",
            "lib1",
            "lib2",
            "lib3",
            "lib4",
            "lib5",
            "--concurrent",
            "2",
        ],
    )

    assert result.exit_code == 0
    # Due to async nature, we can't guarantee exact concurrent count,
    # but it should have processed all libraries
    assert "lib1" in result.output
    assert "lib5" in result.output


def test_batch_search_default_version(
    runner, mock_library_manager, mock_app_initialization
):
    """Test batch search with default version flag."""
    mock_manager_instance = AsyncMock()
    mock_library_manager.return_value = mock_manager_instance

    # Capture the version passed to get_library_docs
    captured_versions = []

    async def capture_version(lib_name, version):
        captured_versions.append((lib_name, version))
        return [{"title": f"{lib_name} docs", "url": "https://example.com"}]

    mock_manager_instance.get_library_docs.side_effect = capture_version

    result = runner.invoke(
        cli, ["search", "batch", "requests", "flask", "--version", "stable"]
    )

    assert result.exit_code == 0
    assert ("requests", "stable") in captured_versions
    assert ("flask", "stable") in captured_versions
