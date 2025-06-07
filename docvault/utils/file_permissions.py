"""File permission security utilities for DocVault.

This module ensures sensitive files have appropriate permissions to prevent
unauthorized access by other users on the system.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from docvault.utils.console import console


class PermissionError(Exception):
    """Raised when file permissions are insecure."""

    pass


class FilePermissionManager:
    """Manages secure file permissions for DocVault files."""

    # Recommended permissions for different file types
    PERMISSION_MAP = {
        "database": 0o600,  # rw-------
        "config": 0o600,  # rw-------
        "credentials": 0o600,  # rw-------
        "logs": 0o600,  # rw-------
        "directory": 0o700,  # rwx------
        "export": 0o644,  # rw-r--r--
    }

    @classmethod
    def check_permission(
        cls, file_path: Path, expected_mode: int
    ) -> tuple[bool, str | None]:
        """Check if a file has the expected permissions.

        Args:
            file_path: Path to check
            expected_mode: Expected permission mode (e.g., 0o600)

        Returns:
            (is_secure, error_message) - True if secure, False with message if not
        """
        if not file_path.exists():
            return True, None  # Non-existent files are not a security risk

        try:
            current_stat = file_path.stat()
            current_mode = current_stat.st_mode & 0o777  # Get permission bits only

            if current_mode != expected_mode:
                current_str = oct(current_mode)
                expected_str = oct(expected_mode)
                return (
                    False,
                    f"Insecure permissions {current_str} (expected {expected_str})",
                )

            return True, None

        except Exception as e:
            return False, f"Failed to check permissions: {e}"

    @classmethod
    def set_permission(cls, file_path: Path, mode: int) -> bool:
        """Set file permissions securely.

        Args:
            file_path: Path to secure
            mode: Permission mode to set

        Returns:
            True if successful
        """
        if not file_path.exists():
            return True

        try:
            # Only set permissions on Unix-like systems
            if os.name != "nt":
                os.chmod(file_path, mode)
            return True
        except Exception as e:
            console.print(f"[red]Failed to set permissions on {file_path}: {e}[/red]")
            return False

    @classmethod
    def secure_file(cls, file_path: Path, file_type: str = "config") -> bool:
        """Ensure a file has secure permissions.

        Args:
            file_path: Path to secure
            file_type: Type of file (database, config, credentials, logs, directory)

        Returns:
            True if file is secure or was secured
        """
        if os.name == "nt":
            # Windows doesn't have Unix-style permissions
            return True

        expected_mode = cls.PERMISSION_MAP.get(file_type, 0o600)
        is_secure, error = cls.check_permission(file_path, expected_mode)

        if not is_secure:
            console.print(f"[yellow]Warning: {file_path} has {error}[/yellow]")
            if cls.set_permission(file_path, expected_mode):
                console.print(
                    f"[green]Fixed: Set permissions to {oct(expected_mode)}[/green]"
                )
                return True
            return False

        return True

    @classmethod
    def audit_permissions(
        cls, base_dir: Path | None = None
    ) -> dict[str, list[tuple[Path, str]]]:
        """Audit all DocVault files for permission issues.

        Args:
            base_dir: Base directory to audit (defaults to DEFAULT_BASE_DIR)

        Returns:
            Dictionary mapping severity to list of (path, issue) tuples
        """
        from docvault import config

        if base_dir is None:
            base_dir = Path(config.DEFAULT_BASE_DIR)

        issues = {
            "critical": [],  # Database, credentials
            "high": [],  # Config files
            "medium": [],  # Log files
            "info": [],  # Other files
        }

        # Check database file
        db_path = Path(config.DB_PATH)
        if db_path.exists():
            is_secure, error = cls.check_permission(db_path, 0o600)
            if not is_secure:
                issues["critical"].append((db_path, error))

        # Check credentials files
        creds_dir = base_dir
        for pattern in [".credentials.key", ".credentials.enc"]:
            for cred_file in creds_dir.glob(pattern):
                is_secure, error = cls.check_permission(cred_file, 0o600)
                if not is_secure:
                    issues["critical"].append((cred_file, error))

        # Check .env file
        env_file = Path(".env")
        if env_file.exists():
            is_secure, error = cls.check_permission(env_file, 0o600)
            if not is_secure:
                issues["high"].append((env_file, error))

        # Check config directory
        is_secure, error = cls.check_permission(base_dir, 0o700)
        if not is_secure:
            issues["high"].append((base_dir, error))

        # Check log files
        log_dir = Path(config.LOG_DIR)
        if log_dir.exists():
            for log_file in log_dir.glob("*.log"):
                is_secure, error = cls.check_permission(log_file, 0o600)
                if not is_secure:
                    issues["medium"].append((log_file, error))

        return issues

    @classmethod
    def fix_all_permissions(cls, base_dir: Path | None = None) -> tuple[int, int]:
        """Fix permissions for all DocVault files.

        Args:
            base_dir: Base directory to fix (defaults to DEFAULT_BASE_DIR)

        Returns:
            (fixed_count, failed_count)
        """
        from docvault import config

        if base_dir is None:
            base_dir = Path(config.DEFAULT_BASE_DIR)

        fixed = 0
        failed = 0

        # Fix database
        db_path = Path(config.DB_PATH)
        if db_path.exists():
            if cls.secure_file(db_path, "database"):
                fixed += 1
            else:
                failed += 1

        # Fix credentials
        creds_dir = base_dir
        for pattern in [".credentials.key", ".credentials.enc"]:
            for cred_file in creds_dir.glob(pattern):
                if cls.secure_file(cred_file, "credentials"):
                    fixed += 1
                else:
                    failed += 1

        # Fix .env
        env_file = Path(".env")
        if env_file.exists():
            if cls.secure_file(env_file, "config"):
                fixed += 1
            else:
                failed += 1

        # Fix config directory
        if cls.secure_file(base_dir, "directory"):
            fixed += 1
        else:
            failed += 1

        # Fix logs
        log_dir = Path(config.LOG_DIR)
        if log_dir.exists():
            if cls.secure_file(log_dir, "directory"):
                fixed += 1
            else:
                failed += 1

            for log_file in log_dir.glob("*.log"):
                if cls.secure_file(log_file, "logs"):
                    fixed += 1
                else:
                    failed += 1

        return fixed, failed


def ensure_secure_permissions():
    """Ensure all sensitive files have secure permissions.

    This should be called during application initialization.
    """
    if os.name == "nt":
        # Windows doesn't have Unix-style permissions
        return

    from docvault import config

    # Secure critical files
    FilePermissionManager.secure_file(Path(config.DB_PATH), "database")
    FilePermissionManager.secure_file(Path(config.DEFAULT_BASE_DIR), "directory")

    # Secure .env if it exists
    env_file = Path(".env")
    if env_file.exists():
        FilePermissionManager.secure_file(env_file, "config")


def check_umask() -> int | None:
    """Check and optionally set a secure umask.

    Returns:
        Current umask value, or None on Windows
    """
    if os.name == "nt":
        return None

    # Get current umask (have to set it to read it, then restore)
    current_umask = os.umask(0o077)  # Temporarily set secure umask
    os.umask(current_umask)  # Restore original

    # Check if umask is secure (should mask group and other)
    if current_umask & 0o077 != 0o077:
        console.print(
            f"[yellow]Warning: Current umask {oct(current_umask)} may create files "
            f"with loose permissions. Consider setting umask 077.[/yellow]"
        )

    return current_umask
