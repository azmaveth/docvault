"""Tag management for documents in DocVault."""

import logging
import sqlite3
from typing import Any, Optional

from docvault import config

logger = logging.getLogger(__name__)


def create_tag(name: str, description: str | None = None) -> int:
    """Create a new tag.

    Args:
        name: Tag name (must be unique)
        description: Optional tag description

    Returns:
        ID of the created tag

    Raises:
        ValueError: If tag name already exists
    """
    conn = sqlite3.connect(config.DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tags (name, description) VALUES (?, ?)",
            (name.lower().strip(), description),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"Tag '{name}' already exists")
    finally:
        conn.close()


def get_tag(name: str) -> dict[str, Any] | None:
    """Get a tag by name.

    Args:
        name: Tag name

    Returns:
        Tag dictionary or None if not found
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tags WHERE name = ?", (name.lower().strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_tags() -> list[dict[str, Any]]:
    """List all tags with their document counts.

    Returns:
        List of tag dictionaries with document counts
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.*, COUNT(dt.document_id) as document_count
            FROM tags t
            LEFT JOIN document_tags dt ON t.id = dt.tag_id
            GROUP BY t.id
            ORDER BY t.name
        """
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def delete_tag(tag_id: int) -> bool:
    """Delete a tag.

    Args:
        tag_id: ID of tag to delete

    Returns:
        True if deleted, False if not found
    """
    conn = sqlite3.connect(config.DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def add_tag_to_document(document_id: int, tag_name: str) -> bool:
    """Add a tag to a document.

    Args:
        document_id: ID of the document
        tag_name: Name of the tag

    Returns:
        True if added successfully, False if already exists

    Raises:
        ValueError: If document or tag not found
    """
    conn = sqlite3.connect(config.DB_PATH)
    try:
        cursor = conn.cursor()

        # Check if document exists
        cursor.execute("SELECT 1 FROM documents WHERE id = ?", (document_id,))
        if not cursor.fetchone():
            raise ValueError(f"Document {document_id} not found")

        # Get or create tag
        tag = get_tag(tag_name)
        if not tag:
            tag_id = create_tag(tag_name)
        else:
            tag_id = tag["id"]

        # Add tag to document
        try:
            cursor.execute(
                "INSERT INTO document_tags (document_id, tag_id) VALUES (?, ?)",
                (document_id, tag_id),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Tag already assigned to document
            return False
    finally:
        conn.close()


def remove_tag_from_document(document_id: int, tag_name: str) -> bool:
    """Remove a tag from a document.

    Args:
        document_id: ID of the document
        tag_name: Name of the tag

    Returns:
        True if removed, False if not found
    """
    conn = sqlite3.connect(config.DB_PATH)
    try:
        cursor = conn.cursor()

        # Get tag ID
        tag = get_tag(tag_name)
        if not tag:
            return False

        cursor.execute(
            "DELETE FROM document_tags WHERE document_id = ? AND tag_id = ?",
            (document_id, tag["id"]),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_document_tags(document_id: int) -> list[str]:
    """Get all tags for a document.

    Args:
        document_id: ID of the document

    Returns:
        List of tag names
    """
    conn = sqlite3.connect(config.DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.name
            FROM tags t
            JOIN document_tags dt ON t.id = dt.tag_id
            WHERE dt.document_id = ?
            ORDER BY t.name
        """,
            (document_id,),
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_documents_by_tag(tag_name: str) -> list[dict[str, Any]]:
    """Get all documents with a specific tag.

    Args:
        tag_name: Name of the tag

    Returns:
        List of document dictionaries
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT d.*
            FROM documents d
            JOIN document_tags dt ON d.id = dt.document_id
            JOIN tags t ON dt.tag_id = t.id
            WHERE t.name = ?
            ORDER BY d.title
        """,
            (tag_name.lower().strip(),),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def search_documents_by_tags(
    tags: list[str], mode: str = "any"
) -> list[dict[str, Any]]:
    """Search documents by multiple tags.

    Args:
        tags: List of tag names
        mode: "any" (OR) or "all" (AND) - how to combine tags

    Returns:
        List of document dictionaries
    """
    if not tags:
        return []

    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()

        # Normalize tag names
        normalized_tags = [tag.lower().strip() for tag in tags]
        placeholders = ",".join(["?" for _ in normalized_tags])

        if mode == "all":
            # Documents must have ALL specified tags
            query = f"""
                SELECT d.*
                FROM documents d
                WHERE NOT EXISTS (
                    SELECT 1 FROM tags t
                    WHERE t.name IN ({placeholders})
                    AND NOT EXISTS (
                        SELECT 1 FROM document_tags dt
                        WHERE dt.document_id = d.id AND dt.tag_id = t.id
                    )
                )
                ORDER BY d.title
            """
        else:  # mode == "any"
            # Documents must have ANY of the specified tags
            query = f"""
                SELECT DISTINCT d.*
                FROM documents d
                JOIN document_tags dt ON d.id = dt.document_id
                JOIN tags t ON dt.tag_id = t.id
                WHERE t.name IN ({placeholders})
                ORDER BY d.title
            """

        cursor.execute(query, normalized_tags)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
