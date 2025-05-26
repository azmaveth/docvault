"""Tests for input validation framework."""

from pathlib import Path

import pytest

from docvault.utils.validators import (
    ValidationError,
    Validators,
    validate_document_operation,
    validate_search_input,
    validate_tag_operation,
)


class TestValidators:
    """Test input validators."""

    def test_validate_search_query(self):
        """Test search query validation."""
        # Valid queries
        assert Validators.validate_search_query("python sqlite") == "python sqlite"
        assert Validators.validate_search_query("  test  ") == "test"

        # Invalid queries
        with pytest.raises(ValidationError, match="empty"):
            Validators.validate_search_query("")

        with pytest.raises(ValidationError, match="empty"):
            Validators.validate_search_query("   ")

        # SQL injection attempts
        with pytest.raises(ValidationError, match="Invalid characters"):
            Validators.validate_search_query("'; DROP TABLE documents; --")

        with pytest.raises(ValidationError, match="Invalid characters"):
            Validators.validate_search_query('test" OR 1=1 --')

        # HTML tags should be stripped
        result = Validators.validate_search_query("<script>alert('xss')</script>test")
        assert result == "test"

        # Length limit
        long_query = "a" * 1001
        with pytest.raises(ValidationError, match="too long"):
            Validators.validate_search_query(long_query)

    def test_validate_identifier(self):
        """Test identifier validation."""
        # Valid identifiers
        assert Validators.validate_identifier("test_tag") == "test_tag"
        assert Validators.validate_identifier("web-dev") == "web-dev"
        assert Validators.validate_identifier("python3.9") == "python3.9"
        assert Validators.validate_identifier("API_v2") == "API_v2"

        # Invalid identifiers
        with pytest.raises(ValidationError, match="empty"):
            Validators.validate_identifier("")

        with pytest.raises(ValidationError, match="only contain"):
            Validators.validate_identifier("test tag")  # Space not allowed

        with pytest.raises(ValidationError, match="only contain"):
            Validators.validate_identifier("test@tag")  # @ not allowed

        # Length limit
        long_id = "a" * 101
        with pytest.raises(ValidationError, match="too long"):
            Validators.validate_identifier(long_id)

    def test_validate_tag(self):
        """Test tag validation."""
        assert Validators.validate_tag("python") == "python"
        assert Validators.validate_tag("web-development") == "web-development"

        # Truncation
        long_tag = "a" * 60
        result = Validators.validate_tag(long_tag)
        assert len(result) == 50

    def test_validate_document_id(self):
        """Test document ID validation."""
        # Valid IDs
        assert Validators.validate_document_id(1) == 1
        assert Validators.validate_document_id("42") == 42
        assert Validators.validate_document_id(999999) == 999999

        # Invalid IDs
        with pytest.raises(ValidationError, match="must be positive"):
            Validators.validate_document_id(0)

        with pytest.raises(ValidationError, match="must be positive"):
            Validators.validate_document_id(-1)

        with pytest.raises(ValidationError, match="Invalid document ID"):
            Validators.validate_document_id("abc")

        with pytest.raises(ValidationError, match="Invalid document ID"):
            Validators.validate_document_id(None)

    def test_validate_file_path(self):
        """Test file path validation."""
        # Valid paths
        assert Validators.validate_file_path("/tmp/test.txt") == Path("/tmp/test.txt")
        assert Validators.validate_file_path("relative/path.md") == Path(
            "relative/path.md"
        )

        # Invalid paths (path traversal)
        with pytest.raises(ValidationError, match="Invalid file path"):
            Validators.validate_file_path("../../../etc/passwd")

        with pytest.raises(ValidationError, match="Invalid file path"):
            Validators.validate_file_path("/etc/passwd")

    def test_validate_url(self):
        """Test URL validation."""
        # Valid URLs
        assert Validators.validate_url("https://example.com") == "https://example.com"
        assert (
            Validators.validate_url("http://docs.python.org/3/")
            == "http://docs.python.org/3/"
        )
        assert Validators.validate_url("  https://test.com  ") == "https://test.com"

        # Invalid URLs
        with pytest.raises(ValidationError, match="empty"):
            Validators.validate_url("")

        with pytest.raises(ValidationError, match="must include scheme"):
            Validators.validate_url("example.com")

        with pytest.raises(ValidationError, match="Only HTTP/HTTPS"):
            Validators.validate_url("ftp://example.com")

        with pytest.raises(ValidationError, match="must include domain"):
            Validators.validate_url("https://")

    def test_validate_command_argument(self):
        """Test command argument validation."""
        # Valid arguments
        assert Validators.validate_command_argument("test") == "test"
        assert Validators.validate_command_argument("test123") == "test123"
        assert Validators.validate_command_argument("") == ""  # Empty is allowed

        # Shell metacharacters
        with pytest.raises(ValidationError, match="invalid characters"):
            Validators.validate_command_argument("test; rm -rf /")

        with pytest.raises(ValidationError, match="invalid characters"):
            Validators.validate_command_argument("test && echo hacked")

        with pytest.raises(ValidationError, match="invalid characters"):
            Validators.validate_command_argument("test | cat /etc/passwd")

        with pytest.raises(ValidationError, match="invalid characters"):
            Validators.validate_command_argument("test`whoami`")

        # Path traversal
        with pytest.raises(ValidationError, match="invalid sequence"):
            Validators.validate_command_argument("../../etc/passwd")

        # Null bytes
        with pytest.raises(ValidationError, match="invalid sequence"):
            Validators.validate_command_argument("test\x00.txt")

    def test_validate_version(self):
        """Test version string validation."""
        # Valid versions
        assert Validators.validate_version("1.2.3") == "1.2.3"
        assert Validators.validate_version("0.5.1-alpha") == "0.5.1-alpha"
        assert Validators.validate_version("2.0.0-beta.1") == "2.0.0-beta.1"
        assert Validators.validate_version("v1.0") == "v1.0"
        assert Validators.validate_version("latest") == "latest"
        assert Validators.validate_version("stable") == "stable"

        # Invalid versions
        with pytest.raises(ValidationError, match="empty"):
            Validators.validate_version("")

        with pytest.raises(ValidationError, match="Invalid version format"):
            Validators.validate_version("not-a-version")

        with pytest.raises(ValidationError, match="too long"):
            Validators.validate_version("1." * 30)

    def test_validate_integer(self):
        """Test integer validation with bounds."""
        # Valid integers
        assert Validators.validate_integer(5) == 5
        assert Validators.validate_integer("10") == 10
        assert Validators.validate_integer(0, min_val=0) == 0
        assert Validators.validate_integer(100, max_val=100) == 100

        # Invalid integers
        with pytest.raises(ValidationError, match="must be an integer"):
            Validators.validate_integer("abc")

        with pytest.raises(ValidationError, match="must be an integer"):
            Validators.validate_integer(3.14)

        # Bounds checking
        with pytest.raises(ValidationError, match="must be at least 10"):
            Validators.validate_integer(5, min_val=10)

        with pytest.raises(ValidationError, match="must be at most 10"):
            Validators.validate_integer(15, max_val=10)

    def test_validate_list_of(self):
        """Test list validation."""
        # Valid list
        tags = ["python", "web-dev", "api"]
        result = Validators.validate_list_of(tags, Validators.validate_tag)
        assert result == tags

        # Invalid item in list
        tags_with_invalid = ["python", "test tag", "api"]
        with pytest.raises(ValidationError, match="items\\[1\\]"):
            Validators.validate_list_of(tags_with_invalid, Validators.validate_tag)

        # Not a list
        with pytest.raises(ValidationError, match="must be a list"):
            Validators.validate_list_of("not-a-list", Validators.validate_tag)

    def test_sanitize_for_display(self):
        """Test text sanitization for display."""
        # HTML removal
        assert Validators.sanitize_for_display("<b>bold</b> text") == "bold text"
        assert Validators.sanitize_for_display("<script>alert()</script>test") == "test"

        # Whitespace normalization
        assert (
            Validators.sanitize_for_display("too    many     spaces")
            == "too many spaces"
        )
        assert Validators.sanitize_for_display("  trim  ") == "trim"

        # Truncation
        long_text = "a" * 100
        result = Validators.sanitize_for_display(long_text, max_length=20)
        assert result == "a" * 17 + "..."
        assert len(result) == 20

        # Empty input
        assert Validators.sanitize_for_display("") == ""
        assert Validators.sanitize_for_display(None) == ""


