"""
Add collections support for document organization.

Collections are project-based groupings of documents, distinct from tags.
While tags are descriptive attributes, collections are curated sets of
documents organized for a specific purpose or project.
"""

import sqlite3

from docvault import config


def upgrade(conn=None):
    """Add collections tables to the database."""
    if conn is None:
        conn = sqlite3.connect(config.DB_PATH)
        close_conn = True
    else:
        close_conn = False

    cursor = conn.cursor()

    try:
        # Create collections table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                default_tags TEXT,  -- JSON array of suggested tags
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create collection_documents junction table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS collection_documents (
                collection_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                position INTEGER DEFAULT 0,  -- For ordered collections
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,  -- Optional notes about why this doc is in collection
                PRIMARY KEY (collection_id, document_id),
                FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """
        )

        # Create indexes for efficient queries
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_collection_documents_collection 
            ON collection_documents(collection_id, position)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_collection_documents_document 
            ON collection_documents(document_id)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_collections_name 
            ON collections(name)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_collections_active 
            ON collections(is_active)
        """
        )

        # Add trigger for updated_at
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS update_collections_updated_at
            AFTER UPDATE ON collections
            FOR EACH ROW
            BEGIN
                UPDATE collections SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        """
        )

        conn.commit()
        print("✓ Added collections tables to database")

    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            print("⚠️  Collections tables already exist")
        else:
            raise
    finally:
        if close_conn:
            conn.close()


def downgrade(conn=None):
    """Remove collections tables from the database."""
    if conn is None:
        conn = sqlite3.connect(config.DB_PATH)
        close_conn = True
    else:
        close_conn = False

    cursor = conn.cursor()

    try:
        # Drop triggers
        cursor.execute("DROP TRIGGER IF EXISTS update_collections_updated_at")

        # Drop indexes
        cursor.execute("DROP INDEX IF EXISTS idx_collection_documents_collection")
        cursor.execute("DROP INDEX IF EXISTS idx_collection_documents_document")
        cursor.execute("DROP INDEX IF EXISTS idx_collections_name")
        cursor.execute("DROP INDEX IF EXISTS idx_collections_active")

        # Drop tables
        cursor.execute("DROP TABLE IF EXISTS collection_documents")
        cursor.execute("DROP TABLE IF EXISTS collections")

        conn.commit()
        print("✓ Removed collections tables from database")

    finally:
        if close_conn:
            conn.close()


# Migration metadata
migration_id = "0007"
description = "Add collections for project-based document organization"
