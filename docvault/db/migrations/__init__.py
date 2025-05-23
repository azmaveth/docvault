"""
Database migrations for DocVault.

This package contains database migrations that are applied automatically
when the application starts.
"""

# This file makes the migrations directory a Python package

# Export migration functions
from .migrations import get_document_sections, migrate_schema

__all__ = [
    "migrate_schema",
    "get_document_sections",
]
