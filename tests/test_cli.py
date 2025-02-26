"""Tests for CLI commands"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from click.testing import CliRunner
import numpy as np
import click
import os
from pathlib import Path

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
    
    with patch('docvault.core.embeddings.generate_embeddings', 
              new=mock_generate_embeddings):
        yield

def test_placeholder():
    """Placeholder test that will pass"""
    assert True

def test_main_init(mock_config, cli_runner, mock_embeddings):
    """Test main CLI initialization"""
    # Import needed modules AFTER patching
    with patch('docvault.core.initialization.ensure_app_initialized') as mock_init:
        # Import main after patching
        from docvault.main import main
        
        with patch('docvault.db.operations.list_documents', return_value=[]):
            # Run the command with standalone_mode=False to ensure context is preserved
            result = cli_runner.invoke(main, ['list'], standalone_mode=False)

            # Verify initialization was called
            mock_init.assert_called_once()

            # Verify command succeeded
            assert result.exit_code == 0


def test_search_command(mock_config, cli_runner):
    """Test search command"""
    from docvault.cli.commands import search
    
    # Mock the docvault.core.embeddings.search function
    sample_results = [
        {
            'id': 1,
            'document_id': 1,
            'content': 'Test content',
            'segment_type': 'text',
            'title': 'Test Document',
            'url': 'https://example.com/test',
            'score': 0.95
        }
    ]
    
    with patch('docvault.core.embeddings.search',
               new=MagicMock(return_value=sample_results)):
        # Run command
        result = cli_runner.invoke(search, ['pytest', '--limit', '5'])
        
        # Verify command succeeded
        assert result.exit_code == 0
        assert "Test Document" in result.output
        assert "https://example.com/test" in result.output


def test_list_command(mock_config, cli_runner):
    """Test list command"""
    from docvault.cli.commands import list_docs
    
    # Mock the list_documents function
    sample_docs = [
        {
            'id': 1,
            'url': 'https://example.com/test1',
            'title': 'Test Document 1',
            'scraped_at': '2024-02-25 10:00:00'
        },
        {
            'id': 2,
            'url': 'https://example.com/test2',
            'title': 'Test Document 2',
            'scraped_at': '2024-02-25 11:00:00'
        }
    ]
    
    with patch('docvault.db.operations.list_documents',
               return_value=sample_docs):
        # Run command
        result = cli_runner.invoke(list_docs)
        
        # Verify command succeeded
        assert result.exit_code == 0
        assert "Test Document 1" in result.output
        assert "Test Document 2" in result.output
        assert "https://example.com/test1" in result.output
        assert "https://example.com/test2" in result.output


def test_lookup_command(mock_config, cli_runner, test_db, mock_embeddings):
    """Test library lookup command"""
    from docvault.cli.commands import lookup
    from docvault.db.schema import initialize_database
    
    # Initialize database with required tables
    initialize_database(force_recreate=True)
    
    # Mock the get_library_docs method
    async def mock_get_library_docs(*args, **kwargs):
        return [{
            'id': 1,
            'url': 'https://docs.pytest.org/en/7.0.0/',
            'title': 'pytest Documentation',
            'resolved_version': '7.0.0'
        }]
    
    with patch('docvault.core.library_manager.LibraryManager.get_library_docs',
               new=mock_get_library_docs):
        # Run command
        result = cli_runner.invoke(lookup, ['pytest', '--version', '7.0.0'])
        
        # Verify command succeeded
        assert result.exit_code == 0
        assert 'pytest Documentation' in result.output
        
def test_scrape_command(mock_config, cli_runner, mock_embeddings):
    """Test scrape command"""
    from docvault.cli.commands import scrape
    
    # Mock the scraper and document result
    mock_document = {
        'id': 1,
        'title': 'Test Documentation',
        'url': 'https://example.com/docs'
    }
    
    # Mock scraper class with stats
    mock_scraper = MagicMock()
    mock_scraper.stats = {
        "pages_scraped": 5,
        "pages_skipped": 2,
        "segments_created": 10
    }
    mock_scraper.scrape_url = AsyncMock(return_value=mock_document)
    
    with patch('docvault.core.scraper.get_scraper', return_value=mock_scraper):
        # Run command
        result = cli_runner.invoke(scrape, ['https://example.com/docs', '--depth', '2'])
        
        # Verify command succeeded
        assert result.exit_code == 0
        assert "Test Documentation" in result.output
        assert "Pages Scraped" in result.output
        assert "5" in result.output  # Pages scraped count
        
def test_add_command(mock_config, cli_runner, mock_embeddings):
    """Test add command (alias for scrape)"""
    from docvault.cli.commands import add, scrape
    
    # Mock the scraper and document result
    mock_document = {
        'id': 1,
        'title': 'Test Documentation',
        'url': 'https://example.com/docs'
    }
    
    # Mock scraper class with stats
    mock_scraper = MagicMock()
    mock_scraper.stats = {
        "pages_scraped": 3,
        "pages_skipped": 1,
        "segments_created": 6
    }
    mock_scraper.scrape_url = AsyncMock(return_value=mock_document)
    
    with patch('docvault.core.scraper.get_scraper', return_value=mock_scraper):
        # Run command using add (which should call scrape)
        result = cli_runner.invoke(add, ['https://example.com/docs'])
        
        # Verify command succeeded
        assert result.exit_code == 0
        assert "Test Documentation" in result.output
        assert "Pages Scraped" in result.output
        assert "3" in result.output  # Pages scraped count

def test_read_command(mock_config, cli_runner):
    """Test read command"""
    from docvault.cli.commands import read
    
    # Create a test document
    mock_doc = {
        'id': 1,
        'title': 'Test Documentation',
        'url': 'https://example.com/docs',
        'markdown_path': '/test/path/doc.md',
        'html_path': '/test/path/doc.html'
    }
    
    # Mock markdown content
    mock_content = "# Test Documentation\n\nThis is test content."
    
    with patch('docvault.db.operations.get_document', return_value=mock_doc):
        with patch('docvault.core.storage.read_markdown', return_value=mock_content):
            with patch('docvault.core.storage.open_html_in_browser') as mock_open_browser:
                # Test markdown format (default)
                md_result = cli_runner.invoke(read, ['1'])
                
                # Verify markdown result
                assert md_result.exit_code == 0
                assert "Test Documentation" in md_result.output
                assert "This is test content" in md_result.output
                
                # Test HTML format
                html_result = cli_runner.invoke(read, ['1', '--format', 'html'])
                
                # Verify HTML result and browser open
                assert html_result.exit_code == 0
                mock_open_browser.assert_called_once_with('/test/path/doc.html')

def test_delete_command(mock_config, cli_runner):
    """Test delete command"""
    from docvault.cli.commands import delete
    
    # Create test documents
    mock_docs = [
        {
            'id': 1,
            'title': 'Test Doc 1',
            'url': 'https://example.com/doc1',
            'html_path': '/test/path/doc1.html',
            'markdown_path': '/test/path/doc1.md'
        },
        {
            'id': 2,
            'title': 'Test Doc 2',
            'url': 'https://example.com/doc2',
            'html_path': '/test/path/doc2.html',
            'markdown_path': '/test/path/doc2.md'
        }
    ]
    
    def mock_get_document(doc_id):
        for doc in mock_docs:
            if doc['id'] == doc_id:
                return doc
        return None
    
    # Set up mocks
    with patch('docvault.db.operations.get_document', side_effect=mock_get_document):
        with patch('docvault.db.operations.delete_document') as mock_delete:
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.unlink') as mock_unlink:
                    # Test deleting multiple documents with force flag
                    result = cli_runner.invoke(delete, ['1', '2', '--force'])
                    
                    # Verify results
                    assert result.exit_code == 0
                    assert "Test Doc 1" in result.output
                    assert "Test Doc 2" in result.output
                    assert "Deleted" in result.output
                    
                    # Check correct calls were made
                    assert mock_delete.call_count == 2
                    assert mock_unlink.call_count == 4  # 2 HTML + 2 Markdown files

def test_rm_command(mock_config, cli_runner):
    """Test rm command (alias for delete)"""
    from docvault.cli.commands import rm, delete
    
    # Create test document
    mock_doc = {
        'id': 3,
        'title': 'Test Doc 3',
        'url': 'https://example.com/doc3',
        'html_path': '/test/path/doc3.html',
        'markdown_path': '/test/path/doc3.md'
    }
    
    # Set up mocks
    with patch('docvault.db.operations.get_document', return_value=mock_doc):
        with patch('docvault.db.operations.delete_document') as mock_delete:
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.unlink'):
                    # Test rm command (should call delete)
                    result = cli_runner.invoke(rm, ['3', '--force'])
                    
                    # Verify results
                    assert result.exit_code == 0
                    assert "Test Doc 3" in result.output
                    assert "Deleted" in result.output
                    
                    # Check delete was called
                    mock_delete.assert_called_once_with(3)

def test_config_command(mock_config, cli_runner):
    """Test config command"""
    from docvault.cli.commands import config
    
    # Test config display (default)
    with patch('docvault.config') as mock_config_module:
        # Set some test config values
        mock_config_module.DB_PATH = "/test/db/path.db"
        mock_config_module.STORAGE_PATH = "/test/storage/path"
        mock_config_module.LOG_DIR = "/test/log/dir"
        mock_config_module.LOG_LEVEL = "INFO"
        mock_config_module.EMBEDDING_MODEL = "test-model"
        mock_config_module.OLLAMA_URL = "http://test:11434"
        mock_config_module.SERVER_HOST = "localhost"
        mock_config_module.SERVER_PORT = "8000"
        
        # Run command
        result = cli_runner.invoke(config)
        
        # Verify output
        assert result.exit_code == 0
        assert "Current Configuration" in result.output
        assert "/test/db/path.db" in result.output
        assert "/test/storage/path" in result.output
        assert "test-model" in result.output
        
    # Test config --init
    with patch('docvault.config') as mock_config_module:
        with patch('docvault.main.create_env_template', return_value="# Test env template"):
            with patch('pathlib.Path.exists', return_value=False):
                with patch('pathlib.Path.write_text') as mock_write:
                    # Set default base dir
                    mock_config_module.DEFAULT_BASE_DIR = "/test/base/dir"
                    
                    # Run command with init flag
                    result = cli_runner.invoke(config, ['--init'])
                    
                    # Verify command succeeded
                    assert result.exit_code == 0
                    assert "Created configuration file" in result.output
                    mock_write.assert_called_once()

def test_init_db_command(mock_config, cli_runner):
    """Test init-db command"""
    from docvault.cli.commands import init_db
    
    # Test successful initialization
    with patch('docvault.db.schema.initialize_database') as mock_init_db:
        # Run command
        result = cli_runner.invoke(init_db)
        
        # Verify results
        assert result.exit_code == 0
        assert "Database initialized successfully" in result.output
        mock_init_db.assert_called_once_with(force_recreate=False)
        
        # Test with force flag
        result_force = cli_runner.invoke(init_db, ['--force'])
        
        # Verify force results
        assert result_force.exit_code == 0
        assert "Database initialized successfully" in result_force.output
        mock_init_db.assert_called_with(force_recreate=True)
        
    # Test error handling
    with patch('docvault.db.schema.initialize_database', side_effect=Exception("Test error")):
        # Run command
        result = cli_runner.invoke(init_db)
        
        # Verify error is reported
        assert result.exit_code != 0
        assert "Error initializing database" in result.output
        
def test_backup_command(mock_config, cli_runner):
    """Test backup command"""
    from docvault.cli.commands import backup
    
    # Mock configuration and datetime
    with patch('docvault.cli.commands.datetime') as mock_datetime:
        # Ensure consistent timestamp
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20240226_120000"
        mock_datetime.now.return_value = mock_now
        
        # Mock configuration
        with patch('docvault.config') as mock_config_module:
            mock_config_module.DEFAULT_BASE_DIR = "/test/base/dir"
            
            # Mock archive creation
            with patch('shutil.make_archive') as mock_archive:
                # Test default (no destination specified)
                result = cli_runner.invoke(backup)
                
                # Verify command succeeded
                assert result.exit_code == 0
                assert "Backup created" in result.output
                mock_archive.assert_called_once()
                
                # Test with custom destination
                mock_archive.reset_mock()
                result_custom = cli_runner.invoke(backup, ['custom_backup'])
                
                # Verify custom backup
                assert result_custom.exit_code == 0
                assert "Backup created" in result_custom.output
                mock_archive.assert_called_once()
                assert "custom_backup" in mock_archive.call_args[0][0]

def test_import_backup_command(mock_config, cli_runner):
    """Test import-backup command"""
    from docvault.cli.commands import import_backup
    
    # Create a temporary file for testing
    with cli_runner.isolated_filesystem():
        # Create a dummy backup file
        with open('backup.zip', 'wb') as f:
            f.write(b'dummy content')
        
        # Mock configuration
        with patch('docvault.config') as mock_config_module:
            mock_config_module.DB_PATH = "/test/db/path.db"
            mock_config_module.STORAGE_PATH = "/test/storage/path"
            
            # Create parent directories for paths
            with patch('pathlib.Path.parent') as mock_parent:
                mock_parent.mkdir = MagicMock()
                
                # Mock path operations
                with patch('pathlib.Path.exists', return_value=True):
                    with patch('pathlib.Path.iterdir', return_value=[MagicMock()]):
                        with patch('tempfile.TemporaryDirectory') as mock_temp:
                            # Create mock context manager
                            mock_temp.return_value.__enter__.return_value = "/tmp/backup"
                            
                            with patch('shutil.unpack_archive') as mock_unpack:
                                with patch('shutil.copy2') as mock_copy:
                                    with patch('shutil.rmtree') as mock_rmtree:
                                        with patch('shutil.copytree') as mock_copytree:
                                            # Test with force flag (no confirmation needed)
                                            result = cli_runner.invoke(import_backup, ['backup.zip', '--force'])
                                            
                                            # Verify force command
                                            assert result.exit_code == 0
                                            assert "Backup imported successfully" in result.output
                                            mock_unpack.assert_called_once()

# Skip the serve command test for now since we don't want to import MCP
@pytest.mark.skip(reason="MCP module not available in test environment")
def test_serve_command(mock_config, cli_runner):
    """Test serve command (skipped)"""
    pass