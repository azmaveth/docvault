"""
Section navigation utilities for hierarchical document traversal.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from docvault.db.operations import get_connection


@dataclass
class SectionNode:
    """Represents a section in the document hierarchy."""

    id: int
    section_title: str
    section_level: int
    section_path: str
    parent_segment_id: int | None
    content_preview: str
    children: list["SectionNode"] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


class SectionNavigator:
    """Navigate and traverse document sections hierarchically."""

    def __init__(self, document_id: int):
        """Initialize navigator for a specific document."""
        self.document_id = document_id
        self._sections_cache = None
        self._root_sections = None

    def get_table_of_contents(self) -> list[SectionNode]:
        """
        Get the table of contents as a hierarchical tree structure.

        Returns:
            List of root-level sections with nested children
        """
        if self._root_sections is not None:
            return self._root_sections

        # Fetch all sections for the document
        sections = self._fetch_all_sections()

        # Build hierarchical structure
        section_map = {
            s["id"]: SectionNode(
                id=s["id"],
                section_title=s["section_title"] or f"Section {s['section_path']}",
                section_level=s["section_level"],
                section_path=s["section_path"],
                parent_segment_id=s["parent_segment_id"],
                content_preview=self._create_preview(s["content"]),
            )
            for s in sections
        }

        # Link parent-child relationships
        root_sections = []
        for section in section_map.values():
            if section.parent_segment_id and section.parent_segment_id in section_map:
                parent = section_map[section.parent_segment_id]
                parent.children.append(section)
            elif section.parent_segment_id is None:
                root_sections.append(section)

        # Sort sections by path for consistent ordering
        self._sort_sections_by_path(root_sections)

        self._root_sections = root_sections
        return root_sections

    def get_section_by_path(self, section_path: str) -> SectionNode | None:
        """
        Get a section by its path (e.g., "1.2.3").

        Args:
            section_path: Dot-separated section path

        Returns:
            SectionNode if found, None otherwise
        """
        sections = self._get_all_sections_flat()
        for section in sections:
            if section.section_path == section_path:
                return section
        return None

    def get_section_children(self, id: int) -> list[SectionNode]:
        """
        Get all direct children of a section.

        Args:
            id: ID of the parent segment

        Returns:
            List of child sections
        """
        sections = self._get_all_sections_flat()
        children = [s for s in sections if s.parent_segment_id == id]
        self._sort_sections_by_path(children)
        return children

    def get_section_ancestors(self, id: int) -> list[SectionNode]:
        """
        Get all ancestors of a section (from root to parent).

        Args:
            id: ID of the segment

        Returns:
            List of ancestor sections from root to immediate parent
        """
        sections_map = {s.id: s for s in self._get_all_sections_flat()}

        ancestors = []
        current = sections_map.get(id)

        while current and current.parent_segment_id:
            parent = sections_map.get(current.parent_segment_id)
            if parent:
                ancestors.insert(0, parent)
                current = parent
            else:
                break

        return ancestors

    def get_section_siblings(self, id: int) -> list[SectionNode]:
        """
        Get all sibling sections (same parent).

        Args:
            id: ID of the segment

        Returns:
            List of sibling sections (excluding self)
        """
        sections_map = {s.id: s for s in self._get_all_sections_flat()}
        section = sections_map.get(id)

        if not section:
            return []

        siblings = [
            s
            for s in sections_map.values()
            if s.parent_segment_id == section.parent_segment_id and s.id != id
        ]
        self._sort_sections_by_path(siblings)
        return siblings

    def get_section_subtree(self, id: int) -> SectionNode | None:
        """
        Get a section with all its descendants as a subtree.

        Args:
            id: ID of the root segment

        Returns:
            SectionNode with populated children, or None if not found
        """
        # Build full TOC to ensure relationships are established
        self.get_table_of_contents()

        # Find the section in the tree
        sections_map = {s.id: s for s in self._get_all_sections_flat()}
        return sections_map.get(id)

    def find_sections_by_title(self, title_pattern: str) -> list[SectionNode]:
        """
        Find sections whose titles match a pattern (case-insensitive).

        Args:
            title_pattern: Pattern to search for in titles

        Returns:
            List of matching sections
        """
        pattern_lower = title_pattern.lower()
        sections = self._get_all_sections_flat()

        matches = [
            s
            for s in sections
            if s.section_title and pattern_lower in s.section_title.lower()
        ]
        self._sort_sections_by_path(matches)
        return matches

    def _fetch_all_sections(self) -> list[dict]:
        """Fetch all sections from database."""
        if self._sections_cache is not None:
            return self._sections_cache

        with get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    id,
                    section_title,
                    section_level,
                    section_path,
                    parent_segment_id,
                    content
                FROM document_segments
                WHERE document_id = ?
                AND section_level IS NOT NULL
                ORDER BY section_path
            """,
                (self.document_id,),
            )

            self._sections_cache = [dict(row) for row in cursor.fetchall()]
            return self._sections_cache

    def _get_all_sections_flat(self) -> list[SectionNode]:
        """Get all sections as a flat list."""
        # Ensure TOC is built
        self.get_table_of_contents()

        # Flatten the tree
        sections = []

        def traverse(nodes: list[SectionNode]):
            for node in nodes:
                sections.append(node)
                if node.children:
                    traverse(node.children)

        traverse(self._root_sections)
        return sections

    def _create_preview(self, content: str, max_length: int = 100) -> str:
        """Create a preview of section content."""
        if not content:
            return ""

        # Clean up the content
        preview = content.strip()

        # Remove markdown formatting for cleaner preview
        import re

        preview = re.sub(r"[#*`_\[\]()]", "", preview)
        preview = re.sub(r"\s+", " ", preview)

        if len(preview) > max_length:
            preview = preview[:max_length] + "..."

        return preview

    def _sort_sections_by_path(self, sections: list[SectionNode]) -> None:
        """Sort sections by their path for consistent ordering."""
        sections.sort(key=lambda s: [int(p) for p in s.section_path.split(".")])


