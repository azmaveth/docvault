"""
Optimized document scraper with performance improvements.
"""

import asyncio
import logging
from typing import Any, Optional

import aiohttp

from docvault.core.embeddings_optimized import generate_embeddings_batch, get_session
from docvault.core.performance import performance_monitor, profiler, timer
from docvault.core.processor import extract_title, html_to_markdown, segment_markdown
from docvault.core.storage import save_html, save_markdown
from docvault.db.batch_operations import batch_insert_segments
from docvault.db.connection_pool import get_connection
from docvault.db.operations import add_document

logger = logging.getLogger(__name__)


class OptimizedDocumentScraper:
    """
    Optimized document scraper with batching, connection pooling, and performance monitoring.
    """

    def __init__(self, quiet: bool = False, max_concurrent_requests: int = 5):
        self.quiet = quiet
        self.max_concurrent_requests = max_concurrent_requests
        self.stats = {
            "pages_scraped": 0,
            "pages_skipped": 0,
            "segments_created": 0,
            "total_pages": 0,
        }

    @performance_monitor("document_scraping")
    async def scrape_url(
        self,
        url: str,
        depth: int = 1,
        max_links: int = 10,
        strict_path: bool = True,
        force_update: bool = False,
        sections: list[str] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Scrape a URL and store the document with optimized performance.

        Returns a dictionary with document information and statistics.
        """
        with profiler("document_scraping") as p:
            p.checkpoint("validation")

            # Validate URL and check for existing document
            existing_doc = self._check_existing_document(url)
            if existing_doc and not force_update:
                logger.info(f"Document already exists: {url}")
                return existing_doc

            p.checkpoint("fetching")

            # Fetch the content
            html_content = await self._fetch_content(url)
            if not html_content:
                raise Exception(f"Failed to fetch content from {url}")

            p.checkpoint("processing")

            # Process the content
            processed_content = await self._process_content(html_content, url, sections)

            p.checkpoint("storage")

            # Store the document
            document_id = await self._store_document(
                url, processed_content, existing_doc
            )

            p.checkpoint("segments")

            # Process and store segments in batches
            await self._process_segments_batch(
                document_id, processed_content["segments"]
            )

            p.checkpoint("linking")

            # Handle additional pages if depth > 1
            if depth > 1 and max_links > 0:
                await self._scrape_linked_pages(
                    url, html_content, depth - 1, max_links, strict_path
                )

            return {
                "id": document_id,
                "title": processed_content["title"],
                "url": url,
                "segments": len(processed_content["segments"]),
                "stats": self.stats.copy(),
            }

    def _check_existing_document(self, url: str) -> dict[str, Any] | None:
        """Check if document already exists in database."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, url FROM documents WHERE url = ?", (url,))
            row = cursor.fetchone()
            if row:
                return {"id": row["id"], "title": row["title"], "url": row["url"]}
        return None

    @performance_monitor("content_fetching")
    async def _fetch_content(self, url: str) -> str | None:
        """Fetch content from URL with optimized session handling."""
        try:
            session = await get_session()

            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    content_type = response.headers.get("Content-Type", "")
                    if "text/html" in content_type or "text/plain" in content_type:
                        return await response.text()
                    else:
                        logger.warning(f"Unsupported content type: {content_type}")
                        return None
                else:
                    logger.error(f"HTTP {response.status} for {url}")
                    return None

        except TimeoutError:
            logger.error(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    @performance_monitor("content_processing")
    async def _process_content(
        self, html_content: str, url: str, sections: list[str] | None = None
    ) -> dict[str, Any]:
        """Process HTML content into structured format."""
        with timer("html_processing"):
            # Parse and process the HTML
            title = extract_title(html_content) or "Untitled Document"
            markdown_content = html_to_markdown(html_content)
            segments = segment_markdown(markdown_content)

            processed = {
                "title": title,
                "content": markdown_content,
                "html": html_content,
                "segments": segments,
            }

            # Filter sections if specified
            if sections:
                filtered_segments = []
                for segment in segments:
                    section_title = segment.get("section_title", "").lower()
                    if any(section.lower() in section_title for section in sections):
                        filtered_segments.append(segment)
                processed["segments"] = filtered_segments
                logger.info(
                    f"Filtered to {len(filtered_segments)} segments matching sections"
                )

        return processed

    @performance_monitor("document_storage")
    async def _store_document(
        self,
        url: str,
        processed_content: dict[str, Any],
        existing_doc: dict[str, Any] | None,
    ) -> int:
        """Store or update document in database."""
        # Save HTML and markdown files
        html_path = save_html(processed_content["html"], url)
        markdown_path = save_markdown(processed_content["content"], url)

        if existing_doc:
            # Update existing document
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE documents
                    SET title = ?, html_path = ?, markdown_path = ?, scraped_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        processed_content["title"],
                        html_path,
                        markdown_path,
                        existing_doc["id"],
                    ),
                )
                conn.commit()

                # Delete existing segments
                cursor.execute(
                    "DELETE FROM document_segments WHERE document_id = ?",
                    (existing_doc["id"],),
                )
                cursor.execute(
                    "DELETE FROM document_segments_vec WHERE segment_id IN "
                    "(SELECT id FROM document_segments WHERE document_id = ?)",
                    (existing_doc["id"],),
                )
                conn.commit()

            return existing_doc["id"]
        else:
            # Create new document
            return add_document(
                url=url,
                title=processed_content["title"],
                html_path=html_path,
                markdown_path=markdown_path,
            )

    @performance_monitor("segment_processing")
    async def _process_segments_batch(
        self, document_id: int, segments: list[dict[str, Any]]
    ):
        """Process document segments in optimized batches."""
        if not segments:
            return

        logger.info(f"Processing {len(segments)} segments in batches")

        # Extract text content for batch embedding generation
        texts = [segment.get("content", "") for segment in segments]

        # Generate embeddings in batches
        with timer("batch_embedding_generation"):
            embeddings = await generate_embeddings_batch(texts, batch_size=10)

        # Prepare segments with embeddings
        segments_with_embeddings = []
        for i, segment in enumerate(segments):
            segment_data = {
                "content": segment.get("content", ""),
                "section_title": segment.get("section_title"),
                "segment_type": segment.get("segment_type", "text"),
                "section_path": segment.get("section_path"),
                "parent_id": segment.get("parent_id"),
                "embedding": embeddings[i],
            }
            segments_with_embeddings.append(segment_data)

        # Insert segments in batches
        with timer("batch_segment_insertion"):
            segment_ids = batch_insert_segments(
                document_id, segments_with_embeddings, batch_size=50
            )

        self.stats["segments_created"] += len(segment_ids)
        logger.info(f"Created {len(segment_ids)} segments for document {document_id}")

    @performance_monitor("linked_page_scraping")
    async def _scrape_linked_pages(
        self,
        base_url: str,
        html_content: str,
        remaining_depth: int,
        max_links: int,
        strict_path: bool,
    ):
        """Scrape linked pages with concurrent processing."""
        if remaining_depth <= 0 or max_links <= 0:
            return

        # Extract links from the page
        links = self._extract_links(html_content, base_url, strict_path)
        links = links[:max_links]  # Limit number of links

        if not links:
            return

        logger.info(f"Scraping {len(links)} linked pages (depth {remaining_depth})")

        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        async def scrape_single_link(url):
            async with semaphore:
                try:
                    return await self.scrape_url(
                        url,
                        depth=remaining_depth,
                        max_links=max_links // 2,  # Reduce links for deeper levels
                        strict_path=strict_path,
                    )
                except Exception as e:
                    logger.warning(f"Failed to scrape linked page {url}: {e}")
                    return None

        # Execute scraping tasks concurrently
        tasks = [scrape_single_link(link) for link in links]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful results
        successful = sum(
            1 for result in results if result and not isinstance(result, Exception)
        )
        logger.info(f"Successfully scraped {successful}/{len(links)} linked pages")

    def _extract_links(
        self, html_content: str, base_url: str, strict_path: bool
    ) -> list[str]:
        """Extract valid links from HTML content."""
        # Implementation would parse HTML and extract links
        # This is a simplified version
        import re
        from urllib.parse import urljoin, urlparse

        # Find all href attributes
        href_pattern = r'href=["\']([^"\']+)["\']'
        matches = re.findall(href_pattern, html_content)

        links = []
        base_domain = urlparse(base_url).netloc

        for match in matches:
            try:
                full_url = urljoin(base_url, match)
                parsed = urlparse(full_url)

                # Skip non-HTTP links
                if parsed.scheme not in ["http", "https"]:
                    continue

                # Apply strict path filtering if enabled
                if strict_path and parsed.netloc != base_domain:
                    continue

                # Skip common non-content URLs
                if any(
                    skip in full_url.lower()
                    for skip in [
                        "javascript:",
                        "mailto:",
                        "#",
                        "css",
                        "js",
                        "png",
                        "jpg",
                        "gif",
                        "pdf",
                    ]
                ):
                    continue

                links.append(full_url)

            except Exception:
                continue

        # Remove duplicates and limit
        return list(dict.fromkeys(links))

    def get_stats(self) -> dict[str, Any]:
        """Get scraping statistics."""
        return self.stats.copy()

    def reset_stats(self):
        """Reset scraping statistics."""
        self.stats = {
            "pages_scraped": 0,
            "pages_skipped": 0,
            "segments_created": 0,
            "total_pages": 0,
        }
