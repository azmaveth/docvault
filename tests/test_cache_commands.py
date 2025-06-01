"""
Test cache management CLI commands.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from docvault.cli.cache_commands import (
    cache_config,
    cache_stats,
    check_updates,
    pin,
    update,
)
from docvault.db.migrations.add_caching_fields_0006 import upgrade as add_cache_fields
from docvault.db.operations import add_document


class TestCacheCommands:
    """Test cache management commands."""

    @pytest.fixture
    def setup_docs(self, test_db):
        """Set up test documents with varying staleness."""
        # Run cache migration
        add_cache_fields()

        # Add test documents
        doc_ids = []
        for i in range(3):
            doc_id = add_document(
                url=f"https://example.com/doc{i}",
                title=f"Test Document {i}",
                html_path=f"/tmp/test{i}.html",
                markdown_path=f"/tmp/test{i}.md",
                version="1.0",
            )
            doc_ids.append(doc_id)

        # Update last_checked times

        conn = test_db
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        # Fresh document
        cursor.execute(
            "UPDATE documents SET last_checked = ?, staleness_status = ? WHERE id = ?",
            ((now - timedelta(days=3)).isoformat(), "fresh", doc_ids[0]),
        )
        # Stale document
        cursor.execute(
            "UPDATE documents SET last_checked = ?, staleness_status = ? WHERE id = ?",
            ((now - timedelta(days=15)).isoformat(), "stale", doc_ids[1]),
        )
        # Outdated document
        cursor.execute(
            "UPDATE documents SET last_checked = ?, staleness_status = ? WHERE id = ?",
            ((now - timedelta(days=45)).isoformat(), "outdated", doc_ids[2]),
        )

        conn.commit()
        conn.close()

        return doc_ids

    def test_check_updates_command(self, setup_docs):
        """Test check-updates command."""
        runner = CliRunner()

        # Check all stale documents
        result = runner.invoke(check_updates, ["--status", "all"])
        assert result.exit_code == 0
        assert "Documents Needing Updates" in result.output

        # Check JSON output
        result = runner.invoke(check_updates, ["--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2  # Should have 2 stale/outdated docs

    def test_check_updates_no_stale(self, test_db):
        """Test check-updates when all documents are fresh."""
        # Run cache migration
        add_cache_fields()

        runner = CliRunner()
        result = runner.invoke(check_updates)
        assert result.exit_code == 0
        assert "All documents are fresh!" in result.output

    def test_pin_command(self, setup_docs):
        """Test pin/unpin command."""
        doc_id = setup_docs[0]
        runner = CliRunner()

        # Pin document
        result = runner.invoke(pin, [str(doc_id)])
        assert result.exit_code == 0
        assert f"Pinned document {doc_id}" in result.output

        # Unpin document
        result = runner.invoke(pin, [str(doc_id), "--unpin"])
        assert result.exit_code == 0
        assert f"Unpinned document {doc_id}" in result.output

    def test_cache_stats_command(self, setup_docs):
        """Test cache-stats command."""
        runner = CliRunner()

        # Table format
        result = runner.invoke(cache_stats)
        assert result.exit_code == 0
        assert "Document Cache Statistics" in result.output
        assert "Total Documents" in result.output

        # JSON format
        result = runner.invoke(cache_stats, ["--format", "json"])
        assert result.exit_code == 0
        stats = json.loads(result.output)
        assert "total_documents" in stats
        assert "fresh" in stats
        assert "stale" in stats
        assert "outdated" in stats

    def test_update_command_dry_run(self, setup_docs):
        """Test update command with dry-run."""
        runner = CliRunner()

        result = runner.invoke(update, ["--all-stale", "--dry-run"])
        assert result.exit_code == 0
        assert "Would update" in result.output

    @patch("docvault.cli.cache_commands.asyncio.run")
    @patch("docvault.cli.cache_commands.get_scraper")
    def test_update_command_single_doc(
        self, mock_get_scraper, mock_asyncio_run, setup_docs, mock_app_initialization
    ):
        """Test updating a single document."""
        doc_id = setup_docs[1]  # Stale document
        runner = CliRunner()

        # Mock the async operations
        mock_asyncio_run.side_effect = [
            (True, "Content changed"),  # check_for_updates
            {"id": doc_id},  # scrape_url
        ]

        result = runner.invoke(update, [str(doc_id)])
        assert result.exit_code == 0
        assert "Update Summary" in result.output

    def test_cache_config_command(self):
        """Test cache-config command."""
        runner = CliRunner()

        # Set fresh days
        result = runner.invoke(cache_config, ["fresh-days", "14"])
        assert result.exit_code == 0
        assert "Would set fresh threshold to 14 days" in result.output

        # Set auto-check
        result = runner.invoke(cache_config, ["auto-check", "true"])
        assert result.exit_code == 0
        assert "Would enable automatic update checks" in result.output

        # Invalid value
        result = runner.invoke(cache_config, ["fresh-days", "invalid"])
        assert result.exit_code == 0
        assert "Value must be a number" in result.output
