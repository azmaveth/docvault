"""
Migration to add section-related fields to document_segments table.
"""


def up(conn):
    """Apply the migration."""
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


def down(conn):
    """Revert the migration."""
    cursor = conn.cursor()

    # Drop indexes first
    cursor.execute("DROP INDEX IF EXISTS idx_segment_document")
    cursor.execute("DROP INDEX IF EXISTS idx_segment_section")
    cursor.execute("DROP INDEX IF EXISTS idx_segment_parent")

    # SQLite doesn't support dropping columns directly, so we need to recreate the table
    cursor.execute(
        """
    CREATE TABLE document_segments_new (
        id INTEGER PRIMARY KEY,
        document_id INTEGER,
        content TEXT,
        embedding BLOB,
        segment_type TEXT,
        position INTEGER,
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """
    )

    # Copy data to the new table
    cursor.execute(
        """
    INSERT INTO document_segments_new 
    (id, document_id, content, embedding, segment_type, position)
    SELECT id, document_id, content, embedding, segment_type, position 
    FROM document_segments
    """
    )

    # Drop the old table and rename the new one
    cursor.execute("DROP TABLE document_segments")
    cursor.execute("ALTER TABLE document_segments_new RENAME TO document_segments")

    # Recreate other indexes
    cursor.execute(
        """
    CREATE INDEX IF NOT EXISTS idx_segment_document 
    ON document_segments(document_id)
    """
    )
