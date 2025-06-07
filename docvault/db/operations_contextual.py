"""
Contextual search operations for DocVault.

This module provides search functions that use contextual embeddings when available.
"""

import logging
import sqlite3
from typing import Any, Optional

from docvault import config
from docvault.db.operations import get_connection
from docvault.db.query_builder import build_document_filter

logger = logging.getLogger(__name__)


def search_segments_contextual(
    embedding: bytes = None,
    limit: int = 5,
    text_query: str = None,
    min_score: float = 0.0,
    doc_filter: dict[str, Any] | None = None,
    use_contextual: bool = True,
) -> list[dict[str, Any]]:
    """Search for similar document segments using contextual embeddings when available.

    This function extends the standard search by preferring contextual embeddings
    over regular embeddings when they exist.

    Args:
        embedding: Vector embedding for semantic search
        limit: Maximum number of results to return
        text_query: Text query for full-text search
        min_score: Minimum similarity score (0.0 to 1.0)
        doc_filter: Dictionary of document filters
        use_contextual: Whether to use contextual embeddings (default: True)

    Returns:
        List of matching document segments with metadata
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Check if contextual retrieval is enabled
    if use_contextual:
        cursor.execute(
            """
            SELECT value FROM config
            WHERE key = 'contextual_retrieval_enabled'
        """
        )
        result = cursor.fetchone()
        use_contextual = result and result["value"] == "true"

    # Prepare document filters
    filter_conditions, filter_params = build_document_filter(doc_filter)

    # Check if we should skip vector search
    use_text_search = embedding is None
    rows = []

    if not use_text_search and use_contextual:
        # Try contextual search first
        try:
            logger.debug("Attempting contextual vector search")

            # Build contextual vector search query
            base_query = """
            WITH contextual_matches AS (
                SELECT
                    s.id,
                    COALESCE(
                        vec_distance_L2(s.context_embedding, ?),
                        vec_distance_L2(v.embedding, ?)
                    ) as distance,
                    CASE
                        WHEN s.context_embedding IS NOT NULL THEN 1
                        ELSE 0
                    END as is_contextual
                FROM document_segments s
                LEFT JOIN document_segments_vec v ON s.id = v.rowid
                WHERE (s.context_embedding IS NOT NULL OR v.embedding IS NOT NULL)
            ),
            ranked_segments AS (
                SELECT
                    s.id,
                    s.document_id,
                    s.content,
                    s.section_title,
                    s.section_path,
                    s.section_level,
                    s.parent_segment_id,
                    s.context_description,
                    s.context_metadata,
                    d.title,
                    d.url,
                    d.version,
                    d.updated_at,
                    d.is_library_doc,
                    d.library_id,
                    l.name as library_name,
                    (2.0 - cm.distance) / 2.0 AS score,
                    cm.is_contextual,
                    ROW_NUMBER() OVER (PARTITION BY s.section_path ORDER BY cm.distance) as rn
                FROM contextual_matches cm
                JOIN document_segments s ON cm.id = s.id
                JOIN documents d ON s.document_id = d.id
                LEFT JOIN libraries l ON d.library_id = l.id
                WHERE cm.distance < 2.0  -- Max distance threshold
            """

            # Add filter conditions
            if filter_conditions:
                base_query += " AND " + " AND ".join(filter_conditions)

            base_query += """
            )
            SELECT * FROM ranked_segments
            WHERE rn = 1 AND score >= ?
            ORDER BY is_contextual DESC, score DESC
            LIMIT ?
            """

            # Execute with parameters
            cursor.execute(
                base_query,
                (embedding, embedding)  # Pass embedding twice for both checks
                + tuple(filter_params)
                + (min_score, limit),
            )

            rows = cursor.fetchall()

            if rows:
                logger.info(f"Contextual search returned {len(rows)} results")
                # Log how many used contextual embeddings
                contextual_count = sum(1 for row in rows if row.get("is_contextual"))
                if contextual_count > 0:
                    logger.info(
                        f"{contextual_count}/{len(rows)} results used contextual embeddings"
                    )

                conn.close()
                return [dict(row) for row in rows]

        except sqlite3.OperationalError as e:
            logger.warning(f"Contextual search failed: {e}")

    # Fall back to regular search
    if not use_text_search:
        try:
            # Use regular embeddings
            logger.debug("Using standard vector search")

            base_query = """
            WITH vector_matches AS (
                SELECT
                    rowid,
                    distance
                FROM document_segments_vec
                WHERE embedding MATCH ?
                ORDER BY distance
                LIMIT ?
            ),
            ranked_segments AS (
                SELECT
                    s.id,
                    s.document_id,
                    s.content,
                    s.section_title,
                    s.section_path,
                    s.section_level,
                    s.parent_segment_id,
                    s.context_description,
                    s.context_metadata,
                    d.title,
                    d.url,
                    d.version,
                    d.updated_at,
                    d.is_library_doc,
                    d.library_id,
                    l.name as library_name,
                    (2.0 - v.distance) / 2.0 AS score,
                    0 as is_contextual,
                    ROW_NUMBER() OVER (PARTITION BY s.section_path ORDER BY v.distance) as rn
                FROM vector_matches v
                JOIN document_segments s ON v.rowid = s.id
                JOIN documents d ON s.document_id = d.id
                LEFT JOIN libraries l ON d.library_id = l.id
                WHERE s.section_path IS NOT NULL
            """

            if filter_conditions:
                base_query += " AND " + " AND ".join(filter_conditions)

            base_query += """
            )
            SELECT * FROM ranked_segments
            WHERE rn = 1 AND score >= ?
            ORDER BY score DESC
            LIMIT ?
            """

            cursor.execute(
                base_query,
                (embedding, limit * 10) + tuple(filter_params) + (min_score, limit),
            )

            rows = cursor.fetchall()

            if rows:
                conn.close()
                return [dict(row) for row in rows]

        except sqlite3.OperationalError as e:
            logger.warning(f"Vector search failed: {e}")
            use_text_search = True

    # Fall back to text search
    if use_text_search and text_query:
        logger.debug("Using text search fallback")
        # Import the regular search function to avoid duplication
        from docvault.db.operations import search_segments

        conn.close()
        return search_segments(
            embedding=None,
            limit=limit,
            text_query=text_query,
            min_score=min_score,
            doc_filter=doc_filter,
        )

    conn.close()
    return []


def get_contextual_segments_stats() -> dict[str, Any]:
    """Get statistics about contextual segments in the database."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Total segments
        cursor.execute("SELECT COUNT(*) as total FROM document_segments")
        total = cursor.fetchone()["total"]

        # Segments with context
        cursor.execute(
            """
            SELECT COUNT(*) as with_context
            FROM document_segments
            WHERE context_description IS NOT NULL
        """
        )
        with_context = cursor.fetchone()["with_context"]

        # Segments with contextual embeddings
        cursor.execute(
            """
            SELECT COUNT(*) as with_embedding
            FROM document_segments
            WHERE context_embedding IS NOT NULL
        """
        )
        with_embedding = cursor.fetchone()["with_embedding"]

        # Documents with any contextual segments
        cursor.execute(
            """
            SELECT COUNT(DISTINCT document_id) as docs_with_context
            FROM document_segments
            WHERE context_description IS NOT NULL
        """
        )
        docs_with_context = cursor.fetchone()["docs_with_context"]

        # Total documents
        cursor.execute("SELECT COUNT(*) as total_docs FROM documents")
        total_docs = cursor.fetchone()["total_docs"]

        return {
            "total_segments": total,
            "segments_with_context": with_context,
            "segments_with_contextual_embedding": with_embedding,
            "coverage_percentage": (with_context / total * 100) if total > 0 else 0,
            "documents_with_context": docs_with_context,
            "total_documents": total_docs,
            "document_coverage_percentage": (
                (docs_with_context / total_docs * 100) if total_docs > 0 else 0
            ),
        }

    finally:
        conn.close()
