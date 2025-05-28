"""
Database indexes for performance optimization.
"""

import logging
import sqlite3
from typing import List

from docvault.db.connection_pool import get_connection

logger = logging.getLogger(__name__)


def create_performance_indexes():
    """
    Create database indexes for frequently queried columns to improve performance.
    """
    indexes = [
        # Document table indexes
        ("idx_documents_url", "documents", "url"),
        ("idx_documents_title", "documents", "title"),
        ("idx_documents_scraped_at", "documents", "scraped_at"),
        ("idx_documents_library_id", "documents", "library_id"),
        # Document segments indexes
        ("idx_segments_document_id", "document_segments", "document_id"),
        ("idx_segments_section_title", "document_segments", "section_title"),
        ("idx_segments_segment_type", "document_segments", "segment_type"),
        ("idx_segments_section_path", "document_segments", "section_path"),
        ("idx_segments_parent_id", "document_segments", "parent_id"),
        # Composite indexes for common queries
        ("idx_segments_doc_type", "document_segments", "document_id, segment_type"),
        ("idx_segments_doc_section", "document_segments", "document_id, section_title"),
        # Vector table index
        ("idx_vector_segment_id", "document_segments_vec", "segment_id"),
        # Libraries table indexes
        ("idx_libraries_name", "libraries", "name"),
        ("idx_libraries_source", "libraries", "source"),
        ("idx_libraries_version", "libraries", "version"),
        # Composite library index
        ("idx_libraries_name_version", "libraries", "name, version"),
        # Tags table indexes
        ("idx_tags_name", "tags", "name"),
        ("idx_tags_document_id", "document_tags", "document_id"),
        ("idx_tags_tag_id", "document_tags", "tag_id"),
        # Collections table indexes
        ("idx_collections_name", "collections", "name"),
        ("idx_collection_docs_collection_id", "collection_documents", "collection_id"),
        ("idx_collection_docs_document_id", "collection_documents", "document_id"),
        # Cross references indexes
        ("idx_cross_refs_from", "cross_references", "from_segment_id"),
        ("idx_cross_refs_to", "cross_references", "to_segment_id"),
        ("idx_cross_refs_type", "cross_references", "reference_type"),
    ]

    with get_connection() as conn:
        cursor = conn.cursor()

        created_count = 0
        skipped_count = 0

        for index_name, table_name, columns in indexes:
            try:
                # Check if index already exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (index_name,),
                )
                if cursor.fetchone():
                    logger.debug(f"Index {index_name} already exists, skipping")
                    skipped_count += 1
                    continue

                # Create the index
                sql = f"CREATE INDEX {index_name} ON {table_name} ({columns})"
                cursor.execute(sql)
                created_count += 1
                logger.debug(f"Created index: {index_name}")

            except sqlite3.Error as e:
                logger.warning(f"Failed to create index {index_name}: {e}")

        conn.commit()
        logger.info(
            f"Index creation complete: {created_count} created, {skipped_count} skipped"
        )


def analyze_table_stats():
    """
    Analyze table statistics to help with query optimization.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Get table row counts
        tables = [
            "documents",
            "document_segments",
            "document_segments_vec",
            "libraries",
            "tags",
            "document_tags",
            "collections",
            "collection_documents",
            "cross_references",
        ]

        stats = {}

        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                stats[table] = {"row_count": count}

                # Get index information
                cursor.execute(f"PRAGMA index_list({table})")
                indexes = cursor.fetchall()
                stats[table]["indexes"] = len(indexes)

            except sqlite3.Error as e:
                logger.warning(f"Failed to get stats for table {table}: {e}")
                stats[table] = {"error": str(e)}

        return stats


def drop_performance_indexes():
    """
    Drop all performance indexes (useful for testing or rebuilding).
    """
    index_names = [
        "idx_documents_url",
        "idx_documents_title",
        "idx_documents_scraped_at",
        "idx_documents_library_id",
        "idx_segments_document_id",
        "idx_segments_section_title",
        "idx_segments_segment_type",
        "idx_segments_section_path",
        "idx_segments_parent_id",
        "idx_segments_doc_type",
        "idx_segments_doc_section",
        "idx_vector_segment_id",
        "idx_libraries_name",
        "idx_libraries_source",
        "idx_libraries_version",
        "idx_libraries_name_version",
        "idx_tags_name",
        "idx_tags_document_id",
        "idx_tags_tag_id",
        "idx_collections_name",
        "idx_collection_docs_collection_id",
        "idx_collection_docs_document_id",
        "idx_cross_refs_from",
        "idx_cross_refs_to",
        "idx_cross_refs_type",
    ]

    with get_connection() as conn:
        cursor = conn.cursor()

        dropped_count = 0

        for index_name in index_names:
            try:
                cursor.execute(f"DROP INDEX IF EXISTS {index_name}")
                dropped_count += 1
                logger.debug(f"Dropped index: {index_name}")
            except sqlite3.Error as e:
                logger.warning(f"Failed to drop index {index_name}: {e}")

        conn.commit()
        logger.info(f"Dropped {dropped_count} indexes")


def optimize_database():
    """
    Run database optimization commands.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        try:
            # Update table statistics
            logger.info("Analyzing database tables...")
            cursor.execute("ANALYZE")

            # Vacuum database to reclaim space and defragment
            logger.info("Vacuuming database...")
            cursor.execute("VACUUM")

            # Update SQLite settings for better performance
            cursor.execute("PRAGMA optimize")

            conn.commit()
            logger.info("Database optimization complete")

        except sqlite3.Error as e:
            logger.error(f"Database optimization failed: {e}")


def get_query_plan(sql: str, params: List = None) -> List[dict]:
    """
    Get query execution plan for a SQL statement.

    Args:
        sql: SQL statement to analyze
        params: Query parameters

    Returns:
        List of query plan steps
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        try:
            # Get query plan
            explain_sql = f"EXPLAIN QUERY PLAN {sql}"
            if params:
                cursor.execute(explain_sql, params)
            else:
                cursor.execute(explain_sql)

            plan = []
            for row in cursor.fetchall():
                plan.append(
                    {
                        "id": row[0],
                        "parent": row[1],
                        "notused": row[2],
                        "detail": row[3],
                    }
                )

            return plan

        except sqlite3.Error as e:
            logger.error(f"Failed to get query plan: {e}")
            return []
