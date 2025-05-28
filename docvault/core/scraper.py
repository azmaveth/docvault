import asyncio
import base64
import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin, urlparse

import aiohttp

import docvault.core.embeddings as embeddings
import docvault.core.processor as processor
import docvault.core.storage as storage
from docvault import config
from docvault.core.depth_analyzer import DepthAnalyzer, DepthStrategy
from docvault.db import operations
from docvault.utils.path_security import PathSecurityError, validate_url_path

# Get WebScraper instance
_scraper = None


def get_scraper():
    """Get or create a WebScraper instance"""
    global _scraper
    if _scraper is None:
        _scraper = WebScraper()
    return _scraper


class WebScraper:
    """Web scraper for fetching documentation"""

    def __init__(self, depth_strategy: Union[str, DepthStrategy] = DepthStrategy.AUTO):
        import os

        from docvault import config

        log_dir = str(config.LOG_DIR)
        log_file = str(config.LOG_FILE)
        log_level = getattr(logging, str(config.LOG_LEVEL).upper(), logging.INFO)
        os.makedirs(log_dir, exist_ok=True)
        self.visited_urls = set()
        self.logger = logging.getLogger("docvault.scraper")

        # Initialize depth analyzer
        if isinstance(depth_strategy, str):
            try:
                self.depth_strategy = DepthStrategy(depth_strategy)
            except ValueError:
                self.logger.warning(
                    f"Invalid depth strategy '{depth_strategy}', using AUTO"
                )
                self.depth_strategy = DepthStrategy.AUTO
        else:
            self.depth_strategy = depth_strategy

        self.depth_analyzer = DepthAnalyzer(self.depth_strategy)
        # Set up logging to file and console if not already set
        if not self.logger.hasHandlers():
            formatter = logging.Formatter(
                "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
            )
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
            self.logger.setLevel(log_level)
        # Stats tracking
        self.stats = {"pages_scraped": 0, "pages_skipped": 0, "segments_created": 0}

    def _filter_content_sections(
        self,
        html_content: str,
        sections: Optional[list] = None,
        filter_selector: Optional[str] = None,
    ) -> str:
        """Filter HTML content based on section headings or CSS selectors"""
        if not sections and not filter_selector:
            return html_content

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")

        # If CSS selector is provided, use it first
        if filter_selector:
            try:
                selected_elements = soup.select(filter_selector)
                if selected_elements:
                    # Create new soup with only selected elements
                    filtered_soup = BeautifulSoup(
                        "<html><body></body></html>", "html.parser"
                    )
                    body = filtered_soup.body
                    for element in selected_elements:
                        body.append(element.extract())
                    return str(filtered_soup)
            except Exception as e:
                self.logger.warning(f"Invalid CSS selector '{filter_selector}': {e}")

        # If sections are specified, filter by heading content
        if sections:
            sections_lower = [s.lower() for s in sections]
            filtered_soup = BeautifulSoup("<html><body></body></html>", "html.parser")
            body = filtered_soup.body

            # Find all headings (h1-h6)
            headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

            for heading in headings:
                heading_text = heading.get_text().strip().lower()
                # Check if any of the requested sections match this heading
                if any(section in heading_text for section in sections_lower):
                    # Include this heading and collect content until the next heading of same or higher level
                    current_level = int(
                        heading.name[1]
                    )  # Extract number from h1, h2, etc.

                    # Clone the heading and add it
                    body.append(soup.new_tag(heading.name))
                    body.contents[-1].string = heading.get_text()

                    # Add subsequent elements until we hit another heading of same or higher level
                    current = heading.next_sibling
                    while current:
                        # Skip text nodes that are just whitespace
                        if isinstance(current, str) and current.strip() == "":
                            current = current.next_sibling
                            continue

                        if (
                            hasattr(current, "name")
                            and current.name
                            and current.name in ["h1", "h2", "h3", "h4", "h5", "h6"]
                        ):
                            next_level = int(current.name[1])
                            if next_level <= current_level:
                                break  # Stop at same or higher level heading

                        # Clone and add the element
                        if hasattr(current, "name") and current.name:
                            cloned = soup.new_tag(current.name)
                            if current.string:
                                cloned.string = current.string
                            elif hasattr(current, "get_text"):
                                cloned.string = current.get_text()
                            body.append(cloned)
                        elif isinstance(current, str):  # Text node
                            text_content = current.strip()
                            if text_content:
                                body.append(soup.new_string(text_content))

                        current = current.next_sibling

            if body.contents:
                return str(filtered_soup)

        # If no matches found, return original content
        return html_content

    async def scrape_url(
        self,
        url: str,
        depth: Union[int, str] = "auto",
        is_library_doc: bool = False,
        library_id: Optional[int] = None,
        max_links: Optional[int] = None,
        strict_path: bool = True,
        force_update: bool = False,
        sections: Optional[list] = None,
        filter_selector: Optional[str] = None,
        depth_strategy: Optional[Union[str, DepthStrategy]] = None,
    ) -> Dict[str, Any]:
        """
        Scrape a URL and store the content

        Args:
            url: URL to scrape
            depth: Recursion depth - can be:
                - int: Fixed depth (1, 2, 3, etc.)
                - "auto": Smart depth detection based on content
            depth_strategy: Override the scraper's default strategy

        Returns document metadata
        """
        # Validate URL for security
        try:
            url = validate_url_path(url)
        except PathSecurityError as e:
            self.logger.error(f"Security error with URL {url}: {e}")
            raise ValueError(f"Invalid or unsafe URL: {e}")

        # Reset visited URLs at the start of each top-level scrape
        self.visited_urls = set()
        self.pages_per_domain = {}

        # Handle depth parameter
        if isinstance(depth, str) and depth.lower() == "auto":
            # Use smart depth detection
            effective_depth = min(
                3, config.MAX_SCRAPING_DEPTH
            )  # Start with reasonable default
            use_smart_depth = True
        else:
            # Use fixed depth with maximum limit
            effective_depth = int(depth) if isinstance(depth, str) else depth
            effective_depth = min(effective_depth, config.MAX_SCRAPING_DEPTH)
            use_smart_depth = False

        # Warn if depth was limited
        if effective_depth != depth and depth != "auto":
            self.logger.warning(
                f"Depth limited from {depth} to {effective_depth} (max allowed: {config.MAX_SCRAPING_DEPTH})"
            )

        # Update depth analyzer if strategy is provided
        if depth_strategy:
            if isinstance(depth_strategy, str):
                try:
                    strategy = DepthStrategy(depth_strategy)
                except ValueError:
                    self.logger.warning(
                        f"Invalid depth strategy '{depth_strategy}', using current"
                    )
                    strategy = self.depth_strategy
            else:
                strategy = depth_strategy

            if strategy != self.depth_strategy:
                self.depth_analyzer = DepthAnalyzer(strategy)

        # GitHub repo special handling: fetch README via API
        parsed = urlparse(url)
        if parsed.netloc in ("github.com", "www.github.com"):
            parts = parsed.path.strip("/").split("/")
            # Wiki page support
            if len(parts) >= 3 and parts[2].lower() == "wiki":
                html_content, _ = await self._safe_fetch_url(url)
                if not html_content:
                    raise ValueError(f"Failed to fetch URL: {url}")
                title = processor.extract_title(html_content) or url
                markdown_content = processor.html_to_markdown(html_content)
                html_path = storage.save_html(html_content, url)
                markdown_path = storage.save_markdown(markdown_content, url)
                content_hash = hashlib.sha256(
                    markdown_content.encode("utf-8")
                ).hexdigest()
                document_id = operations.add_document(
                    url=url,
                    title=title,
                    html_path=html_path,
                    markdown_path=markdown_path,
                    library_id=library_id,
                    is_library_doc=is_library_doc,
                    content_hash=content_hash,
                )
                self.stats["pages_scraped"] += 1
                segments = processor.segment_markdown(markdown_content)
                parent_segments = {}  # Track parent segments by level

                for i, segment in enumerate(segments):
                    # Handle both dictionary and tuple formats for backward compatibility
                    if isinstance(segment, dict):
                        stype = segment.get("type", "text")
                        content = segment.get("content", "")
                        section_title = segment.get("section_title", "Introduction")
                        section_level = segment.get("section_level", 0)
                        section_path = segment.get("section_path", "")
                    else:
                        # Legacy tuple format (stype, content)
                        stype, content = segment
                        section_title = "Introduction"
                        section_level = 0
                        section_path = ""

                    segment_type = stype
                    if len(content.strip()) < 3:
                        continue

                    # Update parent segments tracking
                    if segment_type.startswith("h"):
                        level = int(segment_type[1:])
                        parent_segments[level] = {
                            "title": section_title,
                            "path": section_path,
                        }

                    # Get parent segment ID from the hierarchy
                    parent_segment_id = None
                    if section_level > 1:
                        # Find the nearest parent level
                        for lvl in range(section_level - 1, 0, -1):
                            if lvl in parent_segments:
                                # In a real implementation, we'd look up the segment ID
                                # For now, we'll just track the path
                                parent_segment_id = None  # Will be set by the database
                                break

                    # Generate embedding for the content
                    embedding = await embeddings.generate_embeddings(content)

                    # Add the segment with section information
                    operations.add_document_segment(
                        document_id=document_id,
                        content=content,
                        embedding=embedding,
                        segment_type=segment_type,
                        position=i,
                        section_title=section_title,
                        section_level=section_level,
                        section_path=section_path,
                        parent_segment_id=parent_segment_id,
                    )
                    self.stats["segments_created"] += 1
                # Crawl additional wiki pages
                if (use_smart_depth and effective_depth > 0) or (
                    not use_smart_depth and depth > 1
                ):
                    await self._scrape_links(
                        url,
                        html_content,
                        effective_depth - 1 if not use_smart_depth else effective_depth,
                        is_library_doc,
                        library_id,
                        max_links,
                        strict_path,
                        False,  # Don't force update on linked pages
                        sections=sections,
                        filter_selector=filter_selector,
                        use_smart_depth=use_smart_depth,
                    )
                return operations.get_document(document_id)
            elif len(parts) >= 2:
                owner, repo = parts[0], parts[1]
                md_content = await self._fetch_github_readme(owner, repo)
                if md_content:
                    html_path = storage.save_html(md_content, url)
                    markdown_path = storage.save_markdown(md_content, url)
                    title = f"{owner}/{repo}"
                    content_hash = hashlib.sha256(
                        md_content.encode("utf-8")
                    ).hexdigest()
                    document_id = operations.add_document(
                        url=url,
                        title=title,
                        html_path=html_path,
                        markdown_path=markdown_path,
                        library_id=library_id,
                        is_library_doc=is_library_doc,
                        content_hash=content_hash,
                    )
                    self.stats["pages_scraped"] += 1
                    segments = processor.segment_markdown(md_content)
                    parent_segments = {}  # Track parent segments by level

                    for i, segment in enumerate(segments):
                        # Handle both dictionary and tuple formats for backward compatibility
                        if isinstance(segment, dict):
                            stype = segment.get("type", "text")
                            content = segment.get("content", "")
                            section_title = segment.get("section_title", "Introduction")
                            section_level = segment.get("section_level", 0)
                            section_path = segment.get("section_path", "")
                        else:
                            # Legacy tuple format (stype, content)
                            stype, content = segment
                            section_title = "Introduction"
                            section_level = 0
                            section_path = ""

                        segment_type = stype
                        if len(content.strip()) < 3:
                            continue

                        # Update parent segments tracking
                        if segment_type.startswith("h"):
                            level = int(segment_type[1:])
                            parent_segments[level] = {
                                "title": section_title,
                                "path": section_path,
                            }

                        # Get parent segment ID from the hierarchy
                        parent_segment_id = None
                        if section_level > 1:
                            # Find the nearest parent level
                            for lvl in range(section_level - 1, 0, -1):
                                if lvl in parent_segments:
                                    # In a real implementation, we'd look up the segment ID
                                    # For now, we'll just track the path
                                    parent_segment_id = (
                                        None  # Will be set by the database
                                    )
                                    break

                        # Generate embedding for the content
                        embedding = await embeddings.generate_embeddings(content)

                        # Add the segment with section information
                        operations.add_document_segment(
                            document_id=document_id,
                            content=content,
                            embedding=embedding,
                            segment_type=segment_type,
                            position=i,
                            section_title=section_title,
                            section_level=section_level,
                            section_path=section_path,
                            parent_segment_id=parent_segment_id,
                        )
                        self.stats["segments_created"] += 1
                    await self._process_github_repo_structure(
                        owner, repo, library_id, is_library_doc
                    )
                    return operations.get_document(document_id)

        # Fetch HTML for all detection and processing (only once!)
        html_content, fetch_error = await self._safe_fetch_url(url)
        if not html_content:
            raise ValueError(f"Failed to fetch URL: {url}. Reason: {fetch_error}")

        # Check for llms.txt file at the site root
        llms_txt_url = None
        llms_txt_content = None
        try:
            from ..core.llms_txt import detect_llms_txt

            potential_llms_url = detect_llms_txt(url)
            if potential_llms_url:
                llms_content, llms_error = await self._safe_fetch_url(
                    potential_llms_url
                )
                if llms_content and not llms_error:
                    # Check if it's actually an llms.txt file (starts with # and has markdown)
                    if llms_content.strip().startswith("#"):
                        llms_txt_url = potential_llms_url
                        llms_txt_content = llms_content
                        self.logger.info(f"Found llms.txt file at {llms_txt_url}")
        except Exception as e:
            self.logger.debug(f"Error checking for llms.txt: {e}")

        # Apply section filtering if requested
        if sections or filter_selector:
            self.logger.info(
                f"Applying section filtering: sections={sections}, selector={filter_selector}"
            )
            html_content = self._filter_content_sections(
                html_content, sections, filter_selector
            )

        # OpenAPI/Swagger spec detection and handling
        try:
            spec = json.loads(html_content)
        except Exception:
            spec = None
        if spec and ("swagger" in spec or "openapi" in spec):
            md = self._openapi_to_markdown(spec)
            html_path = storage.save_html(html_content, url)
            markdown_path = storage.save_markdown(md, url)
            content_hash = hashlib.sha256(md.encode("utf-8")).hexdigest()
            doc_id = operations.update_document_by_url(
                url=url,
                title=spec.get("info", {}).get("title", url),
                html_path=html_path,
                markdown_path=markdown_path,
                library_id=library_id,
                is_library_doc=is_library_doc,
                content_hash=content_hash,
            )
            self.stats["pages_scraped"] += 1
            segments = processor.segment_markdown(md)
            for i, (stype, content) in enumerate(segments):
                if len(content.strip()) < 3:
                    continue
                emb = await embeddings.generate_embeddings(content)
                operations.add_document_segment(
                    document_id=doc_id,
                    content=content,
                    embedding=emb,
                    segment_type=stype,
                    position=i,
                )
                self.stats["segments_created"] += 1
            self.visited_urls.add(url)
            return operations.get_document(doc_id)

        # Use specialized content extractors based on documentation type
        from bs4 import BeautifulSoup

        from docvault.core.doc_type_detector import DocTypeDetector
        from docvault.core.extractors import (
            GenericExtractor,
            MkDocsExtractor,
            OpenAPIExtractor,
            SphinxExtractor,
        )

        # Detect documentation type
        detector = DocTypeDetector()
        doc_type, confidence = detector.detect(url, html_content)
        self.logger.info(
            f"Detected documentation type: {doc_type.value} (confidence: {confidence:.2f}) for {url}"
        )

        # Select appropriate extractor
        extractors = {
            "sphinx": SphinxExtractor(),
            "mkdocs": MkDocsExtractor(),
            "openapi": OpenAPIExtractor(),
            "swagger": OpenAPIExtractor(),  # Both swagger and openapi use the same extractor
            "readthedocs": SphinxExtractor(),  # ReadTheDocs often uses Sphinx
            "generic": GenericExtractor(),
            "unknown": GenericExtractor(),
        }

        extractor = extractors.get(doc_type.value, GenericExtractor())

        # Extract content using specialized extractor
        soup = BeautifulSoup(html_content, "html.parser")
        extraction_result = extractor.extract(soup, url)

        # Get title and content
        title = (
            extraction_result.get("metadata", {}).get("title")
            or processor.extract_title(html_content)
            or url
        )
        extracted_content = extraction_result.get("content", "")
        extracted_metadata = extraction_result.get("metadata", {})

        # Convert to markdown if not already
        if doc_type.value in ["sphinx", "mkdocs", "openapi"]:
            # For documentation sites, use the extracted content
            markdown_content = extracted_content
        else:
            # For generic content, convert HTML to markdown
            markdown_content = processor.html_to_markdown(html_content)

        # Save files
        html_path = storage.save_html(html_content, url)
        markdown_path = storage.save_markdown(markdown_content, url)
        content_hash = hashlib.sha256(markdown_content.encode("utf-8")).hexdigest()

        # Store document with extracted metadata
        document_id = operations.add_document(
            url=url,
            title=title,
            html_path=html_path,
            markdown_path=markdown_path,
            library_id=library_id,
            is_library_doc=is_library_doc,
            content_hash=content_hash,
            doc_type=doc_type.value,  # Store the detected doc type
            metadata=json.dumps(extracted_metadata) if extracted_metadata else None,
            has_llms_txt=bool(llms_txt_content),
            llms_txt_url=llms_txt_url,
        )
        self.stats["pages_scraped"] += 1

        # Process llms.txt if found
        if llms_txt_content and llms_txt_url:
            try:
                from ..core.llms_txt import LLMsParser
                from ..db.operations_llms import (
                    add_llms_txt_metadata,
                    add_llms_txt_resource,
                )

                parser = LLMsParser()
                llms_doc = parser.parse(llms_txt_content, llms_txt_url)

                # Validate the document
                is_valid, errors = parser.validate(llms_doc)
                if is_valid:
                    # Store metadata
                    sections_json = json.dumps(
                        {
                            section: [
                                {
                                    "title": r.title,
                                    "url": r.url,
                                    "description": r.description,
                                }
                                for r in resources
                            ]
                            for section, resources in llms_doc.sections.items()
                        }
                    )

                    add_llms_txt_metadata(
                        document_id=document_id,
                        llms_title=llms_doc.title,
                        llms_summary=llms_doc.summary,
                        llms_introduction=llms_doc.introduction,
                        llms_sections=sections_json,
                    )

                    # Store individual resources for searchability
                    for section, resources in llms_doc.sections.items():
                        for resource in resources:
                            add_llms_txt_resource(
                                document_id=document_id,
                                section=section,
                                title=resource.title,
                                url=resource.url,
                                description=resource.description,
                                is_optional=resource.is_optional,
                            )

                    self.logger.info(
                        f"Stored llms.txt metadata for document {document_id}"
                    )
                else:
                    self.logger.warning(f"Invalid llms.txt file: {errors}")
            except Exception as e:
                self.logger.error(f"Error processing llms.txt: {e}")

        # Segment the content
        segments = processor.segment_markdown(markdown_content)
        for i, segment in enumerate(segments):
            # Handle both dictionary and tuple formats for backward compatibility
            if isinstance(segment, dict):
                segment_type = segment.get("type", "text")
                content = segment.get("content", "")
                section_title = segment.get("section_title")
                section_level = segment.get("section_level", 0)
                section_path = segment.get("section_path")
            else:
                # Legacy tuple format (stype, content)
                segment_type, content = segment
                section_title = None
                section_level = 0
                section_path = None

            if len(content.strip()) < 3:
                continue
            embedding = await embeddings.generate_embeddings(content)
            operations.add_document_segment(
                document_id=document_id,
                content=content,
                embedding=embedding,
                segment_type=segment_type,
                position=i,
                section_title=section_title,
                section_level=section_level,
                section_path=section_path,
            )
            self.stats["segments_created"] += 1

        # Store extracted elements (API docs, code examples, etc.)
        if "api_elements" in extracted_metadata:
            for api_elem in extracted_metadata["api_elements"]:
                # Store as a special segment for API elements
                api_content = f"# {api_elem['name']}\n\n"
                if api_elem.get("signature"):
                    api_content += f"```python\n{api_elem['signature']}\n```\n\n"
                if api_elem.get("description"):
                    api_content += f"{api_elem['description']}\n\n"
                if api_elem.get("parameters"):
                    api_content += "**Parameters:**\n"
                    for param in api_elem["parameters"]:
                        api_content += f"- `{param['name']}` ({param.get('type', 'Any')}): {param.get('description', '')}\n"
                    api_content += "\n"
                if api_elem.get("returns"):
                    api_content += f"**Returns:** {api_elem['returns']}\n\n"

                # Generate embedding and store
                embedding = await embeddings.generate_embeddings(api_content)
                operations.add_document_segment(
                    document_id=document_id,
                    content=api_content,
                    embedding=embedding,
                    segment_type="api",
                    position=i + 1000,  # Place API elements after regular content
                    section_title=api_elem["name"],
                    section_level=2,
                )
                self.stats["segments_created"] += 1

        # Crawl additional pages for documentation sites
        if doc_type.value in ["sphinx", "mkdocs"] and (
            (use_smart_depth and effective_depth > 0)
            or (not use_smart_depth and effective_depth > 1)
        ):
            await self._scrape_links(
                url,
                html_content,
                effective_depth - 1 if not use_smart_depth else effective_depth,
                is_library_doc,
                library_id,
                max_links,
                strict_path=False,  # Documentation sites often have complex URL structures
                force_update=False,
                sections=sections,
                filter_selector=filter_selector,
                use_smart_depth=use_smart_depth,
            )

        self.visited_urls.add(url)
        return operations.get_document(document_id)

    async def _safe_fetch_url(self, url: str):
        """Call ``_fetch_url`` in a way that is resilient to monkey‑patches and returns (content, error_detail)."""
        try:
            result = await self._fetch_url(url)
            if isinstance(result, tuple) and len(result) == 2:
                return result
            elif result is None:
                return None, "No result returned"
            else:
                return result, None
        except TypeError as exc:
            msg = str(exc)
            if "positional argument" in msg and "given" in msg:
                fetch_fn = getattr(self.__class__, "_fetch_url", None)
                if fetch_fn is None:
                    raise
                if asyncio.iscoroutinefunction(fetch_fn):
                    result = await fetch_fn(url)
                else:
                    result = fetch_fn(url)
                if isinstance(result, tuple) and len(result) == 2:
                    return result
                elif result is None:
                    return None, "No result returned"
                else:
                    return result, None
            raise

    async def _fetch_url(self, url: str) -> tuple:
        """Fetch HTML content from URL. Returns (content, error_detail)"""
        # Validate URL for security with domain allowlist/blocklist
        try:
            url = validate_url_path(
                url,
                allowed_domains=config.URL_ALLOWED_DOMAINS,
                blocked_domains=config.URL_BLOCKED_DOMAINS,
            )
        except PathSecurityError as e:
            self.logger.error(f"Security error with URL {url}: {e}")
            return None, f"Invalid or unsafe URL: {e}"

        self.logger.debug(f"[BEFORE FETCH] visited_urls={self.visited_urls}")
        self.logger.debug(f"[FETCH] Attempting to fetch: {url}")
        if url in self.visited_urls:
            self.logger.debug(f"URL already visited: {url}")
            return None, "URL already visited"

        # Check pages per domain limit
        parsed = urlparse(url)
        domain = parsed.netloc

        # Check rate limits
        from docvault.utils.rate_limiter import get_rate_limiter, get_resource_monitor

        rate_limiter = get_rate_limiter()
        resource_monitor = get_resource_monitor()

        # Check if we're allowed to make this request
        allowed, reason = await rate_limiter.check_rate_limit(domain)
        if not allowed:
            self.logger.warning(f"Rate limit exceeded for {domain}: {reason}")
            return None, reason

        # Check memory usage
        allowed, reason = await resource_monitor.check_memory_usage()
        if not allowed:
            self.logger.error(f"Resource limit exceeded: {reason}")
            return None, reason
        if hasattr(self, "pages_per_domain"):
            if domain not in self.pages_per_domain:
                self.pages_per_domain[domain] = 0

            if self.pages_per_domain[domain] >= config.MAX_PAGES_PER_DOMAIN:
                self.logger.warning(
                    f"Domain {domain} has reached max pages limit ({config.MAX_PAGES_PER_DOMAIN})"
                )
                return (
                    None,
                    f"Domain page limit reached ({config.MAX_PAGES_PER_DOMAIN} pages)",
                )

        # Attach GitHub token if available
        headers = {"User-Agent": "DocVault/0.5.0 Documentation Indexer"}

        # Try to get GitHub token from secure storage or environment
        from docvault.utils.secure_credentials import get_github_token

        token = get_github_token()

        if token and "github.com" in urlparse(url).netloc:
            headers["Authorization"] = f"token {token}"

        # Configure proxy if available
        proxy = None
        if config.HTTPS_PROXY and url.startswith("https://"):
            proxy = config.HTTPS_PROXY
        elif config.HTTP_PROXY and url.startswith("http://"):
            proxy = config.HTTP_PROXY

        # Configure timeout
        timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)

        content, error_detail = None, None
        operation_id = f"fetch_{domain}_{int(time.time())}"

        try:
            # Start tracking operation time
            await resource_monitor.start_operation(operation_id)

            # Acquire rate limiter slot
            async with rate_limiter:
                # Record the request
                await rate_limiter.record_request(domain)

                connector = aiohttp.TCPConnector(ssl=True)  # Enforce SSL/TLS
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(
                        url, headers=headers, timeout=timeout, proxy=proxy
                    ) as response:
                        if response.status == 200:
                            content_type = response.headers.get("Content-Type", "")
                            if (
                                "text/html" not in content_type
                                and "application/xhtml+xml" not in content_type
                                and "application/xml" not in content_type
                                and "application/json" not in content_type
                                and "text/plain" not in content_type
                            ):
                                msg = f"Skipping non-text content: {url} (Content-Type: {content_type})"
                                if not self.quiet:
                                    self.logger.warning(msg)
                                else:
                                    self.logger.debug(msg)
                                error_detail = msg
                            else:
                                # Check content length
                                content_length = response.headers.get("Content-Length")
                                if (
                                    content_length
                                    and int(content_length) > config.MAX_RESPONSE_SIZE
                                ):
                                    msg = f"Response too large: {int(content_length)} bytes (max: {config.MAX_RESPONSE_SIZE})"
                                    self.logger.warning(msg)
                                    error_detail = msg
                                else:
                                    try:
                                        # Read with size limit
                                        content_bytes = b""
                                        async for (
                                            chunk
                                        ) in response.content.iter_chunked(8192):
                                            content_bytes += chunk
                                            if (
                                                len(content_bytes)
                                                > config.MAX_RESPONSE_SIZE
                                            ):
                                                msg = f"Response exceeded size limit of {config.MAX_RESPONSE_SIZE} bytes"
                                                self.logger.warning(msg)
                                                error_detail = msg
                                                content_bytes = None
                                                break

                                        if content_bytes:
                                            content = content_bytes.decode(
                                                "utf-8", errors="replace"
                                            )
                                    except UnicodeDecodeError as e:
                                        msg = f"Unicode decode error for {url}: {e}"
                                        if not self.quiet:
                                            self.logger.warning(msg)
                                        else:
                                            self.logger.debug(msg)
                                        error_detail = msg
                        else:
                            msg = f"Failed to fetch URL: {url} (Status: {response.status})"
                            if response.status != 404:
                                self.logger.warning(msg)
                            error_detail = msg
        except asyncio.TimeoutError:
            error_detail = f"Request timed out after {config.REQUEST_TIMEOUT} seconds"
            self.logger.debug(f"Timeout fetching URL: {url}")
        except aiohttp.ClientConnectorError as e:
            if "Cannot connect to host" in str(e):
                error_detail = "Cannot connect to host"
            elif "nodename nor servname provided" in str(e):
                error_detail = "Invalid domain name"
            else:
                error_detail = "Connection error"
            self.logger.debug(f"Connection error for {url}: {e}")
        except aiohttp.ClientError as e:
            error_detail = "HTTP client error"
            self.logger.debug(f"Client error fetching {url}: {e}")
        except Exception as e:
            error_detail = "Unexpected error"
            self.logger.debug(f"Unexpected error fetching {url}: {e}", exc_info=True)
        finally:
            # Always clean up operation tracking
            await resource_monitor.end_operation(operation_id)

        if content is not None:
            self.visited_urls.add(url)
            # Increment pages per domain counter
            if hasattr(self, "pages_per_domain") and domain in self.pages_per_domain:
                self.pages_per_domain[domain] += 1
                self.logger.debug(
                    f"Domain {domain} has scraped {self.pages_per_domain[domain]} pages"
                )
        self.logger.debug(f"[AFTER FETCH] visited_urls={self.visited_urls}")
        return content, error_detail

    async def _scrape_links(
        self,
        base_url: str,
        html_content: str,
        depth: int,
        is_library_doc: bool,
        library_id: Optional[int],
        max_links: Optional[int] = None,
        strict_path: bool = True,
        force_update: bool = False,
        sections: Optional[list] = None,
        filter_selector: Optional[str] = None,
        use_smart_depth: bool = False,
    ) -> None:
        """Extract and scrape links from HTML content"""
        from bs4 import BeautifulSoup

        # Parse base URL
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc

        # First, check if we should continue crawling based on content
        if use_smart_depth and depth > 0:
            content_scores = self.depth_analyzer.analyze_content(html_content)
            should_continue, suggested_depth = (
                self.depth_analyzer.should_continue_crawling(content_scores, depth)
            )
            if not should_continue:
                self.logger.info(
                    f"Stopping crawl at {base_url} - content score too low: {content_scores['overall']:.2f}"
                )
                return
            # Adjust depth if suggested
            if suggested_depth < depth:
                self.logger.info(
                    f"Reducing depth from {depth} to {suggested_depth} based on content analysis"
                )
                depth = suggested_depth

        # Parse HTML to extract links
        soup = BeautifulSoup(html_content, "html.parser")
        links = soup.find_all("a", href=True)

        # Extract all potential URLs first
        all_urls = []
        for link in links:
            href = link["href"]

            # Skip empty, fragment, javascript, and mailto links
            if (
                not href
                or href.startswith("#")
                or href.startswith("javascript:")
                or href.startswith("mailto:")
            ):
                continue

            # Resolve relative URLs
            full_url = urljoin(base_url, href)
            parsed_url = urlparse(full_url)

            # Skip fragment URLs that reference the same page
            if (
                parsed_url.fragment
                and parsed_url._replace(fragment="").geturl() == base_url
            ):
                continue

            # Skip already visited URLs
            if full_url in self.visited_urls:
                self.stats["pages_skipped"] += 1
                continue

            all_urls.append(full_url)

        # Use depth analyzer to intelligently filter and prioritize links
        if use_smart_depth:
            # Determine max links based on content quality
            content_scores = self.depth_analyzer.analyze_content(html_content)
            if max_links is None:
                # Adjust max_links based on content quality
                if content_scores["overall"] > 0.7:
                    max_links = 50  # High quality docs can have more links
                elif content_scores["overall"] > 0.4:
                    max_links = 30
                else:
                    max_links = 15  # Low quality, be selective

            # Use depth analyzer to prioritize links
            urls_to_scrape = self.depth_analyzer.prioritize_links(
                all_urls, base_url, depth, max_links
            )

            self.logger.info(
                f"Smart depth: selected {len(urls_to_scrape)} of {len(all_urls)} links at depth {depth}"
            )
        else:
            # Traditional filtering for manual depth mode
            urls_to_scrape = []
            for full_url in all_urls:
                parsed_url = urlparse(full_url)

                # Only scrape links from the same domain
                if parsed_url.netloc != base_domain:
                    continue

                urls_to_scrape.append(full_url)

            # Apply traditional max_links limit
            if max_links is not None:
                max_urls = max_links
            else:
                max_urls = max(30, 100 // depth)

            if len(urls_to_scrape) > max_urls:
                self.logger.info(f"Limiting to {max_urls} URLs at depth {depth}")
                urls_to_scrape = urls_to_scrape[:max_urls]

        # Scrape links concurrently (limited concurrency)
        tasks = []
        for url in urls_to_scrape:
            # Log the URL being scraped
            self.logger.debug(f"Queuing: {url} (depth {depth})")
            # For smart depth, let each URL be analyzed independently
            next_depth = depth - 1 if not use_smart_depth else "auto"

            task = asyncio.create_task(
                self.scrape_url(
                    url,
                    next_depth,
                    is_library_doc,
                    library_id,
                    max_links,
                    strict_path,
                    force_update,
                    sections=sections,
                    filter_selector=filter_selector,
                )
            )
            tasks.append(task)

        # Wait for all tasks to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Log any exceptions (but only for non-404 errors)
            for i, result in enumerate(results):
                if isinstance(result, Exception) and not (
                    hasattr(result, "status") and result.status == 404
                ):
                    self.logger.warning(f"Error scraping {urls_to_scrape[i]}: {result}")

        # Handle documentation site navigation menus and pagination
        if depth > 1:
            # For smart depth, let navigation be handled by regular link analysis
            if not use_smart_depth:
                # Navigation links in <nav> elements
                for nav in soup.find_all("nav"):
                    for a in nav.find_all("a", href=True):
                        nav_url = urljoin(base_url, a["href"])
                        if nav_url not in self.visited_urls:
                            await self.scrape_url(
                                nav_url,
                                depth - 1,
                                is_library_doc,
                                library_id,
                                max_links,
                                strict_path=False,
                                force_update=force_update,
                                sections=sections,
                                filter_selector=filter_selector,
                            )
                # Follow rel="next" pagination link
                next_tag = soup.find("a", rel="next")
                if next_tag and isinstance(next_tag.get("href"), str):
                    next_url = urljoin(base_url, next_tag["href"])
                    if next_url not in self.visited_urls:
                        await self.scrape_url(
                            next_url,
                            depth - 1,
                            is_library_doc,
                            library_id,
                            max_links,
                            strict_path=False,
                            force_update=force_update,
                            sections=sections,
                            filter_selector=filter_selector,
                        )

    async def _fetch_github_readme(self, owner: str, repo: str) -> Optional[str]:
        """Fetch README.md content from GitHub API (base64-encoded)."""
        api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        headers = {}
        token = config.GITHUB_TOKEN
        if token:
            headers["Authorization"] = f"token {token}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data.get("content")
                    if content:
                        return base64.b64decode(content).decode("utf-8")
        return None

    async def _process_github_repo_structure(
        self, owner: str, repo: str, library_id: Optional[int], is_library_doc: bool
    ):
        """Fetch and store documentation files from a GitHub repository structure"""
        import aiohttp

        # Prepare headers for GitHub API
        headers = {}
        if hasattr(config, "GITHUB_TOKEN") and config.GITHUB_TOKEN:
            headers["Authorization"] = f"token {config.GITHUB_TOKEN}"
        # Get default branch
        repo_api = f"https://api.github.com/repos/{owner}/{repo}"
        async with aiohttp.ClientSession() as session:
            async with session.get(repo_api, headers=headers) as resp:
                if resp.status != 200:
                    return
                info = await resp.json()
                default_branch = info.get("default_branch", "main")
            # Get repository tree
            tree_api = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
            async with session.get(tree_api, headers=headers) as resp:
                if resp.status != 200:
                    return
                tree_data = await resp.json()
        tree = tree_data.get("tree", [])
        # Process each file blob
        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            low = path.lower()
            # Include docs folder and markdown/rst files, exclude README
            if (
                low.startswith("docs/") or low.endswith((".md", ".rst"))
            ) and low != "readme.md":
                # Fetch file content
                content_api = (
                    f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
                )
                async with aiohttp.ClientSession() as session:
                    async with session.get(content_api, headers=headers) as fresp:
                        if fresp.status != 200:
                            continue
                        data = await fresp.json()
                encoded = data.get("content")
                if not encoded or data.get("encoding") != "base64":
                    continue
                try:
                    decoded = base64.b64decode(encoded).decode("utf-8", errors="ignore")
                except Exception:
                    continue
                # Store file
                file_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{path}"
                title = path
                html_path = storage.save_html(decoded, file_url)
                markdown_path = storage.save_markdown(decoded, file_url)
                doc_id = operations.add_document(
                    url=file_url,
                    title=title,
                    html_path=html_path,
                    markdown_path=markdown_path,
                    library_id=library_id,
                    is_library_doc=is_library_doc,
                )
                self.stats["pages_scraped"] += 1
                segments = processor.segment_markdown(decoded)
                for i, (stype, content) in enumerate(segments):
                    if len(content.strip()) < 3:
                        continue
                    emb = await embeddings.generate_embeddings(content)
                    operations.add_document_segment(
                        document_id=doc_id,
                        content=content,
                        embedding=emb,
                        segment_type=stype,
                        position=i,
                    )
                    self.stats["segments_created"] += 1

    def _openapi_to_markdown(self, spec: Dict[str, Any]) -> str:
        md = f"# {spec.get('info', {}).get('title', '')}\n\n"
        md += spec.get("info", {}).get("description", "") + "\n\n"
        for path, methods in spec.get("paths", {}).items():
            md += f"## {path}\n\n"
            for method, op in methods.items():
                md += f"### {method.upper()}\n\n"
                if "summary" in op:
                    md += f"- summary: {op['summary']}\n"
                if "description" in op:
                    md += f"{op['description']}\n"
                if "parameters" in op:
                    md += "\n**Parameters**\n\n"
                    for param in op["parameters"]:
                        name = param.get("name")
                        required = param.get("required", False)
                        desc = param.get("description", "")
                        md += f"- `{name}` ({'required' if required else 'optional'}): {desc}\n"
                    md += "\n"
                if "responses" in op:
                    md += "\n**Responses**\n\n"
                    for code, resp in op["responses"].items():
                        desc = resp.get("description", "")
                        md += f"- **{code}**: {desc}\n"
                    md += "\n"
        return md


# Create singleton instance
scraper = WebScraper()


# Convenience function
async def scrape_url(
    url: str,
    depth: int = 1,
    is_library_doc: bool = False,
    library_id: Optional[int] = None,
    max_links: Optional[int] = None,
    strict_path: bool = True,
    sections: Optional[list] = None,
    filter_selector: Optional[str] = None,
) -> Dict[str, Any]:
    """Scrape a URL and store the content"""
    return await scraper.scrape_url(
        url,
        depth,
        is_library_doc,
        library_id,
        max_links,
        strict_path,
        False,
        sections,
        filter_selector,
    )
