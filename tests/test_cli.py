"""Tests for CLI commands"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing"""
    return CliRunner()


@pytest.fixture
def mock_embeddings():
    """Mock embedding generation"""
    sample_embedding = np.random.rand(384).astype(np.float32).tobytes()

    async def mock_generate_embeddings(text):
        return sample_embedding

    with patch(
        "docvault.core.embeddings.generate_embeddings", new=mock_generate_embeddings
    ):
        yield


def test_placeholder():
    """Placeholder test that will pass"""
    assert True


def test_main_help_shown_on_no_args(cli_runner):
    """Test that running dv with no arguments shows main help."""
    from docvault.main import create_main

    main = create_main()
    result = cli_runner.invoke(main, [])
    assert result.exit_code == 0
    assert "DocVault: Document management system" in result.output
    assert "Usage: " in result.output


def test_default_to_search_text_on_unknown_args(cli_runner):
    """Test that unknown args are forwarded as a query to search text."""
    from docvault.main import create_main

    main = create_main()
    result = cli_runner.invoke(main, ["foo", "bar"])
    # Accept exit_code 0 (success) or 1 (no results), but not 2 (usage error)
    assert result.exit_code in (0, 1)
    # Should show search output or 'No matching documents found'
    assert (
        "Search Results" in result.output
        or "No matching documents found" in result.output
    )


def test_default_to_search_text_on_single_unknown_arg(cli_runner):
    """Test that a single unknown arg is forwarded as a query to search text."""
    from docvault.main import create_main

    main = create_main()
    result = cli_runner.invoke(main, ["pygame"])
    # Accept exit_code 0 (success) or 1 (no results), but not 2 (usage error)
    assert result.exit_code in (0, 1)
    # Should show search output or 'No matching documents found'
    assert (
        "Search Results" in result.output
        or "No matching documents found" in result.output
    )


def test_main_init(mock_config, cli_runner, mock_embeddings):
    """Test main CLI initialization"""
    # Import needed modules AFTER patching
    with patch("docvault.core.initialization.ensure_app_initialized") as mock_init:
        # Import main after patching
        from docvault.main import create_main

        main = create_main()
        with patch("docvault.db.operations.list_documents", return_value=[]):
            # Run the command with standalone_mode=False to ensure context is preserved
            result = cli_runner.invoke(main, ["list"], standalone_mode=False)

            # Verify initialization was called
            mock_init.assert_called_once()

            # Verify command succeeded
            assert result.exit_code == 0


def test_search_command(mock_config, cli_runner):
    """Test search command"""
    from docvault.main import create_main

    main = create_main()

    # Mock the docvault.core.embeddings.search function
    sample_results = [
        {
            "id": 1,
            "document_id": 1,
            "content": "Test content",
            "segment_type": "text",
            "title": "Test Document",
            "url": "https://example.com/test",
            "score": 0.95,
        }
    ]

    # Mock embeddings.search async function
    async def mock_search_func(query, limit=5, text_only=False):
        # Return sample results directly
        return sample_results

    # Use AsyncMock to handle the async nature of the function
    mock_search = AsyncMock(side_effect=mock_search_func)

    with patch("docvault.core.embeddings.search", mock_search):
        # Run command
        result = cli_runner.invoke(main, ["search", "text", "pytest", "--limit", "5"])

        # Verify command succeeded
        assert result.exit_code == 0
        assert "Test Document" in result.output
        assert "https://example.com/test" in result.output


def test_list_command(mock_config, cli_runner):
    """Test list command"""
    from docvault.main import create_main

    main = create_main()

    # Mock the list_documents function
    sample_docs = [
        {
            "id": 1,
            "url": "https://example.com/test1",
            "title": "Test Document 1",
            "scraped_at": "2024-02-25 10:00:00",
        },
        {
            "id": 2,
            "url": "https://example.com/test2",
            "title": "Test Document 2",
            "scraped_at": "2024-02-25 11:00:00",
        },
    ]

    with patch("docvault.db.operations.list_documents", return_value=sample_docs):
        # Run command
        result = cli_runner.invoke(main, ["list"])

        # Verify command succeeded
        assert result.exit_code == 0
        # Accept either the full title or split table output
        assert result.output.count("Test Document") >= 2
        assert result.output.count("1") >= 1
        assert result.output.count("2") >= 1


