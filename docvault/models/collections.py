"""
Collections management for DocVault.

Collections are project-based groupings of documents, providing a way to
organize documentation for specific purposes, projects, or learning paths.
Unlike tags (which are descriptive attributes), collections are curated
sets with optional ordering and project-specific context.
"""

import json
import logging
import sqlite3
from typing import Any, List, Optional, Tuple

from docvault.db.operations import get_connection

logger = logging.getLogger(__name__)


def create_collection(
    name: str,
    description: str | None = None,
    default_tags: list[str] | None = None,
) -> int:
    """Create a new collection.

    Args:
        name: Collection name (must be unique)
        description: Optional description of the collection's purpose
        default_tags: Optional list of tags to suggest for documents in this collection

    Returns:
        ID of the created collection

    Raises:
        ValueError: If collection name already exists
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Serialize default tags as JSON
        tags_json = json.dumps(default_tags) if default_tags else None

        try:
            cursor.execute(
                """
                INSERT INTO collections (name, description, default_tags)
                VALUES (?, ?, ?)
            """,
                (name.strip(), description, tags_json),
            )

            conn.commit()
            collection_id = cursor.lastrowid
            logger.info(f"Created collection '{name}' with ID {collection_id}")
            return collection_id

        except sqlite3.IntegrityError:
            raise ValueError(f"Collection '{name}' already exists")


def get_collection(collection_id: int) -> dict[str, Any] | None:
    """Get a collection by ID.

    Args:
        collection_id: Collection ID

    Returns:
        Collection dictionary or None if not found
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, description, is_active, default_tags,
                   created_at, updated_at
            FROM collections
            WHERE id = ?
        """,
            (collection_id,),
        )

        row = cursor.fetchone()
        if row:
            collection = dict(row)
            # Parse JSON tags
            if collection["default_tags"]:
                collection["default_tags"] = json.loads(collection["default_tags"])
            return collection
        return None


def get_collection_by_name(name: str) -> dict[str, Any] | None:
    """Get a collection by name.

    Args:
        name: Collection name

    Returns:
        Collection dictionary or None if not found
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, description, is_active, default_tags,
                   created_at, updated_at
            FROM collections
            WHERE name = ?
        """,
            (name.strip(),),
        )

        row = cursor.fetchone()
        if row:
            collection = dict(row)
            # Parse JSON tags
            if collection["default_tags"]:
                collection["default_tags"] = json.loads(collection["default_tags"])
            return collection
        return None


def list_collections(active_only: bool = True) -> list[dict[str, Any]]:
    """List all collections.

    Args:
        active_only: If True, only return active collections

    Returns:
        List of collection dictionaries
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT c.id, c.name, c.description, c.is_active, c.default_tags,
                   c.created_at, c.updated_at,
                   COUNT(cd.document_id) as document_count
            FROM collections c
            LEFT JOIN collection_documents cd ON c.id = cd.collection_id
        """

        if active_only:
            query += " WHERE c.is_active = 1"

        query += " GROUP BY c.id ORDER BY c.name"

        cursor.execute(query)

        collections = []
        for row in cursor.fetchall():
            collection = dict(row)
            # Parse JSON tags
            if collection["default_tags"]:
                collection["default_tags"] = json.loads(collection["default_tags"])
            collections.append(collection)

        return collections


def add_document_to_collection(
    collection_id: int,
    document_id: int,
    position: int | None = None,
    notes: str | None = None,
) -> bool:
    """Add a document to a collection.

    Args:
        collection_id: Collection ID
        document_id: Document ID
        position: Optional position in ordered collection
        notes: Optional notes about why this document is included

    Returns:
        True if added successfully, False if already exists
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # If no position specified, add at end
        if position is None:
            cursor.execute(
                """
                SELECT COALESCE(MAX(position), -1) + 1
                FROM collection_documents
                WHERE collection_id = ?
            """,
                (collection_id,),
            )
            position = cursor.fetchone()[0]

        try:
            cursor.execute(
                """
                INSERT INTO collection_documents
                (collection_id, document_id, position, notes)
                VALUES (?, ?, ?, ?)
            """,
                (collection_id, document_id, position, notes),
            )

            conn.commit()
            logger.info(f"Added document {document_id} to collection {collection_id}")
            return True

        except sqlite3.IntegrityError:
            logger.warning(
                f"Document {document_id} already in collection {collection_id}"
            )
            return False


