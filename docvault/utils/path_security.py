"""
Path security utilities to prevent path traversal attacks.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Union
from urllib.parse import urlparse

from docvault.core.exceptions import PathSecurityError

logger = logging.getLogger(__name__)


def validate_path(
    path: str | Path,
    allowed_base_paths: list[str | Path] | None = None,
    allow_absolute: bool = False,
) -> Path:
    """
    Validate a path to prevent path traversal attacks.

    Args:
        path: The path to validate
        allowed_base_paths: List of allowed base directories. If provided, the resolved
                           path must be within one of these directories.
        allow_absolute: Whether to allow absolute paths. Default is False.

    Returns:
        Path: The validated, resolved path

    Raises:
        PathSecurityError: If the path contains security violations
    """
    # Convert to Path object
    path_obj = Path(path)

    # Check for null bytes (security issue)
    if "\0" in str(path):
        raise PathSecurityError("Path contains null bytes")

    # Check for path traversal attempts
    path_str = str(path)

    # Check specific dangerous patterns
    if ".." in path_obj.parts:
        raise PathSecurityError("Path traversal detected: contains ..")

    # Also check the raw string for traversal patterns
    if ".." in path_str:
        raise PathSecurityError("Path traversal detected: contains ..")

    # Check for home directory expansion at start
    if path_str.startswith("~"):
        raise PathSecurityError("Path contains home directory reference")

    # Check for environment variable patterns
    if "$" in path_str and (
        path_str.startswith("$") or "/$" in path_str or "\\$" in path_str
    ):
        raise PathSecurityError("Path contains environment variable reference")

    # Windows-specific checks
    if os.name == "nt" and "%" in path_str:
        raise PathSecurityError("Path contains Windows environment variable reference")

    # Check if absolute path when not allowed
    if path_obj.is_absolute() and not allow_absolute:
        raise PathSecurityError("Absolute paths are not allowed")

    # Resolve the path (follows symlinks and resolves ..)
    try:
        # If path doesn't exist, we can't use resolve() with strict=True
        if path_obj.exists():
            resolved_path = path_obj.resolve(strict=True)
        else:
            # For non-existent paths, resolve without strict to normalize the path
            resolved_path = path_obj.resolve(strict=False)
    except (OSError, RuntimeError) as e:
        logger.error(f"Error resolving path {path}: {e}")
        raise PathSecurityError(f"Cannot resolve path: {e}")

    # If allowed base paths are specified, ensure resolved path is within them
    if allowed_base_paths:
        is_allowed = False
        for base_path in allowed_base_paths:
            base_path_obj = Path(base_path).resolve()
            try:
                # Check if resolved_path is relative to base_path
                resolved_path.relative_to(base_path_obj)
                is_allowed = True
                break
            except ValueError:
                # Not relative to this base path
                continue

        if not is_allowed:
            # Log the actual paths for debugging
            logger.warning(
                f"Path {resolved_path} is not within allowed base paths: {[Path(p).resolve() for p in allowed_base_paths]}"
            )
            raise PathSecurityError("Path is not under any allowed base path")

    return resolved_path


def validate_filename(filename: str) -> str:
    """
    Validate a filename to ensure it's safe.

    Args:
        filename: The filename to validate

    Returns:
        str: The validated filename

    Raises:
        PathSecurityError: If the filename is invalid
    """
    if not filename:
        raise PathSecurityError("Filename cannot be empty")

    # Check for null bytes
    if "\0" in filename:
        raise PathSecurityError("Filename contains null bytes")

    # Check for special names
    if filename in [".", ".."]:
        raise PathSecurityError("Invalid filename")

    # Check for path separators (should be just a filename)
    if any(sep in filename for sep in ["/", "\\"]):
        raise PathSecurityError("Filename cannot contain path separators")

    # Check for drive letter patterns (e.g., C:)
    if len(filename) >= 2 and filename[1] == ":":
        raise PathSecurityError("Filename cannot contain drive letters")

    # Check for reserved filenames (Windows compatibility)
    reserved_names = [
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    ]
    base_name = filename.split(".")[0].upper()
    if base_name in reserved_names:
        raise PathSecurityError(f"Reserved filename: {filename}")

    # Check for dangerous characters
    dangerous_chars = ["<", ">", ":", '"', "|", "?", "*"]
    if any(char in filename for char in dangerous_chars):
        raise PathSecurityError("Filename contains invalid characters")

    # Check for leading/trailing dots or spaces (can be problematic)
    if filename.startswith(".") or filename.endswith("."):
        raise PathSecurityError("Filename cannot start or end with a dot")
    if filename.startswith(" ") or filename.endswith(" "):
        raise PathSecurityError("Filename cannot start or end with a space")

    # Check filename length
    if len(filename) > 255:
        raise PathSecurityError("Filename too long (max 255 characters)")

    return filename


def validate_url_path(
    url: str,
    allowed_domains: list[str] | None = None,
    blocked_domains: list[str] | None = None,
) -> str:
    """
    Validate a URL to ensure it's safe to fetch.

    Args:
        url: The URL to validate
        allowed_domains: Optional list of allowed domains (whitelist)
        blocked_domains: Optional list of blocked domains (blacklist)

    Returns:
        str: The validated URL

    Raises:
        PathSecurityError: If the URL is invalid or potentially dangerous
    """
    # Check URL length
    if len(url) > 2048:
        raise PathSecurityError("URL too long (max 2048 characters)")

    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise PathSecurityError(f"Invalid URL format: {e}")

    # Check scheme
    allowed_schemes = ["http", "https"]
    if parsed.scheme not in allowed_schemes:
        raise PathSecurityError(f"URL scheme must be one of: {allowed_schemes}")

    # Check for localhost/private IPs (SSRF prevention)
    hostname = parsed.hostname
    if hostname:
        # Normalize hostname to lowercase
        hostname_lower = hostname.lower()

        # Check for localhost (unless in test mode)
        if hostname_lower in ["localhost", "127.0.0.1", "::1", "0.0.0.0"]:
            if not os.getenv("DOCVAULT_ALLOW_LOCALHOST"):
                raise PathSecurityError("Cannot fetch from localhost")

        # Check for metadata service endpoints (cloud SSRF)
        metadata_hosts = [
            "169.254.169.254",  # AWS/Azure/GCP metadata
            "metadata.google.internal",  # GCP metadata
            "metadata.azure.com",  # Azure metadata
        ]
        if hostname_lower in metadata_hosts:
            raise PathSecurityError("Cannot fetch from cloud metadata services")

        # Check for private IP ranges
        try:
            import ipaddress

            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise PathSecurityError("Cannot fetch from private IP addresses")

            # Check for reserved IP ranges
            if ip.is_reserved or ip.is_multicast:
                raise PathSecurityError("Cannot fetch from reserved IP addresses")
        except ValueError:
            # Not an IP address, it's a domain name
            pass

        # Domain allowlist/blocklist checking
        if allowed_domains:
            # Check if hostname matches any allowed domain
            domain_allowed = False
            for allowed_domain in allowed_domains:
                allowed_lower = allowed_domain.lower()
                if hostname_lower == allowed_lower or hostname_lower.endswith(
                    "." + allowed_lower
                ):
                    domain_allowed = True
                    break
            if not domain_allowed:
                raise PathSecurityError(f"Domain {hostname} is not in the allowed list")

        if blocked_domains:
            # Check if hostname matches any blocked domain
            for blocked_domain in blocked_domains:
                blocked_lower = blocked_domain.lower()
                if hostname_lower == blocked_lower or hostname_lower.endswith(
                    "." + blocked_lower
                ):
                    raise PathSecurityError(f"Domain {hostname} is blocked")

    # Check for empty hostname
    if not hostname:
        raise PathSecurityError("URL must have a valid hostname")

    # Additional validation for malformed URLs
    if parsed.scheme and not parsed.netloc:
        raise PathSecurityError("URL must have a valid netloc/hostname")

    # Check for some other malformed patterns
    if parsed.scheme == "" and parsed.netloc == "":
        raise PathSecurityError("Invalid URL format")

    # Check for double dots in hostname
    if hostname and ".." in hostname:
        raise PathSecurityError("Invalid hostname format")

    # Check for suspicious port numbers
    if parsed.port:
        # Block common internal service ports
        blocked_ports = [
            22,
            23,
            25,
            110,
            135,
            139,
            445,
            3389,
        ]  # SSH, Telnet, SMTP, POP3, RPC, SMB, RDP
        if parsed.port in blocked_ports:
            raise PathSecurityError(f"Port {parsed.port} is not allowed")

    return url


def get_safe_path(
    base_dir: str | Path, user_path: str, create_dirs: bool = False
) -> Path:
    """
    Safely join a user-provided path with a base directory.

    Args:
        base_dir: The base directory
        user_path: The user-provided path component
        create_dirs: Whether to create parent directories if they don't exist

    Returns:
        Path: The safe, resolved path

    Raises:
        PathSecurityError: If the resulting path would be outside base_dir
    """
    base_path = Path(base_dir).resolve()

    # Remove any leading slashes from user path to prevent absolute paths
    user_path = user_path.lstrip("/\\")

    # Use safe join
    target_path = base_path / user_path

    # Validate the result
    validated_path = validate_path(
        target_path, allowed_base_paths=[base_path], allow_absolute=True
    )

    # Create directories if requested
    if create_dirs:
        validated_path.parent.mkdir(parents=True, exist_ok=True)

    return validated_path


def is_safe_archive_member(member_name: str) -> bool:
    """
    Check if an archive member name is safe to extract.

    Args:
        member_name: The name of the archive member

    Returns:
        bool: True if safe, False otherwise
    """
    # Empty or special directory names
    if not member_name or member_name in [".", ".."]:
        return False

    # Check for null bytes
    if "\0" in member_name:
        return False

    # Check for absolute paths
    if member_name.startswith("/") or member_name.startswith("\\"):
        return False

    # Check for drive letters (Windows)
    if len(member_name) > 1 and member_name[1] == ":":
        return False

    # Check for parent directory references
    if ".." in member_name or "/../" in member_name or "\\..\\" in member_name:
        return False

    # Check for home directory
    if member_name.startswith("~"):
        return False

    return True
