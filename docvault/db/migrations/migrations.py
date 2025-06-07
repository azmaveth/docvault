"""Database migration utilities for DocVault.

This module provides functions to manage database schema migrations
in a backward-compatible way.
"""

import logging
import sqlite3
from collections.abc import Callable
from typing import Any, Dict, List, Tuple

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
        migrations: list[tuple[int, MigrationFunc]] = [
            (1, _migrate_to_v1),  # Add section support
            (2, _migrate_to_v2),  # Add registry support
            (3, _migrate_to_v3),  # Add tags support
            (4, _migrate_to_v4),  # Add cross-references support
            (5, _migrate_to_v5),  # Add version tracking and update monitoring
            (6, _migrate_to_v6),  # Add caching and staleness tracking
            (7, _migrate_to_v7),  # Add collections for project-based organization
            (8, _migrate_to_v8),  # Add llms.txt support
            (9, _migrate_to_v9),  # Add contextual retrieval support
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

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(document_segments)")
    columns = {row[1] for row in cursor.fetchall()}

    # Add new columns to document_segments only if they don't exist
    if "section_title" not in columns:
        cursor.execute(
            """
        ALTER TABLE document_segments 
        ADD COLUMN section_title TEXT
        """
        )

    if "section_level" not in columns:
        cursor.execute(
            """
        ALTER TABLE document_segments 
        ADD COLUMN section_level INTEGER DEFAULT 1
        """
        )

    if "section_path" not in columns:
        cursor.execute(
            """
        ALTER TABLE document_segments 
        ADD COLUMN section_path TEXT
        """
        )

    if "parent_segment_id" not in columns:
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


def get_document_sections(document_id: int) -> list[dict[str, Any]]:
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
        """,
            (document_id,),
        )

        sections = [dict(row) for row in cursor.fetchall()]
        return sections

    except Exception as e:
        logger.error(f"Error getting document sections: {e}")
        return []
    finally:
        if conn:
            conn.close()


def _migrate_to_v2(conn: sqlite3.Connection) -> None:
    """Migration to v2: Add documentation registry support."""
    cursor = conn.cursor()

    # Create documentation_sources table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS documentation_sources (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,                   -- e.g., 'Python', 'Elixir', 'Node.js'
            package_manager TEXT,                -- e.g., 'pypi', 'hex', 'npm'
            base_url TEXT,                       -- Base URL for documentation
            version_url_template TEXT,            -- Template URL with {version} placeholder
            latest_version_url TEXT,              -- URL to fetch latest version
            is_active BOOLEAN DEFAULT TRUE,
            last_checked TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, package_manager)
        )
    """
    )

    # Check if libraries table exists first
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='libraries'"
    )
    if not cursor.fetchone():
        # Create libraries table if it doesn't exist
        cursor.execute(
            """
            CREATE TABLE libraries (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                doc_url TEXT NOT NULL,
                last_checked TIMESTAMP,
                UNIQUE(name, version)
            )
            """
        )

    # Check if columns already exist before adding them
    cursor.execute("PRAGMA table_info(libraries)")
    columns = {row[1] for row in cursor.fetchall()}

    # Add new columns to libraries table only if they don't exist
    if "source_id" not in columns:
        cursor.execute(
            "ALTER TABLE libraries ADD COLUMN source_id INTEGER REFERENCES documentation_sources(id)"
        )
    if "package_name" not in columns:
        cursor.execute("ALTER TABLE libraries ADD COLUMN package_name TEXT")
    if "latest_version" not in columns:
        cursor.execute("ALTER TABLE libraries ADD COLUMN latest_version TEXT")
    if "description" not in columns:
        cursor.execute("ALTER TABLE libraries ADD COLUMN description TEXT")
    if "homepage_url" not in columns:
        cursor.execute("ALTER TABLE libraries ADD COLUMN homepage_url TEXT")
    if "repository_url" not in columns:
        cursor.execute("ALTER TABLE libraries ADD COLUMN repository_url TEXT")
    if "created_at" not in columns:
        cursor.execute(
            "ALTER TABLE libraries ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )
    if "updated_at" not in columns:
        cursor.execute(
            "ALTER TABLE libraries ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )

    # Add indexes
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_libraries_source ON libraries(source_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_libraries_package ON libraries(package_name)"
    )

    # Add triggers for updated_at
    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS update_documentation_sources_updated_at
        AFTER UPDATE ON documentation_sources
        FOR EACH ROW
        BEGIN
            UPDATE documentation_sources SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS update_libraries_updated_at
        AFTER UPDATE ON libraries
        FOR EACH ROW
        BEGIN
            UPDATE libraries SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    """
    )

    logger.info("Applied migration: Added documentation registry support")


def _migrate_to_v3(conn: sqlite3.Connection) -> None:
    """Migration to v3: Add tags support for documents."""
    from . import add_tags_0003

    add_tags_0003.migrate(conn)


def _migrate_to_v4(conn: sqlite3.Connection) -> None:
    """Migration to v4: Add cross-references support for documents."""
    from . import add_cross_references_0004

    add_cross_references_0004.migrate(conn)


def _migrate_to_v5(conn: sqlite3.Connection) -> None:
    """Migration to v5: Add version tracking and update monitoring."""
    from . import add_version_tracking_0005

    add_version_tracking_0005.migrate(conn)


def _migrate_to_v6(conn: sqlite3.Connection) -> None:
    """Migration to v6: Add caching and staleness tracking fields."""
    from . import add_caching_fields_0006

    add_caching_fields_0006.upgrade(conn)


def _migrate_to_v7(conn: sqlite3.Connection) -> None:
    """Migration to v7: Add collections for project-based document organization."""
    from . import add_collections_0007

    add_collections_0007.upgrade(conn)


def _migrate_to_v8(conn: sqlite3.Connection) -> None:
    """Migration to v8: Add llms.txt support for AI-friendly documentation."""
    from . import add_llms_txt_support_0008

    add_llms_txt_support_0008.upgrade(conn)


def _migrate_to_v9(conn: sqlite3.Connection) -> None:
    """Migration to v9: Add contextual retrieval support for enhanced RAG."""
    from . import add_contextual_retrieval_0009

    add_contextual_retrieval_0009.upgrade(conn)
