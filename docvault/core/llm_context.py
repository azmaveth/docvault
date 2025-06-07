"""
LLM integration for contextual retrieval.

This module provides interfaces for generating contextual descriptions
of document chunks using various LLM providers.
"""

import asyncio
import hashlib
import json
from abc import ABC, abstractmethod

import aiohttp

from docvault import config
from docvault.db import operations
from docvault.utils.logging import get_logger

logger = get_logger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate_context(
        self, chunk: str, document: str, template: str, max_tokens: int = 150
    ) -> str:
        """Generate contextual description for a chunk.

        Args:
            chunk: The chunk content
            document: The full document content
            template: The prompt template to use
            max_tokens: Maximum tokens for response

        Returns:
            Contextual description
        """
        pass

    @abstractmethod
    async def batch_generate_contexts(
        self,
        chunks: list[tuple[str, str]],  # [(chunk, document), ...]
        template: str,
        max_tokens: int = 150,
    ) -> list[str]:
        """Generate contexts for multiple chunks.

        Args:
            chunks: List of (chunk, document) tuples
            template: The prompt template to use
            max_tokens: Maximum tokens per response

        Returns:
            List of contextual descriptions
        """
        pass


class OllamaProvider(LLMProvider):
    """Ollama LLM provider for local models."""

    def __init__(self, model: str = "llama2", base_url: str = None):
        self.model = model
        self.base_url = base_url or config.OLLAMA_URL

    async def generate_context(
        self, chunk: str, document: str, template: str, max_tokens: int = 150
    ) -> str:
        """Generate context using Ollama."""
        prompt = template.replace("{{CHUNK_CONTENT}}", chunk)
        prompt = prompt.replace(
            "{{WHOLE_DOCUMENT}}", document[:5000]
        )  # Limit document size

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": 0.3,  # Lower temperature for consistency
                        },
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("response", "").strip()
                    else:
                        error_text = await response.text()
                        logger.error(f"Ollama error: {error_text}")
                        return ""
        except Exception as e:
            logger.error(f"Error generating context with Ollama: {e}")
            return ""

    async def batch_generate_contexts(
        self, chunks: list[tuple[str, str]], template: str, max_tokens: int = 150
    ) -> list[str]:
        """Generate contexts for multiple chunks."""
        # Ollama doesn't support batch generation, so we'll do concurrent requests
        tasks = []
        for chunk, document in chunks:
            task = self.generate_context(chunk, document, template, max_tokens)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return results


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"

    async def generate_context(
        self, chunk: str, document: str, template: str, max_tokens: int = 150
    ) -> str:
        """Generate context using OpenAI."""
        prompt = template.replace("{{CHUNK_CONTENT}}", chunk)
        prompt = prompt.replace(
            "{{WHOLE_DOCUMENT}}", document[:3000]
        )  # GPT-3.5 token limit

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are a helpful assistant that creates concise "
                                    "contextual descriptions for document chunks."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": 0.3,
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["choices"][0]["message"]["content"].strip()
                    else:
                        error_text = await response.text()
                        logger.error(f"OpenAI error: {error_text}")
                        return ""
        except Exception as e:
            logger.error(f"Error generating context with OpenAI: {e}")
            return ""

    async def batch_generate_contexts(
        self, chunks: list[tuple[str, str]], template: str, max_tokens: int = 150
    ) -> list[str]:
        """Generate contexts for multiple chunks using concurrent requests."""
        # OpenAI has rate limits, so we'll limit concurrency
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

        async def generate_with_limit(chunk, document):
            async with semaphore:
                return await self.generate_context(
                    chunk, document, template, max_tokens
                )

        tasks = []
        for chunk, document in chunks:
            task = generate_with_limit(chunk, document)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return results


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"

    async def generate_context(
        self, chunk: str, document: str, template: str, max_tokens: int = 150
    ) -> str:
        """Generate context using Claude."""
        prompt = template.replace("{{CHUNK_CONTENT}}", chunk)
        prompt = prompt.replace(
            "{{WHOLE_DOCUMENT}}", document[:8000]
        )  # Claude can handle more

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.3,
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["content"][0]["text"].strip()
                    else:
                        error_text = await response.text()
                        logger.error(f"Anthropic error: {error_text}")
                        return ""
        except Exception as e:
            logger.error(f"Error generating context with Anthropic: {e}")
            return ""

    async def batch_generate_contexts(
        self, chunks: list[tuple[str, str]], template: str, max_tokens: int = 150
    ) -> list[str]:
        """Generate contexts using Claude's batch capability."""
        # For now, use concurrent requests with rate limiting
        # Could be optimized with Anthropic's batch API when available
        semaphore = asyncio.Semaphore(3)  # Anthropic has stricter rate limits

        async def generate_with_limit(chunk, document):
            async with semaphore:
                return await self.generate_context(
                    chunk, document, template, max_tokens
                )

        tasks = []
        for chunk, document in chunks:
            task = generate_with_limit(chunk, document)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return results


class ContextCache:
    """Cache for generated contexts to avoid regeneration."""

    def __init__(self):
        self.cache = {}

    def _generate_key(self, chunk: str, template: str, model: str) -> str:
        """Generate cache key from chunk content."""
        content = f"{chunk}:{template}:{model}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, chunk: str, template: str, model: str) -> str | None:
        """Get cached context if available."""
        key = self._generate_key(chunk, template, model)
        return self.cache.get(key)

    def set(self, chunk: str, template: str, model: str, context: str):
        """Cache generated context."""
        key = self._generate_key(chunk, template, model)
        self.cache[key] = context

    def clear(self):
        """Clear all cached contexts."""
        self.cache.clear()