class TestValidationHelpers:
    """Test validation helper functions."""

    def test_validate_search_input(self):
        """Test search input validation."""
        # Valid input
        result = validate_search_input("python", tags=["web", "api"], limit=20)
        assert result["query"] == "python"
        assert result["tags"] == ["web", "api"]
        assert result["limit"] == 20

        # Default limit
        result = validate_search_input("test")
        assert result["limit"] == 10

        # Invalid limit
        with pytest.raises(ValidationError, match="must be at least 1"):
            validate_search_input("test", limit=0)

        with pytest.raises(ValidationError, match="must be at most 100"):
            validate_search_input("test", limit=200)

    def test_validate_document_operation(self):
        """Test document operation validation."""
        assert validate_document_operation(1) == 1
        assert validate_document_operation("42") == 42

        with pytest.raises(ValidationError):
            validate_document_operation("invalid")

    def test_validate_tag_operation(self):
        """Test tag operation validation."""
        doc_id, tags = validate_tag_operation(1, ["python", "web-dev"])
        assert doc_id == 1
        assert tags == ["python", "web-dev"]

        # Empty tags
        with pytest.raises(ValidationError, match="at least one tag"):
            validate_tag_operation(1, [])

        # Invalid tag
        with pytest.raises(ValidationError):
            validate_tag_operation(1, ["valid", "invalid tag with spaces"])
