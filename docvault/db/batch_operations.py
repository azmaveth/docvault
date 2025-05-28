"""
Batch database operations for improved performance.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from docvault.db.connection_pool import get_connection

logger = logging.getLogger(__name__)


def batch_insert_segments(
    document_id: int, segments: List[Dict[str, Any]], batch_size: int = 100
) -> List[int]:
    """
    Insert document segments in batches for better performance.

    Args:
        document_id: The document ID
        segments: List of segment dictionaries with keys: content, section_title, segment_type, embedding
        batch_size: Number of segments to insert per batch

    Returns:
        List of segment IDs
    """
    segment_ids = []

    with get_connection() as conn:
        cursor = conn.cursor()

        # Process segments in batches
        for i in range(0, len(segments), batch_size):
            batch = segments[i : i + batch_size]

            # Prepare batch data for segments table
            segment_data = []
            vector_data = []

            for segment in batch:
                segment_data.append(
                    (
                        document_id,
                        segment.get("content", ""),
                        segment.get("section_title"),
                        segment.get("segment_type", "text"),
                        segment.get("section_path"),
                        segment.get("parent_id"),
                    )
                )

                # Prepare vector data if embedding exists
                embedding = segment.get("embedding")
                if embedding and len(embedding) > 0:
                    vector_data.append((embedding,))
                else:
                    vector_data.append((None,))

            try:
                # Insert segments batch
                cursor.executemany(
                    """
                    INSERT INTO document_segments 
                    (document_id, content, section_title, segment_type, section_path, parent_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    segment_data,
                )

                # Get the inserted segment IDs
                first_id = cursor.lastrowid
                batch_segment_ids = list(range(first_id - len(batch) + 1, first_id + 1))
                segment_ids.extend(batch_segment_ids)

                # Insert vectors batch (only for segments with embeddings)
                vector_insert_data = []
                for j, (segment_id, (embedding,)) in enumerate(
                    zip(batch_segment_ids, vector_data)
                ):
                    if embedding is not None:
                        vector_insert_data.append((segment_id, embedding))

                if vector_insert_data:
                    try:
                        cursor.executemany(
                            "INSERT INTO document_segments_vec (segment_id, embedding) VALUES (?, ?)",
                            vector_insert_data,
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to insert vector embeddings for batch: {e}"
                        )

                conn.commit()
                logger.debug(f"Inserted batch of {len(batch)} segments")

            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to insert segment batch: {e}")
                raise

    return segment_ids


def batch_update_embeddings(
    segment_embeddings: List[Tuple[int, List[float]]], batch_size: int = 100
) -> int:
    """
    Update embeddings for multiple segments in batches.

    Args:
        segment_embeddings: List of (segment_id, embedding) tuples
        batch_size: Number of updates per batch

    Returns:
        Number of successfully updated segments
    """
    updated_count = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        for i in range(0, len(segment_embeddings), batch_size):
            batch = segment_embeddings[i : i + batch_size]

            try:
                # Update or insert embeddings
                cursor.executemany(
                    """
                    INSERT OR REPLACE INTO document_segments_vec (segment_id, embedding)
                    VALUES (?, ?)
                    """,
                    batch,
                )

                updated_count += len(batch)
                conn.commit()
                logger.debug(f"Updated embeddings for batch of {len(batch)} segments")

            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to update embedding batch: {e}")

    return updated_count


def batch_delete_segments(segment_ids: List[int], batch_size: int = 100) -> int:
    """
    Delete multiple segments in batches.

    Args:
        segment_ids: List of segment IDs to delete
        batch_size: Number of deletions per batch

    Returns:
        Number of successfully deleted segments
    """
    deleted_count = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        for i in range(0, len(segment_ids), batch_size):
            batch = segment_ids[i : i + batch_size]
            placeholders = ",".join("?" * len(batch))

            try:
                # Delete from vector table first
                cursor.execute(
                    f"DELETE FROM document_segments_vec WHERE segment_id IN ({placeholders})",
                    batch,
                )

                # Delete from segments table
                cursor.execute(
                    f"DELETE FROM document_segments WHERE id IN ({placeholders})", batch
                )

                deleted_count += len(batch)
                conn.commit()
                logger.debug(f"Deleted batch of {len(batch)} segments")

            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to delete segment batch: {e}")

    return deleted_count


def batch_search_segments(
    query_vector: List[float],
    limit: int = 20,
    document_ids: Optional[List[int]] = None,
    min_similarity: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Perform batch vector search with optimized query.

    Args:
        query_vector: The search vector
        limit: Maximum number of results
        document_ids: Optional list of document IDs to filter by
        min_similarity: Minimum similarity score

    Returns:
        List of search results
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Build optimized search query
        base_query = """
        SELECT 
            ds.id,
            ds.document_id,
            ds.content,
            ds.section_title,
            ds.segment_type,
            ds.section_path,
            d.title as document_title,
            d.url as document_url,
            vsv.distance as similarity
        FROM document_segments ds
        JOIN documents d ON ds.document_id = d.id
        JOIN (
            SELECT 
                segment_id,
                distance
            FROM document_segments_vec
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
        ) vsv ON ds.id = vsv.segment_id
        """

        params = [str(query_vector), limit * 2]  # Get more candidates for filtering

        # Add document filter if specified
        if document_ids:
            placeholders = ",".join("?" * len(document_ids))
            base_query += f" WHERE ds.document_id IN ({placeholders})"
            params.extend(document_ids)

        # Add similarity filter
        if min_similarity > 0:
            if document_ids:
                base_query += " AND"
            else:
                base_query += " WHERE"
            base_query += " vsv.distance >= ?"
            params.append(min_similarity)

        base_query += " ORDER BY vsv.distance DESC LIMIT ?"
        params.append(limit)

        try:
            cursor.execute(base_query, params)
            results = []

            for row in cursor.fetchall():
                results.append(
                    {
                        "segment_id": row["id"],
                        "document_id": row["document_id"],
                        "content": row["content"],
                        "section_title": row["section_title"],
                        "segment_type": row["segment_type"],
                        "section_path": row["section_path"],
                        "document_title": row["document_title"],
                        "document_url": row["document_url"],
                        "similarity": row["similarity"],
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Batch search failed: {e}")
            return []