class ContextGenerator:
    """Main class for generating contextual descriptions."""

    def __init__(self, provider: LLMProvider | None = None):
        """Initialize with an LLM provider.

        Args:
            provider: LLM provider instance. If None, uses config defaults.
        """
        self.provider = provider or self._create_default_provider()
        self.cache = ContextCache()

    def _create_default_provider(self) -> LLMProvider:
        """Create provider based on config settings."""
        provider_type = config.get("context_llm_provider", "ollama")
        model = config.get("context_llm_model", "llama2")

        if provider_type == "ollama":
            return OllamaProvider(model=model)
        elif provider_type == "openai":
            api_key = config.get("openai_api_key")
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            return OpenAIProvider(api_key=api_key, model=model)
        elif provider_type == "anthropic":
            api_key = config.get("anthropic_api_key")
            if not api_key:
                raise ValueError("Anthropic API key not configured")
            return AnthropicProvider(api_key=api_key, model=model)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

    def get_template(self, doc_type: str | None = None) -> str:
        """Get appropriate template for document type."""
        with operations.get_connection() as conn:
            if doc_type:
                # Try to get specific template for doc type
                cursor = conn.execute(
                    """
                    SELECT template FROM context_templates
                    WHERE doc_type = ? AND is_active = 1
                    LIMIT 1
                """,
                    (doc_type,),
                )
            else:
                # Get general template
                cursor = conn.execute(
                    """
                    SELECT template FROM context_templates
                    WHERE name = 'general' AND is_active = 1
                    LIMIT 1
                """
                )

            result = cursor.fetchone()
            if result:
                return result["template"]

            # Fallback template
            return """<document>
{{WHOLE_DOCUMENT}}
</document>
Here is the chunk we want to situate within the whole document:
<chunk>
{{CHUNK_CONTENT}}
</chunk>
Please give a short succinct context to situate this chunk within the
overall document."""

    async def generate_context_for_chunk(
        self,
        chunk_content: str,
        document_content: str,
        doc_type: str | None = None,
        use_cache: bool = True,
    ) -> dict[str, any]:
        """Generate context for a single chunk.

        Args:
            chunk_content: The chunk text
            document_content: The full document text
            doc_type: Document type for template selection
            use_cache: Whether to use cached results

        Returns:
            Dictionary with context and metadata
        """
        template = self.get_template(doc_type)
        model = config.get("context_llm_model", "llama2")

        # Check cache
        if use_cache and config.get("context_cache_enabled", True):
            cached = self.cache.get(chunk_content, template, model)
            if cached:
                logger.debug("Using cached context")
                return {"context": cached, "model": model, "cached": True}

        # Generate new context
        max_tokens = int(config.get("context_max_tokens", 150))
        context = await self.provider.generate_context(
            chunk_content, document_content, template, max_tokens
        )

        # Cache result
        if context and config.get("context_cache_enabled", True):
            self.cache.set(chunk_content, template, model, context)

        return {"context": context, "model": model, "cached": False}

    async def generate_contexts_for_document(
        self, document_id: int, regenerate: bool = False
    ) -> list[dict]:
        """Generate contexts for all chunks in a document.

        Args:
            document_id: Document to process
            regenerate: Force regeneration even if contexts exist

        Returns:
            List of results with segment IDs and contexts
        """
        # Get document and segments
        document = operations.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Read full document content
        from docvault.core.storage import read_markdown

        document_content = read_markdown(document["markdown_path"])

        # Get segments that need context
        with operations.get_connection() as conn:
            if regenerate:
                cursor = conn.execute(
                    """
                    SELECT id, content, section_title
                    FROM document_segments
                    WHERE document_id = ?
                    ORDER BY section_path
                """,
                    (document_id,),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, content, section_title
                    FROM document_segments
                    WHERE document_id = ?
                    AND context_description IS NULL
                    ORDER BY section_path
                """,
                    (document_id,),
                )

            segments = cursor.fetchall()

        if not segments:
            logger.info("No segments need context generation")
            return []

        # Determine document type
        doc_type = self._detect_doc_type(document_content, document["title"])

        # Process in batches
        batch_size = int(config.get("context_batch_size", 10))
        results = []

        for i in range(0, len(segments), batch_size):
            batch = segments[i : i + batch_size]

            # Prepare batch for processing
            chunks = [(seg["content"], document_content) for seg in batch]

            # Generate contexts
            template = self.get_template(doc_type)
            contexts = await self.provider.batch_generate_contexts(
                chunks, template, int(config.get("context_max_tokens", 150))
            )

            # Combine results
            for seg, context in zip(batch, contexts):
                results.append(
                    {
                        "segment_id": seg["id"],
                        "context": context,
                        "section_title": seg["section_title"],
                    }
                )

        return results

    def _detect_doc_type(self, content: str, title: str) -> str | None:
        """Detect document type for template selection."""
        content_lower = content.lower()
        title_lower = title.lower()

        # Simple heuristics
        if "api" in title_lower or "endpoint" in content_lower[:1000]:
            return "api"
        elif "tutorial" in title_lower or "guide" in title_lower:
            return "tutorial"
        elif "```" in content[:1000] or "function" in content_lower[:1000]:
            return "code"

        return None
