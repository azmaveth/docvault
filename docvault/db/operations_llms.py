"""
Database operations for llms.txt support.
"""

from typing import Any, Dict, List, Optional

from .operations import get_connection


def add_llms_txt_metadata(
    document_id: int,
    llms_title: str,
    llms_summary: Optional[str] = None,
    llms_introduction: Optional[str] = None,
    llms_sections: Optional[str] = None,  # JSON string
) -> int:
    """Add llms.txt metadata for a document."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO llms_txt_metadata 
        (document_id, llms_title, llms_summary, llms_introduction, llms_sections, has_llms_txt)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (document_id, llms_title, llms_summary, llms_introduction, llms_sections),
    )

    metadata_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return metadata_id


def add_llms_txt_resource(
    document_id: int,
    section: str,
    title: str,
    url: str,
    description: Optional[str] = None,
    is_optional: bool = False,
) -> int:
    """Add an llms.txt resource entry."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO llms_txt_resources 
        (document_id, section, title, url, description, is_optional)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (document_id, section, title, url, description, is_optional),
    )

    resource_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return resource_id


def get_llms_txt_metadata(document_id: int) -> Optional[Dict[str, Any]]:
    """Get llms.txt metadata for a document."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM llms_txt_metadata
        WHERE document_id = ?
        """,
        (document_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def get_llms_txt_resources(document_id: int) -> List[Dict[str, Any]]:
    """Get all llms.txt resources for a document."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM llms_txt_resources
        WHERE document_id = ?
        ORDER BY section, id
        """,
        (document_id,),
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def search_llms_txt_resources(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search llms.txt resources by title or description."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT r.*, d.title as document_title, d.url as document_url
        FROM llms_txt_resources r
        JOIN documents d ON r.document_id = d.id
        WHERE r.title LIKE ? OR r.description LIKE ?
        ORDER BY r.title
        LIMIT ?
        """,
        (f"%{query}%", f"%{query}%", limit),
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_documents_with_llms_txt(limit: int = 20) -> List[Dict[str, Any]]:
    """Get all documents that have llms.txt files."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT d.*, m.llms_title, m.llms_summary
        FROM documents d
        JOIN llms_txt_metadata m ON d.id = m.document_id
        WHERE d.has_llms_txt = 1
        ORDER BY d.scraped_at DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]
