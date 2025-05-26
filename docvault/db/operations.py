import datetime
import logging
import sqlite3
from typing import Any, Dict, List, Optional

from docvault import config
from docvault.db.query_builder import build_document_filter
from docvault.db.sql_logging import enable_query_logging

# Set up logger
logger = logging.getLogger(__name__)


# Register adapter for datetime objects to fix deprecation warning in Python 3.12
def adapt_datetime(dt):
    return dt.isoformat()


def get_connection():
    """Get a connection to the SQLite database"""
    # Register the datetime adapter
    sqlite3.register_adapter(datetime.datetime, adapt_datetime)

    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    # Enable loading extensions if sqlite-vec is available (Python package)
    try:
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
    except ImportError:
        pass
    except Exception:
        pass

    # Enable query logging for security auditing
    if getattr(config, "SQL_LOGGING", False):
        enable_query_logging(conn)

    return conn


def add_document(
    url: str,
    title: str,
    html_path: str,
    markdown_path: str,
    library_id: Optional[int] = None,
    is_library_doc: bool = False,
    version: str = "latest",
    content_hash: Optional[str] = None,
    has_llms_txt: bool = False,
    llms_txt_url: Optional[str] = None,
) -> int:
    """Add a document to the database, supporting versioning and content hash."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
    INSERT INTO documents 
    (url, version, title, html_path, markdown_path, content_hash, library_id, is_library_doc, scraped_at, has_llms_txt, llms_txt_url)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            url,
            version,
            title,
            str(html_path),
            str(markdown_path),
            content_hash,
            library_id,
            is_library_doc,
            datetime.datetime.now(),
            has_llms_txt,
            llms_txt_url,
        ),
    )
    document_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return document_id


def update_document_by_url(
    url: str,
    title: str,
    html_path: str,
    markdown_path: str,
    library_id: Optional[int] = None,
    is_library_doc: bool = False,
    version: str = "latest",
    content_hash: Optional[str] = None,
    has_llms_txt: bool = False,
    llms_txt_url: Optional[str] = None,
) -> int:
    """Update a document by deleting the old one (if any) and re-adding it with a new timestamp/version."""
    old_doc = get_document_by_url(url)
    if old_doc:
        delete_document(old_doc["id"])
    return add_document(
        url,
        title,
        html_path,
        markdown_path,
        library_id,
        is_library_doc,
        version,
        content_hash,
        has_llms_txt,
        llms_txt_url,
    )


def delete_document(document_id: int) -> bool:
    """Delete a document and its segments from the database"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Begin transaction
        conn.execute("BEGIN TRANSACTION")

        # Delete segments first (though CASCADE would handle this)
        cursor.execute(
            "DELETE FROM document_segments WHERE document_id = ?", (document_id,)
        )

        # Delete from document_segments_vec
        try:
            # Get segment IDs for this document
            cursor.execute(
                "SELECT id FROM document_segments WHERE document_id = ?", (document_id,)
            )
            segment_ids = [row[0] for row in cursor.fetchall()]

            # Delete from vector table if it exists
            for segment_id in segment_ids:
                try:
                    cursor.execute(
                        "DELETE FROM document_segments_vec WHERE rowid = ?",
                        (segment_id,),
                    )
                except sqlite3.OperationalError:
                    # Vector table might not exist
                    pass
        except Exception:
            # Ignore errors with vector table
            pass

        # Delete the document
        cursor.execute("DELETE FROM documents WHERE id = ?", (document_id,))

        # Commit transaction
        conn.commit()
        return True
    except Exception:
        # Rollback on error
        conn.rollback()
        raise
    finally:
        conn.close()

    return False


def get_document_segments(document_id: int) -> List[Dict[str, Any]]:
    """Get all segments for a document.

    Args:
        document_id: ID of the document

    Returns:
        List of segment dictionaries
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM document_segments
        WHERE document_id = ?
        ORDER BY position
    """,
        (document_id,),
    )

    segments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return segments


def get_document(document_id: int) -> Optional[Dict[str, Any]]:
    """Get a document by ID"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
    row = cursor.fetchone()

    conn.close()

    if row:
        return dict(row)
    return None


def get_document_by_url(url: str) -> Optional[Dict[str, Any]]:
    """Get a document by URL"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM documents WHERE url = ?", (url,))
    row = cursor.fetchone()

    conn.close()

    if row:
        return dict(row)
    return None


