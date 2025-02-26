import sqlite3
import pathlib
from docvault import config

def initialize_database():
    """Initialize the SQLite database with sqlite-vec extension"""
    # Ensure directory exists
    db_path = pathlib.Path(config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(config.DB_PATH)
    
    # Load sqlite-vec extension
    try:
        conn.enable_load_extension(True)
        conn.load_extension("sqlite_vec")
    except sqlite3.OperationalError:
        print("⚠️  Warning: sqlite-vec extension not found")
        print("Please install sqlite-vec: https://github.com/asg017/sqlite-vec")
        print("Database created without vector search capability")
    
    conn.executescript("""
    -- Documents table
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY,
        url TEXT NOT NULL,
        title TEXT,
        html_path TEXT,
        markdown_path TEXT,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        library_id INTEGER,
        is_library_doc BOOLEAN DEFAULT FALSE
    );

    -- Document segments for more granular search
    CREATE TABLE IF NOT EXISTS document_segments (
        id INTEGER PRIMARY KEY,
        document_id INTEGER,
        content TEXT,
        embedding BLOB,
        segment_type TEXT,
        position INTEGER,
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
    );

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
    """)
    
    # Set up vector index if extension is loaded
    try:
        conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS document_segments_vec USING vec(
            id INTEGER PRIMARY KEY,
            embedding BLOB,
            dims INTEGER,
            distance TEXT
        );
        """)
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()
    
    return True
