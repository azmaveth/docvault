"""Cross-reference management for documents in DocVault."""

import logging
import re
import sqlite3
from typing import Any, Dict, List, Optional

from docvault import config

logger = logging.getLogger(__name__)


# Common programming patterns for detecting references
REFERENCE_PATTERNS = {
    "function": [
        r"\b(\w+)\s*\(",  # function_name(
        r"`(\w+)\(\)`",  # `function_name()`
        r"`(\w+)\(`",  # `function_name(`
    ],
    "class": [
        r"\bclass\s+(\w+)",  # class ClassName
        r"`(\w+)`\s+class",  # `ClassName` class
        r"\b([A-Z]\w+)\s+class",  # ClassName class
    ],
    "method": [
        r"\.(\w+)\s*\(",  # .method_name(
        r"`\.(\w+)\(\)`",  # `.method_name()`
        r"\b(\w+)\.(\w+)\s*\(",  # object.method(
    ],
    "module": [
        r"import\s+(\w+)",  # import module
        r"from\s+(\w+)\s+import",  # from module import
        r"`(\w+)`\s+module",  # `module` module
    ],
}


def extract_references(content: str, segment_id: int) -> List[Dict[str, Any]]:
    """Extract potential cross-references from content.

    Args:
        content: The text content to analyze
        segment_id: ID of the source segment

    Returns:
        List of potential references with their types and contexts
    """
    references = []

    # Extract references by type
    for ref_type, patterns in REFERENCE_PATTERNS.items():
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                # Get the reference text
                if ref_type == "method" and len(match.groups()) > 1:
                    ref_text = f"{match.group(1)}.{match.group(2)}"
                else:
                    ref_text = match.group(1)

                # Get context (surrounding text)
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
                context = content[start:end].strip()

                references.append(
                    {
                        "source_segment_id": segment_id,
                        "reference_type": ref_type,
                        "reference_text": ref_text,
                        "reference_context": context,
                        "confidence": 0.8,  # Default confidence for pattern matching
                    }
                )

    # Also extract markdown links
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", content):
        link_text = match.group(1)
        link_url = match.group(2)

        # Check if it's an internal reference (starts with #)
        if link_url.startswith("#"):
            references.append(
                {
                    "source_segment_id": segment_id,
                    "reference_type": "link",
                    "reference_text": link_text,
                    "reference_context": link_url,
                    "confidence": 1.0,  # High confidence for explicit links
                }
            )

    return references


def store_references(references: List[Dict[str, Any]]) -> int:
    """Store extracted references in the database.

    Args:
        references: List of reference dictionaries

    Returns:
        Number of references stored
    """
    if not references:
        return 0

    conn = sqlite3.connect(config.DB_PATH)
    try:
        cursor = conn.cursor()

        # Insert references
        inserted = 0
        for ref in references:
            try:
                cursor.execute(
                    """
                    INSERT INTO cross_references 
                    (source_segment_id, reference_type, reference_text, 
                     reference_context, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        ref["source_segment_id"],
                        ref["reference_type"],
                        ref["reference_text"],
                        ref["reference_context"],
                        ref.get("confidence", 0.8),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                # Reference might already exist
                pass

        conn.commit()
        return inserted
    finally:
        conn.close()


def store_anchor(
    document_id: int,
    segment_id: int,
    anchor_type: str,
    anchor_name: str,
    anchor_signature: Optional[str] = None,
    anchor_path: Optional[str] = None,
) -> int:
    """Store a document anchor (identifier that can be referenced).

    Args:
        document_id: ID of the document
        segment_id: ID of the segment containing the anchor
        anchor_type: Type of anchor (function, class, method, section)
        anchor_name: Name of the anchor
        anchor_signature: Optional full signature
        anchor_path: Optional full path

    Returns:
        ID of the created anchor
    """
    conn = sqlite3.connect(config.DB_PATH)
    try:
        cursor = conn.cursor()

        # Use anchor_name as path if path not provided
        if not anchor_path:
            anchor_path = anchor_name

        cursor.execute(
            """
            INSERT OR REPLACE INTO document_anchors
            (document_id, segment_id, anchor_type, anchor_name, 
             anchor_signature, anchor_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                document_id,
                segment_id,
                anchor_type,
                anchor_name,
                anchor_signature,
                anchor_path,
            ),
        )

        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def extract_anchors_from_segment(
    content: str, segment_id: int, document_id: int
) -> List[Dict[str, Any]]:
    """Extract anchors (identifiers) from a segment.

    Args:
        content: The segment content
        segment_id: ID of the segment
        document_id: ID of the document

    Returns:
        List of extracted anchors
    """
    anchors = []

    # Extract function definitions
    for match in re.finditer(r"(?:def|function)\s+(\w+)\s*\(([^)]*)\)", content):
        func_name = match.group(1)
        func_params = match.group(2)
        signature = f"{func_name}({func_params})"

        anchors.append(
            {
                "document_id": document_id,
                "segment_id": segment_id,
                "anchor_type": "function",
                "anchor_name": func_name,
                "anchor_signature": signature,
                "anchor_path": func_name,
            }
        )

    # Extract class definitions
    for match in re.finditer(r"class\s+(\w+)(?:\s*\([^)]*\))?", content):
        class_name = match.group(1)

        anchors.append(
            {
                "document_id": document_id,
                "segment_id": segment_id,
                "anchor_type": "class",
                "anchor_name": class_name,
                "anchor_signature": match.group(0),
                "anchor_path": class_name,
            }
        )

    # Extract method definitions (simple pattern)
    for match in re.finditer(r"^\s{4,}def\s+(\w+)\s*\(", content, re.MULTILINE):
        method_name = match.group(1)

        anchors.append(
            {
                "document_id": document_id,
                "segment_id": segment_id,
                "anchor_type": "method",
                "anchor_name": method_name,
                "anchor_signature": None,
                "anchor_path": method_name,
            }
        )

    return anchors


