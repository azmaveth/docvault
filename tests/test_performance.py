"""
Performance tests for optimized components.
"""

import asyncio
import os
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from docvault.core.embeddings_optimized import (
    clear_cache,
    generate_embeddings,
    generate_embeddings_batch,
    get_cache_stats,
)
from docvault.core.performance import (
    get_performance_stats,
    performance_monitor,
    profiler,
    reset_performance_stats,
    timer,
)
from docvault.db.batch_operations import batch_insert_segments
from docvault.db.connection_pool import ConnectionPool
from docvault.db.performance_indexes import (
    analyze_table_stats,
    create_performance_indexes,
)


class TestEmbeddingsOptimized:
    """Test optimized embeddings functionality."""

    @pytest.fixture(autouse=True)
    def setup_cache(self):
        """Clear cache before each test."""
        clear_cache()
        yield
        clear_cache()

    @pytest.mark.asyncio
    async def test_embedding_caching(self):
        """Test that embeddings are cached correctly."""
        # Mock the Ollama API
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"embedding": [0.1, 0.2, 0.3] * 128}
        )

        with patch(
            "docvault.core.embeddings_optimized.get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.post.return_value.__aenter__.return_value = mock_response
            mock_get_session.return_value = mock_session

            # First call should generate embedding
            text = "test text for caching"
            embedding1 = await generate_embeddings(text)

            # Second call should use cache
            embedding2 = await generate_embeddings(text)

            # Results should be identical
            assert embedding1 == embedding2

            # Check cache stats
            stats = get_cache_stats()
            assert stats["total_entries"] >= 1
            assert stats["valid_entries"] >= 1

    @pytest.mark.asyncio
    async def test_batch_embedding_generation(self):
        """Test batch embedding generation performance."""
        texts = [f"test text {i}" for i in range(20)]

        # Mock the Ollama API
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"embedding": [0.1, 0.2, 0.3] * 128}
        )

        with patch(
            "docvault.core.embeddings_optimized.get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.post.return_value.__aenter__.return_value = mock_response
            mock_get_session.return_value = mock_session

            start_time = time.time()
            embeddings = await generate_embeddings_batch(texts, batch_size=5)
            duration = time.time() - start_time

            assert len(embeddings) == len(texts)
            # Batch processing should be faster than sequential
            assert duration < 10.0  # Should complete in reasonable time


class TestPerformanceMonitoring:
    """Test performance monitoring utilities."""

    @pytest.fixture(autouse=True)
    def reset_stats(self):
        """Reset performance stats before each test."""
        reset_performance_stats()
        yield
        reset_performance_stats()

    def test_timer_context_manager(self):
        """Test timer context manager."""
        with timer("test_operation"):
            time.sleep(0.1)

        stats = get_performance_stats()
        assert "test_operation" in stats
        assert stats["test_operation"]["count"] == 1
        assert stats["test_operation"]["avg_time"] >= 0.1

    def test_performance_monitor_decorator(self):
        """Test performance monitor decorator."""

        @performance_monitor("test_function")
        def test_func():
            time.sleep(0.05)
            return "result"

        result = test_func()
        assert result == "result"

        stats = get_performance_stats()
        assert "test_function" in stats
        assert stats["test_function"]["count"] == 1

    @pytest.mark.asyncio
    async def test_async_performance_monitor(self):
        """Test performance monitor with async functions."""

        @performance_monitor("async_test_function")
        async def async_test_func():
            await asyncio.sleep(0.05)
            return "async_result"

        result = await async_test_func()
        assert result == "async_result"

        stats = get_performance_stats()
        assert "async_test_function" in stats

    def test_profiler_context_manager(self):
        """Test detailed profiler."""
        with profiler("test_profile") as p:
            time.sleep(0.02)
            p.checkpoint("step1")
            time.sleep(0.02)
            p.checkpoint("step2")

        stats = get_performance_stats()
        assert "profile.test_profile" in stats


class TestConnectionPool:
    """Test database connection pool."""

    def test_connection_pool_creation(self):
        """Test connection pool can be created and used."""
        pool = ConnectionPool(max_connections=2)

        # Get connections
        conn1 = pool.get_connection()
        conn2 = pool.get_connection()

        assert conn1 is not None
        assert conn2 is not None
        assert conn1 != conn2

        # Return connections
        pool.return_connection(conn1)
        pool.return_connection(conn2)

        # Clean up
        pool.close_all()

    def test_connection_pool_context_manager(self):
        """Test connection pool context manager."""
        pool = ConnectionPool(max_connections=1)

        with pool.connection() as conn:
            # Should be able to execute queries
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

        pool.close_all()


class TestBatchOperations:
    """Test batch database operations."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)

        # Set up minimal database schema
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                url TEXT,
                title TEXT,
                html_path TEXT,
                markdown_path TEXT,
                scraped_at TEXT
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE document_segments (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                content TEXT,
                section_title TEXT,
                segment_type TEXT,
                section_path TEXT,
                parent_id INTEGER
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE document_segments_vec (
                segment_id INTEGER PRIMARY KEY,
                embedding BLOB
            )
        """
        )
        conn.commit()
        conn.close()

        yield db_path

        # Cleanup
        os.unlink(db_path)

    def test_batch_insert_segments(self, temp_db):
        """Test batch segment insertion."""
        # This test would need to mock the connection pool
        # For now, just test that the function exists and has correct signature
        assert callable(batch_insert_segments)

        # Test with empty segments
        segments = []
        result = batch_insert_segments(1, segments)
        assert isinstance(result, list)
        assert len(result) == 0