def remove_document_from_collection(collection_id: int, document_id: int) -> bool:
    """Remove a document from a collection.

    Args:
        collection_id: Collection ID
        document_id: Document ID

    Returns:
        True if removed, False if not found
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM collection_documents
            WHERE collection_id = ? AND document_id = ?
        """,
            (collection_id, document_id),
        )

        conn.commit()
        removed = cursor.rowcount > 0

        if removed:
            logger.info(
                f"Removed document {document_id} from collection {collection_id}"
            )

        return removed


def get_collection_documents(
    collection_id: int, include_content: bool = False
) -> list[dict[str, Any]]:
    """Get all documents in a collection.

    Args:
        collection_id: Collection ID
        include_content: If True, include document content

    Returns:
        List of document dictionaries ordered by position
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT d.id, d.title, d.url, d.version, d.scraped_at,
                   cd.position, cd.notes, cd.added_at
        """

        if include_content:
            query += ", d.markdown_path"

        query += """
            FROM collection_documents cd
            JOIN documents d ON cd.document_id = d.id
            WHERE cd.collection_id = ?
            ORDER BY cd.position, cd.added_at
        """

        cursor.execute(query, (collection_id,))

        documents = []
        for row in cursor.fetchall():
            doc = dict(row)
            if include_content and doc.get("markdown_path"):
                try:
                    with open(doc["markdown_path"]) as f:
                        doc["content"] = f.read()
                except Exception as e:
                    logger.warning(f"Could not read content for doc {doc['id']}: {e}")
                    doc["content"] = None
            documents.append(doc)

        return documents


def get_document_collections(document_id: int) -> list[dict[str, Any]]:
    """Get all collections containing a document.

    Args:
        document_id: Document ID

    Returns:
        List of collection dictionaries
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT c.id, c.name, c.description, c.is_active,
                   cd.position, cd.notes, cd.added_at
            FROM collections c
            JOIN collection_documents cd ON c.id = cd.collection_id
            WHERE cd.document_id = ?
            ORDER BY c.name
        """,
            (document_id,),
        )

        collections = []
        for row in cursor.fetchall():
            collections.append(dict(row))

        return collections


def update_collection(
    collection_id: int,
    name: str | None = None,
    description: str | None = None,
    default_tags: list[str] | None = None,
    is_active: bool | None = None,
) -> bool:
    """Update collection properties.

    Args:
        collection_id: Collection ID
        name: New name (if provided)
        description: New description (if provided)
        default_tags: New default tags (if provided)
        is_active: New active status (if provided)

    Returns:
        True if updated, False if not found
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Build update query dynamically
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name.strip())

        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if default_tags is not None:
            updates.append("default_tags = ?")
            params.append(json.dumps(default_tags))

        if is_active is not None:
            updates.append("is_active = ?")
            params.append(int(is_active))

        if not updates:
            return False

        params.append(collection_id)
        query = f"UPDATE collections SET {', '.join(updates)} WHERE id = ?"

        cursor.execute(query, params)
        conn.commit()

        updated = cursor.rowcount > 0
        if updated:
            logger.info(f"Updated collection {collection_id}")

        return updated


def delete_collection(collection_id: int) -> bool:
    """Delete a collection.

    Args:
        collection_id: Collection ID

    Returns:
        True if deleted, False if not found
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        conn.commit()

        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted collection {collection_id}")

        return deleted


def reorder_collection_documents(
    collection_id: int, document_positions: list[tuple[int, int]]
) -> bool:
    """Reorder documents in a collection.

    Args:
        collection_id: Collection ID
        document_positions: List of (document_id, position) tuples

    Returns:
        True if reordered successfully
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        try:
            for doc_id, position in document_positions:
                cursor.execute(
                    """
                    UPDATE collection_documents
                    SET position = ?
                    WHERE collection_id = ? AND document_id = ?
                """,
                    (position, collection_id, doc_id),
                )

            conn.commit()
            logger.info(
                f"Reordered {len(document_positions)} documents in collection {collection_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to reorder collection documents: {e}")
            conn.rollback()
            return False


def search_documents_by_collection(
    collection_id: int,
    query: str | None = None,
    tags: list[str] | None = None,
    tag_mode: str = "any",
) -> list[dict[str, Any]]:
    """Search documents within a collection.

    Args:
        collection_id: Collection ID
        query: Optional search query
        tags: Optional list of tags to filter by
        tag_mode: How to match tags ("any" or "all")

    Returns:
        List of matching documents
    """
    # This is a helper that combines with existing search
    # Will be used by the search command when --collection is specified

    # First get all document IDs in the collection
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT document_id
            FROM collection_documents
            WHERE collection_id = ?
        """,
            (collection_id,),
        )

        doc_ids = [row[0] for row in cursor.fetchall()]

        if not doc_ids:
            return []

        # Return the document IDs to be used as a filter
        return doc_ids
