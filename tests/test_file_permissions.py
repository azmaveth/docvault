"""Tests for file permission security module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from docvault.utils.file_permissions import (
    FilePermissionManager,
    check_umask,
    ensure_secure_permissions,
)


class TestFilePermissionManager:
    """Test file permission management."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.skipif(
        os.name == "nt", reason="Unix permissions not applicable on Windows"
    )
    def test_check_permission_secure(self, temp_dir):
        """Test checking secure file permissions."""
        test_file = temp_dir / "test.db"
        test_file.touch()
        os.chmod(test_file, 0o600)

        is_secure, error = FilePermissionManager.check_permission(test_file, 0o600)
        assert is_secure is True
        assert error is None

    @pytest.mark.skipif(
        os.name == "nt", reason="Unix permissions not applicable on Windows"
    )
    def test_check_permission_insecure(self, temp_dir):
        """Test detecting insecure file permissions."""
        test_file = temp_dir / "test.db"
        test_file.touch()
        os.chmod(test_file, 0o644)  # World-readable

        is_secure, error = FilePermissionManager.check_permission(test_file, 0o600)
        assert is_secure is False
        assert "Insecure permissions" in error
        assert "0o644" in error
        assert "0o600" in error

    def test_check_permission_nonexistent(self, temp_dir):
        """Test checking permissions on non-existent file."""
        test_file = temp_dir / "nonexistent.db"

        is_secure, error = FilePermissionManager.check_permission(test_file, 0o600)
        assert is_secure is True  # Non-existent files are not a security risk
        assert error is None

    @pytest.mark.skipif(
        os.name == "nt", reason="Unix permissions not applicable on Windows"
    )
    def test_set_permission(self, temp_dir):
        """Test setting file permissions."""
        test_file = temp_dir / "test.db"
        test_file.touch()
        os.chmod(test_file, 0o644)

        # Set secure permissions
        result = FilePermissionManager.set_permission(test_file, 0o600)
        assert result is True

        # Verify permissions were changed
        current_mode = test_file.stat().st_mode & 0o777
        assert current_mode == 0o600

    @pytest.mark.skipif(
        os.name == "nt", reason="Unix permissions not applicable on Windows"
    )
    def test_secure_file(self, temp_dir):
        """Test securing a file with wrong permissions."""
        test_file = temp_dir / "test.db"
        test_file.touch()
        os.chmod(test_file, 0o644)

        # Secure the file
        result = FilePermissionManager.secure_file(test_file, "database")
        assert result is True

        # Verify permissions
        current_mode = test_file.stat().st_mode & 0o777
        assert current_mode == 0o600

    @pytest.mark.skipif(
        os.name == "nt", reason="Unix permissions not applicable on Windows"
    )
    def test_audit_permissions(self, temp_dir):
        """Test auditing file permissions."""
        # Create test files with various permissions
        db_file = temp_dir / "docvault.db"
        db_file.touch()
        os.chmod(db_file, 0o644)  # Insecure

        cred_file = temp_dir / ".credentials.key"
        cred_file.touch()
        os.chmod(cred_file, 0o666)  # Very insecure

        log_file = temp_dir / "logs" / "app.log"
        log_file.parent.mkdir()
        log_file.touch()
        os.chmod(log_file, 0o600)  # Secure

        with patch("docvault.config.DB_PATH", str(db_file)):
            with patch("docvault.config.DEFAULT_BASE_DIR", str(temp_dir)):
                with patch("docvault.config.LOG_DIR", str(temp_dir / "logs")):
                    issues = FilePermissionManager.audit_permissions(temp_dir)

        # Should find issues with database and credentials
        assert len(issues["critical"]) >= 2
        assert any(str(db_file) in str(path) for path, _ in issues["critical"])
        assert any(".credentials.key" in str(path) for path, _ in issues["critical"])

        # Log file should be secure
        assert not any(
            "app.log" in str(path)
            for severity in issues.values()
            for path, _ in severity
        )

    @pytest.mark.skipif(
        os.name == "nt", reason="Unix permissions not applicable on Windows"
    )
    def test_fix_all_permissions(self, temp_dir):
        """Test fixing all permission issues."""
        # Create insecure files
        db_file = temp_dir / "docvault.db"
        db_file.touch()
        os.chmod(db_file, 0o644)

        os.chmod(temp_dir, 0o755)  # Directory too open

        with patch("docvault.config.DB_PATH", str(db_file)):
            with patch("docvault.config.DEFAULT_BASE_DIR", str(temp_dir)):
                with patch("docvault.config.LOG_DIR", str(temp_dir / "logs")):
                    fixed, failed = FilePermissionManager.fix_all_permissions(temp_dir)

        assert fixed >= 2  # At least database and directory
        assert failed == 0

        # Verify permissions were fixed
        assert (db_file.stat().st_mode & 0o777) == 0o600
        assert (temp_dir.stat().st_mode & 0o777) == 0o700


class TestUmaskCheck:
    """Test umask checking functionality."""

    @pytest.mark.skipif(os.name == "nt", reason="umask not applicable on Windows")
    def test_check_umask_secure(self):
        """Test checking a secure umask."""
        # Save current umask
        original = os.umask(0o077)
        try:
            result = check_umask()
            assert result == 0o077
        finally:
            # Restore original umask
            os.umask(original)

    @pytest.mark.skipif(os.name == "nt", reason="umask not applicable on Windows")
    def test_check_umask_insecure(self, capsys):
        """Test warning on insecure umask."""
        # Save current umask
        original = os.umask(0o022)  # Common but less secure
        try:
            result = check_umask()
            assert result == 0o022

            # Check for warning
            captured = capsys.readouterr()
            assert "Warning" in captured.out
            assert "may create files with loose permissions" in captured.out
        finally:
            # Restore original umask
            os.umask(original)

    def test_check_umask_windows(self):
        """Test umask check on Windows returns None."""
        with patch("os.name", "nt"):
            result = check_umask()
            assert result is None


class TestEnsureSecurePermissions:
    """Test the main ensure_secure_permissions function."""

    @pytest.mark.skipif(
        os.name == "nt", reason="Unix permissions not applicable on Windows"
    )
    def test_ensure_secure_permissions(self, temp_dir):
        """Test ensuring all permissions are secure."""
        # Create test database with insecure permissions
        db_file = temp_dir / "docvault.db"
        db_file.touch()
        os.chmod(db_file, 0o644)

        with patch("docvault.config.DB_PATH", str(db_file)):
            with patch("docvault.config.DEFAULT_BASE_DIR", str(temp_dir)):
                ensure_secure_permissions()

        # Database should now be secure
        assert (db_file.stat().st_mode & 0o777) == 0o600

    def test_ensure_secure_permissions_windows(self):
        """Test that ensure_secure_permissions is a no-op on Windows."""
        with patch("os.name", "nt"):
            # Should not raise any errors
            ensure_secure_permissions()
