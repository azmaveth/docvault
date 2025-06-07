"""
Secure SQL query builder for DocVault.
Prevents SQL injection by using parameterized queries exclusively.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class QueryBuilder:
    """Secure SQL query builder that prevents SQL injection."""

    def __init__(self):
        self.select_columns: list[str] = []
        self.from_table: str | None = None
        self.joins: list[str] = []
        self.where_conditions: list[str] = []
        self.group_by_columns: list[str] = []
        self.order_by_columns: list[str] = []
        self.limit_value: int | None = None
        self.parameters: list[Any] = []

    def select(self, *columns: str) -> "QueryBuilder":
        """Add SELECT columns."""
        self.select_columns.extend(columns)
        return self

    def from_(self, table: str) -> "QueryBuilder":
        """Set FROM table."""
        self.from_table = table
        return self

    def join(self, join_clause: str) -> "QueryBuilder":
        """Add JOIN clause."""
        self.joins.append(join_clause)
        return self

    def where(self, condition: str, *params: Any) -> "QueryBuilder":
        """Add WHERE condition with parameters."""
        self.where_conditions.append(condition)
        self.parameters.extend(params)
        return self

    def where_in(self, column: str, values: list[Any]) -> "QueryBuilder":
        """Add WHERE IN condition."""
        if values:
            placeholders = ",".join(["?" for _ in values])
            self.where_conditions.append(f"{column} IN ({placeholders})")
            self.parameters.extend(values)
        else:
            # Empty list - no matches
            self.where_conditions.append("1=0")
        return self

    def group_by(self, *columns: str) -> "QueryBuilder":
        """Add GROUP BY columns."""
        self.group_by_columns.extend(columns)
        return self

    def order_by(self, column: str, direction: str = "ASC") -> "QueryBuilder":
        """Add ORDER BY column."""
        direction = direction.upper()
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"Invalid sort direction: {direction}")
        self.order_by_columns.append(f"{column} {direction}")
        return self

    def limit(self, limit: int) -> "QueryBuilder":
        """Set LIMIT value."""
        self.limit_value = limit
        return self

    def build(self) -> tuple[str, list[Any]]:
        """Build the SQL query and return (query, parameters)."""
        if not self.select_columns:
            raise ValueError("No SELECT columns specified")
        if not self.from_table:
            raise ValueError("No FROM table specified")

        parts = []

        # SELECT
        parts.append(f"SELECT {', '.join(self.select_columns)}")

        # FROM
        parts.append(f"FROM {self.from_table}")

        # JOINs
        for join in self.joins:
            parts.append(join)

        # WHERE
        if self.where_conditions:
            parts.append(f"WHERE {' AND '.join(self.where_conditions)}")

        # GROUP BY
        if self.group_by_columns:
            parts.append(f"GROUP BY {', '.join(self.group_by_columns)}")

        # ORDER BY
        if self.order_by_columns:
            parts.append(f"ORDER BY {', '.join(self.order_by_columns)}")

        # LIMIT
        if self.limit_value is not None:
            parts.append(f"LIMIT {self.limit_value}")

        query = "\n".join(parts)

        logger.debug(f"Built query with {len(self.parameters)} parameters")
        return query, self.parameters


class FilterBuilder:
    """Build WHERE clause filters safely."""

    def __init__(self):
        self.conditions: list[str] = []
        self.parameters: list[Any] = []

    def add_condition(self, condition: str, *params: Any) -> "FilterBuilder":
        """Add a condition with parameters."""
        self.conditions.append(condition)
        self.parameters.extend(params)
        return self

    def add_in_condition(self, column: str, values: list[Any]) -> "FilterBuilder":
        """Add IN condition."""
        if values:
            placeholders = ",".join(["?" for _ in values])
            self.conditions.append(f"{column} IN ({placeholders})")
            self.parameters.extend(values)
        return self

    def add_like_condition(self, column: str, pattern: str) -> "FilterBuilder":
        """Add LIKE condition."""
        self.conditions.append(f"{column} LIKE ?")
        self.parameters.append(pattern)
        return self

    def add_date_condition(
        self, column: str, operator: str, date: str
    ) -> "FilterBuilder":
        """Add date comparison condition."""
        if operator not in ("=", "!=", ">", ">=", "<", "<="):
            raise ValueError(f"Invalid operator: {operator}")
        self.conditions.append(f"{column} {operator} ?")
        self.parameters.append(date)
        return self

    def build(self) -> tuple[list[str], list[Any]]:
        """Return conditions and parameters."""
        return self.conditions, self.parameters

    def build_clause(self) -> tuple[str, list[Any]]:
        """Build WHERE clause string and parameters."""
        if not self.conditions:
            return "", []
        return " AND ".join(self.conditions), self.parameters


def sanitize_identifier(identifier: str) -> str:
    """
    Sanitize a SQL identifier (table/column name).
    Only allows alphanumeric characters and underscores.
    """
    if not identifier:
        raise ValueError("Empty identifier")

    # Only allow alphanumeric and underscore
    sanitized = "".join(c for c in identifier if c.isalnum() or c == "_")

    if not sanitized:
        raise ValueError(f"Invalid identifier: {identifier}")

    # Don't allow identifiers starting with numbers
    if sanitized[0].isdigit():
        raise ValueError(f"Identifier cannot start with number: {identifier}")

    return sanitized


def validate_sort_direction(direction: str) -> str:
    """Validate and return sort direction."""
    direction = direction.upper()
    if direction not in ("ASC", "DESC"):
        raise ValueError(f"Invalid sort direction: {direction}")
    return direction


def build_document_filter(
    doc_filter: dict[str, Any] | None,
) -> tuple[list[str], list[Any]]:
    """
    Build filter conditions and parameters from document filter dict.
    Returns (conditions, parameters) tuple.
    """
    if not doc_filter:
        return [], []

    fb = FilterBuilder()

    # Version filter
    if "version" in doc_filter:
        fb.add_condition("d.version = ?", doc_filter["version"])

    # Library filter
    if doc_filter.get("is_library_doc"):
        fb.add_condition("d.is_library_doc = ?", 1)

    # Title filter
    if "title_contains" in doc_filter:
        fb.add_like_condition(
            "LOWER(d.title)", f"%{doc_filter['title_contains'].lower()}%"
        )

    # Date filter
    if "updated_after" in doc_filter:
        fb.add_date_condition("d.updated_at", ">=", doc_filter["updated_after"])

    # Document ID filter
    if "document_ids" in doc_filter:
        value = doc_filter["document_ids"]
        if isinstance(value, list):
            fb.add_in_condition("d.id", value)
        else:
            fb.add_condition("d.id = ?", value)
    elif "document_id" in doc_filter:
        value = doc_filter["document_id"]
        if isinstance(value, list):
            fb.add_in_condition("d.id", value)
        else:
            fb.add_condition("d.id = ?", value)

    # Library name filter
    if "library_name" in doc_filter:
        fb.add_condition("l.name = ?", doc_filter["library_name"])

    # Collection filter
    if "collection_id" in doc_filter:
        fb.add_condition(
            "d.id IN (SELECT document_id FROM collection_documents WHERE collection_id = ?)",
            doc_filter["collection_id"],
        )

    return fb.build()


# Safe column names for validation
SAFE_COLUMNS = {
    "d.id",
    "d.title",
    "d.url",
    "d.version",
    "d.updated_at",
    "d.is_library_doc",
    "d.library_id",
    "s.id",
    "s.document_id",
    "s.content",
    "s.section_title",
    "s.section_path",
    "s.section_level",
    "s.parent_segment_id",
    "l.name",
    "l.id",
    "v.distance",
    "v.rowid",
}


def validate_column_name(column: str) -> bool:
    """Validate that a column name is safe to use."""
    return column in SAFE_COLUMNS
