import logging
from typing import Optional

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
    async def scrape_document(url: str, depth: int = 1) -> types.CallToolResult:
        """Scrape a document from a URL and store it in the document vault"""
        try:
            scraper = get_scraper()
            result = await scraper.scrape_url(url, depth=depth)

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Successfully scraped document: {result['title']} (ID: {result['id']})",
                    )
                ],
                metadata={
                    "document_id": result["id"],
                    "title": result["title"],
                    "url": url,
                    "success": True,
                },
            )
        except Exception as e:
            logger.exception(f"Error scraping document: {e}")
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Error scraping document: {str(e)}"
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
        """Read a document from the vault"""
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

    # Add document listing tool
    @server.tool()
    async def list_documents(filter: str = "", limit: int = 20) -> types.CallToolResult:
        """List all documents in the vault"""
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