def test_search_lib_command(mock_config, cli_runner, test_db, mock_embeddings):
    """Test 'search lib' subcommand for library documentation lookup"""
    from docvault.db.schema import initialize_database
    from docvault.main import create_main

    main = create_main()

    # Initialize database with required tables
    initialize_database(force_recreate=True)

    # Mock the get_library_docs method
    async def mock_get_library_docs(*args, **kwargs):
        return [
            {
                "id": 1,
                "url": "https://docs.pytest.org/en/7.0.0/",
                "title": "pytest Documentation",
                "resolved_version": "7.0.0",
            }
        ]

    with patch(
        "docvault.core.library_manager.LibraryManager.get_library_docs",
        new=mock_get_library_docs,
    ):
        # Run command as 'dv search lib pytest --version 7.0.0'
        result = cli_runner.invoke(
            main, ["search", "lib", "pytest", "--version", "7.0.0"]
        )
        # Verify command succeeded
        assert result.exit_code == 0
        assert "pytest Documentation" in result.output


def test_add_command(mock_config, cli_runner, mock_embeddings):
    """Test add command"""
    from docvault.main import create_main

    main = create_main()

    # Mock the scraper and document result
    mock_document = {
        "id": 1,
        "title": "Test Documentation",
        "url": "https://example.com/docs",
    }

    # Mock scraper class with stats
    mock_scraper = MagicMock()
    mock_scraper.stats = {"pages_scraped": 3, "pages_skipped": 1, "segments_created": 6}
    mock_scraper.scrape_url = AsyncMock(return_value=mock_document)

    with patch("docvault.core.scraper.get_scraper", return_value=mock_scraper):
        # Run command using add
        result = cli_runner.invoke(main, ["add", "https://example.com/docs"])

        # Verify command succeeded
        assert result.exit_code == 0
        assert "Test Documentation" in result.output
        assert "Pages Scraped" in result.output
        assert "3" in result.output  # Pages scraped count


def test_read_command(mock_config, cli_runner):
    """Test read command"""
    from docvault.main import create_main

    main = create_main()

    # Create a test document
    mock_doc = {
        "id": 1,
        "title": "Test Documentation",
        "url": "https://example.com/docs",
        "markdown_path": "/test/path/doc.md",
        "html_path": "/test/path/doc.html",
    }

    # Mock markdown content
    mock_content = "# Test Documentation\n\nThis is test content."

    with patch("docvault.db.operations.get_document", return_value=mock_doc):
        with patch("docvault.core.storage.read_markdown", return_value=mock_content):
            with patch(
                "docvault.core.storage.open_html_in_browser"
            ) as mock_open_browser:
                # Test markdown format (default)
                md_result = cli_runner.invoke(main, ["read", "1"])

                # Verify markdown result
                assert md_result.exit_code == 0
                assert "Test Documentation" in md_result.output
                assert "This is test content" in md_result.output

                # Test HTML format
                html_result = cli_runner.invoke(main, ["read", "1", "--format", "html"])

                # Verify HTML result and browser open
                assert html_result.exit_code == 0
                mock_open_browser.assert_called_once_with("/test/path/doc.html")


