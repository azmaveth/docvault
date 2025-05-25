"""Tests for path security utilities."""

import os
import tempfile
import zipfile
from pathlib import Path

import pytest

from docvault.core.exceptions import PathSecurityError
from docvault.utils.path_security import (
    get_safe_path,
    is_safe_archive_member,
    validate_filename,
    validate_path,
    validate_url_path,
)


class TestPathValidation:
    """Test path validation functions."""

    def test_validate_path_null_bytes(self):
        """Test rejection of null bytes in paths."""
        with pytest.raises(PathSecurityError, match="null bytes"):
            validate_path("test\x00file.txt")

    def test_validate_path_traversal_patterns(self):
        """Test rejection of path traversal patterns."""
        dangerous_paths = [
            "../etc/passwd",
            "../../etc/passwd",
            "./../etc/passwd",
            "test/../../../etc/passwd",
            "test/../../..",
            "..\\..\\windows\\system32",
            "test\\..\\..\\windows",
        ]

        for path in dangerous_paths:
            with pytest.raises(PathSecurityError):
                validate_path(path)

    def test_validate_path_absolute_when_not_allowed(self):
        """Test rejection of absolute paths when not allowed."""
        with pytest.raises(PathSecurityError, match="Absolute paths are not allowed"):
            validate_path("/etc/passwd", allow_absolute=False)

        # Windows absolute paths
        if os.name == "nt":
            with pytest.raises(
                PathSecurityError, match="Absolute paths are not allowed"
            ):
                validate_path("C:\\Windows\\System32", allow_absolute=False)

    def test_validate_path_with_allowed_base_paths(self):
        """Test path validation with allowed base paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            allowed_base = Path(temp_dir)

            # Valid path within allowed base
            valid_path = allowed_base / "subdir" / "file.txt"
            result = validate_path(
                str(valid_path), allowed_base_paths=[allowed_base], allow_absolute=True
            )
            # Compare resolved paths to handle symlink resolution differences
            assert result == valid_path.resolve()

            # Path outside allowed base
            with pytest.raises(
                PathSecurityError, match="not under any allowed base path"
            ):
                validate_path(
                    "/etc/passwd",
                    allowed_base_paths=[allowed_base],
                    allow_absolute=True,
                )

    def test_validate_path_symlink_escape(self):
        """Test prevention of symlink escapes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            safe_dir = base_path / "safe"
            safe_dir.mkdir()

            # Create a symlink pointing outside the safe directory
            link_path = safe_dir / "escape_link"
            target_path = base_path / "outside"
            target_path.mkdir()

            try:
                link_path.symlink_to(target_path)
            except (OSError, NotImplementedError):
                # Skip test if symlinks not supported
                pytest.skip("Symlinks not supported on this system")

            # Try to access through the symlink
            test_path = link_path / "file.txt"
            with pytest.raises(
                PathSecurityError, match="not under any allowed base path"
            ):
                validate_path(
                    str(test_path), allowed_base_paths=[safe_dir], allow_absolute=True
                )


class TestFilenameValidation:
    """Test filename validation functions."""

    def test_validate_filename_valid(self):
        """Test validation of valid filenames."""
        valid_names = [
            "document.txt",
            "my-file.pdf",
            "test_123.html",
            "file.tar.gz",
            "名前.txt",  # Unicode
        ]

        for name in valid_names:
            result = validate_filename(name)
            assert result == name

    def test_validate_filename_invalid(self):
        """Test rejection of invalid filenames."""
        invalid_names = [
            "../etc/passwd",
            "..\\windows\\system32",
            "file\x00name.txt",
            "/etc/passwd",
            "C:\\Windows\\System32",
            ".",
            "..",
            "",
            "con",  # Windows reserved
            "prn.txt",  # Windows reserved with extension
            "file:name.txt",  # Invalid character
            "file|name.txt",  # Invalid character
        ]

        for name in invalid_names:
            with pytest.raises(PathSecurityError):
                validate_filename(name)

    def test_validate_filename_length(self):
        """Test filename length validation."""
        # Filename too long
        long_name = "a" * 256 + ".txt"
        with pytest.raises(PathSecurityError, match="Filename too long"):
            validate_filename(long_name)


class TestSafePath:
    """Test get_safe_path function."""

    def test_get_safe_path_creates_dirs(self):
        """Test that get_safe_path creates directories when requested."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Test with directory creation
            safe_path = get_safe_path(base_path, "subdir/file.txt", create_dirs=True)
            assert safe_path.parent.exists()
            assert safe_path.parent.is_dir()

    def test_get_safe_path_no_create_dirs(self):
        """Test that get_safe_path doesn't create directories by default."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Test without directory creation
            safe_path = get_safe_path(base_path, "subdir/file.txt", create_dirs=False)
            assert not safe_path.parent.exists()

    def test_get_safe_path_validation(self):
        """Test that get_safe_path validates paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Try dangerous path
            with pytest.raises(PathSecurityError):
                get_safe_path(base_path, "../etc/passwd")


class TestArchiveSecurity:
    """Test archive member validation."""

    def test_safe_archive_members(self):
        """Test validation of safe archive members."""
        safe_members = [
            "file.txt",
            "subdir/file.txt",
            "deep/nested/path/file.txt",
            "file-with-dash.txt",
            "file_with_underscore.txt",
        ]

        for member in safe_members:
            assert is_safe_archive_member(member) is True

    def test_unsafe_archive_members(self):
        """Test rejection of unsafe archive members."""
        unsafe_members = [
            "../etc/passwd",
            "../../etc/passwd",
            "/etc/passwd",
            "C:\\Windows\\System32",
            "subdir/../../../etc/passwd",
            "file\x00name.txt",
            "",
            ".",
            "..",
        ]

        for member in unsafe_members:
            assert is_safe_archive_member(member) is False

    def test_actual_zip_validation(self):
        """Test validation with actual zip files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "test.zip"

            # Create a zip with both safe and unsafe paths
            with zipfile.ZipFile(zip_path, "w") as zf:
                # Safe file
                zf.writestr("safe_file.txt", "Safe content")
                # Attempt path traversal
                zf.writestr("../unsafe_file.txt", "Unsafe content")

            # Check members
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    if member == "safe_file.txt":
                        assert is_safe_archive_member(member) is True
                    else:
                        assert is_safe_archive_member(member) is False


