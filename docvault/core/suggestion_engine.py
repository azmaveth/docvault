"""Suggestion engine for recommending related functions, classes, and modules."""

import asyncio
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass

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

        # Language/framework context mappings
        self.language_contexts = {
            "python": ["python", "py", "pip", "django", "flask", "pandas", "requests", "numpy"],
            "javascript": ["javascript", "js", "node", "npm", "react", "vue", "express", "axios"],
            "typescript": ["typescript", "ts", "node", "npm", "react", "vue", "express"],
            "java": ["java", "maven", "gradle", "spring", "hibernate", "junit"],
            "c#": ["csharp", "dotnet", "nuget", "asp.net", "entity"],
            "rust": ["rust", "cargo", "tokio", "serde", "actix"],
            "go": ["golang", "go", "mod", "gin", "gorilla"],
            "php": ["php", "composer", "laravel", "symfony", "psr"],
            "ruby": ["ruby", "gem", "rails", "sinatra", "rspec"],
        }

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
                "url",
                "response",
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

        # Detect language context from query
        language_context = self._detect_language_context(query)

        # Get suggestions from different sources
        suggestions.extend(self._get_semantic_suggestions(query, limit // 2))
        suggestions.extend(
            self._get_pattern_based_suggestions(query, current_document_id)
        )
        suggestions.extend(
            self._get_cross_reference_suggestions(query, current_document_id)
        )
        suggestions.extend(self._get_category_based_suggestions(query, context))

        # Apply language context filtering if detected
        if language_context:
            suggestions = self._filter_by_language_context(suggestions, language_context)

        # Remove duplicates and sort by relevance
        unique_suggestions = self._deduplicate_suggestions(suggestions)
        sorted_suggestions = sorted(
            unique_suggestions, key=lambda x: x.relevance_score, reverse=True
        )

        return sorted_suggestions[:limit]

    def _detect_language_context(self, query: str) -> str | None:
        """Detect programming language/framework context from query."""
        query_lower = query.lower()
        
        for language, keywords in self.language_contexts.items():
            if any(keyword in query_lower for keyword in keywords):
                return language
        
        return None

    def _filter_by_language_context(self, suggestions: list[Suggestion], target_language: str) -> list[Suggestion]:
        """Filter suggestions to prefer those from the target language context."""
        if not target_language:
            return suggestions
            
        language_keywords = self.language_contexts.get(target_language, [])
        
        # Score suggestions based on language relevance
        for suggestion in suggestions:
            content_lower = (suggestion.description + " " + suggestion.title).lower()
            
            # Boost score if content matches target language
            language_matches = sum(1 for keyword in language_keywords if keyword in content_lower)
            if language_matches > 0:
                # Boost score based on language matches
                suggestion.relevance_score = min(1.0, suggestion.relevance_score + (language_matches * 0.2))
                suggestion.reason = f"{suggestion.reason} (language: {target_language})"
            else:
                # Check if it's from a different language context
                other_language_matches = 0
                for other_lang, other_keywords in self.language_contexts.items():
                    if other_lang != target_language:
                        other_language_matches += sum(1 for keyword in other_keywords if keyword in content_lower)
                
                if other_language_matches > 0:
                    # Penalize suggestions from other languages
                    suggestion.relevance_score = max(0.1, suggestion.relevance_score - 0.3)
        
        return suggestions

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
        # Detect language context
        language_context = self._detect_language_context(task_description)
        
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

        # Apply language context filtering if detected
        if language_context:
            suggestions = self._filter_by_language_context(suggestions, language_context)

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
            # Detect language context to improve search
            language_context = self._detect_language_context(query)
            
            # Enhance query with language context if detected
            enhanced_query = query
            if language_context:
                # Add language context to search query for better targeting
                enhanced_query = f"{query} {language_context}"

            # Use existing search functionality to find related content
            results = asyncio.run(search_docs(enhanced_query, limit=limit * 2))

            for result in results:
                # Extract identifiers from the content
                identifiers = self._extract_identifiers_from_content(result["content"])

                for identifier, id_type in identifiers:
                    # Calculate better relevance score based on content quality
                    base_score = result["score"] * 0.8
                    
                    # Boost score if identifier matches query terms
                    query_words = query.lower().split()
                    if any(word in identifier.lower() for word in query_words):
                        base_score = min(1.0, base_score + 0.2)

                    suggestions.append(
                        Suggestion(
                            identifier=identifier,
                            type=id_type,
                            document_id=result["document_id"],
                            segment_id=result["id"],
                            title=result["title"],
                            description=result["content"][:200],
                            relevance_score=base_score,
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
        
        # Detect language context from query to improve search
        language_context = self._detect_language_context(query)
        
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row

        try:
            cursor = conn.cursor()

            # Combine query terms with category keywords for better targeting
            query_words = query.lower().split()
            
            # If we have language context, search for both query + language + category keywords
            if language_context:
                search_terms = query_words + [language_context] + keywords[:2]
            else:
                search_terms = query_words + keywords[:2]

            # Create search pattern that looks for multiple terms
            search_patterns = []
            for term in search_terms[:5]:  # Limit to avoid too complex queries
                search_patterns.append(f"%{term}%")
            
            # Build SQL query that prefers content with multiple matching terms
            sql_conditions = []
            sql_params = []
            
            for pattern in search_patterns:
                sql_conditions.append("(ds.content LIKE ? OR ds.section_title LIKE ? OR d.title LIKE ?)")
                sql_params.extend([pattern, pattern, pattern])
            
            # Execute query that finds segments with any of the terms
            cursor.execute(
                f"""
                SELECT ds.*, d.title, d.id as doc_id,
                       ({' + '.join(['CASE WHEN (ds.content LIKE ? OR ds.section_title LIKE ? OR d.title LIKE ?) THEN 1 ELSE 0 END' for _ in search_patterns])}) as match_count
                FROM document_segments ds
                JOIN documents d ON ds.document_id = d.id
                WHERE {' OR '.join(sql_conditions)}
                ORDER BY match_count DESC, d.title
                LIMIT 10
                """,
                sql_params * 2  # Parameters used twice: once for match_count, once for WHERE
            )

            segments = cursor.fetchall()

            for segment in segments:
                # Calculate relevance based on how many terms match
                match_count = segment.get("match_count", 1)
                base_relevance = min(0.9, 0.4 + (match_count * 0.15))
                
                identifiers = self._extract_identifiers_from_content(
                    segment["content"]
                )

                for identifier, id_type in identifiers[:3]:  # More identifiers from good matches
                    # Boost relevance if identifier matches query terms
                    identifier_relevance = base_relevance
                    if any(word in identifier.lower() for word in query_words):
                        identifier_relevance = min(1.0, identifier_relevance + 0.2)
                    
                    suggestions.append(
                        Suggestion(
                            identifier=identifier,
                            type=id_type,
                            document_id=segment["doc_id"],
                            segment_id=segment["id"],
                            title=segment["section_title"] or segment["title"],
                            description=segment["content"][:200],
                            relevance_score=identifier_relevance,
                            reason=f"Related to {category} (matches: {match_count} terms)",
                        )
                    )

        except Exception as e:
            logger.warning(f"Category-based search failed: {e}")
            # Fallback to simple search
            return self._simple_category_search(category, keywords[:2])
        finally:
            conn.close()

        return suggestions
    
    def _simple_category_search(self, category: str, keywords: list[str]) -> list[Suggestion]:
        """Fallback simple category search."""
        suggestions = []
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row

        try:
            cursor = conn.cursor()
            
            for keyword in keywords:
                cursor.execute(
                    """
                    SELECT ds.*, d.title, d.id as doc_id
                    FROM document_segments ds
                    JOIN documents d ON ds.document_id = d.id
                    WHERE ds.content LIKE ? OR ds.section_title LIKE ?
                    LIMIT 3
                """,
                    (f"%{keyword}%", f"%{keyword}%"),
                )

                segments = cursor.fetchall()
                
                for segment in segments:
                    identifiers = self._extract_identifiers_from_content(segment["content"])

                    for identifier, id_type in identifiers[:1]:
                        suggestions.append(
                            Suggestion(
                                identifier=identifier,
                                type=id_type,
                                document_id=segment["doc_id"],
                                segment_id=segment["id"],
                                title=segment["section_title"] or segment["title"],
                                description=segment["content"][:200],
                                relevance_score=0.5,
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
