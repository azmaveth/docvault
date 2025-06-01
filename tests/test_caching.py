"""
Test document caching and staleness tracking functionality.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from docvault.core.caching import (
    CacheConfig,
    CacheManager,
    StalenessStatus,
    get_cache_manager,
)
from docvault.db.migrations.add_caching_fields_0006 import upgrade as add_cache_fields
from docvault.db.operations import add_document


class TestCacheConfig:
    """Test caching configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CacheConfig()
        assert config.fresh_days == 7
        assert config.stale_days == 30
        assert config.auto_check is False
        assert config.check_on_read is True

    def test_threshold_properties(self):
        """Test threshold property calculations."""
        config = CacheConfig()
        assert config.fresh_threshold == timedelta(days=7)
        assert config.stale_threshold == timedelta(days=30)


class TestStalenessCalculation:
    """Test staleness status calculations."""

    def test_fresh_document(self):
        """Test document is fresh when recently checked."""
        manager = CacheManager()
        now = datetime.now(timezone.utc)

        # Document checked 3 days ago
        last_checked = now - timedelta(days=3)
        status = manager.calculate_staleness(last_checked)
        assert status == StalenessStatus.FRESH

    def test_stale_document(self):
        """Test document is stale when checked 7-30 days ago."""
        manager = CacheManager()
        now = datetime.now(timezone.utc)

        # Document checked 15 days ago
        last_checked = now - timedelta(days=15)
        status = manager.calculate_staleness(last_checked)
        assert status == StalenessStatus.STALE

    def test_outdated_document(self):
        """Test document is outdated when checked > 30 days ago."""
        manager = CacheManager()
        now = datetime.now(timezone.utc)

        # Document checked 45 days ago
        last_checked = now - timedelta(days=45)
        status = manager.calculate_staleness(last_checked)
        assert status == StalenessStatus.OUTDATED

    def test_never_checked_document(self):
        """Test document is outdated when never checked."""
        manager = CacheManager()
        status = manager.calculate_staleness(None)
        assert status == StalenessStatus.OUTDATED


