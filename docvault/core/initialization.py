"""Initialization utilities for DocVault"""

from pathlib import Path


def ensure_app_initialized():
    """Ensure application is properly initialized"""
    from docvault import config

    # Create necessary directories
    Path(config.DEFAULT_BASE_DIR).mkdir(parents=True, exist_ok=True)
    Path(config.STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    Path(config.LOG_DIR).mkdir(parents=True, exist_ok=True)
    # Auto-initialize database (creates tables and vector index)
    from docvault.db.schema import initialize_database

    initialize_database()
