"""Documentation registry models and operations."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from docvault.db.operations import get_connection

logger = logging.getLogger(__name__)


@dataclass
class DocumentationSource:
    """Represents a documentation source (e.g., Python, Elixir, Node.js)."""

    id: Optional[int] = None
    name: str = ""
    package_manager: str = ""
    base_url: str = ""
    version_url_template: str = ""
    latest_version_url: str = ""
    is_active: bool = True
    last_checked: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: Tuple) -> "DocumentationSource":
        """Create a DocumentationSource from a database row."""
        return cls(
            id=row[0],
            name=row[1],
            package_manager=row[2],
            base_url=row[3],
            version_url_template=row[4],
            latest_version_url=row[5] or "",
            is_active=bool(row[6]),
            last_checked=row[7],
            created_at=row[8],
            updated_at=row[9],
        )


@dataclass
class LibraryEntry:
    """Represents a library entry in the documentation registry."""

    id: Optional[int] = None
    name: str = ""
    version: str = ""
    doc_url: str = ""
    source_id: Optional[int] = None
    package_name: Optional[str] = None
    latest_version: Optional[str] = None
    description: Optional[str] = None
    homepage_url: Optional[str] = None
    repository_url: Optional[str] = None
    is_available: bool = True
    last_checked: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: Tuple) -> "LibraryEntry":
        """Create a LibraryEntry from a database row."""
        return cls(
            id=row[0],
            name=row[1],
            version=row[2],
            doc_url=row[3],
            source_id=row[4],
            package_name=row[5],
            latest_version=row[6],
            description=row[7],
            homepage_url=row[8],
            repository_url=row[9],
            is_available=bool(row[10]) if row[10] is not None else None,
            last_checked=row[11],
            created_at=row[12],
            updated_at=row[13],
        )


def add_documentation_source(
    name: str,
    package_manager: str,
    base_url: str,
    version_url_template: str,
    latest_version_url: str = "",
    is_active: bool = True,
) -> DocumentationSource:
    """Add a new documentation source to the registry."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO documentation_sources 
            (name, package_manager, base_url, version_url_template, 
             latest_version_url, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING *
            """,
            (
                name,
                package_manager,
                base_url,
                version_url_template,
                latest_version_url,
                is_active,
            ),
        )

        row = cursor.fetchone()
        conn.commit()
        return DocumentationSource.from_row(row)
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to add documentation source: {e}")
        raise


def get_documentation_source(source_id: int) -> Optional[DocumentationSource]:
    """Get a documentation source by ID."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM documentation_sources WHERE id = ?",
        (source_id,),
    )

    row = cursor.fetchone()
    if not row:
        return None

    return DocumentationSource.from_row(row)


def list_documentation_sources(active_only: bool = True) -> List[DocumentationSource]:
    """List all documentation sources."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM documentation_sources"
    params = ()

    if active_only:
        query += " WHERE is_active = ?"
        params = (True,)

    cursor.execute(query, params)
    return [DocumentationSource.from_row(row) for row in cursor.fetchall()]


def add_library_entry(
    name: str,
    version: str,
    doc_url: str,
    source_id: Optional[int] = None,
    package_name: Optional[str] = None,
    latest_version: Optional[str] = None,
    description: Optional[str] = None,
    homepage_url: Optional[str] = None,
    repository_url: Optional[str] = None,
    is_available: bool = True,
) -> LibraryEntry:
    """Add a new library entry to the registry."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO libraries 
            (name, version, doc_url, source_id, package_name, latest_version,
             description, homepage_url, repository_url, is_available, last_checked,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(name, version) DO UPDATE SET
                doc_url = EXCLUDED.doc_url,
                source_id = EXCLUDED.source_id,
                package_name = EXCLUDED.package_name,
                latest_version = EXCLUDED.latest_version,
                description = EXCLUDED.description,
                homepage_url = EXCLUDED.homepage_url,
                repository_url = EXCLUDED.repository_url,
                is_available = EXCLUDED.is_available,
                last_checked = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (
                name,
                version,
                doc_url,
                source_id,
                package_name,
                latest_version,
                description,
                homepage_url,
                repository_url,
                is_available,
            ),
        )

        row = cursor.fetchone()
        conn.commit()
        return LibraryEntry.from_row(row)
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to add library entry: {e}")
        raise


def find_library(
    name: str, version: Optional[str] = None, source_id: Optional[int] = None
) -> Optional[LibraryEntry]:
    """Find a library by name and optional version/source."""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT * FROM libraries 
        WHERE name = ?
    """
    params = [name]

    if version:
        query += " AND version = ?"
        params.append(version)
    else:
        query += " AND is_available = 1"

    if source_id is not None:
        query += " AND source_id = ?"
        params.append(source_id)

    # Order by version in descending order if no specific version provided
    if not version:
        query += " ORDER BY version DESC"

    query += " LIMIT 1"

    cursor.execute(query, params)
    row = cursor.fetchone()

    return LibraryEntry.from_row(row) if row else None


def search_libraries(
    query: str, source_id: Optional[int] = None, limit: int = 10
) -> List[LibraryEntry]:
    """Search for libraries matching the query."""
    conn = get_connection()
    cursor = conn.cursor()

    search_query = """
        SELECT * FROM libraries 
        WHERE (name LIKE ? OR package_name LIKE ? OR description LIKE ?)
        AND is_available = 1
    """

    params = [f"%{query}%"] * 3

    if source_id is not None:
        search_query += " AND source_id = ?"
        params.append(source_id)

    search_query += " ORDER BY name, version DESC LIMIT ?"
    params.append(limit)

    cursor.execute(search_query, params)
    return [LibraryEntry.from_row(row) for row in cursor.fetchall()]
