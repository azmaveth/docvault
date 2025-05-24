#!/usr/bin/env python3
"""Apply database migrations."""
import os
import sqlite3
from pathlib import Path


def get_migration_files(migration_dir):
    """Get migration files in order."""
    migration_files = []
    for f in os.listdir(migration_dir):
        if f.endswith(".sql") and f.startswith("000"):
            migration_files.append(f)
    return sorted(migration_files)


def apply_migration(conn, migration_file):
    """Apply a single migration file."""
    print(f"Applying migration: {migration_file}")
    with open(migration_file, "r") as f:
        sql = f.read()

    try:
        conn.executescript(sql)
        conn.commit()
        print(f"Successfully applied {migration_file}")
    except sqlite3.Error as e:
        print(f"Error applying {migration_file}: {e}")
        raise


def main():
    """Apply all pending migrations."""
    from docvault import config

    # Ensure database directory exists
    db_path = Path(config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect to the database
    conn = sqlite3.connect(str(db_path))

    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON;")

    # Create migrations table if it doesn't exist
    conn.execute(
        """
    CREATE TABLE IF NOT EXISTS migrations (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    # Get applied migrations
    applied_migrations = set()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM migrations")
    for row in cursor.fetchall():
        applied_migrations.add(row[0])

    # Get all migration files
    migration_dir = os.path.dirname(__file__)
    migration_files = get_migration_files(migration_dir)

    # Apply pending migrations
    for migration_file in migration_files:
        if migration_file not in applied_migrations:
            migration_path = os.path.join(migration_dir, migration_file)
            apply_migration(conn, migration_path)

            # Record the migration
            cursor.execute(
                "INSERT INTO migrations (name) VALUES (?)", (migration_file,)
            )
            conn.commit()

    conn.close()
    print("All migrations applied successfully")


if __name__ == "__main__":
    main()
