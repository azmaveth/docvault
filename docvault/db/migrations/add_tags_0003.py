"""Add tags support for documents."""

import logging
import sqlite3


def migrate(conn: sqlite3.Connection):
    """Add tags support to the database schema."""
    logger = logging.getLogger(__name__)

    try:
        # Create tags table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create document_tags junction table for many-to-many relationship
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_tags (
                document_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (document_id, tag_id),
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        """
        )

        # Create indexes for efficient queries
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_document_tags_document 
            ON document_tags(document_id)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_document_tags_tag 
            ON document_tags(tag_id)
        """
        )

        # Create index on tag names for quick lookup
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tags_name 
            ON tags(name)
        """
        )

        conn.commit()
        logger.info("Successfully added tags support to database schema")

    except Exception as e:
        logger.error(f"Error adding tags support: {e}")
        raise
