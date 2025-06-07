"""
Migration to add llms.txt support to DocVault.
"""

MIGRATION_SQL = """
-- Add llms_txt_metadata table
CREATE TABLE IF NOT EXISTS llms_txt_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    llms_title TEXT,
    llms_summary TEXT,
    llms_introduction TEXT,
    llms_sections TEXT,  -- JSON string of sections and resources
    has_llms_txt BOOLEAN DEFAULT 0,
    llms_txt_url TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Add llms_txt_resources table for searchable resources
CREATE TABLE IF NOT EXISTS llms_txt_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    section TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT,
    is_optional BOOLEAN DEFAULT 0,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Add indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_llms_txt_metadata_document
    ON llms_txt_metadata(document_id);
CREATE INDEX IF NOT EXISTS idx_llms_txt_resources_document
    ON llms_txt_resources(document_id);
CREATE INDEX IF NOT EXISTS idx_llms_txt_resources_section
    ON llms_txt_resources(section);

-- Add llms.txt related columns to documents table
ALTER TABLE documents ADD COLUMN has_llms_txt BOOLEAN DEFAULT 0;
ALTER TABLE documents ADD COLUMN llms_txt_url TEXT;
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Execute migration SQL
    for statement in MIGRATION_SQL.strip().split(";"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)

    db.commit()


def downgrade(db):
    """Rollback the migration."""
    cursor = db.cursor()

    # Drop new tables
    cursor.execute("DROP TABLE IF EXISTS llms_txt_resources")
    cursor.execute("DROP TABLE IF EXISTS llms_txt_metadata")

    # Note: SQLite doesn't support DROP COLUMN, so we'd need to:
    # 1. Create a new table without the columns
    # 2. Copy data
    # 3. Drop old table
    # 4. Rename new table
    # For now, we'll leave the columns as they don't harm anything

    db.commit()
