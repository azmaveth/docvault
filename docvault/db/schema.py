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

    -- Documentation sources table
    CREATE TABLE IF NOT EXISTS documentation_sources (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        package_manager TEXT,
        base_url TEXT,
        version_url_template TEXT,
        latest_version_url TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        last_checked TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(name, package_manager)
    );

    -- Add index for documentation sources
    CREATE INDEX IF NOT EXISTS idx_sources_package_manager ON documentation_sources(package_manager);
    CREATE INDEX IF NOT EXISTS idx_sources_active ON documentation_sources(is_active);
    """
    )

    # Set up vector index if extension is loaded
    try:
        conn.execute(
            """
        CREATE VIRTUAL TABLE IF NOT EXISTS document_segments_vec USING vec0(
            embedding float[768] distance=cosine
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

    # Run migrations to ensure schema is up to date
    from docvault.db.migrations.migrations import migrate_schema

    migrate_schema()

    # Populate default documentation sources if they don't exist
    _populate_default_sources()

    return True


def _populate_default_sources():
    """Populate default documentation sources if they don't exist."""
    from docvault.models.registry import (
        add_documentation_source,
        list_documentation_sources,
    )

    # Check if we already have sources
    existing_sources = list_documentation_sources(active_only=False)
    if existing_sources:
        # Already have sources, don't override
        return

    # Default documentation sources
    default_sources = [
        {
            "name": "Python",
            "package_manager": "pypi",
            "base_url": "https://pypi.org/project/{package}/",
            "version_url_template": "https://pypi.org/project/{package}/{version}/",
            "latest_version_url": "https://pypi.org/pypi/{package}/json",
        },
        {
            "name": "Node.js",
            "package_manager": "npm",
            "base_url": "https://www.npmjs.com/package/{package}",
            "version_url_template": "https://www.npmjs.com/package/{package}/v/{version}",
            "latest_version_url": "https://registry.npmjs.org/{package}/latest",
        },
        {
            "name": "RubyGems",
            "package_manager": "gem",
            "base_url": "https://rubygems.org/gems/{package}",
            "version_url_template": "https://rubygems.org/gems/{package}/versions/{version}",
            "latest_version_url": "https://rubygems.org/api/v1/versions/{package}/latest.json",
        },
        {
            "name": "Hex",
            "package_manager": "hex",
            "base_url": "https://hex.pm/packages/{package}",
            "version_url_template": "https://hex.pm/packages/{package}/{version}",
            "latest_version_url": "https://hex.pm/api/packages/{package}",
        },
        {
            "name": "Go Modules",
            "package_manager": "go",
            "base_url": "https://pkg.go.dev/{package}",
            "version_url_template": "https://pkg.go.dev/{package}@v{version}",
            "latest_version_url": "https://proxy.golang.org/{package}/@latest",
        },
        {
            "name": "Crates.io",
            "package_manager": "cargo",
            "base_url": "https://crates.io/crates/{package}",
            "version_url_template": "https://docs.rs/crate/{package}/{version}",
            "latest_version_url": "https://crates.io/api/v1/crates/{package}",
        },
    ]

    # Add default sources
    for source in default_sources:
        try:
            add_documentation_source(**source)
            logging.getLogger(__name__).info(
                f"Added default documentation source: {source['name']}"
            )
        except Exception as e:
            # Log but don't fail initialization
            logging.getLogger(__name__).warning(
                f"Failed to add default source {source['name']}: {e}"
            )
