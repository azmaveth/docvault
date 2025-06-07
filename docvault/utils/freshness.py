"""Document freshness utilities for calculating and displaying document age."""

from datetime import datetime, timedelta
from enum import Enum


class FreshnessLevel(Enum):
    """Document freshness levels."""

    FRESH = "fresh"
    RECENT = "recent"
    STALE = "stale"
    OUTDATED = "outdated"


# Default freshness thresholds in days
DEFAULT_THRESHOLDS = {
    FreshnessLevel.FRESH: 7,  # Less than 1 week old
    FreshnessLevel.RECENT: 30,  # Less than 1 month old
    FreshnessLevel.STALE: 90,  # Less than 3 months old
    # Anything older is OUTDATED
}

# Freshness level colors for display
FRESHNESS_COLORS = {
    FreshnessLevel.FRESH: "green",
    FreshnessLevel.RECENT: "yellow",
    FreshnessLevel.STALE: "orange3",
    FreshnessLevel.OUTDATED: "red",
}

# Freshness level icons
FRESHNESS_ICONS = {
    FreshnessLevel.FRESH: "✓",
    FreshnessLevel.RECENT: "~",
    FreshnessLevel.STALE: "!",
    FreshnessLevel.OUTDATED: "✗",
}


def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse a timestamp string from the database.

    Args:
        timestamp_str: Timestamp string in ISO format

    Returns:
        datetime object
    """
    # Handle various timestamp formats
    for fmt in [
        "%Y-%m-%d %H:%M:%S",  # SQLite default
        "%Y-%m-%d %H:%M:%S.%f",  # With microseconds
        "%Y-%m-%dT%H:%M:%S",  # ISO format
        "%Y-%m-%dT%H:%M:%S.%f",  # ISO with microseconds
    ]:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue

    # If all formats fail, try parsing as-is
    return datetime.fromisoformat(timestamp_str)


def calculate_age(timestamp_str: str) -> timedelta:
    """Calculate the age of a document from its timestamp.

    Args:
        timestamp_str: Timestamp string from the database

    Returns:
        timedelta representing the document's age
    """
    timestamp = parse_timestamp(timestamp_str)
    return datetime.now() - timestamp


def get_freshness_level(
    age_days: float, thresholds: dict[FreshnessLevel, int] | None = None
) -> FreshnessLevel:
    """Determine the freshness level based on age.

    Args:
        age_days: Age of the document in days
        thresholds: Custom thresholds (optional)

    Returns:
        FreshnessLevel enum value
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    if age_days <= thresholds[FreshnessLevel.FRESH]:
        return FreshnessLevel.FRESH
    elif age_days <= thresholds[FreshnessLevel.RECENT]:
        return FreshnessLevel.RECENT
    elif age_days <= thresholds[FreshnessLevel.STALE]:
        return FreshnessLevel.STALE
    else:
        return FreshnessLevel.OUTDATED


def format_age(age: timedelta) -> str:
    """Format a timedelta into a human-readable string.

    Args:
        age: timedelta to format

    Returns:
        Human-readable age string
    """
    days = age.days

    if days == 0:
        hours = age.seconds // 3600
        if hours == 0:
            minutes = age.seconds // 60
            if minutes == 0:
                return "just now"
            elif minutes == 1:
                return "1 minute ago"
            else:
                return f"{minutes} minutes ago"
        elif hours == 1:
            return "1 hour ago"
        else:
            return f"{hours} hours ago"
    elif days == 1:
        return "1 day ago"
    elif days < 7:
        return f"{days} days ago"
    elif days < 14:
        return "1 week ago"
    elif days < 30:
        weeks = days // 7
        return f"{weeks} weeks ago"
    elif days < 60:
        return "1 month ago"
    elif days < 365:
        months = days // 30
        return f"{months} months ago"
    elif days < 730:
        return "1 year ago"
    else:
        years = days // 365
        return f"{years} years ago"


def get_freshness_info(timestamp_str: str) -> tuple[FreshnessLevel, str, str]:
    """Get comprehensive freshness information for a document.

    Args:
        timestamp_str: Timestamp string from the database

    Returns:
        Tuple of (freshness_level, formatted_age, icon)
    """
    age = calculate_age(timestamp_str)
    age_days = age.total_seconds() / 86400  # Convert to days
    freshness_level = get_freshness_level(age_days)
    formatted_age = format_age(age)
    icon = FRESHNESS_ICONS[freshness_level]

    return freshness_level, formatted_age, icon


def format_freshness_display(
    timestamp_str: str, show_icon: bool = True, show_color: bool = True
) -> str:
    """Format a freshness display string with color and icon.

    Args:
        timestamp_str: Timestamp string from the database
        show_icon: Whether to include the icon
        show_color: Whether to apply color formatting

    Returns:
        Formatted freshness string
    """
    freshness_level, formatted_age, icon = get_freshness_info(timestamp_str)

    # Build display string
    parts = []
    if show_icon:
        parts.append(icon)
    parts.append(formatted_age)

    display = " ".join(parts)

    # Apply color if requested
    if show_color:
        color = FRESHNESS_COLORS[freshness_level]
        return f"[{color}]{display}[/{color}]"
    else:
        return display


def should_suggest_update(timestamp_str: str, threshold_days: int = 90) -> bool:
    """Determine if a document should be updated based on its age.

    Args:
        timestamp_str: Timestamp string from the database
        threshold_days: Age threshold in days (default: 90)

    Returns:
        True if the document should be updated
    """
    age = calculate_age(timestamp_str)
    age_days = age.total_seconds() / 86400
    return age_days > threshold_days


def get_update_suggestion(freshness_level: FreshnessLevel) -> str | None:
    """Get an update suggestion based on freshness level.

    Args:
        freshness_level: The document's freshness level

    Returns:
        Suggestion string or None if no suggestion
    """
    suggestions = {
        FreshnessLevel.STALE: (
            "Consider updating this document for the latest information."
        ),
        FreshnessLevel.OUTDATED: (
            "This document is outdated. Update recommended for accuracy."
        ),
    }

    return suggestions.get(freshness_level)
