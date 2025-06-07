"""
Migration to add contextual retrieval support.

This migration adds columns and tables needed for storing contextual information
alongside document chunks to improve retrieval accuracy.
"""


def upgrade(conn):
    """Add contextual retrieval support."""
    cursor = conn.cursor()

    # Add contextual columns to document_segments table
    cursor.execute(
        """
        ALTER TABLE document_segments
        ADD COLUMN context_description TEXT
    """
    )

    cursor.execute(
        """
        ALTER TABLE document_segments
        ADD COLUMN context_metadata JSON
    """
    )

    cursor.execute(
        """
        ALTER TABLE document_segments
        ADD COLUMN context_embedding BLOB
    """
    )

    cursor.execute(
        """
        ALTER TABLE document_segments
        ADD COLUMN context_generated_at TIMESTAMP
    """
    )

    cursor.execute(
        """
        ALTER TABLE document_segments
        ADD COLUMN context_model TEXT
    """
    )

    # Create table for chunk relationships discovered through context
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chunk_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_segment_id INTEGER NOT NULL,
            target_segment_id INTEGER NOT NULL,
            relationship_type TEXT NOT NULL,
            confidence REAL DEFAULT 0.0,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_segment_id) REFERENCES document_segments(id),
            FOREIGN KEY (target_segment_id) REFERENCES document_segments(id)
        )
    """
    )

    # Create indices for efficient queries
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chunk_rel_source
        ON chunk_relationships(source_segment_id)
    """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chunk_rel_target
        ON chunk_relationships(target_segment_id)
    """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chunk_rel_type
        ON chunk_relationships(relationship_type)
    """
    )

    # Create table for context generation templates
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS context_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            template TEXT NOT NULL,
            doc_type TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Insert default context generation templates
    default_templates = [
        (
            "general",
            """<document>
{{WHOLE_DOCUMENT}}
</document>
Here is the chunk we want to situate within the whole document:
<chunk>
{{CHUNK_CONTENT}}
</chunk>
Please give a short succinct context to situate this chunk within the overall document.
Focus on: 1) What section this is from, 2) What the main topic is, 3) How it
relates to the document's purpose.""",
            None,
        ),
        (
            "code_documentation",
            """<document>
{{WHOLE_DOCUMENT}}
</document>
This chunk contains code documentation:
<chunk>
{{CHUNK_CONTENT}}
</chunk>
Please provide context including: 1) What function/class/module this documents,
2) What functionality it provides, 3) Its relationship to other components,
4) Any important parameters or return values mentioned.""",
            "code",
        ),
        (
            "api_reference",
            """<document>
{{WHOLE_DOCUMENT}}
</document>
This chunk is from API reference documentation:
<chunk>
{{CHUNK_CONTENT}}
</chunk>
Provide context about: 1) Which API endpoint or method this describes,
2) What operations it performs, 3) Required parameters or authentication,
4) Related endpoints or methods in the same API.""",
            "api",
        ),
        (
            "tutorial",
            """<document>
{{WHOLE_DOCUMENT}}
</document>
This chunk is from a tutorial or guide:
<chunk>
{{CHUNK_CONTENT}}
</chunk>
Explain: 1) What step or concept this chunk covers, 2) Prerequisites from earlier
sections, 3) What the reader should understand after this section, 4) How it fits
in the tutorial sequence.""",
            "tutorial",
        ),
    ]

    for name, template, doc_type in default_templates:
        cursor.execute(
            """
            INSERT OR IGNORE INTO context_templates (name, template, doc_type)
            VALUES (?, ?, ?)
        """,
            (name, template, doc_type),
        )

    # Create config table if it doesn't exist
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT
        )
    """
    )

    # Add configuration for contextual retrieval
    cursor.execute(
        """
        INSERT OR IGNORE INTO config (key, value, description)
        VALUES
        ('contextual_retrieval_enabled', 'false',
         'Enable contextual retrieval for new documents'),
        ('context_llm_provider', 'ollama',
         'LLM provider for context generation (ollama, openai, anthropic)'),
        ('context_llm_model', 'llama2', 'Model to use for context generation'),
        ('context_batch_size', '10', 'Number of chunks to process in one LLM call'),
        ('context_max_tokens', '150', 'Maximum tokens for context description'),
        ('context_cache_enabled', 'true',
         'Cache generated contexts to avoid regeneration')
    """
    )

    conn.commit()


def downgrade(conn):
    """Remove contextual retrieval support."""
    cursor = conn.cursor()

    # Remove tables
    cursor.execute("DROP TABLE IF EXISTS chunk_relationships")
    cursor.execute("DROP TABLE IF EXISTS context_templates")

    # Note: We cannot remove columns from document_segments in SQLite
    # They will remain but unused if downgraded

    # Remove config entries
    cursor.execute(
        """
        DELETE FROM config WHERE key IN (
            'contextual_retrieval_enabled',
            'context_llm_provider',
            'context_llm_model',
            'context_batch_size',
            'context_max_tokens',
            'context_cache_enabled'
        )
    """
    )

    conn.commit()