def add_document_segment(
    document_id: int,
    content: str,
    embedding: bytes = None,
    segment_type: str = "text",
    position: int = 0,
    section_title: str = None,
    section_level: int = 1,
    section_path: str = None,
    parent_segment_id: int = None,
) -> int:
    """Add a segment to a document with optional section information

    Args:
        document_id: ID of the parent document
        content: Text content of the segment
        embedding: Optional embedding vector
        segment_type: Type of segment (e.g., 'text', 'heading1', 'heading2')
        position: Position within the document
        section_title: Title of the section
        section_level: Heading level (1 for h1, 2 for h2, etc.)
        section_path: Path-like string representing the section hierarchy (e.g., '1.2.3')
        parent_segment_id: ID of the parent segment (for nested sections)

    Returns:
        int: The ID of the newly created segment
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Generate a default section title if not provided
        if section_title is None:
            if segment_type.startswith("h"):
                # For headings, use the content as the section title
                section_title = content.strip()
            else:
                section_title = "Introduction"

        # Generate a default section path if not provided
        if section_path is None:
            section_path = str(position)

        # Ensure section_level is an integer
        try:
            section_level = int(section_level) if section_level is not None else 1
        except (ValueError, TypeError):
            section_level = 1

        # Insert the segment
        cursor.execute(
            """
            INSERT INTO document_segments 
            (document_id, content, embedding, segment_type, position, 
             section_title, section_level, section_path, parent_segment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                content,
                embedding,
                segment_type,
                position,
                section_title,
                section_level,
                section_path,
                parent_segment_id,
            ),
        )

        segment_id = cursor.lastrowid

        # If we have the vector extension, add to the vector table
        if embedding is not None:
            try:
                cursor.execute(
                    """
                    INSERT INTO document_segments_vec (rowid, embedding)
                    VALUES (?, ?)
                    """,
                    (segment_id, embedding),
                )
            except Exception as vec_error:
                logger.warning(f"Could not add vector data: {vec_error}")

        conn.commit()
        return segment_id

    except Exception as e:
        logger.error(f"Error adding document segment: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def search_segments(
    embedding: bytes = None,
    limit: int = 5,
    text_query: str = None,
    min_score: float = 0.0,
    doc_filter: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Search for similar document segments with metadata filtering

    Args:
        embedding: Vector embedding for semantic search
        limit: Maximum number of results to return
        text_query: Text query for full-text search
        min_score: Minimum similarity score (0.0 to 1.0)
        doc_filter: Dictionary of document filters (e.g., {'version': '1.0', 'is_library_doc': True})

    Returns:
        List of matching document segments with metadata
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Prepare document filters using secure query builder
    filter_conditions, filter_params = build_document_filter(doc_filter)

    # Check if we should skip vector search
    use_text_search = embedding is None
    rows = []

    if not use_text_search:
        try:
            # Debug: log the query
            logger = logging.getLogger(__name__)
            logger.debug(f"Vector search with {len(filter_params)} filter params")

            # Build vector search query - use static base query with additional conditions
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
                    d.title, 
                    d.url,
                    d.version,
                    d.updated_at,
                    d.is_library_doc,
                    d.library_id,
                    l.name as library_name,
                    (2.0 - v.distance) / 2.0 AS score,  -- Convert distance [0,2] to similarity [0,1]
                    ROW_NUMBER() OVER (PARTITION BY s.section_path ORDER BY v.distance) as rn
                FROM vector_matches v
                JOIN document_segments s ON v.rowid = s.id
                JOIN documents d ON s.document_id = d.id
                LEFT JOIN libraries l ON d.library_id = l.id
                WHERE s.section_path IS NOT NULL
            """

            # Add filter conditions
            if filter_conditions:
                # Since filter_conditions come from our controlled build_document_filter function,
                # and all user input is parameterized, this is safe
                base_query += " AND " + " AND ".join(filter_conditions)

            base_query += """
            )
            SELECT * FROM ranked_segments 
            WHERE rn = 1 AND score >= ?
            ORDER BY score DESC
            LIMIT ?
            """

            # Execute with properly ordered parameters
            cursor.execute(
                base_query,
                (embedding, limit * 10)  # Get more results for filtering
                + tuple(filter_params)
                + (min_score, limit),
            )

            rows = cursor.fetchall()

            # Debug: log results
            logger.debug(f"Vector search returned {len(rows)} rows")

            # If we got results, return them
            if len(rows) > 0:
                conn.close()
                return [dict(row) for row in rows]

            # Otherwise, fall back to text search
            use_text_search = True
            logger = logging.getLogger(__name__)
            logger.warning(
                "Vector search returned no matching results; falling back to text search. Ensure sqlite-vec extension is installed."
            )

        except sqlite3.OperationalError as e:
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Vector search failed ({e}); falling back to text search. To enable vector search, install sqlite-vec extension and ensure it's available."
            )
            use_text_search = True

    # Perform text search if needed
    if use_text_search:
        if text_query is not None and text_query.strip():
            # Prepare search patterns for text search
            search_terms = text_query.lower().split()
            like_patterns = [
                f"%{term}%" for term in search_terms[:3]
            ]  # Use first 3 terms for performance

            # Construct the query dynamically based on number of terms
            base_query = """
            WITH ranked_segments AS (
                SELECT 
                    s.id, 
                    s.document_id, 
                    s.content, 
                    s.section_title,
                    s.section_path,
                    s.section_level,
                    s.parent_segment_id,
                    s.segment_type, 
                    d.title, 
                    d.url,
                    d.version,
                    d.updated_at,
                    d.is_library_doc,
                    d.library_id,
                    l.name as library_name,
                    (CASE 
            """

            # Score for exact matches
            score_cases = []
            for i, term in enumerate(search_terms[:3]):
                # Higher score for matches in title or section title
                score_cases.append(
                    f"WHEN (LOWER(s.content) LIKE ?) AND (LOWER(s.section_title) LIKE ?) THEN {10.0 - i*0.5}"
                )
                score_cases.append(
                    f"WHEN (LOWER(s.content) LIKE ?) AND (LOWER(d.title) LIKE ?) THEN {8.0 - i*0.5}"
                )
                score_cases.append(f"WHEN LOWER(s.content) LIKE ? THEN {5.0 - i*0.5}")

            # Add default case
            score_cases.append("ELSE 0.5")

            # Build score cases for ORDER BY (without the END)
            order_score_cases = score_cases.copy()

            # Complete the query with section filtering
            query = (
                base_query
                + "\n".join(score_cases)
                + " END) AS score"
                + """
                    ,
                    ROW_NUMBER() OVER (PARTITION BY s.section_path ORDER BY 
                        (CASE 
                """
                + "\n".join(order_score_cases)
                + """
                        END) DESC
                    ) as rn
                FROM document_segments s
                JOIN documents d ON s.document_id = d.id
                LEFT JOIN libraries l ON d.library_id = l.id
                WHERE s.section_path IS NOT NULL
                """
            )

            # Add filter conditions
            if filter_conditions:
                query += " AND " + " AND ".join(filter_conditions)

            query += " AND ("

            # Add WHERE conditions for each term with OR
            where_clauses = []
            for _ in search_terms[:3]:
                # Search in content, section title, and document title
                where_clauses.append(
                    "LOWER(s.content) LIKE ? OR LOWER(s.section_title) LIKE ? OR LOWER(d.title) LIKE ?"
                )

            query += " OR ".join(where_clauses)
            query += """
                )
                GROUP BY s.document_id, s.section_path
            )
            SELECT * FROM ranked_segments 
            WHERE rn = 1 AND score >= ?
            ORDER BY score DESC
            LIMIT ?
            """

            # Prepare all parameters - for each term, we need to add it multiple times for each condition
            params = []
            # For the score calculation in SELECT clause
            for term in like_patterns:
                # For each term, we have 3 WHEN conditions, each checking 2 fields for first two, 1 for the third
                params.extend(
                    [f"%{term}%", f"%{term}%"]
                )  # First WHEN: content LIKE ? AND section_title LIKE ?
                params.extend(
                    [f"%{term}%", f"%{term}%"]
                )  # Second WHEN: content LIKE ? AND title LIKE ?
                params.append(f"%{term}%")  # Third WHEN: content LIKE ?

            # For the score calculation in ORDER BY clause (same as above)
            order_params = []
            for term in like_patterns:
                order_params.extend([f"%{term}%", f"%{term}%"])  # First WHEN
                order_params.extend([f"%{term}%", f"%{term}%"])  # Second WHEN
                order_params.append(f"%{term}%")  # Third WHEN

            # For the WHERE clause
            where_params = []
            for term in like_patterns:
                where_params.extend(
                    [f"%{term}%"] * 3
                )  # For each of the 3 fields we search in

            # Combine all parameters: SELECT CASE params + ORDER BY CASE params + filter params + WHERE params + min_score + limit
            params = (
                params
                + order_params
                + filter_params
                + where_params
                + [min_score, limit]
            )

            cursor.execute(query, params)
        else:
            # No text query available, return random documents with metadata
            # Build query for no text search
            query = """
            WITH ranked_segments AS (
                SELECT 
                    s.id, 
                    s.document_id, 
                    s.content, 
                    s.section_title,
                    s.section_path,
                    s.section_level,
                    s.parent_segment_id,
                    s.segment_type, 
                    d.title, 
                    d.url,
                    d.version,
                    d.updated_at,
                    d.is_library_doc,
                    d.library_id,
                    l.name as library_name,
                    0.1 AS score,
                    ROW_NUMBER() OVER (PARTITION BY s.section_path ORDER BY RANDOM()) as rn
                FROM document_segments s
                JOIN documents d ON s.document_id = d.id
                LEFT JOIN libraries l ON d.library_id = l.id
                WHERE s.section_path IS NOT NULL
            """

            # Add filter conditions
            if filter_conditions:
                query += " AND " + " AND ".join(filter_conditions)

            query += """
            )
            SELECT * FROM ranked_segments 
            WHERE rn = 1 AND score >= ?
            ORDER BY RANDOM()
            LIMIT ?
            """

            cursor.execute(
                query,
                (min_score, limit) + tuple(filter_params),
            )

    # Fetch rows and close connection
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def document_exists(doc_id: str) -> bool:
    """
    Check if a document exists in the database by its ID.

    Args:
        doc_id: The ID of the document to check (format: "library_name:version")

    Returns:
        bool: True if the document exists, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if this is a library document (format: "library_name:version")
        if ":" in doc_id:
            lib_name, version = doc_id.split(":", 1)
            cursor.execute(
                """
                SELECT 1 FROM documents d
                JOIN libraries l ON d.library_id = l.id
                WHERE l.name = ? AND d.version = ?
                LIMIT 1
                """,
                (lib_name, version),
            )
        else:
            # Check by document ID directly
            cursor.execute("SELECT 1 FROM documents WHERE id = ? LIMIT 1", (doc_id,))

        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    except Exception as e:
        logger.error(f"Error checking if document exists: {e}")
        return False