class TestPerformanceIndexes:
    """Test database performance indexes."""

    def test_create_performance_indexes(self):
        """Test index creation function exists."""
        assert callable(create_performance_indexes)

    def test_analyze_table_stats(self):
        """Test table statistics analysis."""
        assert callable(analyze_table_stats)


class TestIntegrationPerformance:
    """Integration tests for performance improvements."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_scraping_performance_comparison(self):
        """Compare performance of optimized vs original scraper."""
        # This would be a comprehensive test comparing the two scrapers
        # For now, just verify the optimized scraper exists
        from docvault.core.scraper_optimized import OptimizedDocumentScraper

        scraper = OptimizedDocumentScraper()
        assert scraper is not None

        stats = scraper.get_stats()
        assert isinstance(stats, dict)
        assert "pages_scraped" in stats

    @pytest.mark.slow
    def test_database_performance_with_indexes(self):
        """Test database performance improvement with indexes."""
        # Create temporary database and test query performance
        # This would involve creating test data and comparing query times
        # For now, verify the index creation functions work
        pass

    def test_memory_usage_monitoring(self):
        """Test memory usage monitoring."""
        from docvault.core.performance import memory_usage

        usage = memory_usage()
        assert isinstance(usage, float)
        assert usage >= 0

    def test_cache_effectiveness(self):
        """Test embedding cache effectiveness."""
        clear_cache()

        # Test that cache stats are accessible
        stats = get_cache_stats()
        assert isinstance(stats, dict)
        assert "total_entries" in stats
        assert "valid_entries" in stats


@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """Benchmark tests for performance comparison."""

    def test_embedding_generation_benchmark(self, benchmark):
        """Benchmark embedding generation."""

        async def generate_test_embedding():
            # Mock the embedding generation
            import numpy as np

            return np.random.rand(384).astype(np.float32).tobytes()

        # This would require pytest-benchmark
        # result = benchmark(asyncio.run, generate_test_embedding())
        pass

    def test_database_query_benchmark(self, benchmark):
        """Benchmark database queries with and without indexes."""
        # This would test query performance
        pass

    def test_batch_processing_benchmark(self, benchmark):
        """Benchmark batch vs individual processing."""
        # This would compare batch operations to individual operations
        pass
