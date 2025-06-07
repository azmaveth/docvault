"""
Section indexing system for efficient navigation and search.

This module provides optimized section-to-chunk mapping and search capabilities
for quick content location and navigation.
"""

import json
from dataclasses import dataclass

from docvault.core.content_chunker import ChunkingStrategy, ContentChunker
from docvault.db.operations import get_connection
from docvault.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SectionIndex:
    """Index entry for a section."""

    section_id: int
    section_path: str
    section_title: str
    start_position: int
    end_position: int
    chunk_numbers: list[int]  # Which chunks contain this section
    primary_chunk: int  # Main chunk for this section


class SectionIndexer:
    """Build and query section indexes for efficient navigation."""

    def __init__(self, document_id: int):
        """Initialize indexer for a document.

        Args:
            document_id: Document to index
        """
        self.document_id = document_id
        self._index_cache = None
        self._chunk_map_cache = None

    def build_index(
        self,
        chunk_size: int = 5000,
        strategy: ChunkingStrategy = ChunkingStrategy.SECTION,
    ) -> dict[str, SectionIndex]:
        """Build a complete section index for the document.

        Args:
            chunk_size: Size of chunks to use
            strategy: Chunking strategy

        Returns:
            Dictionary mapping section paths to index entries
        """
        if self._index_cache and self._chunk_map_cache:
            return self._index_cache

        index = {}
        ContentChunker(self.document_id)

        # Get all sections
        with get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    id,
                    section_title,
                    section_path,
                    content,
                    LENGTH(content) as content_length
                FROM document_segments
                WHERE document_id = ?
                ORDER BY section_path
            """,
                (self.document_id,),
            )

            sections = cursor.fetchall()

        if not sections:
            return index

        # Build chunk mapping
        chunk_map = {}  # chunk_number -> [section_paths]
        section_positions = {}  # section_path -> (start, end)

        # For section-based chunking
        if strategy == ChunkingStrategy.SECTION:
            # Group sections into chunks
            current_chunk = []
            current_size = 0
            chunk_number = 1
            position = 0

            for section in sections:
                section_size = section["content_length"]
                section_path = section["section_path"]

                # Track position
                section_positions[section_path] = (position, position + section_size)

                # Check if we need a new chunk
                if current_size + section_size > chunk_size and current_chunk:
                    # Record chunk mapping
                    chunk_map[chunk_number] = [s["section_path"] for s in current_chunk]

                    # Start new chunk
                    chunk_number += 1
                    current_chunk = [section]
                    current_size = section_size
                else:
                    current_chunk.append(section)
                    current_size += section_size

                position += section_size

            # Add final chunk
            if current_chunk:
                chunk_map[chunk_number] = [s["section_path"] for s in current_chunk]

        else:
            # For other strategies, calculate which chunks contain each section
            # This is more approximate but still useful
            total_size = sum(s["content_length"] for s in sections)
            total_chunks = (total_size + chunk_size - 1) // chunk_size

            position = 0
            for section in sections:
                section_size = section["content_length"]
                section_path = section["section_path"]

                # Calculate which chunks this section spans
                start_chunk = (position // chunk_size) + 1
                end_chunk = ((position + section_size - 1) // chunk_size) + 1

                section_positions[section_path] = (position, position + section_size)

                # Add to chunk map
                for chunk_num in range(
                    start_chunk, min(end_chunk + 1, total_chunks + 1)
                ):
                    if chunk_num not in chunk_map:
                        chunk_map[chunk_num] = []
                    chunk_map[chunk_num].append(section_path)

                position += section_size

        # Build index entries
        for section in sections:
            path = section["section_path"]

            # Find which chunks contain this section
            containing_chunks = []
            primary_chunk = None

            for chunk_num, section_paths in chunk_map.items():
                if path in section_paths:
                    containing_chunks.append(chunk_num)
                    if primary_chunk is None:
                        primary_chunk = chunk_num

            # Get positions
            start_pos, end_pos = section_positions.get(path, (0, 0))

            index[path] = SectionIndex(
                section_id=section["id"],
                section_path=path,
                section_title=section["section_title"] or "",
                start_position=start_pos,
                end_position=end_pos,
                chunk_numbers=containing_chunks,
                primary_chunk=primary_chunk or 1,
            )

        self._index_cache = index
        self._chunk_map_cache = chunk_map

        return index

    def find_section_chunk(
        self,
        section_path: str,
        chunk_size: int = 5000,
        strategy: ChunkingStrategy = ChunkingStrategy.SECTION,
    ) -> int | None:
        """Find the primary chunk number for a section.

        Args:
            section_path: Path of the section
            chunk_size: Chunk size being used
            strategy: Chunking strategy

        Returns:
            Chunk number containing this section, or None
        """
        index = self.build_index(chunk_size, strategy)

        if section_path in index:
            return index[section_path].primary_chunk

        return None

    def find_sections_in_chunk(
        self,
        chunk_number: int,
        chunk_size: int = 5000,
        strategy: ChunkingStrategy = ChunkingStrategy.SECTION,
    ) -> list[str]:
        """Find all sections in a specific chunk.

        Args:
            chunk_number: Chunk to query
            chunk_size: Chunk size being used
            strategy: Chunking strategy

        Returns:
            List of section paths in this chunk
        """
        self.build_index(chunk_size, strategy)

        if self._chunk_map_cache and chunk_number in self._chunk_map_cache:
            return self._chunk_map_cache[chunk_number]

        return []

    def search_sections(
        self,
        query: str,
        search_type: str = "all",
        limit: int = 10,
        chunk_size: int = 5000,
        strategy: ChunkingStrategy = ChunkingStrategy.SECTION,
    ) -> list[dict]:
        """Search sections and return with chunk information.

        Args:
            query: Search query
            search_type: Type of search (all, code, headings, examples, content)
            limit: Maximum results
            chunk_size: Chunk size for navigation
            strategy: Chunking strategy

        Returns:
            List of search results with chunk information
        """
        # Build index first
        index = self.build_index(chunk_size, strategy)

        # Build search conditions
        conditions = []
        params = [self.document_id]

        if search_type == "code":
            conditions.append(
                """
                (content LIKE '%```%' OR content LIKE '%code%' OR
                 content LIKE '%def %' OR content LIKE '%function %' OR
                 content LIKE '%class %')
            """
            )
        elif search_type == "headings":
            conditions.append("LOWER(section_title) LIKE ?")
            params.append(f"%{query.lower()}%")
        elif search_type == "examples":
            conditions.append(
                """
                (LOWER(section_title) LIKE '%example%' OR
                 LOWER(content) LIKE '%example:%' OR
                 LOWER(content) LIKE '%usage:%')
            """
            )

        # Add content search for non-heading searches
        if search_type != "headings":
            conditions.append("LOWER(content) LIKE ?")
            params.append(f"%{query.lower()}%")

        # Execute search
        with get_connection() as conn:
            query_sql = f"""
                SELECT
                    id,
                    section_title,
                    section_path,
                    content
                FROM document_segments
                WHERE document_id = ?
                    AND ({" AND ".join(conditions) if conditions else "1=1"})
                ORDER BY
                    CASE
                        WHEN LOWER(section_title) LIKE ? THEN 0
                        ELSE 1
                    END,
                    section_path
                LIMIT ?
            """
            params.extend([f"%{query.lower()}%", limit])

            cursor = conn.execute(query_sql, params)
            results = cursor.fetchall()

        # Enhance results with chunk information
        enhanced_results = []
        for result in results:
            section_path = result["section_path"]

            # Get index entry
            index_entry = index.get(section_path)

            enhanced_results.append(
                {
                    "id": result["id"],
                    "section_title": result["section_title"],
                    "section_path": section_path,
                    "content_preview": result["content"][:200],
                    "chunk_number": index_entry.primary_chunk if index_entry else None,
                    "chunk_numbers": index_entry.chunk_numbers if index_entry else [],
                    "spans_chunks": (
                        len(index_entry.chunk_numbers) > 1 if index_entry else False
                    ),
                }
            )

        return enhanced_results

    def get_navigation_info(
        self,
        section_path: str,
        chunk_size: int = 5000,
        strategy: ChunkingStrategy = ChunkingStrategy.SECTION,
    ) -> dict:
        """Get detailed navigation information for a section.

        Args:
            section_path: Section to get info for
            chunk_size: Chunk size being used
            strategy: Chunking strategy

        Returns:
            Navigation information including chunks and neighbors
        """
        index = self.build_index(chunk_size, strategy)

        if section_path not in index:
            return {}

        entry = index[section_path]

        # Find previous and next sections
        sorted_paths = sorted(index.keys())
        current_idx = sorted_paths.index(section_path)

        prev_section = sorted_paths[current_idx - 1] if current_idx > 0 else None
        next_section = (
            sorted_paths[current_idx + 1]
            if current_idx < len(sorted_paths) - 1
            else None
        )

        return {
            "section_path": section_path,
            "section_title": entry.section_title,
            "primary_chunk": entry.primary_chunk,
            "all_chunks": entry.chunk_numbers,
            "spans_multiple_chunks": len(entry.chunk_numbers) > 1,
            "prev_section": (
                {
                    "path": prev_section,
                    "title": (
                        index[prev_section].section_title if prev_section else None
                    ),
                    "chunk": (
                        index[prev_section].primary_chunk if prev_section else None
                    ),
                }
                if prev_section
                else None
            ),
            "next_section": (
                {
                    "path": next_section,
                    "title": (
                        index[next_section].section_title if next_section else None
                    ),
                    "chunk": (
                        index[next_section].primary_chunk if next_section else None
                    ),
                }
                if next_section
                else None
            ),
        }
