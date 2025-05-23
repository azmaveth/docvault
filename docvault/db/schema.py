import logging
import pathlib
import sqlite3

from docvault import config


def initialize_database(force_recreate=False):
    """Initialize the SQLite database with sqlite-vec extension"""
    # Ensure directory exists
    db_path = pathlib.Path(config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Delete existing database if force_recreate is True
    if force_recreate and db_path.exists():
        db_path.unlink()
        print(f"Deleted existing database at {db_path}")

    conn = sqlite3.connect(config.DB_PATH)

    # Load sqlite-vec extension (if available)
    try:
        import sqlite_vec  # type: ignore

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        logging.getLogger(__name__).info("sqlite-vec extension loaded successfully")
    except ImportError:
        logging.getLogger(__name__).warning(
            "sqlite-vec Python package not found; vector search disabled"
        )
    except (AttributeError, sqlite3.OperationalError) as e:
        logging.getLogger(__name__).warning(
            "sqlite-vec extension cannot be loaded: %s; vector search disabled", e
        )

    conn.executescript(
        """
    -- Documents table
    CREATE TABLE IF NOT EXISTS documents (
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
    );

    -- Document segments for more granular search
    CREATE TABLE IF NOT EXISTS document_segments (
        id INTEGER PRIMARY KEY,
        document_id INTEGER,
        content TEXT,
        embedding BLOB,
        segment_type TEXT,
        position INTEGER,
        section_title TEXT,
        section_level INTEGER,
        section_path TEXT,
        parent_segment_id INTEGER,
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
        FOREIGN KEY (parent_segment_id) REFERENCES document_segments(id) ON DELETE SET NULL
    );

    -- Index for section navigation
    CREATE INDEX IF NOT EXISTS idx_segment_document ON document_segments(document_id);
    CREATE INDEX IF NOT EXISTS idx_segment_section ON document_segments(document_id, section_path);
    CREATE INDEX IF NOT EXISTS idx_segment_parent ON document_segments(document_id, parent_segment_id);

    -- Library documentation mapping
    CREATE TABLE IF NOT EXISTS libraries (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        version TEXT NOT NULL,
        doc_url TEXT NOT NULL,
        last_checked TIMESTAMP,
        is_available BOOLEAN,
        UNIQUE(name, version)
    );
    """
    )

    # Set up vector index if extension is loaded
    try:
        conn.execute(
            """
        CREATE VIRTUAL TABLE IF NOT EXISTS document_segments_vec USING vec(
            id INTEGER PRIMARY KEY,
            embedding BLOB,
            dims INTEGER,
            distance TEXT
        );
        """
        )
    except sqlite3.OperationalError:
        # Likely sqlite-vec not available
        logging.getLogger(__name__).debug(
            "Skipping creation of vector table; sqlite-vec unavailable"
        )

    conn.commit()
    conn.close()

    return True
