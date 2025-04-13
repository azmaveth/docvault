import asyncio
import logging
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import importlib.metadata

from docvault import config
from docvault.mcp.handlers import (
    handle_scrape_document, 
    handle_search_documents,
    handle_read_document,
    handle_lookup_library_docs,
    handle_list_documents
)

# Simple server implementation to avoid package version issues
class MCPServer:
    def __init__(self, name: str):
        self.name = name
        self.tools = {}
        self.logger = logging.getLogger(f"docvault.mcp.server")
        
    def tool(self, name):
        def decorator(func):
            self.tools[name] = func
            return func
        return decorator
    
    async def handle_request(self, request_data):
        try:
            request = json.loads(request_data)
            tool_name = request.get('name')
            params = request.get('params', {})
            
            if tool_name not in self.tools:
                return json.dumps({
                    "error": f"Tool '{tool_name}' not found",
                    "available_tools": list(self.tools.keys())
                })
            
            result = await self.tools[tool_name](**params)
            return json.dumps({"result": result})
        except Exception as e:
            self.logger.exception(f"Error handling request: {e}")
            return json.dumps({"error": str(e)})
    
    async def start_sse_server(self, host: str, port: int):
        """Start a basic SSE server for the MCP implementation"""
        from aiohttp import web
        
        app = web.Application()
        routes = web.RouteTableDef()
        
        @routes.post('/mcp')
        async def mcp_handler(request):
            try:
                body = await request.text()
                response = await self.handle_request(body)
                return web.Response(text=response, content_type='application/json')
            except Exception as e:
                self.logger.exception(f"Error in MCP handler: {e}")
                return web.Response(status=500, text=json.dumps({"error": str(e)}))
        
        @routes.get('/')
        async def index_handler(request):
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>DocVault MCP Server</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                    h1 {{ color: #333; }}
                    h2 {{ color: #444; margin-top: 30px; }}
                    pre {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; }}
                    .tool {{ margin-bottom: 20px; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }}
                    .tool-name {{ font-weight: bold; color: #0066cc; }}
                    .description {{ font-style: italic; color: #666; }}
                </style>
            </head>
            <body>
                <h1>DocVault MCP Server</h1>
                <p>This server implements the Model Context Protocol for accessing documentation via DocVault.</p>
                
                <h2>Available Tools</h2>
                <div class="tools-list">
                    {''.join([f'''
                        <div class="tool">
                            <div class="tool-name">{name}</div>
                            <div class="description">{func.__doc__ or 'No description'}</div>
                        </div>
                    ''' for name, func in self.tools.items()])}
                </div>
                
                <h2>API Usage</h2>
                <p>Send a POST request to <code>/mcp</code> with the following JSON structure:</p>
                <pre>{{
    "name": "tool_name",
    "params": {{
        "param1": "value1",
        "param2": "value2"
    }}
}}</pre>
            </body>
            </html>
            """
            return web.Response(text=html, content_type='text/html')
        
        app.add_routes(routes)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        
        self.logger.info(f"Starting MCP server at http://{host}:{port}")
        await site.start()
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    
    async def start_stdio_server(self):
        """Start a basic stdio server for the MCP implementation"""
        self.logger.info("Starting MCP server with stdio transport")
        
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, input)
                if not line:
                    continue
                    
                response = await self.handle_request(line)
                print(response, flush=True)
            except EOFError:
                break
            except Exception as e:
                self.logger.exception(f"Error in stdio server: {e}")
                print(json.dumps({"error": str(e)}), flush=True)

logger = logging.getLogger("docvault.mcp")

def create_server() -> MCPServer:
    """Create and configure the MCP server"""
    # Create MCP server
    server = MCPServer("DocVault")
    
    # Add document scraping tool
    @server.tool("scrape_document")
    async def scrape_document(url: str, depth: int = 1) -> Dict[str, Any]:
        """Scrape a document from a URL and store it in the document vault"""
        return await handle_scrape_document({"url": url, "depth": depth})
    
    # Add document search tool
    @server.tool("search_documents")
    async def search_documents(query: str, limit: int = 5) -> Dict[str, Any]:
        """Search documents in the vault using semantic search"""
        return await handle_search_documents({"query": query, "limit": limit})
    
    # Add document read tool
    @server.tool("read_document")
    async def read_document(document_id: int, format: str = "markdown") -> Dict[str, Any]:
        """Read a document from the vault"""
        return await handle_read_document({"document_id": document_id, "format": format})
    
    # Add library docs lookup tool
    @server.tool("lookup_library_docs")
    async def lookup_library_docs(library_name: str, version: str = "latest") -> Dict[str, Any]:
        """Lookup and fetch documentation for a specific library and version if not already available"""
        return await handle_lookup_library_docs({"library_name": library_name, "version": version})
    
    # Add document listing tool
    @server.tool("list_documents")
    async def list_documents(filter: str = "", limit: int = 20) -> Dict[str, Any]:
        """List all documents in the vault"""
        return await handle_list_documents({"filter": filter, "limit": limit})
    
    return server

async def _run_server_async(host: Optional[str] = None, port: Optional[int] = None, 
                           transport: str = "stdio") -> None:
    """Run the MCP server asynchronously"""
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
    
    logger.info(f"Starting DocVault MCP server with {transport} transport")
    
    server = create_server()
    
    # Start the appropriate transport
    if transport == "sse":
        logger.info(f"Server will be available at http://{host}:{port}")
        try:
            await server.start_sse_server(host=host, port=port)
        except KeyboardInterrupt:
            logger.info("Server stopped by keyboard interrupt")
    else:
        await server.start_stdio_server()

def run_server(host: Optional[str] = None, port: Optional[int] = None, 
              transport: str = "stdio") -> None:
    """Run the MCP server"""
    try:
        asyncio.run(_run_server_async(host, port, transport))
    except KeyboardInterrupt:
        logger.info("Server stopped by keyboard interrupt")
