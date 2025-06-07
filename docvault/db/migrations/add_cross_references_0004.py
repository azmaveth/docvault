"""Add cross-references support for documents."""

import logging
import sqlite3


def migrate(conn: sqlite3.Connection):
    """Add cross-references support to the database schema."""
    logger = logging.getLogger(__name__)

    try:
        # Create cross_references table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cross_references (
                id INTEGER PRIMARY KEY,
                source_segment_id INTEGER NOT NULL,
                target_segment_id INTEGER,
                target_document_id INTEGER,
                reference_type TEXT NOT NULL,  -- 'function', 'class', 'module', 'link', etc.
                reference_text TEXT NOT NULL,  -- The actual text that references (e.g., 'foo()')
                reference_context TEXT,        -- Surrounding context
                confidence REAL DEFAULT 1.0,   -- Confidence score for auto-detected references
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_segment_id) REFERENCES document_segments(id) ON DELETE CASCADE,
                FOREIGN KEY (target_segment_id) REFERENCES document_segments(id) ON DELETE SET NULL,
                FOREIGN KEY (target_document_id) REFERENCES documents(id) ON DELETE SET NULL
            )
        """
        )

        # Create indexes for efficient queries
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cross_references_source
            ON cross_references(source_segment_id)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cross_references_target_segment
            ON cross_references(target_segment_id)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cross_references_target_document
            ON cross_references(target_document_id)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cross_references_type
            ON cross_references(reference_type)
        """
        )

        # Create a table for storing document anchors/identifiers
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_anchors (
                id INTEGER PRIMARY KEY,
                document_id INTEGER NOT NULL,
                segment_id INTEGER NOT NULL,
                anchor_type TEXT NOT NULL,     -- 'function', 'class', 'method', 'section', etc.
                anchor_name TEXT NOT NULL,     -- The identifier (e.g., 'MyClass', 'foo', 'installation')
                anchor_signature TEXT,         -- Full signature for functions/methods
                anchor_path TEXT,              -- Full path (e.g., 'module.class.method')
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY (segment_id) REFERENCES document_segments(id) ON DELETE CASCADE,
                UNIQUE(document_id, anchor_path)
            )
        """
        )

        # Create indexes for anchor lookups
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_document_anchors_document
            ON document_anchors(document_id)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_document_anchors_name
            ON document_anchors(anchor_name)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_document_anchors_type
            ON document_anchors(anchor_type)
        """
        )

        conn.commit()
        logger.info("Successfully added cross-references support to database schema")

    except Exception as e:
        logger.error(f"Error adding cross-references support: {e}")
        raise
