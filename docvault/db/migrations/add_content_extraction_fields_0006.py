"""Add fields for content extraction improvements."""

import sqlite3


def migrate(conn: sqlite3.Connection) -> None:
    """Add doc_type and metadata fields to documents table."""
    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(documents)")
    columns = {col[1] for col in cursor.fetchall()}

    # Add doc_type column if it doesn't exist
    if "doc_type" not in columns:
        cursor.execute(
            """
            ALTER TABLE documents
            ADD COLUMN doc_type TEXT DEFAULT 'unknown'
        """
        )

    # Add metadata column if it doesn't exist
    if "metadata" not in columns:
        cursor.execute(
            """
            ALTER TABLE documents
            ADD COLUMN metadata TEXT
        """
        )

    conn.commit()


def rollback(conn: sqlite3.Connection) -> None:
    """Rollback is not supported for column additions."""
    # SQLite doesn't support dropping columns easily
    pass


def get_version() -> int:
    """Return the migration version number."""
    return 6