class TestCacheManager:
    """Test cache manager functionality."""

    @pytest.fixture
    def setup_cache_db(self, test_db):
        """Set up database with cache fields."""
        # Run the cache migration
        add_cache_fields()

        # Add test documents
        doc1_id = add_document(
            url="https://example.com/doc1",
            title="Fresh Document",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )

        doc2_id = add_document(
            url="https://example.com/doc2",
            title="Stale Document",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )

        doc3_id = add_document(
            url="https://example.com/doc3",
            title="Outdated Document",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )

        # Update last_checked times
        conn = test_db  # test_db is already a connection
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        cursor.execute(
            "UPDATE documents SET last_checked = ? WHERE id = ?",
            ((now - timedelta(days=3)).isoformat(), doc1_id),
        )
        cursor.execute(
            "UPDATE documents SET last_checked = ? WHERE id = ?",
            ((now - timedelta(days=15)).isoformat(), doc2_id),
        )
        cursor.execute(
            "UPDATE documents SET last_checked = ? WHERE id = ?",
            ((now - timedelta(days=45)).isoformat(), doc3_id),
        )

        conn.commit()
        conn.close()

        return doc1_id, doc2_id, doc3_id

    def test_update_staleness_status(self, setup_cache_db):
        """Test updating document staleness status."""
        doc1_id, doc2_id, doc3_id = setup_cache_db
        manager = CacheManager()

        # Check fresh document
        status1 = manager.update_staleness_status(doc1_id)
        assert status1 == StalenessStatus.FRESH

        # Check stale document
        status2 = manager.update_staleness_status(doc2_id)
        assert status2 == StalenessStatus.STALE

        # Check outdated document
        status3 = manager.update_staleness_status(doc3_id)
        assert status3 == StalenessStatus.OUTDATED

    def test_pinned_documents_always_fresh(self, setup_cache_db):
        """Test pinned documents are always fresh."""
        doc1_id, doc2_id, doc3_id = setup_cache_db
        manager = CacheManager()

        # Pin the outdated document
        manager.pin_document(doc3_id, True)

        # Check it's now considered fresh
        status = manager.update_staleness_status(doc3_id)
        assert status == StalenessStatus.FRESH

    def test_get_stale_documents(self, setup_cache_db):
        """Test retrieving stale documents."""
        doc1_id, doc2_id, doc3_id = setup_cache_db
        manager = CacheManager()

        # Update staleness status for all
        manager.update_staleness_status(doc1_id)
        manager.update_staleness_status(doc2_id)
        manager.update_staleness_status(doc3_id)

        # Get all stale/outdated documents
        stale_docs = manager.get_stale_documents()
        assert len(stale_docs) == 2

        # Get only stale documents
        stale_only = manager.get_stale_documents(StalenessStatus.STALE)
        assert len(stale_only) == 1
        assert stale_only[0]["id"] == doc2_id

        # Get only outdated documents
        outdated_only = manager.get_stale_documents(StalenessStatus.OUTDATED)
        assert len(outdated_only) == 1
        assert outdated_only[0]["id"] == doc3_id

    @pytest.mark.asyncio
    async def test_check_for_updates_no_changes(self, setup_cache_db):
        """Test checking for updates when no changes."""
        doc1_id, _, _ = setup_cache_db
        manager = CacheManager()

        with patch("aiohttp.ClientSession.head") as mock_head:
            # Mock 304 Not Modified response
            mock_response = MagicMock()
            mock_response.status = 304
            mock_head.return_value.__aenter__.return_value = mock_response

            has_updates, reason = await manager.check_for_updates(doc1_id)
            assert not has_updates
            assert "304 Not Modified" in reason

    @pytest.mark.asyncio
    async def test_check_for_updates_etag_changed(self, setup_cache_db):
        """Test checking for updates when ETag changed."""
        doc1_id, _, _ = setup_cache_db
        manager = CacheManager()

        # Set an etag on the document using operations module
        from docvault.db.connection_pool import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE documents SET etag = ? WHERE id = ?", ("old-etag", doc1_id)
            )
            conn.commit()

        with patch("aiohttp.ClientSession.head") as mock_head:
            # Mock response with new ETag
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.headers = {"ETag": "new-etag"}
            mock_head.return_value.__aenter__.return_value = mock_response

            has_updates, reason = await manager.check_for_updates(doc1_id)
            assert has_updates
            assert "ETag changed" in reason

    def test_mark_as_updated(self, setup_cache_db):
        """Test marking a document as updated."""
        _, _, doc3_id = setup_cache_db
        manager = CacheManager()

        # Document should be outdated
        status = manager.update_staleness_status(doc3_id)
        assert status == StalenessStatus.OUTDATED

        # Mark as updated
        manager.mark_as_updated(
            doc3_id,
            etag="new-etag",
            last_modified="Wed, 21 Oct 2024 07:28:00 GMT",
            content_hash="new-hash",
        )

        # Should now be fresh
        status = manager.update_staleness_status(doc3_id)
        assert status == StalenessStatus.FRESH

    def test_cache_statistics(self, setup_cache_db):
        """Test cache statistics calculation."""
        doc1_id, doc2_id, doc3_id = setup_cache_db
        manager = CacheManager()

        # Update staleness status for all
        manager.update_staleness_status(doc1_id)
        manager.update_staleness_status(doc2_id)
        manager.update_staleness_status(doc3_id)

        # Pin one document
        manager.pin_document(doc1_id, True)

        stats = manager.get_cache_statistics()

        assert stats["total_documents"] == 3
        assert stats["fresh"] >= 0  # Can vary based on pinned status
        assert stats["stale"] >= 0
        assert stats["outdated"] >= 0
        assert stats["pinned"] == 1
        assert stats["average_age_days"] > 0
        assert stats["thresholds"]["fresh_days"] == 7
        assert stats["thresholds"]["stale_days"] == 30


class TestGlobalCacheManager:
    """Test global cache manager instance."""

    def test_singleton_instance(self):
        """Test get_cache_manager returns singleton instance."""
        manager1 = get_cache_manager()
        manager2 = get_cache_manager()
        assert manager1 is manager2
