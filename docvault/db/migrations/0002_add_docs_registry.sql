-- Migration to add documentation registry support

-- Add new table for documentation sources
CREATE TABLE IF NOT EXISTS documentation_sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,                   -- e.g., 'Python', 'Elixir', 'Node.js'
    package_manager TEXT,                -- e.g., 'pypi', 'hex', 'npm'
    base_url TEXT,                       -- Base URL for documentation
    version_url_template TEXT,            -- Template URL with {version} placeholder
    latest_version_url TEXT,              -- URL to fetch latest version
    is_active BOOLEAN DEFAULT TRUE,
    last_checked TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, package_manager)
);

-- Enhance libraries table with more metadata
ALTER TABLE libraries ADD COLUMN source_id INTEGER REFERENCES documentation_sources(id);
ALTER TABLE libraries ADD COLUMN package_name TEXT;  -- Original package name in the registry
ALTER TABLE libraries ADD COLUMN latest_version TEXT; -- Track latest available version
ALTER TABLE libraries ADD COLUMN description TEXT;    -- Package description
ALTER TABLE libraries ADD COLUMN homepage_url TEXT;   -- Project homepage
ALTER TABLE libraries ADD COLUMN repository_url TEXT; -- Source code repository
ALTER TABLE libraries ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE libraries ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_libraries_source ON libraries(source_id);
CREATE INDEX IF NOT EXISTS idx_libraries_package ON libraries(package_name);

-- Add triggers for updated_at
CREATE TRIGGER IF NOT EXISTS update_documentation_sources_updated_at
AFTER UPDATE ON documentation_sources
FOR EACH ROW
BEGIN
    UPDATE documentation_sources SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_libraries_updated_at
AFTER UPDATE ON libraries
FOR EACH ROW
BEGIN
    UPDATE libraries SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
