"""
Optimized embeddings module with connection pooling, batching, and caching.
"""

import asyncio
import hashlib
import logging
import time
from typing import Any, Optional

import aiohttp
import numpy as np

from docvault import config
from docvault.db import operations
from docvault.db.batch_operations import batch_search_segments

# Global session and cache
_session: aiohttp.ClientSession | None = None
_embedding_cache: dict[str, bytes] = {}
_cache_timestamps: dict[str, float] = {}
CACHE_TTL = 3600  # 1 hour cache TTL

logger = logging.getLogger(__name__)


async def get_session() -> aiohttp.ClientSession:
    """Get a reusable aiohttp session with connection pooling."""
    global _session
    if _session is None or _session.closed:
        # Create session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=10,  # Per-host connection limit
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True,
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        _session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return _session


async def close_session():
    """Close the global session."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


def _get_cache_key(text: str) -> str:
    """Generate cache key for text."""
    return hashlib.md5(text.encode()).hexdigest()


def _is_cache_valid(cache_key: str) -> bool:
    """Check if cached embedding is still valid."""
    if cache_key not in _cache_timestamps:
        return False
    return time.time() - _cache_timestamps[cache_key] < CACHE_TTL


def _clean_cache():
    """Remove expired cache entries."""
    current_time = time.time()
    expired_keys = [
        key
        for key, timestamp in _cache_timestamps.items()
        if current_time - timestamp > CACHE_TTL
    ]
    for key in expired_keys:
        _embedding_cache.pop(key, None)
        _cache_timestamps.pop(key, None)


async def generate_embeddings(text: str) -> bytes:
    """
    Generate embeddings for text using Ollama with caching.
    Returns binary embeddings (numpy array as bytes).
    """
    # Check cache first
    cache_key = _get_cache_key(text)
    if cache_key in _embedding_cache and _is_cache_valid(cache_key):
        logger.debug("Using cached embedding")
        return _embedding_cache[cache_key]

    # Clean expired cache entries periodically
    if len(_embedding_cache) > 1000:
        _clean_cache()

    # Format request for Ollama
    request_data = {"model": config.EMBEDDING_MODEL, "prompt": text}

    try:
        session = await get_session()

        # Make the request with retry logic
        for attempt in range(3):
            try:
                resp = await session.post(
                    f"{config.OLLAMA_URL}/api/embeddings",
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=30),
                )

                if resp.status != 200:
                    error_text = await resp.text()
                    logger.warning(
                        f"Embedding generation failed (attempt {attempt + 1}): {error_text}"
                    )
                    if attempt == 2:  # Last attempt
                        embedding = np.zeros(384, dtype=np.float32).tobytes()
                        break
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue

                result = await resp.json()
                if "embedding" not in result:
                    logger.error(f"Embedding not found in response: {result}")
                    embedding = np.zeros(384, dtype=np.float32).tobytes()
                else:
                    # Convert to numpy array and then to bytes
                    embedding = np.array(result["embedding"], dtype=np.float32)
                    embedding = embedding.tobytes()

                    # Cache the result
                    _embedding_cache[cache_key] = embedding
                    _cache_timestamps[cache_key] = time.time()

                break

            except TimeoutError:
                logger.warning(f"Timeout generating embedding (attempt {attempt + 1})")
                if attempt == 2:
                    embedding = np.zeros(384, dtype=np.float32).tobytes()
                    break
                await asyncio.sleep(2**attempt)
            except Exception as e:
                logger.warning(
                    f"Error generating embedding (attempt {attempt + 1}): {e}"
                )
                if attempt == 2:
                    embedding = np.zeros(384, dtype=np.float32).tobytes()
                    break
                await asyncio.sleep(2**attempt)

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        embedding = np.zeros(384, dtype=np.float32).tobytes()

    return embedding


async def generate_embeddings_batch(
    texts: list[str], batch_size: int = 10
) -> list[bytes]:
    """
    Generate embeddings for multiple texts in batches for better performance.

    Args:
        texts: List of texts to generate embeddings for
        batch_size: Number of texts to process concurrently

    Returns:
        List of binary embeddings
    """
    logger.info(
        f"Generating embeddings for {len(texts)} texts in batches of {batch_size}"
    )

    embeddings = []

    # Process texts in batches
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]

        # Create tasks for concurrent processing
        tasks = [generate_embeddings(text) for text in batch]

        # Wait for batch to complete
        batch_embeddings = await asyncio.gather(*tasks)
        embeddings.extend(batch_embeddings)

        logger.debug(
            f"Completed batch {i // batch_size + 1}/{(len(texts) + batch_size - 1) // batch_size}"
        )

        # Small delay to avoid overwhelming the service
        if i + batch_size < len(texts):
            await asyncio.sleep(0.1)

    return embeddings


async def search(
    query: str | None = None,
    limit: int = 5,
    text_only: bool = False,
    min_score: float = 0.0,
    doc_filter: dict[str, Any] | None = None,
    document_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """
    Search for documents using optimized semantic search with metadata filtering.

    Args:
        query: Search query string (optional if using filters)
        limit: Maximum number of results to return
        text_only: If True, use only text search (no embeddings)
        min_score: Minimum similarity score (0.0 to 1.0)
        doc_filter: Dictionary of document filters (e.g., {'version': '1.0'})
        document_ids: Optional list of document IDs to filter by

    Returns:
        List of document segments with scores and metadata
    """
    try:
        # If no query and no filters, return empty results
        if not query and not doc_filter and not document_ids:
            logger.warning("No search query or filters provided")
            return []

        # Prepare search terms - main terms and alternative forms
        search_terms = []
        expanded_terms = []
        expanded_query = ""

        if query:
            search_terms = query.lower().split()
            # Include stemmed/simplified versions of terms
            for term in search_terms:
                # Simple stemming: remove common suffixes
                if len(term) > 5:
                    if term.endswith("ing"):
                        expanded_terms.append(term[:-3])
                    elif term.endswith("ed"):
                        expanded_terms.append(term[:-2])
                    elif term.endswith("s"):
                        expanded_terms.append(term[:-1])
                    elif term.endswith("ly"):
                        expanded_terms.append(term[:-2])

            # Create expanded query
            expanded_query = " ".join(search_terms + expanded_terms)
            logger.info(f"Searching for: {query} (expanded: {expanded_query})")
        else:
            logger.info("Searching with filters only")

        # Log filters if any
        if doc_filter:
            logger.info(f"Using document filters: {doc_filter}")
        if document_ids:
            logger.info(f"Filtering by document IDs: {document_ids}")

        if text_only or not query:
            # Skip embedding generation and use text search only
            logger.info("Using text-only search")
            results = operations.search_segments(
                None,
                limit=limit,
                text_query=expanded_query if query else None,
                min_score=min_score,
                doc_filter=doc_filter,
            )
        else:
            # Try optimized batch search first
            try:
                query_embedding_bytes = await generate_embeddings(query)
                query_embedding = np.frombuffer(
                    query_embedding_bytes, dtype=np.float32
                ).tolist()

                results = batch_search_segments(
                    query_vector=query_embedding,
                    limit=limit,
                    document_ids=document_ids,
                    min_similarity=min_score,
                )

                # Convert similarity scores to the expected format
                for result in results:
                    result["score"] = result.pop("similarity", 0.0)

                logger.info("Used optimized batch search")

            except Exception as e:
                logger.warning(
                    f"Batch search failed, falling back to regular search: {e}"
                )

                # Fallback to regular search
                query_embedding = await generate_embeddings(query)
                logger.info(
                    f"Generated embedding for query: {len(query_embedding)} bytes"
                )

                # Search database with both embedding and text query
                results = operations.search_segments(
                    query_embedding,
                    limit=limit,
                    text_query=expanded_query,
                    min_score=min_score,
                    doc_filter=doc_filter,
                )

        # Log results count and top scores if available
        if results:
            scores = [r.get("score", 0) for r in results]
            logger.info(
                f"Found {len(results)} results (scores: {min(scores):.2f}-{max(scores):.2f})"
            )
        else:
            logger.info("No results found")

        return results

    except Exception as e:
        logger.error(f"Error searching documents: {e}", exc_info=True)
        return []


def get_cache_stats() -> dict[str, Any]:
    """Get embedding cache statistics."""
    current_time = time.time()
    valid_entries = sum(
        1
        for timestamp in _cache_timestamps.values()
        if current_time - timestamp < CACHE_TTL
    )

    return {
        "total_entries": len(_embedding_cache),
        "valid_entries": valid_entries,
        "expired_entries": len(_embedding_cache) - valid_entries,
        "cache_hit_ratio": "N/A",  # Would need to track hits/misses
        "memory_usage_mb": sum(
            len(embedding) for embedding in _embedding_cache.values()
        )
        / (1024 * 1024),
    }


def clear_cache():
    """Clear the embedding cache."""
    global _embedding_cache, _cache_timestamps
    _embedding_cache.clear()
    _cache_timestamps.clear()
    logger.info("Embedding cache cleared")
