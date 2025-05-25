"""Add enhanced version tracking and update monitoring."""

import logging
import sqlite3


def migrate(conn: sqlite3.Connection):
    """Add version tracking and update monitoring to the database schema."""
    logger = logging.getLogger(__name__)

    try:
        # Create document_versions table to track multiple versions of the same document
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_versions (
                id INTEGER PRIMARY KEY,
                base_document_id INTEGER NOT NULL,  -- Original document ID
                version_string TEXT NOT NULL,       -- Version identifier
                url TEXT NOT NULL,                  -- URL for this version
                title TEXT,
                html_path TEXT,
                markdown_path TEXT,
                content_hash TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_latest BOOLEAN DEFAULT FALSE,    -- Mark the latest version
                change_summary TEXT,                -- Summary of changes from previous version
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (base_document_id) REFERENCES documents(id) ON DELETE CASCADE,
                UNIQUE(base_document_id, version_string)
            )
        """
        )

        # Create update_checks table to track when documents were last checked for updates
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS update_checks (
                id INTEGER PRIMARY KEY,
                document_id INTEGER NOT NULL,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                check_url TEXT,                     -- URL to check for updates
                latest_available_version TEXT,      -- Latest version found
                needs_update BOOLEAN DEFAULT FALSE, -- Whether an update is available
                check_error TEXT,                   -- Error message if check failed
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                UNIQUE(document_id)
            )
        """
        )

        # Create version_comparisons table to store diff information between versions
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS version_comparisons (
                id INTEGER PRIMARY KEY,
                document_id INTEGER NOT NULL,
                old_version_id INTEGER,
                new_version_id INTEGER,
                comparison_type TEXT DEFAULT 'content',  -- 'content', 'structure', 'functions'
                added_content TEXT,                      -- Content that was added
                removed_content TEXT,                    -- Content that was removed
                modified_sections TEXT,                  -- JSON of modified sections
                similarity_score REAL,                  -- Similarity score (0-1)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY (old_version_id) REFERENCES document_versions(id) ON DELETE SET NULL,
                FOREIGN KEY (new_version_id) REFERENCES document_versions(id) ON DELETE SET NULL
            )
        """
        )

        # Add version tracking fields to existing documents table
        try:
            conn.execute("ALTER TABLE documents ADD COLUMN base_url TEXT")
        except sqlite3.OperationalError:
            pass  # Column might already exist

        try:
            conn.execute(
                "ALTER TABLE documents ADD COLUMN check_for_updates BOOLEAN DEFAULT TRUE"
            )
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute(
                "ALTER TABLE documents ADD COLUMN update_frequency INTEGER DEFAULT 7"
            )  # Check every 7 days
        except sqlite3.OperationalError:
            pass

        # Create indexes for efficient queries
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_document_versions_base 
            ON document_versions(base_document_id)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_document_versions_version 
            ON document_versions(version_string)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_update_checks_document 
            ON update_checks(document_id)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_update_checks_needs_update 
            ON update_checks(needs_update)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_version_comparisons_document 
            ON version_comparisons(document_id)
        """
        )

        # Create triggers to maintain updated_at timestamps
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS update_checks_updated_at
            AFTER UPDATE ON update_checks
            FOR EACH ROW
            BEGIN
                UPDATE update_checks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        """
        )

        conn.commit()
        logger.info(
            "Successfully added version tracking and update monitoring to database schema"
        )

    except Exception as e:
        logger.error(f"Error adding version tracking: {e}")
        raise
