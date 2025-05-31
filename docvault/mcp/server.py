import logging
from typing import Optional, Union

import mcp.server.stdio

# Import types for responses
import mcp.types as types

# Import the FastMCP server
from mcp.server.fastmcp import FastMCP

import docvault.core.storage as storage
from docvault import config
from docvault.core.library_manager import lookup_library_docs
from docvault.core.scraper import get_scraper
from docvault.db import operations

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
        depth: Union[int, str] = 1,
        sections: Optional[list] = None,
        filter_selector: Optional[str] = None,
        depth_strategy: Optional[str] = None,
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
        query: Optional[str] = None,
        limit: int = 5,
        min_score: float = 0.0,
        version: Optional[str] = None,
        library: bool = False,
        title_contains: Optional[str] = None,
        updated_after: Optional[str] = None,
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
                result_text += f"Score: {r.get('score', 0):.2f}\n"
                result_text += f"Content: {r.get('content', '')[:200]}{'...' if len(r.get('content', '')) > 200 else ''}\n"
                if r.get("section_title"):
                    result_text += f"Section: {r['section_title']}\n"
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
        document_id: int, format: str = "markdown"
    ) -> types.CallToolResult:
        """Read the full content of a document from the vault.

        Args:
            document_id: The ID of the document to read
            format: Format to return - "markdown" (default) or "html"

        Examples:
            read_document(5)  # Read as markdown
            read_document(10, format="html")  # Read as HTML

        Note: For large documents, consider using get_document_sections and
        read_document_section to navigate and read specific parts."""
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

            if format.lower() == "html":
                content = storage.read_html(document["html_path"])
            else:
                content = storage.read_markdown(document["markdown_path"])

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content)],
                metadata={
                    "success": True,
                    "document_id": document_id,
                    "title": document["title"],
                    "url": document["url"],
                    "format": format,
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
        complementary: Optional[str] = None,
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
        document_id: Optional[int] = None,
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
            navigator = SectionNavigator(document_id)

            # Navigate to section by ID or path
            if section_id:
                # Get section by ID
                from docvault.db.operations import get_document_segment

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

                # Navigate to section by path
                section = navigator.navigate_to_section(section_path)
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
                sections = navigator.get_section_with_children(section_path)
                content_text = f"Section {section_path} and subsections from '{document['title']}':\n\n"

                for s in sections:
                    content_text += f"{'#' * s['level']} {s['title']}\n\n"
                    content_text += s["content"] + "\n\n"
            else:
                content_text = f"Section {section_path} from '{document['title']}':\n\n"
                content_text += f"{'#' * section['level']} {section['title']}\n\n"
                content_text += section["content"]

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content_text)],
                metadata={
                    "success": True,
                    "document_id": document_id,
                    "section_path": section_path,
                    "section_title": section["title"],
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

            navigator = SectionNavigator(document_id)

            # Determine if it's a section ID, path, or title
            if section.startswith("s") and section[1:].replace(".", "").isdigit():
                # It's a path with 's' prefix
                section_path = section[1:]  # Remove 's' prefix
                section_obj = navigator.navigate_to_section(section_path)
            elif section.isdigit():
                # It's a section ID
                from docvault.db.operations import get_document_segment

                section_obj = get_document_segment(int(section))
                if section_obj and section_obj.get("document_id") == document_id:
                    section_path = section_obj.get("section_path", "")
                else:
                    section_obj = None
            else:
                # Try as a path or title
                section_obj = navigator.navigate_to_section(section)
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
            if include_subsections and hasattr(navigator, "get_section_with_children"):
                sections = navigator.get_section_with_children(section_path or section)
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
    host: Optional[str] = None, port: Optional[int] = None, transport: str = "stdio"
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
