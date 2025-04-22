# This file is kept for backward compatibility but is no longer used directly.
# Tool definitions are now handled by FastMCP decorators in server.py

# Tool definitions for DocVault MCP server
from typing import Any, Dict

import mcp.types as types

# These constants define the input schemas for our tools
# They're kept here for reference but the actual schemas are now
# inferred from the function signatures by FastMCP

SCRAPE_DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "The URL to scrape"},
        "depth": {
            "type": "integer",
            "description": "How many levels deep to scrape",
            "default": 1,
        },
    },
    "required": ["url"],
}

SEARCH_DOCUMENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "The search query"},
        "limit": {
            "type": "integer",
            "description": "Maximum number of results",
            "default": 5,
        },
    },
    "required": ["query"],
}

READ_DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "document_id": {"type": "integer", "description": "ID of the document to read"},
        "format": {
            "type": "string",
            "description": "Format to return the document in",
            "enum": ["markdown", "html"],
            "default": "markdown",
        },
    },
    "required": ["document_id"],
}

LOOKUP_LIBRARY_DOCS_SCHEMA = {
    "type": "object",
    "properties": {
        "library_name": {
            "type": "string",
            "description": "Name of the library (e.g., 'pandas', 'tensorflow')",
        },
        "version": {
            "type": "string",
            "description": "Version of the library (e.g., '1.5.0', 'latest')",
            "default": "latest",
        },
    },
    "required": ["library_name"],
}

LIST_DOCUMENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "filter": {
            "type": "string",
            "description": "Optional filter string",
            "default": "",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of documents to return",
            "default": 20,
        },
    },
}


# New function to create a ToolResult from a legacy handler response
def create_tool_result(response: Dict[str, Any]) -> types.ToolResult:
    """Convert a legacy handler response to a ToolResult object"""
    success = response.get("success", False)

    if success:
        if "content" in response:
            content = response["content"]
        elif "results" in response:
            content = "\n\n".join(
                [f"{r['title']}: {r['content']}" for r in response["results"]]
            )
        elif "documents" in response:
            content = "\n\n".join([f"{doc['title']}" for doc in response["documents"]])
        elif "message" in response:
            content = response["message"]
        else:
            content = "Operation completed successfully"
    else:
        content = response.get("error", "Unknown error occurred")

    return types.ToolResult(
        content=[types.TextContent(type="text", text=content)], metadata=response
    )
