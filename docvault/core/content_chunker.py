"""
Advanced content chunking system with section-awareness, semantic boundaries, and streaming support.

This module provides sophisticated chunking strategies that respect content structure
and natural boundaries, unlike simple character-based splitting.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

from docvault.core.section_navigator import SectionNavigator, get_section_content
from docvault.db import operations
from docvault.db.operations import get_connection
from docvault.utils.logging import get_logger

logger = get_logger(__name__)


class ChunkingStrategy(Enum):
    """Available chunking strategies."""

    CHARACTER = "character"  # Simple character-based (legacy)
    SECTION = "section"  # Section-aware chunking
    SEMANTIC = "semantic"  # Natural boundary chunking
    PARAGRAPH = "paragraph"  # Paragraph-based chunking
    HYBRID = "hybrid"  # Combination of section and semantic


@dataclass
class ChunkMetadata:
    """Metadata for a content chunk."""

    chunk_number: int
    total_chunks: int
    start_position: int
    end_position: int
    section_path: str | None = None
    section_title: str | None = None
    has_next: bool = False
    has_prev: bool = False
    next_section: str | None = None
    prev_section: str | None = None
    strategy_used: str = "character"


@dataclass
class ContentChunk:
    """A chunk of content with metadata."""

    content: str
    metadata: ChunkMetadata

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "content": self.content,
            "metadata": {
                "chunk_number": self.metadata.chunk_number,
                "total_chunks": self.metadata.total_chunks,
                "start_position": self.metadata.start_position,
                "end_position": self.metadata.end_position,
                "section_path": self.metadata.section_path,
                "section_title": self.metadata.section_title,
                "has_next": self.metadata.has_next,
                "has_prev": self.metadata.has_prev,
                "next_section": self.metadata.next_section,
                "prev_section": self.metadata.prev_section,
                "strategy_used": self.metadata.strategy_used,
            },
        }


class ContentChunker:
    """Advanced content chunking with multiple strategies."""

    # Regex patterns for semantic boundaries
    SEMANTIC_BOUNDARIES = {
        "heading": re.compile(r"^#{1,6}\s+.*$", re.MULTILINE),
        "code_block": re.compile(r"^```.*?```", re.MULTILINE | re.DOTALL),
        "paragraph": re.compile(r"\n\s*\n"),
        "list_item": re.compile(r"^\s*[-*+]\s+", re.MULTILINE),
        "numbered_item": re.compile(r"^\s*\d+\.\s+", re.MULTILINE),
        "horizontal_rule": re.compile(r"^---+$|^___+$|^\*\*\*+$", re.MULTILINE),
    }

    def __init__(self, document_id: int):
        """Initialize chunker for a specific document.

        Args:
            document_id: ID of the document to chunk
        """
        self.document_id = document_id
        self._document = None
        self._sections = None
        self._content = None

    def get_chunk(
        self,
        chunk_number: int = 1,
        chunk_size: int = 5000,
        strategy: ChunkingStrategy | str = ChunkingStrategy.HYBRID,
        respect_code_blocks: bool = True,
        min_chunk_size: int = 1000,
    ) -> ContentChunk:
        """Get a specific chunk of the document.

        Args:
            chunk_number: Which chunk to retrieve (1-based)
            chunk_size: Target size for each chunk
            strategy: Chunking strategy to use
            respect_code_blocks: Don't split code blocks
            min_chunk_size: Minimum size before forcing a split

        Returns:
            ContentChunk with content and metadata
        """
        if isinstance(strategy, str):
            strategy = ChunkingStrategy(strategy)

        # Load document if needed
        if not self._document:
            self._load_document()

        # Route to appropriate chunking method
        if strategy == ChunkingStrategy.CHARACTER:
            return self._character_chunk(chunk_number, chunk_size)
        elif strategy == ChunkingStrategy.SECTION:
            return self._section_chunk(chunk_number, chunk_size)
        elif strategy == ChunkingStrategy.SEMANTIC:
            return self._semantic_chunk(chunk_number, chunk_size, respect_code_blocks)
        elif strategy == ChunkingStrategy.PARAGRAPH:
            return self._paragraph_chunk(chunk_number, chunk_size)
        else:  # HYBRID
            return self._hybrid_chunk(chunk_number, chunk_size, respect_code_blocks)

    def stream_chunks(
        self,
        chunk_size: int = 5000,
        strategy: ChunkingStrategy | str = ChunkingStrategy.HYBRID,
        overlap: int = 200,
    ) -> Iterator[ContentChunk]:
        """Stream chunks without loading entire document into memory.

        Args:
            chunk_size: Target size for each chunk
            strategy: Chunking strategy to use
            overlap: Number of characters to overlap between chunks

        Yields:
            ContentChunk objects
        """
        if isinstance(strategy, str):
            strategy = ChunkingStrategy(strategy)

        # For streaming, we'll read the file in blocks
        document = operations.get_document(self.document_id)
        if not document:
            return

        # Get file path directly from document
        file_path = document["markdown_path"]

        try:
            with open(file_path, encoding="utf-8") as f:
                chunk_number = 1
                buffer = ""
                position = 0

                while True:
                    # Read a block
                    block = f.read(chunk_size)
                    if not block:
                        # Yield final chunk if buffer has content
                        if buffer:
                            yield ContentChunk(
                                content=buffer,
                                metadata=ChunkMetadata(
                                    chunk_number=chunk_number,
                                    total_chunks=chunk_number,
                                    start_position=position - len(buffer),
                                    end_position=position,
                                    has_next=False,
                                    has_prev=chunk_number > 1,
                                    strategy_used="streaming",
                                ),
                            )
                        break

                    buffer += block

                    # Find appropriate break point
                    break_point = self._find_break_point(buffer, chunk_size, strategy)

                    if break_point > 0:
                        # Yield chunk
                        chunk_content = buffer[:break_point]
                        yield ContentChunk(
                            content=chunk_content,
                            metadata=ChunkMetadata(
                                chunk_number=chunk_number,
                                total_chunks=-1,  # Unknown in streaming
                                start_position=position - len(buffer),
                                end_position=position - len(buffer) + break_point,
                                has_next=True,
                                has_prev=chunk_number > 1,
                                strategy_used="streaming",
                            ),
                        )

                        # Keep overlap
                        if overlap > 0 and len(buffer) > break_point:
                            buffer = buffer[break_point - overlap :]
                        else:
                            buffer = buffer[break_point:]

                        chunk_number += 1

                    position += len(block)

        except Exception as e:
            logger.error(f"Error streaming chunks: {e}")

    def _load_document(self):
        """Load document and metadata."""
        self._document = operations.get_document(self.document_id)
        if not self._document:
            raise ValueError(f"Document {self.document_id} not found")

        # Load content
        from docvault.core.storage import read_markdown

        self._content = read_markdown(self._document["markdown_path"])

        # Load sections
        try:
            navigator = SectionNavigator(self.document_id)
            self._sections = navigator.get_table_of_contents()
        except Exception as e:
            logger.warning(f"Failed to load sections: {e}")
            self._sections = []

    def _character_chunk(self, chunk_number: int, chunk_size: int) -> ContentChunk:
        """Simple character-based chunking (legacy method)."""
        if not self._content:
            self._load_document()

        total_length = len(self._content)
        total_chunks = (total_length + chunk_size - 1) // chunk_size

        if chunk_number < 1 or chunk_number > total_chunks:
            raise ValueError(
                f"Invalid chunk number {chunk_number}. Valid range: 1-{total_chunks}"
            )

        start = (chunk_number - 1) * chunk_size
        end = min(start + chunk_size, total_length)

        return ContentChunk(
            content=self._content[start:end],
            metadata=ChunkMetadata(
                chunk_number=chunk_number,
                total_chunks=total_chunks,
                start_position=start,
                end_position=end,
                has_next=chunk_number < total_chunks,
                has_prev=chunk_number > 1,
                strategy_used="character",
            ),
        )

    def _section_chunk(self, chunk_number: int, chunk_size: int) -> ContentChunk:
        """Section-aware chunking."""
        with get_connection() as conn:
            # Get all sections ordered by path
            cursor = conn.execute(
                """
                SELECT id, section_title, section_path, content,
                       LENGTH(content) as content_length
                FROM document_segments
                WHERE document_id = ?
                ORDER BY section_path
            """,
                (self.document_id,),
            )

            sections = cursor.fetchall()

        if not sections:
            # Fall back to character chunking
            return self._character_chunk(chunk_number, chunk_size)

        # Group sections into chunks
        chunks = []
        current_chunk = []
        current_size = 0

        for section in sections:
            section_size = section["content_length"]

            # If adding this section would exceed chunk size
            if current_size + section_size > chunk_size and current_chunk:
                chunks.append(current_chunk)
                current_chunk = [section]
                current_size = section_size
            else:
                current_chunk.append(section)
                current_size += section_size

        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk)

        # Validate chunk number
        if chunk_number < 1 or chunk_number > len(chunks):
            raise ValueError(
                f"Invalid chunk number {chunk_number}. Valid range: 1-{len(chunks)}"
            )

        # Build chunk content
        chunk_sections = chunks[chunk_number - 1]
        content_parts = []

        for section in chunk_sections:
            if section["section_title"]:
                # Add section heading
                level = len(section["section_path"].split("."))
                content_parts.append(f"{'#' * level} {section['section_title']}\n\n")
            content_parts.append(section["content"])
            content_parts.append("\n\n")

        content = "".join(content_parts).strip()

        # Get metadata
        first_section = chunk_sections[0]
        last_section = chunk_sections[-1]

        # Find next/prev sections
        next_section = None
        prev_section = None

        if chunk_number > 1:
            prev_chunk = chunks[chunk_number - 2]
            prev_section = prev_chunk[-1]["section_path"]

        if chunk_number < len(chunks):
            next_chunk = chunks[chunk_number]
            next_section = next_chunk[0]["section_path"]

        return ContentChunk(
            content=content,
            metadata=ChunkMetadata(
                chunk_number=chunk_number,
                total_chunks=len(chunks),
                start_position=0,  # Not applicable for section chunks
                end_position=len(content),
                section_path=f"{first_section['section_path']}-{last_section['section_path']}",
                section_title=first_section["section_title"],
                has_next=chunk_number < len(chunks),
                has_prev=chunk_number > 1,
                next_section=next_section,
                prev_section=prev_section,
                strategy_used="section",
            ),
        )

    def _semantic_chunk(
        self, chunk_number: int, chunk_size: int, respect_code_blocks: bool = True
    ) -> ContentChunk:
        """Semantic chunking that respects natural boundaries."""
        if not self._content:
            self._load_document()

        # Find all semantic boundaries
        boundaries = self._find_semantic_boundaries(self._content, respect_code_blocks)

        # Create chunks based on boundaries
        chunks = self._create_semantic_chunks(self._content, boundaries, chunk_size)

        if chunk_number < 1 or chunk_number > len(chunks):
            raise ValueError(
                f"Invalid chunk number {chunk_number}. Valid range: 1-{len(chunks)}"
            )

        chunk_start, chunk_end = chunks[chunk_number - 1]
        content = self._content[chunk_start:chunk_end].strip()

        return ContentChunk(
            content=content,
            metadata=ChunkMetadata(
                chunk_number=chunk_number,
                total_chunks=len(chunks),
                start_position=chunk_start,
                end_position=chunk_end,
                has_next=chunk_number < len(chunks),
                has_prev=chunk_number > 1,
                strategy_used="semantic",
            ),
        )

    def _paragraph_chunk(self, chunk_number: int, chunk_size: int) -> ContentChunk:
        """Paragraph-based chunking."""
        if not self._content:
            self._load_document()

        # Split into paragraphs
        paragraphs = self._content.split("\n\n")

        # Group paragraphs into chunks
        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para)

            if current_size + para_size > chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size + 2  # +2 for \n\n

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        if chunk_number < 1 or chunk_number > len(chunks):
            raise ValueError(
                f"Invalid chunk number {chunk_number}. Valid range: 1-{len(chunks)}"
            )

        content = chunks[chunk_number - 1]

        return ContentChunk(
            content=content,
            metadata=ChunkMetadata(
                chunk_number=chunk_number,
                total_chunks=len(chunks),
                start_position=0,
                end_position=len(content),
                has_next=chunk_number < len(chunks),
                has_prev=chunk_number > 1,
                strategy_used="paragraph",
            ),
        )

    def _hybrid_chunk(
        self, chunk_number: int, chunk_size: int, respect_code_blocks: bool = True
    ) -> ContentChunk:
        """Hybrid chunking combining section and semantic awareness."""
        # First try section-based chunking
        try:
            section_chunk = self._section_chunk(chunk_number, chunk_size)

            # If section chunk is too large, apply semantic chunking to it
            if len(section_chunk.content) > chunk_size * 1.5:
                # Apply semantic boundaries within the section
                boundaries = self._find_semantic_boundaries(
                    section_chunk.content, respect_code_blocks
                )
                self._create_semantic_chunks(
                    section_chunk.content, boundaries, chunk_size
                )

                # Adjust metadata
                section_chunk.metadata.strategy_used = "hybrid"

            return section_chunk

        except Exception as e:
            logger.warning(f"Hybrid chunking fell back to semantic: {e}")
            # Fall back to pure semantic chunking
            return self._semantic_chunk(chunk_number, chunk_size, respect_code_blocks)

    def _find_semantic_boundaries(
        self, content: str, respect_code_blocks: bool = True
    ) -> list[int]:
        """Find positions of semantic boundaries in content."""
        boundaries = [0]  # Start of content

        # Find code blocks first if respecting them
        code_blocks = []
        if respect_code_blocks:
            for match in self.SEMANTIC_BOUNDARIES["code_block"].finditer(content):
                code_blocks.append((match.start(), match.end()))

        # Find other boundaries
        for boundary_type, pattern in self.SEMANTIC_BOUNDARIES.items():
            if boundary_type == "code_block":
                continue

            for match in pattern.finditer(content):
                pos = match.start()

                # Skip if inside a code block
                if respect_code_blocks:
                    inside_code = any(start <= pos <= end for start, end in code_blocks)
                    if inside_code:
                        continue

                boundaries.append(pos)

        boundaries.append(len(content))  # End of content

        # Sort and deduplicate
        boundaries = sorted(set(boundaries))

        return boundaries

    def _create_semantic_chunks(
        self, content: str, boundaries: list[int], chunk_size: int
    ) -> list[tuple[int, int]]:
        """Create chunks based on semantic boundaries."""
        chunks = []
        current_start = 0

        for i in range(1, len(boundaries)):
            boundary = boundaries[i]

            # If we've exceeded chunk size, create a chunk
            if boundary - current_start >= chunk_size:
                # Find the best boundary to break at
                best_boundary = current_start
                for j in range(i - 1, 0, -1):
                    if boundaries[j] - current_start <= chunk_size:
                        best_boundary = boundaries[j]
                        break

                if best_boundary > current_start:
                    chunks.append((current_start, best_boundary))
                    current_start = best_boundary
                else:
                    # No good boundary found, force break at chunk_size
                    chunks.append((current_start, current_start + chunk_size))
                    current_start = current_start + chunk_size

        # Add final chunk
        if current_start < len(content):
            chunks.append((current_start, len(content)))

        return chunks

    def _find_break_point(
        self, buffer: str, chunk_size: int, strategy: ChunkingStrategy
    ) -> int:
        """Find the best point to break the buffer for streaming."""
        if len(buffer) < chunk_size:
            return -1  # Need more data

        # Look for natural break points
        if strategy in [ChunkingStrategy.SEMANTIC, ChunkingStrategy.HYBRID]:
            # Try paragraph break
            para_break = buffer.rfind("\n\n", 0, chunk_size)
            if para_break > chunk_size * 0.7:
                return para_break + 2

            # Try sentence break
            sentence_ends = [".", "!", "?"]
            for i in range(chunk_size - 1, int(chunk_size * 0.7), -1):
                if (
                    buffer[i] in sentence_ends
                    and i + 1 < len(buffer)
                    and buffer[i + 1] in " \n"
                ):
                    return i + 1

            # Try line break
            line_break = buffer.rfind("\n", 0, chunk_size)
            if line_break > chunk_size * 0.7:
                return line_break + 1

        # Default to chunk_size
        return chunk_size
