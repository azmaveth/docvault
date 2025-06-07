"""Input validation framework for DocVault.

This module provides comprehensive input validation to prevent security vulnerabilities
such as SQL injection, command injection, path traversal, and XSS.
"""

import re
from pathlib import Path
from typing import Any, List, Optional, Union
from urllib.parse import urlparse

from docvault.utils.path_security import PathSecurityError, validate_path


class ValidationError(Exception):
    """Raised when input validation fails."""

    pass


class Validators:
    """Collection of input validators for various data types."""

    # Regular expressions for common patterns
    SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9._-]+$")
    SQL_DANGEROUS_CHARS = re.compile(r"[;'\"\\]|--|/\*|\*/")
    SHELL_DANGEROUS_CHARS = re.compile(r'[;&|`$<>\\"\']')
    HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
    VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$")

    # Maximum lengths for various inputs
    MAX_QUERY_LENGTH = 1000
    MAX_IDENTIFIER_LENGTH = 100
    MAX_PATH_LENGTH = 4096
    MAX_TAG_LENGTH = 50
    MAX_CATEGORY_LENGTH = 50
    MAX_VERSION_LENGTH = 50

    @classmethod
    def validate_search_query(cls, query: str) -> str:
        """Validate a search query string.

        Args:
            query: The search query to validate

        Returns:
            The validated query

        Raises:
            ValidationError: If the query is invalid
        """
        if not query:
            raise ValidationError("Search query cannot be empty")

        if len(query) > cls.MAX_QUERY_LENGTH:
            raise ValidationError(
                f"Search query too long (max {cls.MAX_QUERY_LENGTH} chars)"
            )

        # Remove any HTML tags
        if cls.HTML_TAG_PATTERN.search(query):
            query = cls.HTML_TAG_PATTERN.sub("", query)

        # Check for SQL injection attempts
        if cls.SQL_DANGEROUS_CHARS.search(query):
            # Don't reveal what was detected
            raise ValidationError("Invalid characters in search query")

        return query.strip()

    @classmethod
    def validate_identifier(cls, identifier: str, name: str = "identifier") -> str:
        """Validate an identifier (e.g., tag name, category).

        Args:
            identifier: The identifier to validate
            name: Name of the field for error messages

        Returns:
            The validated identifier

        Raises:
            ValidationError: If the identifier is invalid
        """
        if not identifier:
            raise ValidationError(f"{name.capitalize()} cannot be empty")

        if len(identifier) > cls.MAX_IDENTIFIER_LENGTH:
            raise ValidationError(
                f"{name.capitalize()} too long (max {cls.MAX_IDENTIFIER_LENGTH} chars)"
            )

        # Allow alphanumeric, underscore, hyphen, and dot
        if not re.match(r"^[a-zA-Z0-9._-]+$", identifier):
            raise ValidationError(
                f"{name.capitalize()} can only contain letters, numbers, dots, "
                "underscores, and hyphens"
            )

        return identifier.strip()

    @classmethod
    def validate_tag(cls, tag: str) -> str:
        """Validate a tag name."""
        return cls.validate_identifier(tag, "tag")[: cls.MAX_TAG_LENGTH]

    @classmethod
    def validate_category(cls, category: str) -> str:
        """Validate a category name."""
        return cls.validate_identifier(category, "category")[: cls.MAX_CATEGORY_LENGTH]

    @classmethod
    def validate_document_id(cls, doc_id: str | int) -> int:
        """Validate a document ID.

        Args:
            doc_id: The document ID to validate

        Returns:
            The validated document ID as an integer

        Raises:
            ValidationError: If the ID is invalid
        """
        try:
            doc_id_int = int(doc_id)
            if doc_id_int <= 0:
                raise ValidationError("Document ID must be positive")
            return doc_id_int
        except (ValueError, TypeError):
            raise ValidationError("Invalid document ID format")

    @classmethod
    def validate_file_path(cls, path: str | Path) -> Path:
        """Validate a file path for security.

        Args:
            path: The file path to validate

        Returns:
            The validated path as a Path object

        Raises:
            ValidationError: If the path is invalid or insecure
        """
        try:
            # Use existing path security validation
            validated_path = validate_path(str(path))
            return Path(validated_path)
        except PathSecurityError as e:
            raise ValidationError(f"Invalid file path: {e}")

    @classmethod
    def validate_url(cls, url: str) -> str:
        """Validate a URL (basic validation, full SSRF protection in path_security).

        Args:
            url: The URL to validate

        Returns:
            The validated URL

        Raises:
            ValidationError: If the URL is invalid
        """
        if not url:
            raise ValidationError("URL cannot be empty")

        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                raise ValidationError("URL must include scheme (http/https)")
            if parsed.scheme not in ["http", "https"]:
                raise ValidationError("Only HTTP/HTTPS URLs are allowed")
            if not parsed.netloc:
                raise ValidationError("URL must include domain")
        except Exception as e:
            raise ValidationError(f"Invalid URL format: {e}")

        return url.strip()

    @classmethod
    def validate_command_argument(cls, arg: str, name: str = "argument") -> str:
        """Validate a command-line argument to prevent injection.

        Args:
            arg: The argument to validate
            name: Name of the argument for error messages

        Returns:
            The validated argument

        Raises:
            ValidationError: If the argument contains dangerous characters
        """
        if not arg:
            return arg

        # Check for shell metacharacters
        if cls.SHELL_DANGEROUS_CHARS.search(arg):
            raise ValidationError(f"{name.capitalize()} contains invalid characters")

        # Additional checks for common injection patterns
        dangerous_patterns = [
            "..",
            "~/",
            "./",
            "../",
            ".\\",
            "..\\",
            "\x00",
            "\n",
            "\r",
            "\t",
        ]

        for pattern in dangerous_patterns:
            if pattern in arg:
                raise ValidationError(f"{name.capitalize()} contains invalid sequence")

        return arg

    @classmethod
    def validate_version(cls, version: str) -> str:
        """Validate a version string.

        Args:
            version: The version string to validate

        Returns:
            The validated version

        Raises:
            ValidationError: If the version format is invalid
        """
        if not version:
            raise ValidationError("Version cannot be empty")

        if len(version) > cls.MAX_VERSION_LENGTH:
            raise ValidationError(
                f"Version too long (max {cls.MAX_VERSION_LENGTH} chars)"
            )

        # Allow semantic versioning and common formats
        if not cls.VERSION_PATTERN.match(version):
            # Also allow simple formats like "1.0", "v1.0", "latest"
            if not re.match(r"^(v?\d+(\.\d+)*|latest|stable|dev)$", version):
                raise ValidationError(
                    "Invalid version format. Use semantic versioning (1.2.3) or "
                    "common formats (1.0, v1.0, latest)"
                )

        return version.strip()

    @classmethod
    def validate_integer(
        cls,
        value: Any,
        name: str = "value",
        min_val: int | None = None,
        max_val: int | None = None,
    ) -> int:
        """Validate an integer value with optional bounds.

        Args:
            value: The value to validate
            name: Name of the field for error messages
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)

        Returns:
            The validated integer

        Raises:
            ValidationError: If the value is invalid
        """
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{name.capitalize()} must be an integer")

        if min_val is not None and int_value < min_val:
            raise ValidationError(f"{name.capitalize()} must be at least {min_val}")

        if max_val is not None and int_value > max_val:
            raise ValidationError(f"{name.capitalize()} must be at most {max_val}")

        return int_value

    @classmethod
    def validate_list_of(
        cls, items: list[Any], validator_func, name: str = "items"
    ) -> list[Any]:
        """Validate a list of items using a validator function.

        Args:
            items: List of items to validate
            validator_func: Function to validate each item
            name: Name of the list for error messages

        Returns:
            List of validated items

        Raises:
            ValidationError: If any item is invalid
        """
        if not isinstance(items, list):
            raise ValidationError(f"{name.capitalize()} must be a list")

        validated = []
        for i, item in enumerate(items):
            try:
                validated.append(validator_func(item))
            except ValidationError as e:
                raise ValidationError(f"{name.capitalize()}[{i}]: {e}")

        return validated

    @classmethod
    def sanitize_for_display(cls, text: str, max_length: int | None = None) -> str:
        """Sanitize text for safe display.

        Args:
            text: Text to sanitize
            max_length: Maximum length to allow

        Returns:
            Sanitized text safe for display
        """
        if not text:
            return ""

        # Remove any HTML tags
        text = cls.HTML_TAG_PATTERN.sub("", text)

        # Replace multiple whitespaces with single space
        text = " ".join(text.split())

        # Truncate if needed
        if max_length and len(text) > max_length:
            text = text[: max_length - 3] + "..."

        return text


