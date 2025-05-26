"""Initialization utilities for DocVault"""

import os
from pathlib import Path


def ensure_app_initialized():
    """Ensure application is properly initialized"""
    from docvault import config
    from docvault.utils.file_permissions import check_umask, ensure_secure_permissions

    # Check umask for security
    check_umask()

    # Create necessary directories with secure permissions
    for directory in [config.DEFAULT_BASE_DIR, config.STORAGE_PATH, config.LOG_DIR]:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        # Set secure permissions on directories (700)
        if os.name != "nt":
            os.chmod(path, 0o700)

    # Auto-initialize database (creates tables and vector index)
    from docvault.db.schema import initialize_database

    initialize_database()

    # Ensure all files have secure permissions
    ensure_secure_permissions()