def test_rm_command(mock_config, cli_runner):
    """Test rm command"""
    from docvault.main import create_main

    main = create_main()

    # Create test documents
    mock_docs = [
        {
            "id": 3,
            "title": "Test Doc 3",
            "url": "https://example.com/doc3",
            "html_path": "/test/path/doc3.html",
            "markdown_path": "/test/path/doc3.md",
        },
        {
            "id": 4,
            "title": "Test Doc 4",
            "url": "https://example.com/doc4",
            "html_path": "/test/path/doc4.html",
            "markdown_path": "/test/path/doc4.md",
        },
        {
            "id": 5,
            "title": "Test Doc 5",
            "url": "https://example.com/doc5",
            "html_path": "/test/path/doc5.html",
            "markdown_path": "/test/path/doc5.md",
        },
    ]

    def mock_get_document(doc_id):
        for doc in mock_docs:
            if doc["id"] == doc_id:
                return doc
        return None

    # Set up mocks
    with patch("docvault.db.operations.get_document", side_effect=mock_get_document):
        with patch("docvault.db.operations.delete_document") as mock_delete:
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.unlink"):
                    # Test single ID
                    result1 = cli_runner.invoke(main, ["rm", "3", "--force"])
                    assert result1.exit_code == 0
                    assert "Test Doc 3" in result1.output

                    # Test comma-separated IDs
                    result2 = cli_runner.invoke(main, ["rm", "4,5", "--force"])
                    assert result2.exit_code == 0
                    assert "Test Doc 4" in result2.output
                    assert "Test Doc 5" in result2.output

                    # Test range syntax
                    mock_delete.reset_mock()
                    result3 = cli_runner.invoke(main, ["rm", "3-5", "--force"])
                    assert result3.exit_code == 0
                    assert mock_delete.call_count == 3

                    # Test mixed format
                    mock_delete.reset_mock()
                    result4 = cli_runner.invoke(main, ["rm", "3,4-5", "--force"])
                    assert result4.exit_code == 0
                    assert mock_delete.call_count == 3


def test_config_command(mock_config, cli_runner):
    """Test config command"""
    from docvault.main import create_main

    with (
        patch("docvault.config") as mock_config_module,
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.write_text") as mock_write,
        patch("pathlib.Path.mkdir"),
        patch("os.environ", {}),
    ):
        # Set some test config values
        mock_config_module.DB_PATH = "/test/db/path.db"
        mock_config_module.STORAGE_PATH = "/test/storage/path"
        mock_config_module.LOG_DIR = "/test/log/dir"
        mock_config_module.LOG_LEVEL = "INFO"
        mock_config_module.EMBEDDING_MODEL = "test-model"
        mock_config_module.OLLAMA_URL = "http://test:11434"
        mock_config_module.SERVER_HOST = "localhost"
        mock_config_module.SERVER_PORT = "8000"
        mock_config_module.DEFAULT_BASE_DIR = "/test/base/dir"

        main = create_main()

        # Run command
        result = cli_runner.invoke(main, ["config"])
        assert result.exit_code == 0
        assert "Current Configuration" in result.output
        assert "/test/db/path.db" in result.output
        assert "/test/storage/path" in result.output
        assert "test-model" in result.output

        # Run command with init flag
        with patch(
            "docvault.main.create_env_template", return_value="# Test env template"
        ):
            result = cli_runner.invoke(main, ["config", "--init"])
            assert result.exit_code == 0
            assert "Created configuration file" in result.output
            mock_write.assert_called()


def test_init_db_command(mock_config, cli_runner):
    """Test init-db command"""
    # Patch BEFORE importing main, so Click command uses the patched function
    with patch("docvault.db.schema.initialize_database") as mock_init_db:
        from docvault.main import create_main

        main = create_main()
        mock_init_db.reset_mock()  # Ignore calls during CLI creation
        # Test successful initialization
        result = cli_runner.invoke(main, ["init-db"])

        # Verify results
        assert result.exit_code == 0
        assert "Database initialized successfully" in result.output
        found = False
        for call in mock_init_db.call_args_list:
            if call[1].get("force_recreate", False) is False:
                found = True
        assert found, "initialize_database should be called with force_recreate=False"

        # Test with force flag
        mock_init_db.reset_mock()
        result_force = cli_runner.invoke(main, ["init-db", "--force"])

        # Verify force results
        assert result_force.exit_code == 0
        assert "Database initialized successfully" in result_force.output
        found = False
        for call in mock_init_db.call_args_list:
            if call[1].get("force_recreate", False) is True:
                found = True
        assert found, "initialize_database should be called with force_recreate=True"

    # Test error handling
    with patch(
        "docvault.db.schema.initialize_database", side_effect=Exception("Test error")
    ):
        from docvault.main import create_main

        main = create_main()
        # Run command
        result = cli_runner.invoke(main, ["init-db"])

        # Verify error is reported
        assert result.exit_code != 0
        assert result.exception is not None
        assert "Test error" in str(result.exception)