def validate_search_input(
    query: str, tags: list[str] | None = None, limit: int | None = None
) -> dict:
    """Validate search command inputs.

    Args:
        query: Search query
        tags: Optional list of tags to filter by
        limit: Optional result limit

    Returns:
        Dictionary of validated inputs

    Raises:
        ValidationError: If any input is invalid
    """
    result = {
        "query": Validators.validate_search_query(query) if query else None,
        "tags": None,
        "limit": 10,  # default
    }

    if tags:
        result["tags"] = Validators.validate_list_of(
            tags, Validators.validate_tag, "tags"
        )

    if limit is not None:
        result["limit"] = Validators.validate_integer(
            limit, "limit", min_val=1, max_val=100
        )

    return result


def validate_document_operation(doc_id: str | int, operation: str = "access") -> int:
    """Validate inputs for document operations.

    Args:
        doc_id: Document ID
        operation: Type of operation (for error messages)

    Returns:
        Validated document ID

    Raises:
        ValidationError: If inputs are invalid
    """
    return Validators.validate_document_id(doc_id)


def validate_tag_operation(
    doc_id: str | int, tags: list[str], operation: str = "tag"
) -> tuple:
    """Validate inputs for tag operations.

    Args:
        doc_id: Document ID
        tags: List of tags
        operation: Type of operation (for error messages)

    Returns:
        Tuple of (validated_doc_id, validated_tags)

    Raises:
        ValidationError: If inputs are invalid
    """
    validated_id = Validators.validate_document_id(doc_id)
    validated_tags = Validators.validate_list_of(tags, Validators.validate_tag, "tags")

    if not validated_tags:
        raise ValidationError("At least one tag must be provided")

    return validated_id, validated_tags
