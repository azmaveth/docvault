import sqlite3
import datetime
from typing import List, Dict, Any, Optional
from docvault import config

def get_connection():
    """Get a connection to the SQLite database"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Enable loading extensions if sqlite-vec is available
    extension_loaded = False
    try:
        conn.enable_load_extension(True)
        conn.load_extension("sqlite_vec")
        extension_loaded = True
    except sqlite3.OperationalError:
        try:
            # Try to import the Python package which might register the extension
            import sqlite_vec
            extension_loaded = True
        except ImportError:
            pass
        
    return conn

def add_document(url: str, title: str, html_path: str, markdown_path: str, 
                library_id: Optional[int] = None, 
                is_library_doc: bool = False) -> int:
    """Add a document to the database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO documents 
    (url, title, html_path, markdown_path, library_id, is_library_doc, scraped_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (url, title, str(html_path), str(markdown_path), 
          library_id, is_library_doc, datetime.datetime.now()))
    
    document_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return document_id

def get_document(document_id: int) -> Optional[Dict[str, Any]]:
    """Get a document by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return dict(row)
    return None

def get_document_by_url(url: str) -> Optional[Dict[str, Any]]:
    """Get a document by URL"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM documents WHERE url = ?", (url,))
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return dict(row)
    return None

def add_document_segment(document_id: int, content: str, 
                        embedding: bytes = None, 
                        segment_type: str = "text", 
                        position: int = 0) -> int:
    """Add a segment to a document"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO document_segments 
    (document_id, content, embedding, segment_type, position)
    VALUES (?, ?, ?, ?, ?)
    """, (document_id, content, embedding, segment_type, position))
    
    segment_id = cursor.lastrowid
    
    # Add to vector index if embedding is provided
    if embedding is not None:
        try:
            dims = len(embedding) // 4  # Assuming float32 (4 bytes per dimension)
            cursor.execute("""
            INSERT INTO document_segments_vec (id, embedding, dims, distance)
            VALUES (?, ?, ?, ?)
            """, (segment_id, embedding, dims, "cosine"))
        except sqlite3.OperationalError:
            # Vector table might not exist if extension isn't loaded
            pass
    
    conn.commit()
    conn.close()
    
    return segment_id

def search_segments(embedding: bytes, limit: int = 5) -> List[Dict[str, Any]]:
    """Search for similar document segments"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Search using vector similarity
        cursor.execute("""
        SELECT s.id, s.document_id, s.content, s.segment_type, d.title, d.url,
               vec_cosine_similarity(v.embedding, ?) AS score
        FROM document_segments_vec v
        JOIN document_segments s ON v.id = s.id
        JOIN documents d ON s.document_id = d.id
        ORDER BY score DESC
        LIMIT ?
        """, (embedding, limit))
        
        rows = cursor.fetchall()
        
    except sqlite3.OperationalError:
        # Fallback to text search if vector extension is not available
        cursor.execute("""
        SELECT s.id, s.document_id, s.content, s.segment_type, d.title, d.url,
               0 AS score
        FROM document_segments s
        JOIN documents d ON s.document_id = d.id
        LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
    
    conn.close()
    
    return [dict(row) for row in rows]

def list_documents(limit: int = 20, offset: int = 0, 
                  filter_text: Optional[str] = None) -> List[Dict[str, Any]]:
    """List documents with optional filtering"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM documents"
    params = []
    
    if filter_text:
        query += " WHERE title LIKE ? OR url LIKE ?"
        params.extend([f"%{filter_text}%", f"%{filter_text}%"])
    
    query += " ORDER BY scraped_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    conn.close()
    
    return [dict(row) for row in rows]

def add_library(name: str, version: str, doc_url: str) -> int:
    """Add a library to the database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT OR REPLACE INTO libraries 
    (name, version, doc_url, last_checked, is_available)
    VALUES (?, ?, ?, ?, ?)
    """, (name, version, doc_url, datetime.datetime.now(), True))
    
    library_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return library_id

def get_library(name: str, version: str) -> Optional[Dict[str, Any]]:
    """Get a library by name and version"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT * FROM libraries 
    WHERE name = ? AND version = ?
    """, (name, version))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def get_library_documents(library_id: int) -> List[Dict[str, Any]]:
    """Get all documents for a library"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT * FROM documents 
    WHERE library_id = ?
    """, (library_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]
