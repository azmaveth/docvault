from mcp import Tool, ToolParameter
from typing import List

# Define tools using MCP SDK
scrape_document_tool = Tool(
    name="scrape_document",
    description="Scrape a document from a URL and store it in the document vault",
    parameters=[
        ToolParameter(
            name="url",
            description="The URL to scrape",
            required=True,
            type="string"
        ),
        ToolParameter(
            name="depth",
            description="How many levels deep to scrape",
            required=False,
            type="integer",
            default=1
        )
    ]
)

search_documents_tool = Tool(
    name="search_documents",
    description="Search documents in the vault using semantic search",
    parameters=[
        ToolParameter(
            name="query",
            description="The search query",
            required=True,
            type="string"
        ),
        ToolParameter(
            name="limit",
            description="Maximum number of results",
            required=False,
            type="integer",
            default=5
        )
    ]
)

read_document_tool = Tool(
    name="read_document",
    description="Read a document from the vault",
    parameters=[
        ToolParameter(
            name="document_id",
            description="ID of the document to read",
            required=True,
            type="integer"
        ),
        ToolParameter(
            name="format",
            description="Format to return the document in",
            required=False,
            type="string",
            enum=["markdown", "html"],
            default="markdown"
        )
    ]
)

lookup_library_docs_tool = Tool(
    name="lookup_library_docs",
    description="Lookup and fetch documentation for a specific library and version if not already available",
    parameters=[
        ToolParameter(
            name="library_name",
            description="Name of the library (e.g., 'pandas', 'tensorflow')",
            required=True,
            type="string"
        ),
        ToolParameter(
            name="version",
            description="Version of the library (e.g., '1.5.0', 'latest')",
            required=False,
            type="string",
            default="latest"
        )
    ]
)

list_documents_tool = Tool(
    name="list_documents",
    description="List all documents in the vault",
    parameters=[
        ToolParameter(
            name="filter",
            description="Optional filter string",
            required=False,
            type="string",
            default=""
        ),
        ToolParameter(
            name="limit",
            description="Maximum number of documents to return",
            required=False,
            type="integer",
            default=20
        )
    ]
)

# Collect all tools
docvault_tools = [
    scrape_document_tool,
    search_documents_tool,
    read_document_tool,
    lookup_library_docs_tool,
    list_documents_tool
]