class TestURLValidation:
    """Test URL validation functions."""

    def test_valid_urls(self):
        """Test validation of valid URLs."""
        valid_urls = [
            "https://example.com",
            "https://example.com/path/to/resource",
            "https://example.com:8080/path",
            "https://sub.example.com",
            "https://example.com/path?query=value",
            "https://example.com/path#fragment",
        ]

        for url in valid_urls:
            result = validate_url_path(url)
            assert result == url

    def test_invalid_schemes(self):
        """Test rejection of invalid URL schemes."""
        invalid_urls = [
            "file:///etc/passwd",
            "ftp://example.com",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "about:blank",
            "chrome://settings",
        ]

        for url in invalid_urls:
            with pytest.raises(PathSecurityError, match="URL scheme"):
                validate_url_path(url)

    def test_localhost_rejection(self):
        """Test rejection of localhost URLs."""
        localhost_urls = [
            "http://localhost/admin",
            "http://localhost:8080/api",
            "http://127.0.0.1/",
            "http://127.0.0.1:3000/",
            "http://[::1]/",
            "http://[::1]:8080/",
            "http://0.0.0.0/",
        ]

        for url in localhost_urls:
            with pytest.raises(PathSecurityError, match="localhost"):
                validate_url_path(url)

    def test_private_ip_rejection(self):
        """Test rejection of private IP addresses."""
        private_ips = [
            "http://10.0.0.1/",
            "http://10.255.255.255/",
            "http://172.16.0.1/",
            "http://172.31.255.255/",
            "http://192.168.0.1/",
            "http://192.168.255.255/",
            "http://169.254.0.1/",  # Link-local
        ]

        for url in private_ips:
            with pytest.raises(PathSecurityError, match="private IP"):
                validate_url_path(url)

    def test_invalid_url_format(self):
        """Test rejection of malformed URLs."""
        invalid_urls = [
            "not a url",
            "ht!tp://example.com",
            "https://",
            "//example.com",
            "https://example..com",
        ]

        for url in invalid_urls:
            with pytest.raises(PathSecurityError):
                validate_url_path(url)

    def test_url_length_limit(self):
        """Test URL length validation."""
        # Create a very long URL
        long_url = "https://example.com/" + "a" * 2100
        with pytest.raises(PathSecurityError, match="URL too long"):
            validate_url_path(long_url)

    def test_cloud_metadata_rejection(self):
        """Test rejection of cloud metadata service URLs."""
        metadata_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://metadata.azure.com/metadata/instance",
        ]

        for url in metadata_urls:
            with pytest.raises(PathSecurityError, match="metadata services"):
                validate_url_path(url)

    def test_reserved_ips_rejection(self):
        """Test rejection of reserved and multicast IP addresses."""
        # Test multicast
        with pytest.raises(PathSecurityError, match="reserved IP"):
            validate_url_path("http://224.0.0.1/")

        # Test broadcast (detected as private)
        with pytest.raises(PathSecurityError, match="private IP"):
            validate_url_path("http://255.255.255.255/")

    def test_blocked_ports_rejection(self):
        """Test rejection of common internal service ports."""
        blocked_port_urls = [
            "http://example.com:22/",  # SSH
            "http://example.com:23/",  # Telnet
            "http://example.com:25/",  # SMTP
            "http://example.com:3389/",  # RDP
        ]

        for url in blocked_port_urls:
            with pytest.raises(PathSecurityError, match="is not allowed"):
                validate_url_path(url)

    def test_domain_allowlist(self):
        """Test domain allowlist functionality."""
        allowed_domains = ["example.com", "docs.python.org"]

        # Test allowed domains
        valid_urls = [
            "https://example.com/page",
            "https://subdomain.example.com/page",
            "https://docs.python.org/3/",
        ]

        for url in valid_urls:
            result = validate_url_path(url, allowed_domains=allowed_domains)
            assert result == url

        # Test blocked domains
        with pytest.raises(PathSecurityError, match="not in the allowed list"):
            validate_url_path("https://evil.com/", allowed_domains=allowed_domains)

    def test_domain_blocklist(self):
        """Test domain blocklist functionality."""
        blocked_domains = ["evil.com", "malware.org"]

        # Test blocked domains
        blocked_urls = [
            "https://evil.com/page",
            "https://subdomain.evil.com/page",
            "https://malware.org/",
        ]

        for url in blocked_urls:
            with pytest.raises(PathSecurityError, match="is blocked"):
                validate_url_path(url, blocked_domains=blocked_domains)

        # Test allowed domains
        result = validate_url_path(
            "https://example.com/", blocked_domains=blocked_domains
        )
        assert result == "https://example.com/"
