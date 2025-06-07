"""
Vector-based document summarization using embeddings for intelligent content extraction.

This module uses vector similarity search to find the most relevant sections of a document
for creating concise, targeted summaries.
"""

import json
from typing import Dict, List, Optional, Tuple

from docvault import config
from docvault.db import operations
from docvault.db.operations import get_connection
from docvault.utils.logging import get_logger

logger = get_logger(__name__)


class VectorSummarizer:
    """Summarizes documents using vector similarity to find key sections."""

    # Query templates for finding important documentation sections
    SUMMARY_QUERIES = {
        "overview": [
            "introduction overview description purpose",
            "what is this library about",
            "getting started quickstart",
        ],
        "installation": [
            "installation setup install pip requirements",
            "how to install",
            "dependencies prerequisites",
        ],
        "functions": [
            "API functions methods interface",
            "function reference method signatures",
            "public API methods",
        ],
        "examples": [
            "code examples usage snippets",
            "how to use example code",
            "sample code demonstrations",
        ],
        "classes": [
            "class reference objects types",
            "class documentation interfaces",
            "object oriented API",
        ],
        "parameters": [
            "parameters arguments options configuration",
            "function parameters method arguments",
            "configuration options settings",
        ],
        "errors": [
            "error handling exceptions troubleshooting",
            "common errors issues problems",
            "debugging error messages",
        ],
    }

    def __init__(self, use_embeddings: bool = True):
        """Initialize the vector summarizer.

        Args:
            use_embeddings: Whether to use vector search (True) or fall back to text search
        """
        self.use_embeddings = use_embeddings
        self._check_embeddings_available()

    def _check_embeddings_available(self):
        """Check if embeddings are available and functional."""
        # For now, just check if Ollama URL is configured
        if not hasattr(config, "OLLAMA_URL") or not config.OLLAMA_URL:
            logger.warning("Ollama not configured, falling back to text search")
            self.use_embeddings = False

    def summarize_document(
        self, document_id: int, max_sections: int = 3
    ) -> dict[str, any]:
        """
        Generate a comprehensive summary of a document using vector search.

        Args:
            document_id: ID of the document to summarize
            max_sections: Maximum number of sections to include per category

        Returns:
            Dictionary containing categorized summary sections
        """
        summary = {
            "overview": [],
            "installation": [],
            "functions": [],
            "classes": [],
            "examples": [],
            "parameters": [],
            "key_sections": [],
            "metadata": {
                "document_id": document_id,
                "method": "vector" if self.use_embeddings else "text",
            },
        }

        # Get document info
        document = operations.get_document(document_id)
        if not document:
            return summary

        summary["metadata"]["title"] = document.get("title", "")
        summary["metadata"]["url"] = document.get("url", "")

        # Search for each category
        for category, queries in self.SUMMARY_QUERIES.items():
            sections = []

            for query in queries:
                # Search for relevant sections
                results = self._search_sections(
                    document_id=document_id, query=query, limit=max_sections
                )

                for result in results:
                    # Avoid duplicates
                    if not any(s["id"] == result["id"] for s in sections):
                        sections.append(
                            {
                                "id": result["id"],
                                "title": result.get("section_title", ""),
                                "content": result.get("content", ""),
                                "score": result.get("score", 0.0),
                                "path": result.get("section_path", ""),
                            }
                        )

                # Limit sections per category
                if len(sections) >= max_sections:
                    break

            # Sort by score and limit
            sections.sort(key=lambda x: x["score"], reverse=True)
            summary[category] = sections[:max_sections]

        # Get most relevant sections overall
        all_sections = []
        for category_sections in summary.values():
            if isinstance(category_sections, list):
                all_sections.extend(category_sections)

        # Deduplicate and get top sections
        seen_ids = set()
        unique_sections = []
        for section in sorted(
            all_sections, key=lambda x: x.get("score", 0), reverse=True
        ):
            if section.get("id") not in seen_ids:
                seen_ids.add(section.get("id"))
                unique_sections.append(section)

        summary["key_sections"] = unique_sections[:10]

        return summary

    def _search_sections(
        self, document_id: int, query: str, limit: int = 5
    ) -> list[dict]:
        """Search for relevant sections within a document.

        Args:
            document_id: Document to search within
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching sections with scores
        """
        if self.use_embeddings:
            return self._vector_search(document_id, query, limit)
        else:
            return self._text_search(document_id, query, limit)

    def _vector_search(self, document_id: int, query: str, limit: int) -> list[dict]:
        """Perform vector similarity search using existing search infrastructure."""
        try:
            # Import search function dynamically to avoid circular imports
            import asyncio

            from docvault.core.embeddings import search as embedding_search

            # Use the existing search function with document filter
            doc_filter = {"document_id": document_id}

            # Run async search in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    embedding_search(
                        query=query,
                        limit=limit,
                        text_only=False,  # Use embeddings
                        doc_filter=doc_filter,
                    )
                )
            finally:
                loop.close()

            # Transform results to our format
            return [
                {
                    "id": r.get("segment_id", r.get("id")),
                    "section_title": r.get("segment_title", r.get("title", "")),
                    "section_path": r.get("section_path", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0.5),
                }
                for r in results
            ]

        except Exception as e:
            logger.warning(f"Vector search failed: {e}, falling back to text search")
            return self._text_search(document_id, query, limit)

    def _text_search(self, document_id: int, query: str, limit: int) -> list[dict]:
        """Fallback text-based search."""
        with get_connection() as conn:
            # Simple text matching
            query_terms = query.lower().split()

            # Build search conditions
            conditions = []
            params = [document_id]

            for term in query_terms:
                conditions.append(
                    "(LOWER(content) LIKE ? OR LOWER(section_title) LIKE ?)"
                )
                params.extend([f"%{term}%", f"%{term}%"])

            if not conditions:
                return []

            query_sql = f"""
                SELECT
                    id,
                    section_title,
                    section_path,
                    content,
                    0.5 as score
                FROM document_segments
                WHERE document_id = ?
                    AND ({" OR ".join(conditions)})
                LIMIT ?
            """
            params.append(limit)

            results = conn.execute(query_sql, params).fetchall()

            return [
                {
                    "id": r["id"],
                    "section_title": r["section_title"],
                    "section_path": r["section_path"],
                    "content": r["content"],
                    "score": r["score"],
                }
                for r in results
            ]

    def format_summary(self, summary: dict, format: str = "markdown") -> str:
        """Format the vector-based summary for display.

        Args:
            summary: Summary dictionary from summarize_document
            format: Output format ('markdown' or 'text')

        Returns:
            Formatted summary string
        """
        if format == "markdown":
            output = []

            # Title and metadata
            title = summary["metadata"].get("title", "Document")
            output.append(f"# Summary of {title}\n")
            output.append(
                "*Generated using vector similarity search to find key sections*\n"
            )

            # Overview
            if summary.get("overview"):
                output.append("## Overview\n")
                for section in summary["overview"][:1]:  # Just the top overview
                    content = section["content"][:500]
                    if len(section["content"]) > 500:
                        content += "..."
                    output.append(f"{content}\n")

            # Installation
            if summary.get("installation"):
                output.append("## Installation\n")
                for section in summary["installation"][:1]:
                    content = section["content"][:300]
                    output.append(f"{content}\n")

            # Functions/API
            if summary.get("functions"):
                output.append("## Key Functions/Methods\n")
                for section in summary["functions"]:
                    if section["title"]:
                        output.append(f"### {section['title']}\n")
                    # Extract function signatures from content
                    content_lines = section["content"].split("\n")
                    for line in content_lines[:10]:  # First 10 lines
                        if any(
                            indicator in line
                            for indicator in ["(", "function", "def", "->"]
                        ):
                            output.append(f"`{line.strip()}`  ")
                output.append("")

            # Examples
            if summary.get("examples"):
                output.append("## Examples\n")
                for i, section in enumerate(summary["examples"], 1):
                    if section["title"]:
                        output.append(f"### {section['title']}\n")
                    else:
                        output.append(f"### Example {i}\n")
                    # Look for code blocks
                    content = section["content"]
                    if "```" in content:
                        # Extract first code block
                        parts = content.split("```")
                        if len(parts) >= 3:
                            output.append(f"```{parts[1].split('\\n', 1)[0]}")
                            code = (
                                parts[1].split("\\n", 1)[1]
                                if "\\n" in parts[1]
                                else parts[1]
                            )
                            output.append(f"{code[:300]}...")
                            output.append("```\n")
                    else:
                        output.append(f"{content[:200]}...\n")

            # Key sections
            if summary.get("key_sections"):
                output.append("## Additional Key Sections\n")
                for section in summary["key_sections"][:5]:
                    if section["title"] and section["path"]:
                        output.append(
                            f"- **{section['title']}** (section {section['path']})"
                        )

            return "\n".join(output)

        else:  # text format
            output = []
            title = summary["metadata"].get("title", "Document")
            output.append(f"SUMMARY OF: {title}")
            output.append(f"METHOD: {summary['metadata'].get('method', 'unknown')}")
            output.append("")

            for category, sections in summary.items():
                if category != "metadata" and sections:
                    output.append(f"{category.upper()}:")
                    for section in sections[:2]:
                        output.append(f"  - {section.get('title', 'Untitled')}")
                        content = section.get("content", "")[:100].replace("\n", " ")
                        output.append(f"    {content}...")
                    output.append("")

            return "\n".join(output)
