"""Tests for the index CLI command."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from docvault.main import cli


class TestIndexCommand:
    """Test the index command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_project_manager(self):
        """Mock ProjectManager."""
        with patch("docvault.cli.commands.ProjectManager") as mock:
            yield mock

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection."""
        with patch("docvault.cli.commands.operations.get_db_connection") as mock:
            mock_conn = MagicMock(spec=sqlite3.Connection)
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock.return_value.__enter__.return_value = mock_conn
            yield mock, mock_conn, mock_cursor

    @pytest.fixture
    def mock_embeddings(self):
        """Mock embedding generation."""
        with patch("docvault.cli.commands.generate_embeddings") as mock:
            mock.return_value = [0.1, 0.2, 0.3] * 128  # 384-dim vector
            yield mock

    def test_index_all_documents(
        self, cli_runner, mock_project_manager, mock_db_connection, mock_embeddings
    ):
        """Test indexing all documents."""
        mock_get_conn, mock_conn, mock_cursor = mock_db_connection
        mock_pm = MagicMock()
        mock_pm.db_path = Path("/test/vault.db")
        mock_project_manager.return_value = mock_pm

        # Mock documents without embeddings
        mock_cursor.fetchall.return_value = [
            (1, "Document 1", "Content 1", None),
            (2, "Document 2", "Content 2", None),
        ]

        result = cli_runner.invoke(cli, ["index"])

        assert result.exit_code == 0
        assert "Found 2 segments to process" in result.output
        assert "Successfully indexed 2 segments" in result.output
        assert mock_embeddings.call_count == 2

    def test_index_verbose_output(
        self, cli_runner, mock_project_manager, mock_db_connection, mock_embeddings
    ):
        """Test indexing with verbose output."""
        mock_get_conn, mock_conn, mock_cursor = mock_db_connection
        mock_pm = MagicMock()
        mock_pm.db_path = Path("/test/vault.db")
        mock_project_manager.return_value = mock_pm

        # Mock documents
        mock_cursor.fetchall.return_value = [
            (1, "Document 1", "Content 1", None),
        ]

        result = cli_runner.invoke(cli, ["index", "--verbose"])

        assert result.exit_code == 0
        assert "Processing segment 1" in result.output

    def test_index_force_reindex(
        self, cli_runner, mock_project_manager, mock_db_connection, mock_embeddings
    ):
        """Test force reindexing all documents."""
        mock_get_conn, mock_conn, mock_cursor = mock_db_connection
        mock_pm = MagicMock()
        mock_pm.db_path = Path("/test/vault.db")
        mock_project_manager.return_value = mock_pm

        # Mock documents with existing embeddings
        mock_cursor.fetchall.return_value = [
            (1, "Document 1", "Content 1", b"existing_embedding"),
            (2, "Document 2", "Content 2", b"existing_embedding"),
        ]

        result = cli_runner.invoke(cli, ["index", "--force"])

        assert result.exit_code == 0
        assert "Found 2 segments to process" in result.output
        assert mock_embeddings.call_count == 2

    def test_index_batch_processing(
        self, cli_runner, mock_project_manager, mock_db_connection, mock_embeddings
    ):
        """Test batch processing with custom batch size."""
        mock_get_conn, mock_conn, mock_cursor = mock_db_connection
        mock_pm = MagicMock()
        mock_pm.db_path = Path("/test/vault.db")
        mock_project_manager.return_value = mock_pm

        # Mock many documents
        mock_cursor.fetchall.return_value = [
            (i, f"Document {i}", f"Content {i}", None) for i in range(1, 11)
        ]

        result = cli_runner.invoke(cli, ["index", "--batch-size", "5"])

        assert result.exit_code == 0
        assert "Found 10 segments to process" in result.output
        assert mock_embeddings.call_count == 10

    def test_index_rebuild_table(
        self, cli_runner, mock_project_manager, mock_db_connection, mock_embeddings
    ):
        """Test rebuilding the vector table."""
        mock_get_conn, mock_conn, mock_cursor = mock_db_connection
        mock_pm = MagicMock()
        mock_pm.db_path = Path("/test/vault.db")
        mock_project_manager.return_value = mock_pm

        # Mock documents
        mock_cursor.fetchall.return_value = [(1, "Doc", "Content", None)]

        result = cli_runner.invoke(cli, ["index", "--rebuild-table"])

        assert result.exit_code == 0
        # Check that DROP TABLE was called
        drop_calls = [
            call
            for call in mock_cursor.execute.call_args_list
            if "DROP TABLE" in str(call)
        ]
        assert len(drop_calls) > 0

    def test_index_no_documents(
        self, cli_runner, mock_project_manager, mock_db_connection
    ):
        """Test indexing when no documents need processing."""
        mock_get_conn, mock_conn, mock_cursor = mock_db_connection
        mock_pm = MagicMock()
        mock_pm.db_path = Path("/test/vault.db")
        mock_project_manager.return_value = mock_pm

        # No documents
        mock_cursor.fetchall.return_value = []

        result = cli_runner.invoke(cli, ["index"])

        assert result.exit_code == 0
        assert "No segments need indexing" in result.output

    def test_index_embedding_error(
        self, cli_runner, mock_project_manager, mock_db_connection, mock_embeddings
    ):
        """Test handling embedding generation errors."""
        mock_get_conn, mock_conn, mock_cursor = mock_db_connection
        mock_pm = MagicMock()
        mock_pm.db_path = Path("/test/vault.db")
        mock_project_manager.return_value = mock_pm

        # Mock documents
        mock_cursor.fetchall.return_value = [(1, "Doc", "Content", None)]
        mock_embeddings.side_effect = Exception("Embedding error")

        result = cli_runner.invoke(cli, ["index", "--verbose"])

        assert result.exit_code == 0
        assert "Error generating embedding" in result.output
        assert "Skipped 1 segments due to errors" in result.output

    def test_index_database_error(self, cli_runner, mock_project_manager):
        """Test handling database connection errors."""
        mock_pm = MagicMock()
        mock_pm.db_path = Path("/test/vault.db")
        mock_project_manager.return_value = mock_pm

        with patch(
            "docvault.cli.commands.operations.get_db_connection"
        ) as mock_get_conn:
            mock_get_conn.side_effect = sqlite3.Error("Database error")

            result = cli_runner.invoke(cli, ["index"])

            assert result.exit_code == 1
            assert "Error" in result.output
            assert "Database error" in result.output

    def test_index_sqlite_vec_unavailable(
        self, cli_runner, mock_project_manager, mock_db_connection
    ):
        """Test handling when sqlite-vec is not available."""
        mock_get_conn, mock_conn, mock_cursor = mock_db_connection
        mock_pm = MagicMock()
        mock_pm.db_path = Path("/test/vault.db")
        mock_project_manager.return_value = mock_pm

        # Mock sqlite-vec not available
        with patch("docvault.cli.commands.operations.SQLITE_VEC_AVAILABLE", False):
            result = cli_runner.invoke(cli, ["index"])

            assert result.exit_code == 1
            assert "sqlite-vec extension is not available" in result.output
