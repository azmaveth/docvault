"""Suggestion engine for recommending related functions, classes, and modules."""

import asyncio
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Tuple

from docvault import config
from docvault.core.context_extractor import ContextExtractor
from docvault.core.embeddings import search as search_docs

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    """Represents a suggestion for related content."""

    identifier: str  # Function/class/module name
    type: str  # 'function', 'class', 'module', 'concept'
    document_id: int
    segment_id: int
    title: str
    description: str
    relevance_score: float
    reason: str  # Why this is suggested
    usage_example: str | None = None


class SuggestionEngine:
    """Generates suggestions for related functions, classes, and concepts."""

    def __init__(self):
        self.context_extractor = ContextExtractor()

        # Common programming task categories
        self.task_categories = {
            "data_processing": [
                "parse",
                "process",
                "transform",
                "filter",
                "map",
                "reduce",
                "convert",
            ],
            "file_operations": [
                "read",
                "write",
                "open",
                "save",
                "load",
                "file",
                "path",
            ],
            "web_requests": [
                "request",
                "http",
                "get",
                "post",
                "api",
                "client",
                "fetch",
            ],
            "database": [
                "query",
                "select",
                "insert",
                "update",
                "delete",
                "connection",
                "cursor",
            ],
            "async_programming": [
                "async",
                "await",
                "coroutine",
                "future",
                "thread",
                "concurrent",
            ],
            "error_handling": ["exception", "error", "try", "catch", "handle", "raise"],
            "testing": ["test", "assert", "mock", "fixture", "unittest", "pytest"],
            "configuration": [
                "config",
                "settings",
                "environment",
                "parameter",
                "option",
            ],
        }

    def get_suggestions(
        self,
        query: str,
        current_document_id: int | None = None,
        context: str | None = None,
        limit: int = 10,
    ) -> list[Suggestion]:
        """Get suggestions based on a query or current context.

        Args:
            query: Search query or function/class name
            current_document_id: ID of currently viewed document (for context)
            context: Additional context about the current task
            limit: Maximum number of suggestions

        Returns:
            List of suggestions ordered by relevance
        """
        suggestions = []

        # Get suggestions from different sources
        suggestions.extend(self._get_semantic_suggestions(query, limit // 2))
        suggestions.extend(
            self._get_pattern_based_suggestions(query, current_document_id)
        )
        suggestions.extend(
            self._get_cross_reference_suggestions(query, current_document_id)
        )
        suggestions.extend(self._get_category_based_suggestions(query, context))

        # Remove duplicates and sort by relevance
        unique_suggestions = self._deduplicate_suggestions(suggestions)
        sorted_suggestions = sorted(
            unique_suggestions, key=lambda x: x.relevance_score, reverse=True
        )

        return sorted_suggestions[:limit]

    def get_task_based_suggestions(
        self, task_description: str, limit: int = 5
    ) -> list[Suggestion]:
        """Get suggestions based on a task description.

        Args:
            task_description: Description of what the user wants to accomplish
            limit: Maximum number of suggestions

        Returns:
            List of relevant suggestions
        """
        # Analyze task description to identify categories
        task_lower = task_description.lower()
        relevant_categories = []

        for category, keywords in self.task_categories.items():
            if any(keyword in task_lower for keyword in keywords):
                relevant_categories.append(category)

        suggestions = []

        # Get suggestions for each relevant category
        for category in relevant_categories:
            category_suggestions = self._get_suggestions_for_category(
                category, task_description
            )
            suggestions.extend(category_suggestions)

        # If no specific categories match, use general search
        if not suggestions:
            suggestions = self._get_semantic_suggestions(task_description, limit)

        return sorted(suggestions, key=lambda x: x.relevance_score, reverse=True)[
            :limit
        ]

    def get_complementary_functions(
        self, function_name: str, limit: int = 5
    ) -> list[Suggestion]:
        """Get functions that are commonly used together with the given function.

        Args:
            function_name: Name of the function to find complements for
            limit: Maximum number of suggestions

        Returns:
            List of complementary functions
        """
        suggestions = []

        # Find documents containing this function
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row

        try:
            cursor = conn.cursor()

            # Find segments mentioning the function
            cursor.execute(
                """
                SELECT ds.*, d.title, d.id as doc_id
                FROM document_segments ds
                JOIN documents d ON ds.document_id = d.id
                WHERE ds.content LIKE ?
            """,
                (f"%{function_name}%",),
            )

            segments = cursor.fetchall()

            # Analyze each segment to find related functions
            for segment in segments:
                related_functions = self._extract_functions_from_content(
                    segment["content"]
                )

                for func in related_functions:
                    if func != function_name and len(func) > 2:
                        suggestions.append(
                            Suggestion(
                                identifier=func,
                                type="function",
                                document_id=segment["doc_id"],
                                segment_id=segment["id"],
                                title=segment["section_title"]
                                or segment["content"][:50],
                                description=f"Often used with {function_name}",
                                relevance_score=0.7,
                                reason=f"Frequently appears with {function_name}",
                            )
                        )

        finally:
            conn.close()

        # Count frequency and boost relevance for common combinations
        function_counts = Counter(s.identifier for s in suggestions)
        for suggestion in suggestions:
            frequency = function_counts[suggestion.identifier]
            suggestion.relevance_score = min(1.0, 0.5 + (frequency * 0.1))

        return self._deduplicate_suggestions(suggestions)[:limit]

    def _get_semantic_suggestions(self, query: str, limit: int) -> list[Suggestion]:
        """Get suggestions using semantic search."""
        suggestions = []

        try:
            # Use existing search functionality to find related content
            results = asyncio.run(search_docs(query, limit=limit * 2))

            for result in results:
                # Extract identifiers from the content
                identifiers = self._extract_identifiers_from_content(result["content"])

                for identifier, id_type in identifiers:
                    suggestions.append(
                        Suggestion(
                            identifier=identifier,
                            type=id_type,
                            document_id=result["document_id"],
                            segment_id=result["id"],
                            title=result["title"],
                            description=result["content"][:200],
                            relevance_score=result["score"]
                            * 0.8,  # Slightly lower than direct matches
                            reason="Semantic similarity to query",
                        )
                    )

        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")

        return suggestions

    def _get_pattern_based_suggestions(
        self, query: str, current_doc_id: int | None
    ) -> list[Suggestion]:
        """Get suggestions based on naming patterns and conventions."""
        suggestions = []

        # Generate pattern-based suggestions
        if re.match(r".*[Gg]et.*", query):
            # If query contains 'get', suggest corresponding 'set' functions
            set_variant = re.sub(r"[Gg]et", "set", query)
            suggestions.extend(
                self._find_function_variants([set_variant], "Setter function")
            )

        elif re.match(r".*[Ss]et.*", query):
            # If query contains 'set', suggest corresponding 'get' functions
            get_variant = re.sub(r"[Ss]et", "get", query)
            suggestions.extend(
                self._find_function_variants([get_variant], "Getter function")
            )

        elif re.match(r".*[Oo]pen.*", query):
            # If query contains 'open', suggest 'close' functions
            close_variant = re.sub(r"[Oo]pen", "close", query)
            suggestions.extend(
                self._find_function_variants(
                    [close_variant], "Corresponding close function"
                )
            )

        elif re.match(r".*[Cc]reate.*", query):
            # If query contains 'create', suggest 'delete' functions
            delete_variant = re.sub(r"[Cc]reate", "delete", query)
            suggestions.extend(
                self._find_function_variants(
                    [delete_variant], "Corresponding delete function"
                )
            )

        # Look for similar named functions
        base_name = re.sub(r"[^a-zA-Z]", "", query.lower())
        if len(base_name) > 3:
            similar_functions = self._find_similar_named_functions(base_name)
            suggestions.extend(similar_functions)

        return suggestions

    def _get_cross_reference_suggestions(
        self, query: str, current_doc_id: int | None
    ) -> list[Suggestion]:
        """Get suggestions using cross-reference information."""
        suggestions = []

        if not current_doc_id:
            return suggestions

        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row

        try:
            cursor = conn.cursor()

            # Find cross-references from the current document
            cursor.execute(
                """
                SELECT cr.*, ds.content, ds.section_title, d.title
                FROM cross_references cr
                JOIN document_segments ds_source ON cr.source_segment_id = ds_source.id
                JOIN document_segments ds ON cr.target_segment_id = ds.id
                JOIN documents d ON ds.document_id = d.id
                WHERE ds_source.document_id = ? AND cr.reference_text LIKE ?
            """,
                (current_doc_id, f"%{query}%"),
            )

            refs = cursor.fetchall()

            for ref in refs:
                suggestions.append(
                    Suggestion(
                        identifier=ref["reference_text"],
                        type=ref["reference_type"],
                        document_id=ref["target_document_id"] or current_doc_id,
                        segment_id=ref["target_segment_id"],
                        title=ref["section_title"] or ref["title"],
                        description=(
                            ref["content"][:200]
                            if ref["content"]
                            else "Cross-referenced item"
                        ),
                        relevance_score=0.9,
                        reason="Cross-referenced in current document",
                    )
                )

        finally:
            conn.close()

        return suggestions

    def _get_category_based_suggestions(
        self, query: str, context: str | None
    ) -> list[Suggestion]:
        """Get suggestions based on task categories."""
        suggestions = []

        # Combine query and context for analysis
        full_text = f"{query} {context or ''}".lower()

        # Identify relevant categories
        for category, keywords in self.task_categories.items():
            if any(keyword in full_text for keyword in keywords):
                category_suggestions = self._get_suggestions_for_category(
                    category, query
                )
                suggestions.extend(category_suggestions)

        return suggestions

    def _get_suggestions_for_category(
        self, category: str, query: str
    ) -> list[Suggestion]:
        """Get suggestions for a specific task category."""
        suggestions = []

        # Get keywords for this category
        keywords = self.task_categories.get(category, [])

        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row

        try:
            cursor = conn.cursor()

            # Find segments related to this category
            for keyword in keywords[:3]:  # Limit to avoid too many queries
                cursor.execute(
                    """
                    SELECT ds.*, d.title, d.id as doc_id
                    FROM document_segments ds
                    JOIN documents d ON ds.document_id = d.id
                    WHERE ds.content LIKE ? OR ds.section_title LIKE ?
                    LIMIT 5
                """,
                    (f"%{keyword}%", f"%{keyword}%"),
                )

                segments = cursor.fetchall()

                for segment in segments:
                    identifiers = self._extract_identifiers_from_content(
                        segment["content"]
                    )

                    for identifier, id_type in identifiers[:2]:  # Limit per segment
                        suggestions.append(
                            Suggestion(
                                identifier=identifier,
                                type=id_type,
                                document_id=segment["doc_id"],
                                segment_id=segment["id"],
                                title=segment["section_title"] or segment["title"],
                                description=segment["content"][:200],
                                relevance_score=0.6,
                                reason=f"Related to {category}",
                            )
                        )

        finally:
            conn.close()

        return suggestions

    def _extract_identifiers_from_content(self, content: str) -> list[tuple[str, str]]:
        """Extract function/class identifiers from content."""
        identifiers = []

        # Function patterns
        for match in re.finditer(r"\b(\w+)\s*\(", content):
            func_name = match.group(1)
            if len(func_name) > 2 and not func_name[0].isupper():  # Skip classes
                identifiers.append((func_name, "function"))

        # Class patterns
        for match in re.finditer(r"\bclass\s+(\w+)", content):
            class_name = match.group(1)
            identifiers.append((class_name, "class"))

        # Method patterns
        for match in re.finditer(r"\.(\w+)\s*\(", content):
            method_name = match.group(1)
            if len(method_name) > 2:
                identifiers.append((method_name, "method"))

        # Module/package patterns
        for match in re.finditer(r"import\s+(\w+)", content):
            module_name = match.group(1)
            identifiers.append((module_name, "module"))

        return identifiers

    def _extract_functions_from_content(self, content: str) -> list[str]:
        """Extract function names from content."""
        functions = []

        # Various function call patterns
        patterns = [
            r"\b(\w+)\s*\(",  # function_name(
            r"\.(\w+)\s*\(",  # .method_name(
            r"`(\w+)\(\)`",  # `function_name()`
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, content):
                func_name = match.group(1)
                if len(func_name) > 2 and func_name not in [
                    "if",
                    "for",
                    "while",
                    "with",
                ]:
                    functions.append(func_name)

        return functions

    def _find_function_variants(
        self, variants: list[str], reason: str
    ) -> list[Suggestion]:
        """Find function variants in the database."""
        suggestions = []

        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row

        try:
            cursor = conn.cursor()

            for variant in variants:
                cursor.execute(
                    """
                    SELECT da.*, ds.content, d.title, d.id as doc_id
                    FROM document_anchors da
                    JOIN document_segments ds ON da.segment_id = ds.id
                    JOIN documents d ON da.document_id = d.id
                    WHERE da.anchor_name LIKE ?
                    LIMIT 3
                """,
                    (f"%{variant}%",),
                )

                results = cursor.fetchall()

                for result in results:
                    suggestions.append(
                        Suggestion(
                            identifier=result["anchor_name"],
                            type=result["anchor_type"],
                            document_id=result["doc_id"],
                            segment_id=result["segment_id"],
                            title=result["title"],
                            description=(
                                result["content"][:200] if result["content"] else ""
                            ),
                            relevance_score=0.8,
                            reason=reason,
                        )
                    )

        finally:
            conn.close()

        return suggestions

    def _find_similar_named_functions(self, base_name: str) -> list[Suggestion]:
        """Find functions with similar names."""
        suggestions = []

        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row

        try:
            cursor = conn.cursor()

            # Look for anchors with similar names
            cursor.execute(
                """
                SELECT da.*, ds.content, d.title, d.id as doc_id
                FROM document_anchors da
                JOIN document_segments ds ON da.segment_id = ds.id
                JOIN documents d ON da.document_id = d.id
                WHERE da.anchor_name LIKE ?
                LIMIT 5
            """,
                (f"%{base_name}%",),
            )

            results = cursor.fetchall()

            for result in results:
                # Calculate name similarity
                similarity = self._calculate_name_similarity(
                    base_name, result["anchor_name"].lower()
                )

                if similarity > 0.5:  # Only include reasonably similar names
                    suggestions.append(
                        Suggestion(
                            identifier=result["anchor_name"],
                            type=result["anchor_type"],
                            document_id=result["doc_id"],
                            segment_id=result["segment_id"],
                            title=result["title"],
                            description=(
                                result["content"][:200] if result["content"] else ""
                            ),
                            relevance_score=similarity * 0.7,
                            reason="Similar name pattern",
                        )
                    )

        finally:
            conn.close()

        return suggestions

    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names."""
        if name1 == name2:
            return 1.0

        # Simple similarity based on common characters and length
        common_chars = len(set(name1) & set(name2))
        total_chars = len(set(name1) | set(name2))

        if total_chars == 0:
            return 0.0

        return common_chars / total_chars

    def _deduplicate_suggestions(
        self, suggestions: list[Suggestion]
    ) -> list[Suggestion]:
        """Remove duplicate suggestions, keeping the highest scoring ones."""
        seen = {}

        for suggestion in suggestions:
            key = (suggestion.identifier, suggestion.type, suggestion.document_id)

            if (
                key not in seen
                or suggestion.relevance_score > seen[key].relevance_score
            ):
                seen[key] = suggestion

        return list(seen.values())
