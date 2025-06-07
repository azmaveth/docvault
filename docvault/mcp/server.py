import logging
import re
from typing import Optional, Union

import mcp.server.stdio

# Import types for responses
import mcp.types as types

# Import the FastMCP server
from mcp.server.fastmcp import FastMCP

import docvault.core.storage as storage
from docvault import config
from docvault.core.content_chunker import ChunkingStrategy, ContentChunker
from docvault.core.library_manager import lookup_library_docs
from docvault.core.scraper import get_scraper
from docvault.core.section_index import SectionIndexer
from docvault.core.summarizer import DocumentSummarizer
from docvault.core.vector_summarizer import VectorSummarizer
from docvault.db import operations
from docvault.db.operations import get_connection

types.ToolResult = types.CallToolResult  # alias for backward compatibility with tests

logger = logging.getLogger("docvault.mcp")


def create_server() -> FastMCP:
    """Create and configure the MCP server using FastMCP"""
    # Create FastMCP server
    server = FastMCP("DocVault")

    # Add document scraping tool
    @server.tool()
    async def scrape_document(
        url: str,
        depth: int | str = 1,
        sections: list | None = None,
        filter_selector: str | None = None,
        depth_strategy: str | None = None,
        force_update: bool = False,
    ) -> types.CallToolResult:
        """Scrape a document from a URL and store it in the document vault.

        Args:
            url: The URL to scrape
            depth: How many levels deep to scrape - number (1=single page) or
                   strategy (auto/conservative/aggressive) (default: 1)
            sections: Filter by section headings (e.g., ['Installation', 'API Reference'])
            filter_selector: CSS selector to filter specific sections (e.g., '.documentation', '#api-docs')
            depth_strategy: Override the depth control strategy (auto/conservative/aggressive/manual)
            force_update: If True, re-scrape even if document already exists (updates existing)

        Examples:
            scrape_document("https://docs.python.org/3/")
            scrape_document("https://docs.example.com", depth=2)
            scrape_document("https://api.example.com", sections=["Authentication", "Endpoints"])
            scrape_document("https://docs.example.com", force_update=True)  # Update existing
        """
        try:
            # Parse depth parameter - handle both int and string
            if isinstance(depth, str):
                if depth.lower() in ["auto", "conservative", "aggressive"]:
                    depth_param = depth.lower()
                else:
                    try:
                        depth_param = int(depth)
                    except ValueError:
                        depth_param = "auto"
            else:
                depth_param = depth

            scraper = get_scraper()
            result = await scraper.scrape_url(
                url,
                depth=depth_param,
                sections=sections,
                filter_selector=filter_selector,
                depth_strategy=depth_strategy,
                force_update=force_update,
            )

            # Build success message with section info
            success_msg = (
                f"Successfully scraped document: {result['title']} (ID: {result['id']})"
            )
            if sections:
                success_msg += f" - Filtered by sections: {', '.join(sections)}"
            if filter_selector:
                success_msg += f" - Filtered by CSS selector: {filter_selector}"

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=success_msg,
                    )
                ],
                metadata={
                    "document_id": result["id"],
                    "title": result["title"],
                    "url": url,
                    "sections": sections,
                    "filter_selector": filter_selector,
                    "success": True,
                },
            )
        except Exception as e:
            logger.exception(f"Error scraping document: {e}")
            error_msg = str(e)

            # Provide more helpful error messages for common issues
            if "rate limit" in error_msg.lower():
                error_msg = (
                    f"Rate limit exceeded for this domain. {error_msg}\n"
                    "Try again later or reduce the scraping depth."
                )
            elif "cooldown" in error_msg.lower():
                # Extract cooldown time if possible
                import re

                cooldown_match = re.search(r"cooldown for (\d+) seconds", error_msg)
                if cooldown_match:
                    seconds = cooldown_match.group(1)
                    error_msg = (
                        f"Domain is in cooldown period. Please wait {seconds} seconds.\n"
                        f"This prevents overwhelming the target server."
                    )
            elif "timeout" in error_msg.lower():
                error_msg = (
                    "Request timed out. The server may be slow or unresponsive.\n"
                    "Try again with a single page (depth=1) first."
                )
            elif "connection" in error_msg.lower():
                error_msg = (
                    "Connection error. Please check:\n"
                    "- The URL is correct and accessible\n"
                    "- Your internet connection is stable\n"
                    "- The target server is online"
                )

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error scraping document: {error_msg}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Add document search tool
    @server.tool()
    async def search_documents(
        query: str | None = None,
        limit: int = 5,
        min_score: float = 0.0,
        version: str | None = None,
        library: bool = False,
        title_contains: str | None = None,
        updated_after: str | None = None,
    ) -> types.CallToolResult:
        """Search documents in the vault using semantic search with metadata filtering.

        Args:
            query: The search query (optional if using filters)
            limit: Maximum number of results to return (default: 5)
            min_score: Minimum similarity score (0.0 to 1.0, default: 0.0)
            version: Filter by document version
            library: Only show library documentation
            title_contains: Filter by document title containing text
            updated_after: Filter by last updated after date (YYYY-MM-DD)

        Examples:
            search_documents("python sqlite", version="3.10")
            search_documents(library=True, title_contains="API")
            search_documents(updated_after="2023-01-01")
        """
        try:
            # Prepare document filters
            doc_filter = {}
            if version:
                doc_filter["version"] = version
            if library:
                doc_filter["is_library_doc"] = True
            if title_contains:
                doc_filter["title_contains"] = title_contains
            if updated_after:
                try:
                    from datetime import datetime

                    # Parse and validate date format
                    parsed_date = datetime.strptime(updated_after, "%Y-%m-%d")
                    doc_filter["updated_after"] = parsed_date.strftime("%Y-%m-%d")
                except ValueError as e:
                    error_msg = f"Invalid date format. Use YYYY-MM-DD: {e}"
                    logger.error(error_msg)
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=error_msg)],
                        metadata={"success": False, "error": error_msg},
                    )

            # Use text-only search if no query but filters are provided
            text_only = not bool(query) and bool(doc_filter)

            # Import here to avoid circular imports
            from docvault.core.embeddings import search

            results = await search(
                query=query,
                limit=limit,
                text_only=text_only,
                min_score=min_score,
                doc_filter=doc_filter if doc_filter else None,
            )

            content_items = []
            for r in results:
                # Build metadata line
                metadata_parts = []
                if r.get("version"):
                    metadata_parts.append(f"v{r['version']}")
                if r.get("updated_at"):
                    updated = (
                        r["updated_at"].split("T")[0]
                        if isinstance(r.get("updated_at"), str)
                        else r.get("updated_at")
                    )
                    metadata_parts.append(f"updated: {updated}")
                if r.get("is_library_doc") and r.get("library_name"):
                    metadata_parts.append(f"library: {r['library_name']}")

                result_text = f"Document: {r.get('title', 'Untitled')} (ID: {r.get('document_id', 'N/A')})\n"
                if metadata_parts:
                    result_text += f"{' • '.join(metadata_parts)}\n"
                result_text += f"Score: {r.get('score', 0):.2f}"
                if r.get("is_contextual"):
                    result_text += " [contextual]"
                result_text += "\n"
                result_text += f"Content: {r.get('content', '')[:200]}{'...' if len(r.get('content', '')) > 200 else ''}\n"
                if r.get("section_title"):
                    result_text += f"Section: {r['section_title']}\n"
                if r.get("context_description"):
                    result_text += f"Context: {r['context_description'][:100]}...\n"
                result_text += "\n"

                content_items.append(types.TextContent(type="text", text=result_text))

            # If no results, add a message
            if not content_items:
                if query:
                    msg = f"No results found for '{query}'".strip()
                else:
                    msg = "No documents found matching the specified filters"

                filter_msg = []
                if version:
                    filter_msg.append(f"version={version}")
                if library:
                    filter_msg.append("library=True")
                if title_contains:
                    filter_msg.append(f"title_contains={title_contains}")
                if updated_after:
                    filter_msg.append(f"updated_after={updated_after}")

                if filter_msg:
                    msg += f" with filters: {', '.join(filter_msg)}"

                content_items.append(types.TextContent(type="text", text=msg))

            return types.CallToolResult(
                content=content_items,
                metadata={
                    "success": True,
                    "result_count": len(results),
                    "query": query,
                    "filters": doc_filter if doc_filter else {},
                },
            )
        except Exception as e:
            logger.exception(f"Error searching documents: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error searching documents: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Add document read tool
    @server.tool()
    async def read_document(
        document_id: int,
        format: str = "markdown",
        mode: str = "summary",
        chunk_size: int = 5000,
        chunk_number: int = 1,
        summary_method: str = "vector",
        chunking_strategy: str = "hybrid",
    ) -> types.CallToolResult:
        """Read document content from the vault with automatic summarization or chunking.

        Args:
            document_id: The ID of the document to read
            format: Format to return - "markdown" (default) or "html"
            mode: Reading mode - "summary" (default), "full", or "chunk"
                  - summary: Returns concise summary with key functions, classes, and examples
                  - full: Returns complete document content (may fail for large docs)
                  - chunk: Returns a specific chunk of the document
            chunk_size: Size of each chunk in characters (for chunk mode)
            chunk_number: Which chunk to return (1-based, for chunk mode)
            summary_method: Method for summarization - "vector" (default) or "pattern"
                  - vector: Uses embeddings to find most relevant sections
                  - pattern: Uses regex patterns to extract functions/classes
            chunking_strategy: Strategy for chunking - "hybrid" (default), "section", "semantic", "paragraph", or "character"
                  - hybrid: Combines section and semantic awareness
                  - section: Chunks align with document sections
                  - semantic: Chunks at natural boundaries (paragraphs, sentences)
                  - paragraph: Chunks at paragraph boundaries
                  - character: Simple character-based chunking (legacy)

        Examples:
            read_document(5)  # Get summary (default)
            read_document(5, mode="full")  # Try to get full content
            read_document(5, mode="chunk", chunk_number=1)  # Get first chunk
            read_document(5, mode="chunk", chunk_number=2)  # Get second chunk
        """
        try:
            document = operations.get_document(document_id)

            if not document:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=f"Document not found: {document_id}"
                        )
                    ],
                    metadata={
                        "success": False,
                        "error": f"Document not found: {document_id}",
                    },
                )

            # Read the content
            if format.lower() == "html":
                content = storage.read_html(document["html_path"])
            else:
                content = storage.read_markdown(document["markdown_path"])

            # Handle different modes
            if mode == "summary":
                # Choose summarization method
                if summary_method == "vector":
                    # Try vector-based summarization
                    try:
                        vector_summarizer = VectorSummarizer(use_embeddings=True)
                        vector_summary = vector_summarizer.summarize_document(
                            document_id, max_sections=3
                        )
                        result_content = vector_summarizer.format_summary(
                            vector_summary, format="markdown"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Vector summarization failed, falling back to pattern-based: {e}"
                        )
                        # Fall back to pattern-based summarizer
                        summarizer = DocumentSummarizer()
                        summary = summarizer.summarize(content, max_items=15)
                        formatted_summary = summarizer.format_summary(
                            summary, format="markdown"
                        )

                        # Add metadata about summarization
                        result_content = f"# Summary of {document['title']}\n\n"
                        result_content += "*This is a summarized version focusing on key functions, classes, and examples.*\n\n"
                        result_content += formatted_summary
                else:
                    # Use pattern-based summarizer
                    summarizer = DocumentSummarizer()
                    summary = summarizer.summarize(content, max_items=15)
                    formatted_summary = summarizer.format_summary(
                        summary, format="markdown"
                    )

                    # Add metadata about summarization
                    result_content = f"# Summary of {document['title']}\n\n"
                    result_content += "*This is a summarized version focusing on key functions, classes, and examples.*\n\n"
                    result_content += formatted_summary

                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=result_content)],
                    metadata={
                        "success": True,
                        "document_id": document_id,
                        "title": document["title"],
                        "url": document["url"],
                        "format": format,
                        "mode": "summary",
                        "summary_method": summary_method,
                        "original_length": len(content),
                        "summary_length": len(result_content),
                    },
                )

            elif mode == "chunk":
                # Use advanced chunking system
                try:
                    chunker = ContentChunker(document_id)
                    chunk = chunker.get_chunk(
                        chunk_number=chunk_number,
                        chunk_size=chunk_size,
                        strategy=ChunkingStrategy(chunking_strategy),
                    )

                    # Format chunk with metadata
                    chunk_header = f"# {document['title']} - Chunk {chunk.metadata.chunk_number}/{chunk.metadata.total_chunks}\n\n"

                    # Add section info if available
                    if chunk.metadata.section_title:
                        chunk_header += f"**Section**: {chunk.metadata.section_title}\n"
                    if chunk.metadata.section_path:
                        chunk_header += f"**Path**: {chunk.metadata.section_path}\n\n"

                    # Add continuation markers
                    if chunk.metadata.has_prev:
                        chunk_header += "*...continued from previous chunk*\n\n"

                    chunk_footer = ""
                    if chunk.metadata.has_next:
                        chunk_footer = "\n\n*...continues in next chunk*"
                        if chunk.metadata.next_section:
                            chunk_footer += (
                                f" (Next: Section {chunk.metadata.next_section})"
                            )

                    result_content = chunk_header + chunk.content + chunk_footer

                    # Return with rich metadata
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=result_content)],
                        metadata={
                            "success": True,
                            "document_id": document_id,
                            "title": document["title"],
                            "url": document["url"],
                            "format": format,
                            "mode": "chunk",
                            "chunking_strategy": chunk.metadata.strategy_used,
                            "chunk_number": chunk.metadata.chunk_number,
                            "total_chunks": chunk.metadata.total_chunks,
                            "chunk_size": chunk_size,
                            "section_path": chunk.metadata.section_path,
                            "section_title": chunk.metadata.section_title,
                            "has_next": chunk.metadata.has_next,
                            "has_prev": chunk.metadata.has_prev,
                            "next_section": chunk.metadata.next_section,
                            "prev_section": chunk.metadata.prev_section,
                        },
                    )

                except ValueError as e:
                    # Handle invalid chunk numbers gracefully
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=str(e))],
                        metadata={
                            "success": False,
                            "error": str(e),
                        },
                    )
                except Exception as e:
                    logger.warning(
                        f"Advanced chunking failed, falling back to character chunking: {e}"
                    )
                    # Fall back to simple character chunking
                    total_length = len(content)
                    total_chunks = (total_length + chunk_size - 1) // chunk_size

                    if chunk_number < 1 or chunk_number > total_chunks:
                        return types.CallToolResult(
                            content=[
                                types.TextContent(
                                    type="text",
                                    text=f"Invalid chunk number {chunk_number}. Document has {total_chunks} chunks.",
                                )
                            ],
                            metadata={
                                "success": False,
                                "error": f"Invalid chunk number. Valid range: 1-{total_chunks}",
                                "total_chunks": total_chunks,
                            },
                        )

                    # Calculate chunk boundaries
                    start = (chunk_number - 1) * chunk_size
                    end = min(start + chunk_size, total_length)
                    chunk_content = content[start:end]

                    # Add chunk metadata
                    chunk_header = f"# {document['title']} - Chunk {chunk_number}/{total_chunks}\n\n"
                    if chunk_number > 1:
                        chunk_header += "*...continued from previous chunk*\n\n"

                    chunk_footer = ""
                    if chunk_number < total_chunks:
                        chunk_footer = "\n\n*...continues in next chunk*"

                    result_content = chunk_header + chunk_content + chunk_footer

                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=result_content)],
                        metadata={
                            "success": True,
                            "document_id": document_id,
                            "title": document["title"],
                            "url": document["url"],
                            "format": format,
                            "mode": "chunk",
                            "chunking_strategy": "character",
                            "chunk_number": chunk_number,
                            "total_chunks": total_chunks,
                            "chunk_size": chunk_size,
                        },
                    )

            else:  # mode == "full"
                # Return full content with a warning if large
                if len(content) > 25000:  # Roughly 6250 tokens
                    warning = (
                        "⚠️ **Warning**: This document is very large and may exceed token limits.\n"
                        "Consider using mode='summary' for a concise version or mode='chunk' to read in parts.\n\n"
                    )
                    content = warning + content

                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=content)],
                    metadata={
                        "success": True,
                        "document_id": document_id,
                        "title": document["title"],
                        "url": document["url"],
                        "format": format,
                        "mode": "full",
                        "content_length": len(content),
                    },
                )

        except Exception as e:
            logger.exception(f"Error reading document: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error reading document: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Add library docs lookup tool
    @server.tool(name="lookup_library_docs")
    async def lookup_library_docs_tool(
        library_name: str, version: str = "latest"
    ) -> types.CallToolResult:
        """Lookup and fetch documentation for a specific library and version if not already available"""
        try:
            documents = await lookup_library_docs(library_name, version)

            if not documents:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Could not find documentation for {library_name} {version}",
                        )
                    ],
                    metadata={
                        "success": False,
                        "message": f"Could not find documentation for {library_name} {version}",
                    },
                )

            content_text = (
                f"Documentation for {library_name} {version} is available:\n\n"
            )
            for doc in documents:
                content_text += f"- {doc['title']} (ID: {doc['id']})\n"

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content_text)],
                metadata={
                    "success": True,
                    "message": f"Documentation for {library_name} {version} is available",
                    "document_count": len(documents),
                    "documents": [
                        {"id": doc["id"], "title": doc["title"], "url": doc["url"]}
                        for doc in documents
                    ],
                },
            )
        except Exception as e:
            logger.exception(f"Error looking up library docs: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Error looking up library documentation: {str(e)}",
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Add suggestion tool
    @server.tool()
    async def suggest(
        query: str,
        limit: int = 5,
        task_based: bool = False,
        complementary: str | None = None,
    ) -> types.CallToolResult:
        """Get AI-powered suggestions for functions, classes, or documentation based on a query.

        Args:
            query: The task or concept to get suggestions for (e.g., "database connection", "error handling")
            limit: Maximum number of suggestions to return (default: 5)
            task_based: If True, returns task-oriented suggestions instead of just matching functions
            complementary: Find functions that complement this function name (e.g., "open" -> suggests "close")

        Examples:
            suggest("file handling", task_based=True)
            suggest("database queries", limit=10)
            suggest("open", complementary="open")
        """
        try:
            from docvault.core.suggestion_engine import SuggestionEngine

            engine = SuggestionEngine()

            # Use the appropriate method based on the request type
            if complementary:
                suggestions = engine.get_complementary_functions(
                    function_name=complementary, limit=limit
                )
            elif task_based:
                suggestions = engine.get_task_based_suggestions(
                    task_description=query, limit=limit
                )
            else:
                suggestions = engine.get_suggestions(query=query, limit=limit)

            if not suggestions:
                msg = f"No suggestions found for '{query}'"
                if complementary:
                    msg = f"No complementary functions found for '{complementary}'"
                elif task_based:
                    msg = f"No task-based suggestions found for '{query}'"

                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=msg)],
                    metadata={"success": True, "suggestion_count": 0},
                )

            content_text = f"Suggestions for '{query}':\n\n"
            if complementary:
                content_text = f"Functions complementary to '{complementary}':\n\n"
            elif task_based:
                content_text = f"Task-based suggestions for '{query}':\n\n"

            for i, suggestion in enumerate(suggestions, 1):
                content_text += f"{i}. {suggestion.title}\n"
                content_text += f"   Type: {suggestion.type}\n"
                if suggestion.description:
                    content_text += f"   Description: {suggestion.description}\n"
                if hasattr(suggestion, "document_title"):
                    content_text += f"   From: {suggestion.document_title}\n"
                if suggestion.relevance_score:
                    content_text += f"   Relevance: {suggestion.relevance_score:.2f}\n"
                content_text += "\n"

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content_text)],
                metadata={
                    "success": True,
                    "suggestion_count": len(suggestions),
                    "query": query,
                    "task_based": task_based,
                    "complementary": complementary,
                    "suggestions": [
                        {
                            "identifier": s.identifier,
                            "type": s.type,
                            "title": s.title,
                            "description": s.description,
                            "relevance_score": s.relevance_score,
                            "reason": s.reason,
                        }
                        for s in suggestions
                    ],
                },
            )
        except Exception as e:
            logger.exception(f"Error getting suggestions: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error getting suggestions: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Add tag operations
    @server.tool()
    async def add_tags(
        document_id: int,
        tags: list[str],
    ) -> types.CallToolResult:
        """Add tags to a document for better organization and searchability.

        Args:
            document_id: The ID of the document to tag
            tags: List of tags to add (e.g., ["python", "api", "async"])

        Examples:
            add_tags(5, ["python", "database", "orm"])
            add_tags(10, ["javascript", "frontend", "react"])
        """
        try:
            from docvault.models.tags import add_tag_to_document

            # Validate document exists
            document = operations.get_document(document_id)
            if not document:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=f"Document not found: {document_id}"
                        )
                    ],
                    metadata={
                        "success": False,
                        "error": f"Document not found: {document_id}",
                    },
                )

            # Add tags one by one
            for tag in tags:
                add_tag_to_document(document_id, tag)

            content_text = (
                f"Successfully added {len(tags)} tags to document {document_id}:\n"
            )
            content_text += f"Document: {document['title']}\n"
            content_text += f"Tags added: {', '.join(tags)}\n"

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content_text)],
                metadata={
                    "success": True,
                    "document_id": document_id,
                    "tags_added": tags,
                    "tag_count": len(tags),
                },
            )
        except Exception as e:
            logger.exception(f"Error adding tags: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(type="text", text=f"Error adding tags: {str(e)}")
                ],
                metadata={"success": False, "error": str(e)},
            )

    @server.tool()
    async def search_by_tags(
        tags: list[str],
        match_all: bool = False,
        limit: int = 10,
    ) -> types.CallToolResult:
        """Search documents by tags.

        Args:
            tags: List of tags to search for
            match_all: If True, only return documents with ALL tags. If False, return documents with ANY tags.
            limit: Maximum number of results to return (default: 10)

        Examples:
            search_by_tags(["python", "api"])  # Documents with python OR api
            search_by_tags(["database", "orm"], match_all=True)  # Documents with database AND orm
        """
        try:
            from docvault.models.tags import search_documents_by_tags

            documents = search_documents_by_tags(
                tags, mode="all" if match_all else "any"
            )

            # Apply limit
            if limit and len(documents) > limit:
                documents = documents[:limit]

            if not documents:
                match_type = "all" if match_all else "any"
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"No documents found with {match_type} of these tags: {', '.join(tags)}",
                        )
                    ],
                    metadata={"success": True, "document_count": 0},
                )

            match_type = "all" if match_all else "any"
            content_text = f"Found {len(documents)} documents with {match_type} of these tags: {', '.join(tags)}\n\n"

            for doc in documents:
                content_text += f"- ID {doc['id']}: {doc['title']}\n"
                if doc.get("tags"):
                    content_text += f"  Tags: {', '.join(doc['tags'])}\n"
                content_text += f"  URL: {doc['url']}\n\n"

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content_text)],
                metadata={
                    "success": True,
                    "document_count": len(documents),
                    "tags_searched": tags,
                    "match_all": match_all,
                    "documents": [
                        {
                            "id": doc["id"],
                            "title": doc["title"],
                            "url": doc["url"],
                            "tags": doc.get("tags", []),
                        }
                        for doc in documents
                    ],
                },
            )
        except Exception as e:
            logger.exception(f"Error searching by tags: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error searching by tags: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Add freshness checking
    @server.tool()
    async def check_freshness(
        document_id: int | None = None,
        stale_only: bool = False,
    ) -> types.CallToolResult:
        """Check the freshness status of documents to identify outdated content.

        Args:
            document_id: Check a specific document. If None, checks all documents.
            stale_only: If True, only return stale/outdated documents

        Examples:
            check_freshness()  # Check all documents
            check_freshness(5)  # Check specific document
            check_freshness(stale_only=True)  # Only show outdated docs
        """
        try:
            from docvault.utils.freshness import FreshnessLevel, get_freshness_info

            if document_id:
                # Check single document
                document = operations.get_document(document_id)
                if not document:
                    return types.CallToolResult(
                        content=[
                            types.TextContent(
                                type="text", text=f"Document not found: {document_id}"
                            )
                        ],
                        metadata={
                            "success": False,
                            "error": f"Document not found: {document_id}",
                        },
                    )

                # get_freshness_info returns (level, age_desc, formatted_date)
                level, age_desc, formatted_date = get_freshness_info(
                    document["scraped_at"]
                )
                status_emoji = {
                    FreshnessLevel.FRESH: "✅",
                    FreshnessLevel.RECENT: "✅",
                    FreshnessLevel.STALE: "⚠️",
                    FreshnessLevel.OUTDATED: "❌",
                }[level]

                content_text = (
                    f"{status_emoji} Document {document_id}: {document['title']}\n"
                )
                content_text += f"Status: {level.value.upper()}\n"
                content_text += f"Age: {age_desc}\n"
                content_text += f"Last updated: {formatted_date}\n"

                from docvault.utils.freshness import get_update_suggestion

                recommendation = get_update_suggestion(level)
                if recommendation:
                    content_text += f"Recommendation: {recommendation}\n"

                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=content_text)],
                    metadata={
                        "success": True,
                        "document_id": document_id,
                        "status": level.value,
                    },
                )
            else:
                # Check all documents
                documents = operations.list_documents(limit=1000)
                fresh_count = 0
                stale_count = 0
                outdated_count = 0
                results = []

                for doc in documents:
                    level, age_desc, _ = get_freshness_info(doc["scraped_at"])

                    if level in (FreshnessLevel.FRESH, FreshnessLevel.RECENT):
                        fresh_count += 1
                        if not stale_only:
                            results.append((doc, level, age_desc))
                    elif level == FreshnessLevel.STALE:
                        stale_count += 1
                        results.append((doc, level, age_desc))
                    else:  # OUTDATED
                        outdated_count += 1
                        results.append((doc, level, age_desc))

                content_text = "Document Freshness Summary:\n"
                content_text += f"✅ Fresh: {fresh_count}\n"
                content_text += f"⚠️  Stale: {stale_count}\n"
                content_text += f"❌ Outdated: {outdated_count}\n\n"

                if stale_only:
                    content_text += "Stale/Outdated Documents:\n\n"
                else:
                    content_text += "All Documents:\n\n"

                for doc, level, age_desc in results[:20]:  # Limit output
                    status_emoji = {
                        FreshnessLevel.FRESH: "✅",
                        FreshnessLevel.RECENT: "✅",
                        FreshnessLevel.STALE: "⚠️",
                        FreshnessLevel.OUTDATED: "❌",
                    }[level]

                    content_text += f"{status_emoji} ID {doc['id']}: {doc['title']}\n"
                    content_text += f"   Age: {age_desc}\n"

                if len(results) > 20:
                    content_text += f"\n... and {len(results) - 20} more documents"

                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=content_text)],
                    metadata={
                        "success": True,
                        "fresh_count": fresh_count,
                        "stale_count": stale_count,
                        "outdated_count": outdated_count,
                        "total_count": len(documents),
                    },
                )
        except Exception as e:
            logger.exception(f"Error checking freshness: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error checking freshness: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Add quick add from package managers
    @server.tool()
    async def add_from_package_manager(
        package: str,
        manager: str = "auto",
        version: str = "latest",
        force: bool = False,
    ) -> types.CallToolResult:
        """Quickly add documentation for a package from various package managers.

        Args:
            package: Package name (e.g., "requests", "express", "phoenix")
            manager: Package manager - one of: auto, pypi, npm, gem, hex, go, cargo
                    'auto' will try to detect based on package name patterns
            version: Package version (default: "latest")
            force: If True, re-fetch documentation even if it already exists

        Examples:
            add_from_package_manager("requests")  # Auto-detect Python package
            add_from_package_manager("express", "npm")  # Node.js package
            add_from_package_manager("rails", "gem", "7.0.0")  # Specific version
        """
        try:
            # Import the quick add functionality
            from docvault.cli.quick_add_commands import (
                get_package_manager_info,
                quick_add_package,
            )

            # Auto-detect package manager if needed
            if manager == "auto":
                # Simple heuristics
                if "/" in package:  # Go packages often have slashes
                    manager = "go"
                elif package.endswith("-rs") or package in ["tokio", "serde", "axum"]:
                    manager = "cargo"
                elif package in ["phoenix", "ecto", "poison"]:
                    manager = "hex"
                elif package in ["rails", "sinatra", "rspec"]:
                    manager = "gem"
                elif package in ["express", "react", "vue", "lodash"]:
                    manager = "npm"
                else:
                    manager = "pypi"  # Default to Python

            # Map manager aliases to actual package manager names
            pm_name, display_name = get_package_manager_info(manager)

            if not pm_name:
                # If not found in aliases, check if it's a direct package manager name
                valid_managers = [
                    "pypi",
                    "npm",
                    "gem",
                    "hex",
                    "go",
                    "crates",
                    "packagist",
                ]
                if manager in valid_managers:
                    pm_name = manager
                    display_name = manager.upper()
                else:
                    return types.CallToolResult(
                        content=[
                            types.TextContent(
                                type="text",
                                text=f"Unknown package manager: {manager}. Supported: pypi, npm, gem, hex, go, cargo/crates, composer/packagist",
                            )
                        ],
                        metadata={
                            "success": False,
                            "error": f"Unknown package manager: {manager}",
                        },
                    )

            # Call the quick_add_package function
            result = await quick_add_package(pm_name, package, version, force=force)

            # Parse the result
            if result:
                # Check if it already exists
                if result.get("already_exists"):
                    if result.get("has_local_docs", True):
                        content_text = (
                            f"Documentation for {package} already exists in DocVault:\n"
                        )
                        content_text += f"Title: {result.get('title', 'Unknown')}\n"
                        content_text += f"Version: {result.get('version', version)}\n"
                        content_text += f"Document ID: {result.get('id', 'Unknown')}\n"
                        content_text += f"URL: {result.get('url', 'Unknown')}\n"
                        content_text += (
                            "\nUse force=True to re-fetch the documentation."
                        )
                    else:
                        content_text = (
                            f"Package {package} is registered but documentation is not available locally.\n"
                            f"The documentation may have been deleted or the URL may be invalid."
                        )

                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=content_text)],
                        metadata={
                            "success": False,
                            "package": package,
                            "manager": pm_name,
                            "version": version,
                            "already_exists": True,
                            "has_local_docs": result.get("has_local_docs", True),
                            "document": (
                                result if result.get("has_local_docs", True) else None
                            ),
                        },
                    )
                else:
                    # Successfully added new documentation
                    content_text = f"Successfully added documentation for {package} from {display_name or pm_name}:\n"
                    content_text += f"Title: {result.get('title', 'Unknown')}\n"
                    content_text += f"Version: {version}\n"
                    content_text += f"Document ID: {result.get('id', 'Unknown')}\n"
                    content_text += f"URL: {result.get('url', 'Unknown')}\n"

                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=content_text)],
                        metadata={
                            "success": True,
                            "package": package,
                            "manager": pm_name,
                            "version": version,
                            "document": result,
                        },
                    )
            else:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Failed to add {package} from {display_name or pm_name}: Documentation not found",
                        )
                    ],
                    metadata={"success": False, "error": "Documentation not found"},
                )

        except Exception as e:
            logger.exception(f"Error adding from package manager: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error adding from package manager: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Add section navigation
    @server.tool()
    async def get_document_sections(
        document_id: int,
        max_depth: int = 3,
    ) -> types.CallToolResult:
        """Get the table of contents and section structure of a document.

        Args:
            document_id: The ID of the document to get sections for
            max_depth: Maximum heading depth to include (1-6, default: 3)

        Examples:
            get_document_sections(5)  # Get top 3 levels of sections
            get_document_sections(10, max_depth=2)  # Only H1 and H2
        """
        try:
            from docvault.core.section_navigator import SectionNavigator, SectionNode

            # Validate document exists
            document = operations.get_document(document_id)
            if not document:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=f"Document not found: {document_id}"
                        )
                    ],
                    metadata={
                        "success": False,
                        "error": f"Document not found: {document_id}",
                    },
                )

            # Get section navigator
            navigator = SectionNavigator(document_id)
            toc = navigator.get_table_of_contents()

            # Apply max_depth filtering
            def filter_by_depth(sections, current_depth=1):
                filtered = []
                for section in sections:
                    if current_depth <= max_depth:
                        filtered_section = SectionNode(
                            id=section.id,
                            section_title=section.section_title,
                            section_level=section.section_level,
                            section_path=section.section_path,
                            parent_segment_id=section.parent_segment_id,
                            content_preview=section.content_preview,
                        )
                        if section.children and current_depth < max_depth:
                            filtered_section.children = filter_by_depth(
                                section.children, current_depth + 1
                            )
                        filtered.append(filtered_section)
                return filtered

            toc = filter_by_depth(toc)

            if not toc:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"No sections found in document {document_id}",
                        )
                    ],
                    metadata={"success": True, "section_count": 0},
                )

            content_text = f"Table of Contents for '{document['title']}':\n\n"

            def format_toc(sections, indent=0):
                text = ""
                for section in sections:
                    prefix = "  " * indent + "- "
                    text += f"{prefix}{section.section_title} (path: {section.section_path})\n"
                    if section.children:
                        text += format_toc(section.children, indent + 1)
                return text

            content_text += format_toc(toc)

            # Count total sections
            def count_sections(sections):
                count = len(sections)
                for s in sections:
                    if s.children:
                        count += count_sections(s.children)
                return count

            total_sections = count_sections(toc)
            content_text += f"\nTotal sections: {total_sections}"

            # Convert SectionNode objects to dictionaries for metadata
            def section_to_dict(section):
                return {
                    "id": section.id,
                    "title": section.section_title,
                    "level": section.section_level,
                    "path": section.section_path,
                    "preview": section.content_preview,
                    "children": [section_to_dict(child) for child in section.children],
                }

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content_text)],
                metadata={
                    "success": True,
                    "document_id": document_id,
                    "section_count": total_sections,
                    "max_depth": max_depth,
                    "table_of_contents": [section_to_dict(section) for section in toc],
                },
            )
        except Exception as e:
            logger.exception(f"Error getting document sections: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error getting document sections: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    @server.tool()
    async def read_document_section(
        document_id: int,
        section_path: str = None,
        section_id: int = None,
        include_subsections: bool = False,
    ) -> types.CallToolResult:
        """Read a specific section from a document using its path or ID.

        Args:
            document_id: The ID of the document
            section_path: The section path (e.g., "1.2.3" for nested sections) - use quotes!
            section_id: Alternative - the section ID (from get_document_sections)
            include_subsections: If True, include all subsections

        Examples:
            read_document_section(5, section_path="2")  # Read section 2
            read_document_section(5, section_path="2.1")  # Read subsection 2.1
            read_document_section(5, section_id=123)  # Read section by ID
            read_document_section(5, section_path="2", include_subsections=True)  # With subsections
        """
        try:
            from docvault.core.section_navigator import SectionNavigator

            # Validate document exists
            document = operations.get_document(document_id)
            if not document:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=f"Document not found: {document_id}"
                        )
                    ],
                    metadata={
                        "success": False,
                        "error": f"Document not found: {document_id}",
                    },
                )

            # Validate input
            if not section_path and not section_id:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text="Error: Either section_path or section_id must be provided",
                        )
                    ],
                    metadata={
                        "success": False,
                        "error": "Missing section_path or section_id parameter",
                    },
                )

            # Get section navigator
            SectionNavigator(document_id)

            # Import the function we need
            from docvault.core.section_navigator import get_section_content
            from docvault.db.operations import get_document_segment

            # Navigate to section by ID or path
            if section_id:
                # Get section by ID
                section_data = get_document_segment(section_id)
                if not section_data or section_data.get("document_id") != document_id:
                    return types.CallToolResult(
                        content=[
                            types.TextContent(
                                type="text",
                                text=f"Section not found: ID {section_id} in document {document_id}",
                            )
                        ],
                        metadata={
                            "success": False,
                            "error": f"Section not found: ID {section_id}",
                        },
                    )
                section_path = section_data.get("section_path", "")
                section = section_data
            else:
                # Convert numeric strings if needed (workaround for MCP parameter issue)
                if section_path and section_path.replace(".", "").isdigit():
                    # It's a numeric path, ensure it's treated as string
                    section_path = str(section_path)

                # Get section content by path
                section = get_section_content(document_id, section_path)
                if not section:
                    return types.CallToolResult(
                        content=[
                            types.TextContent(
                                type="text",
                                text=f"Section not found: {section_path} in document {document_id}",
                            )
                        ],
                        metadata={
                            "success": False,
                            "error": f"Section not found: {section_path}",
                        },
                    )

            # Get section content
            if include_subsections:
                # For subsections, we need to get all segments with paths starting with section_path
                from docvault.db.operations import get_connection

                with get_connection() as conn:
                    cursor = conn.execute(
                        """SELECT section_title, section_level, section_path, content
                           FROM document_segments
                           WHERE document_id = ? AND section_path LIKE ?
                           ORDER BY section_path""",
                        (document_id, f"{section_path}%"),
                    )
                    sections = cursor.fetchall()

                content_text = f"Section {section_path} and subsections from '{document['title']}':\n\n"
                for s in sections:
                    content_text += (
                        f"{'#' * s['section_level']} {s['section_title']}\n\n"
                    )
                    content_text += s["content"] + "\n\n"
            else:
                content_text = f"Section {section_path} from '{document['title']}':\n\n"
                content_text += f"{'#' * section.get('section_level', 1)} {section.get('section_title', 'Section')}\n\n"
                content_text += section.get("content", "")

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content_text)],
                metadata={
                    "success": True,
                    "document_id": document_id,
                    "section_path": section_path,
                    "section_title": section.get("section_title", ""),
                    "include_subsections": include_subsections,
                },
            )
        except Exception as e:
            logger.exception(f"Error reading document section: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error reading document section: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Alternative section reading tool that uses a prefix to force string handling
    @server.tool()
    async def read_section(
        document_id: int,
        section: str,
        include_subsections: bool = False,
    ) -> types.CallToolResult:
        """Read a document section. Prefix numeric paths with 's' (e.g., 's1.2' for section 1.2).

        Args:
            document_id: The ID of the document
            section: Section identifier - either numeric ID or path with 's' prefix
            include_subsections: If True, include all subsections

        Examples:
            read_section(5, "s2")  # Read section 2
            read_section(5, "s2.1")  # Read section 2.1
            read_section(5, "163")  # Read by section ID if numeric
            read_section(5, "installation")  # Read by section title/slug
        """
        try:
            from docvault.core.section_navigator import get_section_content
            from docvault.db.operations import get_connection, get_document_segment

            # Validate document exists
            document = operations.get_document(document_id)
            if not document:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=f"Document not found: {document_id}"
                        )
                    ],
                    metadata={
                        "success": False,
                        "error": f"Document not found: {document_id}",
                    },
                )

            # Determine if it's a section ID, path, or title
            if section.startswith("s") and section[1:].replace(".", "").isdigit():
                # It's a path with 's' prefix
                section_path = section[1:]  # Remove 's' prefix
                section_obj = get_section_content(document_id, section_path)
            elif section.isdigit():
                # It's a section ID
                section_obj = get_document_segment(int(section))
                if section_obj and section_obj.get("document_id") == document_id:
                    section_path = section_obj.get("section_path", "")
                else:
                    section_obj = None
            else:
                # Try as a path
                section_obj = get_section_content(document_id, section)
                section_path = section

            if not section_obj:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Section not found: {section} in document {document_id}",
                        )
                    ],
                    metadata={
                        "success": False,
                        "error": f"Section not found: {section}",
                    },
                )

            # Get section content
            if include_subsections:
                # Get all segments with paths starting with section_path
                with get_connection() as conn:
                    cursor = conn.execute(
                        """SELECT section_title, section_level, section_path, content
                           FROM document_segments
                           WHERE document_id = ? AND section_path LIKE ?
                           ORDER BY section_path""",
                        (document_id, f"{section_path}%"),
                    )
                    sections = cursor.fetchall()
                content_text = (
                    f"Section {section} and subsections from '{document['title']}':\n\n"
                )

                for s in sections:
                    content_text += f"{'#' * s.get('section_level', 1)} {s.get('section_title', 'Section')}\n\n"
                    content_text += s.get("content", "") + "\n\n"
            else:
                content_text = f"Section {section} from '{document['title']}':\n\n"
                content_text += f"{'#' * section_obj.get('section_level', 1)} {section_obj.get('section_title', 'Section')}\n\n"
                content_text += section_obj.get("content", "")

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content_text)],
                metadata={
                    "success": True,
                    "document_id": document_id,
                    "section": section,
                    "section_title": section_obj.get("section_title", ""),
                },
            )

        except Exception as e:
            logger.exception(f"Error reading section: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error reading section: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Add chunk navigation tool
    @server.tool()
    async def get_chunk_info(
        document_id: int, chunk_size: int = 5000, chunking_strategy: str = "hybrid"
    ) -> types.CallToolResult:
        """Get information about available chunks for a document.

        Args:
            document_id: The ID of the document
            chunk_size: Size of each chunk in characters
            chunking_strategy: Strategy for chunking - "hybrid", "section", "semantic", "paragraph", or "character"

        Returns:
            Information about total chunks and navigation hints
        """
        try:
            document = operations.get_document(document_id)
            if not document:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=f"Document not found: {document_id}"
                        )
                    ],
                    metadata={
                        "success": False,
                        "error": f"Document not found: {document_id}",
                    },
                )

            # Get chunk information
            chunker = ContentChunker(document_id)

            # Get first chunk to determine total chunks
            try:
                first_chunk = chunker.get_chunk(
                    chunk_number=1,
                    chunk_size=chunk_size,
                    strategy=ChunkingStrategy(chunking_strategy),
                )
                total_chunks = first_chunk.metadata.total_chunks

                # Get section information if using section-based chunking
                sections_info = []
                if chunking_strategy in ["section", "hybrid"]:
                    with get_connection() as conn:
                        cursor = conn.execute(
                            """
                            SELECT section_path, section_title
                            FROM document_segments
                            WHERE document_id = ?
                            ORDER BY section_path
                            LIMIT 20
                        """,
                            (document_id,),
                        )
                        sections = cursor.fetchall()
                        sections_info = [
                            f"{s['section_path']}: {s['section_title']}"
                            for s in sections
                            if s["section_title"]
                        ]

                content_text = f"Document: {document['title']}\n\n"
                content_text += f"Total chunks: {total_chunks} (using {chunking_strategy} strategy)\n"
                content_text += f"Chunk size: {chunk_size} characters\n\n"

                if sections_info:
                    content_text += "Available sections:\n"
                    for section in sections_info[:10]:
                        content_text += f"  - {section}\n"
                    if len(sections_info) > 10:
                        content_text += (
                            f"  ... and {len(sections_info) - 10} more sections\n"
                        )

                content_text += f"\nUse read_document with mode='chunk' and chunk_number=1 to {total_chunks} to read specific chunks."

                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=content_text)],
                    metadata={
                        "success": True,
                        "document_id": document_id,
                        "total_chunks": total_chunks,
                        "chunk_size": chunk_size,
                        "chunking_strategy": chunking_strategy,
                        "sections_count": len(sections_info),
                    },
                )

            except Exception as e:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=f"Error analyzing chunks: {str(e)}"
                        )
                    ],
                    metadata={"success": False, "error": str(e)},
                )

        except Exception as e:
            logger.exception(f"Error getting chunk info: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error getting chunk info: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Add section search tool
    @server.tool()
    async def search_sections(
        document_id: int, query: str, search_type: str = "all", limit: int = 10
    ) -> types.CallToolResult:
        """Search for specific sections within a document and get navigation info.

        Args:
            document_id: The ID of the document to search within
            query: Search query (e.g., "code example", "error handling", "def function_name")
            search_type: Type of search - "all", "code", "headings", "examples", or "content"
                - all: Search everything
                - code: Focus on code blocks and examples
                - headings: Search section titles only
                - examples: Search for example sections
                - content: Search body text
            limit: Maximum number of results to return

        Returns:
            Section paths and chunk numbers for direct navigation

        Examples:
            search_sections(40, "requests.get", search_type="code")
            search_sections(40, "error handling", search_type="headings")
            search_sections(40, "example", search_type="examples")
        """
        try:
            document = operations.get_document(document_id)
            if not document:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=f"Document not found: {document_id}"
                        )
                    ],
                    metadata={
                        "success": False,
                        "error": f"Document not found: {document_id}",
                    },
                )

            # Build search query based on type
            search_conditions = []
            params = [document_id]

            if search_type == "code":
                # Search for code blocks
                search_conditions.append(
                    """
                    (content LIKE '%```%' || content LIKE '%code%' || content LIKE '%def %' ||
                     content LIKE '%function %' || content LIKE '%class %')
                """
                )
            elif search_type == "headings":
                # Search section titles only
                search_conditions.append("LOWER(section_title) LIKE ?")
                params.append(f"%{query.lower()}%")
            elif search_type == "examples":
                # Search for example sections
                search_conditions.append(
                    """
                    (LOWER(section_title) LIKE '%example%' OR
                     LOWER(content) LIKE '%example:%' OR
                     LOWER(content) LIKE '%usage:%')
                """
                )

            # Always search content for the query
            if search_type != "headings":
                search_conditions.append("LOWER(content) LIKE ?")
                params.append(f"%{query.lower()}%")

            # Execute search
            with get_connection() as conn:
                query_sql = f"""
                    SELECT
                        id,
                        section_title,
                        section_path,
                        content,
                        LENGTH(content) as content_length
                    FROM document_segments
                    WHERE document_id = ?
                        AND ({" AND ".join(search_conditions) if search_conditions else "1=1"})
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

            if not results:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"No sections found matching '{query}' in document {document_id}",
                        )
                    ],
                    metadata={
                        "success": True,
                        "result_count": 0,
                    },
                )

            # Use section indexer for efficient chunk mapping
            indexer = SectionIndexer(document_id)

            # Get enhanced results with chunk information
            enhanced_results = indexer.search_sections(
                query=query,
                search_type=search_type,
                limit=limit,
                chunk_size=5000,
                strategy=ChunkingStrategy.SECTION,
            )

            section_info = []

            for result in enhanced_results:

                # Use content preview from enhanced results
                content_preview = result.get("content_preview", "")

                # Get content for better preview if needed
                if search_type in ["code", "examples"] and result.get("id"):
                    # Fetch full content for better extraction
                    with get_connection() as conn:
                        cursor = conn.execute(
                            "SELECT content FROM document_segments WHERE id = ?",
                            (result["id"],),
                        )
                        full_content = cursor.fetchone()

                        if full_content:
                            if search_type == "code":
                                # Try to extract code block
                                code_match = re.search(
                                    r"```[^`]*```", full_content["content"], re.DOTALL
                                )
                                if code_match:
                                    content_preview = code_match.group(0)[:300]
                            elif search_type == "examples":
                                # Try to extract example
                                example_match = re.search(
                                    r"(Example|Usage):\s*\n(.*?)(?=\n\n|\Z)",
                                    full_content["content"],
                                    re.IGNORECASE | re.DOTALL,
                                )
                                if example_match:
                                    content_preview = example_match.group(0)[:300]

                section_info.append(
                    {
                        "section_path": result["section_path"],
                        "section_title": result["section_title"],
                        "content_preview": content_preview,
                        "chunk_number": result.get("chunk_number"),
                        "spans_chunks": result.get("spans_chunks", False),
                    }
                )

            # Format results
            content_text = f"Found {len(section_info)} sections matching '{query}' in {document['title']}:\n\n"

            for i, info in enumerate(section_info, 1):
                content_text += f"{i}. "
                if info["section_title"]:
                    content_text += f"**{info['section_title']}**"
                else:
                    content_text += f"Section {info['section_path']}"

                content_text += f" (path: {info['section_path']})"

                if info["chunk_number"]:
                    content_text += f"\n   → Chunk {info['chunk_number']}"
                    if info["spans_chunks"]:
                        content_text += " (spans multiple chunks)"

                content_text += f"\n   Preview: {info['content_preview']}"
                if len(info["content_preview"]) >= 200:
                    content_text += "..."
                content_text += "\n\n"

            content_text += "\nUse `read_document_section` with section_path or `read_document` with mode='chunk' to read these sections."

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content_text)],
                metadata={
                    "success": True,
                    "document_id": document_id,
                    "result_count": len(results),
                    "search_type": search_type,
                    "sections": [
                        {
                            "path": info["section_path"],
                            "title": info["section_title"],
                            "chunk_number": info.get("chunk_number"),
                            "spans_chunks": info.get("spans_chunks", False),
                        }
                        for info in section_info
                    ],
                },
            )

        except Exception as e:
            logger.exception(f"Error searching sections: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error searching sections: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Add contextual retrieval management tools
    @server.tool()
    async def enable_contextual_retrieval() -> types.CallToolResult:
        """Enable contextual retrieval for enhanced search accuracy.

        When enabled, new documents will be processed with context augmentation,
        which can improve search accuracy by up to 49%.
        """
        try:
            with operations.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE config
                    SET value = 'true'
                    WHERE key = 'contextual_retrieval_enabled'
                    """
                )
                conn.commit()

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text="✓ Contextual retrieval enabled. New documents will be processed with contextual augmentation for improved search accuracy.",
                    )
                ],
                metadata={"success": True, "enabled": True},
            )
        except Exception as e:
            logger.exception(f"Error enabling contextual retrieval: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Error enabling contextual retrieval: {str(e)}",
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    @server.tool()
    async def disable_contextual_retrieval() -> types.CallToolResult:
        """Disable contextual retrieval."""
        try:
            with operations.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE config
                    SET value = 'false'
                    WHERE key = 'contextual_retrieval_enabled'
                    """
                )
                conn.commit()

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text="✓ Contextual retrieval disabled."
                    )
                ],
                metadata={"success": True, "enabled": False},
            )
        except Exception as e:
            logger.exception(f"Error disabling contextual retrieval: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Error disabling contextual retrieval: {str(e)}",
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    @server.tool()
    async def get_contextual_retrieval_status() -> types.CallToolResult:
        """Get the status and statistics of contextual retrieval."""
        try:
            with operations.get_connection() as conn:
                # Get config status
                cursor = conn.execute(
                    """
                    SELECT value FROM config
                    WHERE key = 'contextual_retrieval_enabled'
                    """
                )
                result = cursor.fetchone()
                enabled = result["value"] == "true" if result else False

                # Get provider info
                cursor = conn.execute(
                    """
                    SELECT key, value FROM config
                    WHERE key IN ('context_llm_provider', 'context_llm_model')
                    """
                )
                config_items = {row["key"]: row["value"] for row in cursor.fetchall()}

                # Get statistics
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(DISTINCT document_id) as docs_with_context,
                        COUNT(*) as segments_with_context,
                        COUNT(DISTINCT context_model) as models_used
                    FROM document_segments
                    WHERE context_description IS NOT NULL
                    """
                )
                stats = cursor.fetchone()

                # Get total counts
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(DISTINCT d.id) as total_docs,
                        COUNT(*) as total_segments
                    FROM documents d
                    JOIN document_segments ds ON d.id = ds.document_id
                    """
                )
                totals = cursor.fetchone()

                # Calculate coverage
                doc_coverage = (
                    (stats["docs_with_context"] / totals["total_docs"] * 100)
                    if totals["total_docs"] > 0
                    else 0
                )
                segment_coverage = (
                    (stats["segments_with_context"] / totals["total_segments"] * 100)
                    if totals["total_segments"] > 0
                    else 0
                )

                # Format status text
                status_text = f"Contextual Retrieval Status: {'ENABLED' if enabled else 'DISABLED'}\n\n"

                if enabled:
                    provider = config_items.get("context_llm_provider", "ollama")
                    model = config_items.get("context_llm_model", "llama2")
                    status_text += f"Provider: {provider}\n"
                    status_text += f"Model: {model}\n\n"

                status_text += "Coverage Statistics:\n"
                status_text += f"- Documents with context: {stats['docs_with_context']}/{totals['total_docs']} ({doc_coverage:.1f}%)\n"
                status_text += f"- Segments with context: {stats['segments_with_context']}/{totals['total_segments']} ({segment_coverage:.1f}%)\n"

                if stats["docs_with_context"] > 0:
                    status_text += f"\nModels used: {stats['models_used']}"

                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=status_text)],
                    metadata={
                        "success": True,
                        "enabled": enabled,
                        "provider": config_items.get("context_llm_provider"),
                        "model": config_items.get("context_llm_model"),
                        "doc_coverage": doc_coverage,
                        "segment_coverage": segment_coverage,
                        "docs_with_context": stats["docs_with_context"],
                        "total_docs": totals["total_docs"],
                    },
                )
        except Exception as e:
            logger.exception(f"Error getting contextual retrieval status: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Error getting contextual retrieval status: {str(e)}",
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    @server.tool()
    async def process_document_with_context(
        document_id: int, force: bool = False
    ) -> types.CallToolResult:
        """Process a specific document with contextual retrieval.

        Args:
            document_id: The ID of the document to process
            force: If True, reprocess even if context already exists

        This adds context to each chunk before embedding, improving search accuracy.
        """
        try:
            # Check if document exists
            document = operations.get_document(document_id)
            if not document:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=f"Document not found: {document_id}"
                        )
                    ],
                    metadata={
                        "success": False,
                        "error": f"Document not found: {document_id}",
                    },
                )

            # Check if already processed
            if not force:
                with operations.get_connection() as conn:
                    cursor = conn.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM document_segments
                        WHERE document_id = ? AND context_description IS NOT NULL
                        """,
                        (document_id,),
                    )
                    result = cursor.fetchone()
                    if result["count"] > 0:
                        return types.CallToolResult(
                            content=[
                                types.TextContent(
                                    type="text",
                                    text=f"Document {document_id} already has contextual data. Use force=True to reprocess.",
                                )
                            ],
                            metadata={
                                "success": False,
                                "already_processed": True,
                            },
                        )

            # Process with contextual retrieval
            from docvault.core.contextual_processor import ContextualChunkProcessor

            processor = ContextualChunkProcessor()

            # Process the document
            result = await processor.process_document(document_id, force=force)
            success = result.get("status") == "completed"

            if success:
                # Get stats
                with operations.get_connection() as conn:
                    cursor = conn.execute(
                        """
                        SELECT COUNT(*) as processed_count
                        FROM document_segments
                        WHERE document_id = ? AND context_description IS NOT NULL
                        """,
                        (document_id,),
                    )
                    result = cursor.fetchone()
                    processed_count = result["processed_count"]

                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"✓ Successfully processed document {document_id} with contextual retrieval.\n"
                            f"Processed {processed_count} segments with context.",
                        )
                    ],
                    metadata={
                        "success": True,
                        "document_id": document_id,
                        "segments_processed": processed_count,
                    },
                )
            else:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Failed to process document {document_id} with contextual retrieval.",
                        )
                    ],
                    metadata={
                        "success": False,
                        "document_id": document_id,
                    },
                )

        except Exception as e:
            logger.exception(f"Error processing document with context: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Error processing document with context: {str(e)}",
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    @server.tool()
    async def configure_contextual_retrieval(
        provider: str = "ollama", model: str | None = None
    ) -> types.CallToolResult:
        """Configure the LLM provider for contextual retrieval.

        Args:
            provider: LLM provider - 'ollama', 'openai', or 'anthropic'
            model: Model name (optional - uses defaults if not specified)
                   - ollama: llama2, mistral, etc.
                   - openai: gpt-3.5-turbo, gpt-4
                   - anthropic: claude-3-haiku, claude-3-sonnet
        """
        try:
            # Validate provider
            valid_providers = ["ollama", "openai", "anthropic"]
            if provider not in valid_providers:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Invalid provider '{provider}'. Must be one of: {', '.join(valid_providers)}",
                        )
                    ],
                    metadata={"success": False, "error": "Invalid provider"},
                )

            # Set default models if not specified
            if not model:
                default_models = {
                    "ollama": "llama2",
                    "openai": "gpt-3.5-turbo",
                    "anthropic": "claude-3-haiku-20240307",
                }
                model = default_models[provider]

            # Update configuration
            with operations.get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO config (key, value)
                    VALUES ('context_llm_provider', ?)
                    """,
                    (provider,),
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO config (key, value)
                    VALUES ('context_llm_model', ?)
                    """,
                    (model,),
                )
                conn.commit()

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"✓ Contextual retrieval configured:\n"
                        f"Provider: {provider}\n"
                        f"Model: {model}",
                    )
                ],
                metadata={
                    "success": True,
                    "provider": provider,
                    "model": model,
                },
            )
        except Exception as e:
            logger.exception(f"Error configuring contextual retrieval: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Error configuring contextual retrieval: {str(e)}",
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    @server.tool()
    async def find_similar_by_context(
        document_id: int, segment_id: int | None = None, limit: int = 5
    ) -> types.CallToolResult:
        """Find similar content using contextual metadata.

        Args:
            document_id: The document ID
            segment_id: Optional specific segment ID to find similar content for
            limit: Maximum number of similar items to return

        This uses contextual embeddings to find semantically similar content.
        """
        try:
            # Validate document
            document = operations.get_document(document_id)
            if not document:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=f"Document not found: {document_id}"
                        )
                    ],
                    metadata={
                        "success": False,
                        "error": f"Document not found: {document_id}",
                    },
                )

            # Use contextual processor to find similar content
            from docvault.core.contextual_processor import ContextualChunkProcessor

            processor = ContextualChunkProcessor()

            similar_items = processor.find_similar_by_metadata(
                document_id=document_id, segment_id=segment_id, limit=limit
            )

            if not similar_items:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text="No similar content found. Make sure documents are processed with contextual retrieval.",
                        )
                    ],
                    metadata={"success": True, "result_count": 0},
                )

            content_text = "Similar content found:\n\n"
            for i, item in enumerate(similar_items, 1):
                content_text += f"{i}. Document: {item['document_title']} (ID: {item['document_id']})\n"
                if item.get("section_title"):
                    content_text += f"   Section: {item['section_title']}\n"
                content_text += f"   Similarity: {item['similarity_score']:.2f}\n"
                if item.get("context_description"):
                    content_text += (
                        f"   Context: {item['context_description'][:100]}...\n"
                    )
                content_text += f"   Preview: {item['content'][:150]}...\n\n"

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content_text)],
                metadata={
                    "success": True,
                    "result_count": len(similar_items),
                    "similar_items": [
                        {
                            "document_id": item["document_id"],
                            "segment_id": item["segment_id"],
                            "document_title": item["document_title"],
                            "section_title": item.get("section_title"),
                            "similarity_score": item["similarity_score"],
                        }
                        for item in similar_items
                    ],
                },
            )
        except Exception as e:
            logger.exception(f"Error finding similar content: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error finding similar content: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    # Add document listing tool
    @server.tool()
    async def list_documents(filter: str = "", limit: int = 20) -> types.CallToolResult:
        """List all documents in the vault with their metadata.

        Args:
            filter: Optional text filter to search document titles
            limit: Maximum number of documents to return (default: 20)

        Examples:
            list_documents()  # List first 20 documents
            list_documents(filter="python")  # List documents with "python" in title
            list_documents(limit=50)  # List up to 50 documents

        Returns document IDs, titles, URLs, and scrape timestamps."""
        try:
            documents = operations.list_documents(limit=limit, filter_text=filter)

            if not documents:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text="No documents found in the vault."
                        )
                    ],
                    metadata={"success": True, "document_count": 0},
                )

            content_text = f"Found {len(documents)} documents in the vault:\n\n"
            for doc in documents:
                content_text += f"- ID {doc['id']}: {doc['title']} ({doc['url']})\n"

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content_text)],
                metadata={
                    "success": True,
                    "document_count": len(documents),
                    "documents": [
                        {
                            "id": doc["id"],
                            "title": doc["title"],
                            "url": doc["url"],
                            "scraped_at": doc["scraped_at"],
                        }
                        for doc in documents
                    ],
                },
            )
        except Exception as e:
            logger.exception(f"Error listing documents: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error listing documents: {str(e)}"
                    )
                ],
                metadata={"success": False, "error": str(e)},
            )

    return server


async def _run_stdio_server(server: FastMCP):
    """Run the server with stdio transport"""
    async with mcp.server.stdio.stdio_server():
        await server.run()


def run_server(
    host: str | None = None, port: int | None = None, transport: str = "stdio"
) -> None:
    """Run the MCP server"""
    try:
        # Configure logging
        logging.basicConfig(
            level=logging.getLevelName(config.LOG_LEVEL),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(), logging.FileHandler(config.LOG_FILE)],
        )

        logger.info(f"Starting DocVault MCP server with {transport} transport")

        # Create server
        server = create_server()

        # Use the appropriate transport
        if transport == "stdio":
            server.run()
        else:
            # Use HOST/PORT for SSE/web mode (Uvicorn)
            host = host or config.HOST
            port = port or config.PORT
            logger.info(f"Server will be available at http://{host}:{port}")
            server.run("sse")
    except Exception as e:
        logger.exception(f"Error running server: {e}")