def list_documents(
    limit: int = 20, offset: int = 0, filter_text: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List documents with optional filtering"""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM documents"
    params = []

    if filter_text:
        query += " WHERE title LIKE ? OR url LIKE ?"
        params.extend([f"%{filter_text}%", f"%{filter_text}%"])

    query += " ORDER BY scraped_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]


def add_library(name: str, version: str, doc_url: str) -> int:
    """Add a library to the database"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
    INSERT OR REPLACE INTO libraries 
    (name, version, doc_url, last_checked, is_available)
    VALUES (?, ?, ?, ?, ?)
    """,
        (name, version, doc_url, datetime.datetime.now(), True),
    )

    library_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return library_id


def get_library(name: str, version: str) -> Optional[Dict[str, Any]]:
    """Get a library by name and version"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
    SELECT * FROM libraries 
    WHERE name = ? AND version = ?
    """,
        (name, version),
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def get_library_documents(library_id: int) -> List[Dict[str, Any]]:
    """Get all documents for a library"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
    SELECT * FROM documents 
    WHERE library_id = ?
    """,
        (library_id,),
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_latest_library_version(name: str) -> Optional[Dict[str, Any]]:
    """Get the latest version of a library by name"""
    conn = get_connection()
    cursor = conn.cursor()

    # First try to find an explicitly 'latest' version
    cursor.execute(
        """
    SELECT * FROM libraries 
    WHERE name = ? AND version != 'latest' AND is_available = 1
    ORDER BY 
        CASE 
            WHEN version = 'stable' THEN 0
            WHEN version GLOB '[0-9]*.[0-9]*.[0-9]*' THEN 1 
            WHEN version GLOB '[0-9]*.[0-9]*' THEN 2
            ELSE 3
        END,
        CAST(REPLACE(REPLACE(REPLACE(version, 'v', ''), '-beta', ''), '-alpha', '') AS TEXT) DESC,
        last_checked DESC
    LIMIT 1
    """,
        (name,),
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None
