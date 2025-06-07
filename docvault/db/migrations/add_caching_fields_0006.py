"""
Add caching and staleness tracking fields to documents table.

This migration adds fields to track document freshness and enable
smart caching strategies.
"""

import sqlite3

from docvault import config


def upgrade(conn=None):
    """Add caching-related fields to documents table."""
    if conn is None:
        conn = sqlite3.connect(config.DB_PATH)
        close_conn = True
    else:
        close_conn = False
    cursor = conn.cursor()

    try:
        # Add last_checked timestamp - when we last verified if doc is up-to-date
        cursor.execute(
            """
            ALTER TABLE documents
            ADD COLUMN last_checked TIMESTAMP
        """
        )

        # Add etag for HTTP caching
        cursor.execute(
            """
            ALTER TABLE documents
            ADD COLUMN etag TEXT
        """
        )

        # Add staleness status
        cursor.execute(
            """
            ALTER TABLE documents
            ADD COLUMN staleness_status TEXT DEFAULT 'fresh'
            CHECK (staleness_status IN ('fresh', 'stale', 'outdated'))
        """
        )

        # Add pinned flag - pinned documents never become stale
        cursor.execute(
            """
            ALTER TABLE documents
            ADD COLUMN is_pinned BOOLEAN DEFAULT FALSE
        """
        )

        # Add last_modified from the server
        cursor.execute(
            """
            ALTER TABLE documents
            ADD COLUMN server_last_modified TIMESTAMP
        """
        )

        # Create index for staleness queries
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_documents_staleness
            ON documents(staleness_status, last_checked)
        """
        )

        # Create index for pinned documents
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_documents_pinned
            ON documents(is_pinned)
        """
        )

        # Initialize last_checked to scraped_at for existing documents
        cursor.execute(
            """
            UPDATE documents
            SET last_checked = scraped_at
            WHERE last_checked IS NULL
        """
        )

        conn.commit()
        print("✓ Added caching fields to documents table")

    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("⚠️  Caching fields already exist")
        else:
            raise
    finally:
        if close_conn:
            conn.close()


def downgrade():
    """Remove caching-related fields from documents table."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    try:
        # SQLite doesn't support dropping columns easily, so we need to recreate
        # the table
        cursor.execute(
            """
            CREATE TABLE documents_new (
                id INTEGER PRIMARY KEY,
                url TEXT NOT NULL,
                version TEXT NOT NULL,
                title TEXT,
                html_path TEXT,
                markdown_path TEXT,
                content_hash TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                library_id INTEGER,
                is_library_doc BOOLEAN DEFAULT FALSE,
                UNIQUE(url, version)
            )
        """
        )

        cursor.execute(
            """
            INSERT INTO documents_new
            SELECT id, url, version, title, html_path, markdown_path,
                   content_hash, scraped_at, updated_at, library_id, is_library_doc
            FROM documents
        """
        )

        cursor.execute("DROP TABLE documents")
        cursor.execute("ALTER TABLE documents_new RENAME TO documents")

        # Drop indexes
        cursor.execute("DROP INDEX IF EXISTS idx_documents_staleness")
        cursor.execute("DROP INDEX IF EXISTS idx_documents_pinned")

        conn.commit()
        print("✓ Removed caching fields from documents table")

    finally:
        conn.close()


# Migration metadata
migration_id = "0006"
description = "Add caching and staleness tracking fields"
