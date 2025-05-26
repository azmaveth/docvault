"""Tests for document freshness utilities and commands."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from docvault.utils.freshness import (
    FreshnessLevel,
    calculate_age,
    format_age,
    format_freshness_display,
    get_freshness_info,
    get_freshness_level,
    get_update_suggestion,
    parse_timestamp,
    should_suggest_update,
)


class TestFreshnessUtilities:
    """Test freshness utility functions."""

    def test_parse_timestamp_formats(self):
        """Test parsing various timestamp formats."""
        # SQLite default format
        ts = parse_timestamp("2024-01-15 10:30:45")
        assert ts.year == 2024
        assert ts.month == 1
        assert ts.day == 15
        assert ts.hour == 10
        assert ts.minute == 30

        # With microseconds
        ts = parse_timestamp("2024-01-15 10:30:45.123456")
        assert ts.microsecond == 123456

        # ISO format
        ts = parse_timestamp("2024-01-15T10:30:45")
        assert ts.hour == 10

        # ISO with microseconds
        ts = parse_timestamp("2024-01-15T10:30:45.123456")
        assert ts.microsecond == 123456

    def test_calculate_age(self):
        """Test age calculation from timestamp."""
        # Create a timestamp 5 days ago
        past_time = datetime.now() - timedelta(days=5)
        timestamp_str = past_time.strftime("%Y-%m-%d %H:%M:%S")

        age = calculate_age(timestamp_str)
        # Allow for small timing differences
        assert 4.9 < age.days <= 5

    def test_get_freshness_level(self):
        """Test freshness level determination."""
        assert get_freshness_level(3) == FreshnessLevel.FRESH
        assert get_freshness_level(7) == FreshnessLevel.FRESH
        assert get_freshness_level(8) == FreshnessLevel.RECENT
        assert get_freshness_level(30) == FreshnessLevel.RECENT
        assert get_freshness_level(31) == FreshnessLevel.STALE
        assert get_freshness_level(90) == FreshnessLevel.STALE
        assert get_freshness_level(91) == FreshnessLevel.OUTDATED
        assert get_freshness_level(365) == FreshnessLevel.OUTDATED

    def test_format_age(self):
        """Test age formatting."""
        # Just now
        assert format_age(timedelta(seconds=30)) == "just now"

        # Minutes
        assert format_age(timedelta(minutes=1)) == "1 minute ago"
        assert format_age(timedelta(minutes=5)) == "5 minutes ago"

        # Hours
        assert format_age(timedelta(hours=1)) == "1 hour ago"
        assert format_age(timedelta(hours=3)) == "3 hours ago"

        # Days
        assert format_age(timedelta(days=1)) == "1 day ago"
        assert format_age(timedelta(days=5)) == "5 days ago"

        # Weeks
        assert format_age(timedelta(days=7)) == "1 week ago"
        assert format_age(timedelta(days=14)) == "2 weeks ago"

        # Months
        assert format_age(timedelta(days=30)) == "1 month ago"
        assert format_age(timedelta(days=60)) == "2 months ago"

        # Years
        assert format_age(timedelta(days=365)) == "1 year ago"
        assert format_age(timedelta(days=730)) == "2 years ago"

    def test_get_freshness_info(self):
        """Test comprehensive freshness info retrieval."""
        # Create a timestamp 10 days ago
        past_time = datetime.now() - timedelta(days=10)
        timestamp_str = past_time.strftime("%Y-%m-%d %H:%M:%S")

        level, age_str, icon = get_freshness_info(timestamp_str)

        assert level == FreshnessLevel.RECENT
        assert "10 days ago" in age_str or "1 week ago" in age_str
        assert icon == "~"

    def test_format_freshness_display(self):
        """Test freshness display formatting."""
        # Create a fresh timestamp
        recent_time = datetime.now() - timedelta(hours=2)
        timestamp_str = recent_time.strftime("%Y-%m-%d %H:%M:%S")

        # With color and icon
        display = format_freshness_display(
            timestamp_str, show_icon=True, show_color=True
        )
        assert "[green]" in display
        assert "✓" in display
        assert "2 hours ago" in display

        # Without color
        display = format_freshness_display(
            timestamp_str, show_icon=True, show_color=False
        )
        assert "[green]" not in display
        assert "✓" in display

        # Without icon
        display = format_freshness_display(
            timestamp_str, show_icon=False, show_color=False
        )
        assert "✓" not in display
        assert "2 hours ago" in display

    def test_should_suggest_update(self):
        """Test update suggestion logic."""
        # Fresh document - no update needed
        recent_time = datetime.now() - timedelta(days=10)
        timestamp_str = recent_time.strftime("%Y-%m-%d %H:%M:%S")
        assert not should_suggest_update(timestamp_str, threshold_days=90)

        # Old document - update needed
        old_time = datetime.now() - timedelta(days=100)
        timestamp_str = old_time.strftime("%Y-%m-%d %H:%M:%S")
        assert should_suggest_update(timestamp_str, threshold_days=90)

        # Custom threshold
        assert should_suggest_update(timestamp_str, threshold_days=50)

    def test_get_update_suggestion(self):
        """Test update suggestion messages."""
        assert get_update_suggestion(FreshnessLevel.FRESH) is None
        assert get_update_suggestion(FreshnessLevel.RECENT) is None

        suggestion = get_update_suggestion(FreshnessLevel.STALE)
        assert "Consider updating" in suggestion

        suggestion = get_update_suggestion(FreshnessLevel.OUTDATED)
        assert "outdated" in suggestion
        assert "Update recommended" in suggestion


class TestFreshnessCommands:
    """Test freshness CLI commands."""

    @pytest.fixture
    def mock_documents(self):
        """Create mock documents with different ages."""
        now = datetime.now()
        return [
            {
                "id": 1,
                "title": "Fresh Document",
                "url": "https://example.com/fresh",
                "scraped_at": (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "id": 2,
                "title": "Recent Document",
                "url": "https://example.com/recent",
                "scraped_at": (now - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "id": 3,
                "title": "Stale Document",
                "url": "https://example.com/stale",
                "scraped_at": (now - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "id": 4,
                "title": "Outdated Document",
                "url": "https://example.com/outdated",
                "scraped_at": (now - timedelta(days=120)).strftime("%Y-%m-%d %H:%M:%S"),
            },
        ]

    def test_freshness_check_command_all(self, runner, mock_documents):
        """Test freshness check command with all documents."""
        with patch(
            "docvault.db.operations.list_documents", return_value=mock_documents
        ):
            result = runner.invoke(["freshness"])

            assert result.exit_code == 0
            assert "Document Freshness Report" in result.output
            assert "Fresh Document" in result.output
            assert "Recent Document" in result.output
            assert "Stale Document" in result.output
            assert "Outdated Document" in result.output
            assert "Summary" in result.output

    def test_freshness_check_command_filtered(self, runner, mock_documents):
        """Test freshness check with filter."""
        with patch(
            "docvault.db.operations.list_documents", return_value=mock_documents
        ):
            # Filter for stale documents
            result = runner.invoke(["freshness", "--filter", "stale"])

            assert result.exit_code == 0
            assert "Stale Document" in result.output
            assert "Fresh Document" not in result.output
            assert "Recent Document" not in result.output
            assert "Outdated Document" not in result.output

    def test_freshness_check_command_json(self, runner, mock_documents):
        """Test freshness check with JSON output."""
        with patch(
            "docvault.db.operations.list_documents", return_value=mock_documents
        ):
            result = runner.invoke(["freshness", "--format", "json"])

            assert result.exit_code == 0
            # Check for JSON structure
            assert "[" in result.output
            assert "]" in result.output
            assert '"freshness_level"' in result.output
            assert '"needs_update"' in result.output

    def test_freshness_check_command_list(self, runner, mock_documents):
        """Test freshness check with list format."""
        with patch(
            "docvault.db.operations.list_documents", return_value=mock_documents
        ):
            result = runner.invoke(["freshness", "--format", "list"])

            assert result.exit_code == 0
            # Check for icon indicators
            assert "✓" in result.output  # Fresh
            assert "~" in result.output  # Recent
            assert "!" in result.output  # Stale
            assert "✗" in result.output  # Outdated

    def test_freshness_check_suggest_updates(self, runner, mock_documents):
        """Test freshness check with update suggestions only."""
        with patch(
            "docvault.db.operations.list_documents", return_value=mock_documents
        ):
            result = runner.invoke(["freshness", "--suggest-updates"])

            assert result.exit_code == 0
            # Should only show outdated document (>90 days)
            assert "Outdated Document" in result.output
            assert "Fresh Document" not in result.output

    def test_check_document_freshness_command(self, runner):
        """Test individual document freshness check."""
        mock_doc = {
            "id": 1,
            "title": "Test Document",
            "url": "https://example.com/test",
            "scraped_at": (datetime.now() - timedelta(days=45)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

        with patch("docvault.db.operations.get_document", return_value=mock_doc):
            result = runner.invoke(["check-freshness", "1"])

            assert result.exit_code == 0
            assert "Test Document" in result.output
            assert "https://example.com/test" in result.output
            assert "Stale" in result.output
            assert "Consider updating" in result.output

    def test_check_document_freshness_not_found(self, runner):
        """Test freshness check for non-existent document."""
        with patch("docvault.db.operations.get_document", return_value=None):
            result = runner.invoke(["check-freshness", "999"])

            assert result.exit_code == 1
            assert "Document not found" in result.output
