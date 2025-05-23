"""Database migration utilities for DocVault.

This module provides functions to manage database schema migrations
in a backward-compatible way.
"""

import logging
import sqlite3
from typing import Any, Callable, Dict, List, Tuple

from docvault import config

logger = logging.getLogger(__name__)

# Type alias for migration functions
MigrationFunc = Callable[[sqlite3.Connection], None]


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get the current schema version from the database.

    If the version table doesn't exist, it means this is a fresh install.
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
        version = cursor.fetchone()
        return version[0] if version else 0
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return 0


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Set the schema version in the database."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()


def migrate_schema() -> bool:
    """Run all pending database migrations.

    Returns:
        bool: True if migrations were applied successfully, False otherwise
    """
    conn = None
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row

        # Enable foreign keys and WAL mode for better concurrency
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")

        # Create schema version table if it doesn't exist
        conn.execute(
            """
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
        )

        # Get current schema version
        current_version = get_schema_version(conn)

        # Define migrations
        migrations: List[Tuple[int, MigrationFunc]] = [
            (1, _migrate_to_v1),  # Add section support
        ]

        # Apply pending migrations
        applied = 0
        for version, migration_func in migrations:
            if version > current_version:
                logger.info(f"Applying database migration to v{version}...")
                try:
                    with conn:  # Use transaction
                        migration_func(conn)
                        set_schema_version(conn, version)
                    applied += 1
                    logger.info(f"Successfully applied migration to v{version}")
                except Exception as e:
                    logger.error(f"Failed to apply migration v{version}: {e}")
                    logger.exception("Migration error details:")
                    return False

        if applied > 0:
            logger.info(f"Successfully applied {applied} database migrations")

        return True

    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def _migrate_to_v1(conn: sqlite3.Connection) -> None:
    """Migration to v1: Add section support to document segments."""
    cursor = conn.cursor()

    # Add new columns to document_segments
    cursor.execute(
        """
    ALTER TABLE document_segments 
    ADD COLUMN section_title TEXT
    """
    )

    cursor.execute(
        """
    ALTER TABLE document_segments 
    ADD COLUMN section_level INTEGER DEFAULT 1
    """
    )

    cursor.execute(
        """
    ALTER TABLE document_segments 
    ADD COLUMN section_path TEXT
    """
    )

    cursor.execute(
        """
    ALTER TABLE document_segments 
    ADD COLUMN parent_segment_id INTEGER
    REFERENCES document_segments(id) ON DELETE SET NULL
    """
    )

    # Create indexes for section navigation
    cursor.execute(
        """
    CREATE INDEX IF NOT EXISTS idx_segment_document 
    ON document_segments(document_id)
    """
    )

    cursor.execute(
        """
    CREATE INDEX IF NOT EXISTS idx_segment_section 
    ON document_segments(document_id, section_path)
    """
    )

    cursor.execute(
        """
    CREATE INDEX IF NOT EXISTS idx_segment_parent 
    ON document_segments(document_id, parent_segment_id)
    """
    )

    # Update existing segments with default values
    cursor.execute(
        """
    UPDATE document_segments 
    SET section_title = 'Introduction', 
        section_path = '0',
        section_level = 1
    WHERE section_title IS NULL
    """
    )

    logger.info("Applied migration: Added section support to document segments")


def get_document_sections(document_id: int) -> List[Dict[str, Any]]:
    """Get the sections hierarchy for a document.

    Args:
        document_id: ID of the document

    Returns:
        List of sections with their hierarchy
    """
    conn = None
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, section_title, section_level, section_path, parent_segment_id
            FROM document_segments
            WHERE document_id = ? AND section_title IS NOT NULL
            ORDER BY section_path
        SELECT 
            id,
            section_title as title,
            section_level as level,
            section_path as path,
            parent_segment_id as parent_id
        FROM document_segments
        WHERE document_id = ? 
        AND section_title IS NOT NULL
        ORDER BY section_path, position
        """,
            (document_id,),
        )

        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
