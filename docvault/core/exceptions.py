"""Custom exceptions for DocVault."""


class DocVaultError(Exception):
    """Base exception for all DocVault errors."""

    pass


class LibraryNotFoundError(DocVaultError):
    """Raised when a library is not found in the documentation sources."""

    pass


class VersionNotFoundError(DocVaultError):
    """Raised when a specific version of a library is not found."""

    pass


class DocumentNotFoundError(DocVaultError):
    """Raised when a document is not found in the vault."""

    pass


class InvalidDocumentError(DocVaultError):
    """Raised when a document is invalid or malformed."""

    pass


class DatabaseError(DocVaultError):
    """Raised for database-related errors."""

    pass


class NetworkError(DocVaultError):
    """Raised for network-related errors during document fetching."""

    pass


class ConfigurationError(DocVaultError):
    """Raised for configuration-related errors."""

    pass
