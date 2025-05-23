"""Database components for DocVault"""

import logging

from docvault.db.migrations.migrations import get_document_sections, migrate_schema
from docvault.db.operations import (
    add_document,
    add_document_segment,
    add_library,
    delete_document,
    get_document,
    get_document_by_url,
    get_latest_library_version,
    get_library,
    get_library_documents,
    list_documents,
    search_segments,
    update_document_by_url,
)

# Initialize logger
logger = logging.getLogger(__name__)


# Run migrations when the module is imported
def initialize_database() -> None:
    """Initialize the database by running migrations."""
    try:
        if migrate_schema():
            logger.info("Database schema is up to date")
        else:
            logger.error("Failed to run database migrations")
    except Exception as e:
        logger.error(f"Error running database migrations: {e}")


# Run database initialization when the module is imported
initialize_database()

__all__ = [
    "add_document",
    "add_document_segment",
    "add_library",
    "delete_document",
    "get_document",
    "get_document_by_url",
    "get_document_sections",
    "get_latest_library_version",
    "get_library",
    "get_library_documents",
    "initialize_database",
    "list_documents",
    "migrate_schema",
    "search_segments",
    "update_document_by_url",
]
