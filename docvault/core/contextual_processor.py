"""
Context-aware chunk processor for contextual retrieval.

This module integrates with the document processing pipeline to generate
contextual descriptions for chunks before embedding them.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Optional

from docvault import config
from docvault.core.content_chunker import ContentChunker
from docvault.core.llm_context import ContextGenerator, LLMProvider
from docvault.db import operations
from docvault.utils.logging import get_logger

logger = get_logger(__name__)


class ContextualChunkProcessor:
    """Processes chunks with contextual augmentation for improved retrieval."""

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        enable_metadata_embeddings: bool = True,
    ):
        """Initialize the contextual processor.

        Args:
            llm_provider: LLM provider for context generation
            enable_metadata_embeddings: Whether to create separate metadata embeddings
        """
        self.context_generator = ContextGenerator(llm_provider)
        self.enable_metadata_embeddings = enable_metadata_embeddings
        self.chunker = ContentChunker()

    async def process_document(
        self,
        document_id: int,
        regenerate: bool = False,
        force: bool = False,
        chunk_size: int = 5000,
        chunking_strategy: str = "hybrid",
    ) -> dict[str, Any]:
        """Process a document with contextual augmentation.

        Args:
            document_id: Document to process
            regenerate: Force regeneration of contexts (deprecated, use force)
            force: Force regeneration of contexts
            chunk_size: Size of chunks in characters
            chunking_strategy: Strategy for chunking

        Returns:
            Processing results with statistics
        """
        start_time = datetime.now()

        # Get document
        document = operations.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        logger.info(f"Processing document {document_id}: {document['title']}")

        # Check if contextual retrieval is enabled
        # Handle both regenerate and force parameters
        regenerate = regenerate or force

        # Check if contextual retrieval is enabled in database
        with operations.get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM config WHERE key = 'contextual_retrieval_enabled'"
            )
            result = cursor.fetchone()
            enabled = result["value"] == "true" if result else False

        if not enabled:
            logger.warning("Contextual retrieval is not enabled. Enable it in config.")
            return {
                "status": "skipped",
                "reason": "contextual_retrieval_enabled is false",
                "document_id": document_id,
            }

        # Read document content
        from docvault.core.storage import read_markdown

        content = read_markdown(document["markdown_path"])

        # Get existing segments or create new ones
        segments = self._get_or_create_segments(
            document_id, content, chunk_size, chunking_strategy, regenerate
        )

        # Generate contexts for segments
        results = await self._generate_contexts_for_segments(
            segments, content, document, regenerate
        )

        # Update embeddings with contextualized content
        embedding_results = await self._update_embeddings(results)

        # Generate metadata embeddings if enabled
        metadata_results = None
        if self.enable_metadata_embeddings:
            metadata_results = await self._generate_metadata_embeddings(results)

        # Calculate statistics
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return {
            "status": "success",
            "document_id": document_id,
            "segments_processed": len(segments),
            "contexts_generated": len([r for r in results if r.get("context")]),
            "embeddings_updated": embedding_results["updated"],
            "metadata_embeddings": (
                metadata_results["created"] if metadata_results else 0
            ),
            "duration_seconds": duration,
            "regenerated": regenerate,
        }

    def _get_or_create_segments(
        self,
        document_id: int,
        content: str,
        chunk_size: int,
        chunking_strategy: str,
        regenerate: bool,
    ) -> list[dict]:
        """Get existing segments or create new ones."""
        with operations.get_connection() as conn:
            # Check if segments exist
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM document_segments WHERE document_id = ?",
                (document_id,),
            )
            segment_count = cursor.fetchone()["count"]

            if segment_count > 0 and not regenerate:
                # Get existing segments
                cursor = conn.execute(
                    """
                    SELECT id, content, section_title, section_path, chunk_index
                    FROM document_segments
                    WHERE document_id = ?
                    ORDER BY chunk_index
                """,
                    (document_id,),
                )
                return [dict(row) for row in cursor.fetchall()]

            # Create new segments
            logger.info(f"Creating segments for document {document_id}")

            # Use chunker to create chunks
            chunks = self.chunker.chunk_document(
                content, chunk_size=chunk_size, strategy=chunking_strategy
            )

            # Store chunks as segments
            segments = []
            for i, chunk in enumerate(chunks):
                segment_data = {
                    "document_id": document_id,
                    "content": chunk["content"],
                    "section_title": chunk.get("metadata", {}).get("section", ""),
                    "section_path": chunk.get("metadata", {}).get("path", ""),
                    "chunk_index": i,
                    "metadata": json.dumps(chunk.get("metadata", {})),
                }

                # Insert segment
                cursor = conn.execute(
                    """
                    INSERT INTO document_segments
                    (document_id, content, section_title, section_path,
                     chunk_index, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        segment_data["document_id"],
                        segment_data["content"],
                        segment_data["section_title"],
                        segment_data["section_path"],
                        segment_data["chunk_index"],
                        segment_data["metadata"],
                    ),
                )

                segment_data["id"] = cursor.lastrowid
                segments.append(segment_data)

            conn.commit()
            logger.info(f"Created {len(segments)} segments")

        return segments

    async def _generate_contexts_for_segments(
        self,
        segments: list[dict],
        document_content: str,
        document: dict,
        regenerate: bool,
    ) -> list[dict]:
        """Generate contextual descriptions for segments."""
        results = []

        # Detect document type
        doc_type = self.context_generator._detect_doc_type(
            document_content, document["title"]
        )

        # Process each segment
        for segment in segments:
            # Skip if context exists and not regenerating
            if segment.get("context_description") and not regenerate:
                results.append(
                    {
                        "segment_id": segment["id"],
                        "context": segment["context_description"],
                        "skipped": True,
                    }
                )
                continue

            # Build hierarchical context
            hierarchical_context = self._build_hierarchical_context(segment, document)

            # Generate context
            try:
                context_result = (
                    await self.context_generator.generate_context_for_chunk(
                        chunk_content=segment["content"],
                        document_content=document_content,
                        doc_type=doc_type,
                    )
                )

                # Add hierarchical context to metadata
                context_metadata = context_result.get("metadata", {})
                context_metadata.update(hierarchical_context)

                # Store context in database
                with operations.get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE document_segments
                        SET context_description = ?,
                            context_metadata = ?,
                            context_generated_at = CURRENT_TIMESTAMP,
                            context_model = ?
                        WHERE id = ?
                    """,
                        (
                            context_result["context"],
                            json.dumps(context_metadata),
                            context_result["model"],
                            segment["id"],
                        ),
                    )
                    conn.commit()

                results.append(
                    {
                        "segment_id": segment["id"],
                        "context": context_result["context"],
                        "metadata": context_metadata,
                        "model": context_result["model"],
                    }
                )

            except Exception as e:
                logger.error(
                    f"Error generating context for segment {segment['id']}: {e}"
                )
                results.append({"segment_id": segment["id"], "error": str(e)})

        return results

    def _build_hierarchical_context(
        self, segment: dict, document: dict
    ) -> dict[str, Any]:
        """Build hierarchical context information."""
        context = {
            "document_title": document["title"],
            "document_url": document["url"],
            "section_hierarchy": [],
        }

        # Add section hierarchy if available
        if segment.get("section_path"):
            path_parts = segment["section_path"].split(".")
            hierarchy = []

            # Build progressive path
            for i in range(len(path_parts)):
                partial_path = ".".join(path_parts[: i + 1])

                # Try to get section title for this level
                with operations.get_connection() as conn:
                    cursor = conn.execute(
                        """
                        SELECT DISTINCT section_title
                        FROM document_segments
                        WHERE document_id = ? AND section_path = ?
                        LIMIT 1
                    """,
                        (document["id"], partial_path),
                    )

                    result = cursor.fetchone()
                    if result:
                        hierarchy.append(
                            {
                                "level": i,
                                "path": partial_path,
                                "title": result["section_title"],
                            }
                        )

            context["section_hierarchy"] = hierarchy

        # Add semantic role if detected
        content_lower = segment["content"].lower()
        if "```" in segment["content"]:
            context["semantic_role"] = "code_example"
        elif any(word in content_lower for word in ["example:", "usage:", "demo:"]):
            context["semantic_role"] = "example"
        elif any(
            word in content_lower for word in ["class ", "function ", "def ", "method "]
        ):
            context["semantic_role"] = "api_reference"
        elif any(word in content_lower for word in ["install", "setup", "configure"]):
            context["semantic_role"] = "setup_guide"
        else:
            context["semantic_role"] = "general"

        return context

    async def _update_embeddings(self, results: list[dict]) -> dict[str, int]:
        """Update embeddings with contextualized content."""
        from docvault.core.embeddings import generate_embedding

        updated_count = 0

        for result in results:
            if "error" in result or result.get("skipped"):
                continue

            segment_id = result["segment_id"]
            context = result["context"]

            # Get original content
            with operations.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT content FROM document_segments WHERE id = ?", (segment_id,)
                )
                segment = cursor.fetchone()

                if not segment:
                    continue

                # Create contextualized content
                contextualized_content = f"{context}\n\n{segment['content']}"

                # Generate new embedding
                try:
                    embedding = await generate_embedding(contextualized_content)

                    # Store contextualized embedding
                    conn.execute(
                        """
                        UPDATE document_segments
                        SET context_embedding = ?
                        WHERE id = ?
                    """,
                        (embedding.tobytes(), segment_id),
                    )

                    updated_count += 1

                except Exception as e:
                    logger.error(
                        f"Error updating embedding for segment {segment_id}: {e}"
                    )

            # Commit after batch
            if updated_count % 10 == 0:
                with operations.get_connection() as conn:
                    conn.commit()

        # Final commit
        with operations.get_connection() as conn:
            conn.commit()

        return {"updated": updated_count}

    async def _generate_metadata_embeddings(
        self, results: list[dict]
    ) -> dict[str, int]:
        """Generate embeddings for metadata to enable similarity search."""
        from docvault.core.embeddings import generate_embedding

        created_count = 0

        # Create metadata embeddings table if it doesn't exist
        with operations.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS segment_metadata_embeddings (
                    segment_id INTEGER PRIMARY KEY,
                    metadata_embedding BLOB,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (segment_id) REFERENCES document_segments(id)
                )
            """
            )
            conn.commit()

        for result in results:
            if "error" in result or not result.get("metadata"):
                continue

            segment_id = result["segment_id"]
            metadata = result["metadata"]

            # Create metadata string for embedding
            metadata_str = self._metadata_to_string(metadata)

            try:
                # Generate metadata embedding
                embedding = await generate_embedding(metadata_str)

                # Store metadata embedding
                with operations.get_connection() as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO segment_metadata_embeddings
                        (segment_id, metadata_embedding, metadata_json)
                        VALUES (?, ?, ?)
                    """,
                        (segment_id, embedding.tobytes(), json.dumps(metadata)),
                    )
                    conn.commit()

                created_count += 1

            except Exception as e:
                logger.error(
                    f"Error creating metadata embedding for segment {segment_id}: {e}"
                )

        return {"created": created_count}

    def _metadata_to_string(self, metadata: dict) -> str:
        """Convert metadata to string for embedding."""
        parts = []

        # Document info
        if "document_title" in metadata:
            parts.append(f"Document: {metadata['document_title']}")

        # Section hierarchy
        if "section_hierarchy" in metadata:
            for level in metadata["section_hierarchy"]:
                parts.append(f"Section L{level['level']}: {level['title']}")

        # Semantic role
        if "semantic_role" in metadata:
            parts.append(f"Type: {metadata['semantic_role']}")

        # Other metadata
        for key, value in metadata.items():
            if key not in ["document_title", "section_hierarchy", "semantic_role"]:
                if isinstance(value, str | int | float):
                    parts.append(f"{key}: {value}")

        return " | ".join(parts)

    async def find_similar_by_metadata(
        self, segment_id: int, limit: int = 10, filter_role: str | None = None
    ) -> list[dict]:
        """Find segments with similar metadata.

        Args:
            segment_id: Reference segment
            limit: Maximum results
            filter_role: Filter by semantic role

        Returns:
            List of similar segments with scores
        """
        # Get reference metadata embedding
        with operations.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT metadata_embedding, metadata_json
                FROM segment_metadata_embeddings
                WHERE segment_id = ?
            """,
                (segment_id,),
            )

            result = cursor.fetchone()
            if not result:
                return []

            reference_embedding = result["metadata_embedding"]

            # Build query with optional filter
            query = """
                SELECT
                    s.id,
                    s.content,
                    s.section_title,
                    s.document_id,
                    m.metadata_json,
                    vec_distance_L2(m.metadata_embedding, ?) as distance
                FROM segment_metadata_embeddings m
                JOIN document_segments s ON m.segment_id = s.id
                WHERE s.id != ?
            """

            params = [reference_embedding, segment_id]

            if filter_role:
                query += " AND json_extract(m.metadata_json, '$.semantic_role') = ?"
                params.append(filter_role)

            query += " ORDER BY distance LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "segment_id": row["id"],
                        "document_id": row["document_id"],
                        "section_title": row["section_title"],
                        "content_preview": row["content"][:200] + "...",
                        "metadata": json.loads(row["metadata_json"]),
                        "similarity_score": 1
                        / (1 + row["distance"]),  # Convert distance to similarity
                    }
                )

            return results