def resolve_references(document_id: int) -> int:
    """Resolve cross-references for a document by matching with anchors.

    Args:
        document_id: ID of the document to process

    Returns:
        Number of references resolved
    """
    conn = sqlite3.connect(config.DB_PATH)
    try:
        cursor = conn.cursor()

        # Get all unresolved references for this document
        cursor.execute(
            """
            SELECT cr.id, cr.reference_text, cr.reference_type
            FROM cross_references cr
            JOIN document_segments ds ON cr.source_segment_id = ds.id
            WHERE ds.document_id = ? AND cr.target_segment_id IS NULL
        """,
            (document_id,),
        )

        unresolved = cursor.fetchall()
        resolved_count = 0

        for ref_id, ref_text, ref_type in unresolved:
            # Try to find matching anchor
            cursor.execute(
                """
                SELECT da.segment_id, da.document_id
                FROM document_anchors da
                WHERE da.anchor_name = ? 
                AND (da.anchor_type = ? OR ? = 'link')
                ORDER BY 
                    CASE WHEN da.document_id = ? THEN 0 ELSE 1 END,
                    da.id DESC
                LIMIT 1
            """,
                (ref_text, ref_type, ref_type, document_id),
            )

            match = cursor.fetchone()
            if match:
                target_segment_id, target_doc_id = match
                cursor.execute(
                    """
                    UPDATE cross_references
                    SET target_segment_id = ?, target_document_id = ?
                    WHERE id = ?
                """,
                    (target_segment_id, target_doc_id, ref_id),
                )
                resolved_count += 1

        conn.commit()
        return resolved_count
    finally:
        conn.close()


def get_references_from_segment(segment_id: int) -> List[Dict[str, Any]]:
    """Get all references from a segment.

    Args:
        segment_id: ID of the segment

    Returns:
        List of references with target information
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                cr.*,
                ds.section_title as target_section,
                d.title as target_document_title,
                d.url as target_document_url
            FROM cross_references cr
            LEFT JOIN document_segments ds ON cr.target_segment_id = ds.id
            LEFT JOIN documents d ON cr.target_document_id = d.id
            WHERE cr.source_segment_id = ?
            ORDER BY cr.reference_type, cr.reference_text
        """,
            (segment_id,),
        )

        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_references_to_segment(segment_id: int) -> List[Dict[str, Any]]:
    """Get all references pointing to a segment.

    Args:
        segment_id: ID of the target segment

    Returns:
        List of references from other segments
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                cr.*,
                ds.section_title as source_section,
                d.title as source_document_title,
                d.url as source_document_url
            FROM cross_references cr
            JOIN document_segments ds ON cr.source_segment_id = ds.id
            JOIN documents d ON ds.document_id = d.id
            WHERE cr.target_segment_id = ?
            ORDER BY d.title, ds.section_title
        """,
            (segment_id,),
        )

        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def build_reference_graph(document_id: int) -> Dict[str, Any]:
    """Build a reference graph for a document.

    Args:
        document_id: ID of the document

    Returns:
        Dictionary containing nodes (segments) and edges (references)
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()

        # Get all segments for the document
        cursor.execute(
            """
            SELECT id, section_title, section_path
            FROM document_segments
            WHERE document_id = ?
        """,
            (document_id,),
        )

        segments = {row["id"]: dict(row) for row in cursor.fetchall()}

        # Get all references within the document
        cursor.execute(
            """
            SELECT cr.*
            FROM cross_references cr
            JOIN document_segments ds ON cr.source_segment_id = ds.id
            WHERE ds.document_id = ? 
            AND cr.target_document_id = ?
        """,
            (document_id, document_id),
        )

        references = [dict(row) for row in cursor.fetchall()]

        return {
            "nodes": list(segments.values()),
            "edges": references,
            "document_id": document_id,
        }
    finally:
        conn.close()
