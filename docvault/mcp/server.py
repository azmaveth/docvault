import asyncio
import logging
from typing import Dict, Any

from mcp import Server

from docvault import config
from docvault.mcp.tools import docvault_tools
from docvault.mcp.handlers import (
    handle_scrape_document, 
    handle_search_documents,
    handle_read_document,
    handle_lookup_library_docs,
    handle_list_documents
)

def create_server():
    """Create and configure the MCP server"""
    server = Server(
        name="DocVault",
        description="Document management system with vector search",
        version="0.1.0",
        # Bind handlers to tools
        tool_handlers={
            "scrape_document": handle_scrape_document,
            "search_documents": handle_search_documents,
            "read_document": handle_read_document,
            "lookup_library_docs": handle_lookup_library_docs,
            "list_documents": handle_list_documents
        },
        # Add tools
        tools=docvault_tools
    )
    
    return server

def run_server(host=None, port=None):
    """Run the MCP server"""
    host = host or config.SERVER_HOST
    port = port or config.SERVER_PORT
    
    # Configure logging
    logging.basicConfig(
        level=logging.getLevelName(config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.LOG_FILE)
        ]
    )
    
    logger = logging.getLogger("docvault.mcp")
    logger.info(f"Starting DocVault MCP server on {host}:{port}")
    
    server = create_server()
    server.run(host=host, port=port)