def get_document_toc(document_id: int) -> list[dict]:
    """
    Get table of contents for a document as a structured dictionary.

    Args:
        document_id: ID of the document

    Returns:
        List of dictionaries representing the TOC hierarchy
    """
    navigator = SectionNavigator(document_id)
    toc_nodes = navigator.get_table_of_contents()

    def node_to_dict(node: SectionNode) -> dict:
        return {
            "id": node.id,
            "title": node.section_title,
            "level": node.section_level,
            "path": node.section_path,
            "preview": node.content_preview,
            "children": [node_to_dict(child) for child in node.children],
        }

    return [node_to_dict(node) for node in toc_nodes]


def get_section_content(document_id: int, section_path: str) -> dict | None:
    """
    Get full content of a section and its children.

    Args:
        document_id: ID of the document
        section_path: Path of the section (e.g., "1.2")

    Returns:
        Dictionary with section info and content, or None if not found
    """
    with get_connection() as conn:
        # Get the section and all its descendants
        cursor = conn.execute(
            """
            SELECT 
                id,
                section_title,
                section_level,
                section_path,
                content,
                segment_type
            FROM document_segments
            WHERE document_id = ?
            AND (section_path = ? OR section_path LIKE ?)
            ORDER BY section_path
        """,
            (document_id, section_path, f"{section_path}.%"),
        )

        segments = cursor.fetchall()
        if not segments:
            return None

        # Build the response
        main_section = dict(segments[0])

        # Collect all content
        full_content = []
        for segment in segments:
            segment_dict = dict(segment)
            full_content.append(
                {
                    "path": segment_dict["section_path"],
                    "title": segment_dict["section_title"],
                    "level": segment_dict["section_level"],
                    "content": segment_dict["content"],
                    "type": segment_dict["segment_type"],
                }
            )

        return {
            "id": main_section["id"],
            "title": main_section["section_title"],
            "path": main_section["section_path"],
            "level": main_section["section_level"],
            "segments": full_content,
        }