def test_backup_command(mock_config, cli_runner):
    """Test backup command"""
    from docvault.main import create_main

    with (
        patch("docvault.cli.commands.datetime") as mock_datetime,
        patch("shutil.make_archive") as mock_archive,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.mkdir"),
        patch("os.environ", {}),
        patch("docvault.config") as mock_config_module,
    ):
        # Ensure consistent timestamp
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20240226_120000"
        mock_datetime.now.return_value = mock_now
        mock_config_module.DEFAULT_BASE_DIR = "/test/base/dir"

        main = create_main()

        # Run command
        result = cli_runner.invoke(main, ["backup"])
        assert result.exit_code == 0
        assert "Backup created" in result.output
        mock_archive.assert_called_once()

        # Test with custom destination
        mock_archive.reset_mock()
        result_custom = cli_runner.invoke(main, ["backup", "custom_backup"])
        assert result_custom.exit_code == 0
        assert "Backup created" in result_custom.output
        mock_archive.assert_called_once()
        assert "custom_backup" in mock_archive.call_args[0][0]


def test_import_backup_command(mock_config, cli_runner):
    """Test import-backup command"""
    import os
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    from docvault.main import create_main

    def custom_open(file, mode="r", *args, **kwargs):
        if file == "backup.zip" or (
            hasattr(file, "name") and file.name == "backup.zip"
        ):
            return patch(
                "builtins.open", return_value=MagicMock(read_data=b"dummy content")
            )()
        return patch("builtins.open")()

    with (
        cli_runner.isolated_filesystem(),
        patch("docvault.config") as mock_config_module,
        patch("pathlib.Path.exists", return_value=True),
        patch("os.path.exists", return_value=True),
        patch("os.path.isfile", return_value=True),
        patch("pathlib.Path.iterdir", return_value=[MagicMock()]),
        patch("tempfile.TemporaryDirectory") as mock_temp,
        patch("shutil.unpack_archive") as mock_unpack,
        patch("shutil.copy2"),
        patch("shutil.rmtree"),
        patch("shutil.copytree"),
        patch("os.environ", {}),
        patch("builtins.open", custom_open),
    ):
        mock_unpack.side_effect = lambda *a, **k: None
        mock_temp.return_value.__enter__.return_value = "/tmp/backup"
        mock_config_module.DB_PATH = "test_db/path.db"
        mock_config_module.STORAGE_PATH = "test_storage/path"
        import os
        from pathlib import Path

        Path(mock_config_module.STORAGE_PATH).mkdir(parents=True, exist_ok=True)
        mock_config_module.DEFAULT_BASE_DIR = os.getcwd()
        main = create_main()
        Path("backup.zip").write_bytes(b"dummy content")
        result = cli_runner.invoke(
            main,
            ["import-backup", "backup.zip", "--force"],
        )
        if result.exit_code != 0:
            print("DEBUG: result.output:", result.output)
            print("DEBUG: result.exception:", result.exception)
        assert result.exit_code == 0
        assert "Backup imported successfully" in result.output
        mock_unpack.assert_called_once()


# Skip the serve command test for now since we don't want to import MCP
@pytest.mark.skip(reason="MCP module not available in test environment")
def test_serve_command(mock_config, cli_runner):
    """Test serve command (skipped)"""
    pass
