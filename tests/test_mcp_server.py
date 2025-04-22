from unittest.mock import AsyncMock, patch

import mcp.types as types
import pytest

from docvault.mcp.server import create_server


# Test fixtures
@pytest.fixture
def mock_get_scraper():
    scraper_mock = AsyncMock()
    scraper_mock.scrape_url = AsyncMock(
        return_value={
            "id": 123,
            "title": "Test Document",
            "url": "https://example.com/doc",
        }
    )
    with patch("docvault.mcp.server.get_scraper", return_value=scraper_mock):
        yield scraper_mock


@pytest.fixture
def mock_search():
    search_mock = AsyncMock(
        return_value=[
            {
                "id": 456,
                "document_id": 123,
                "title": "Test Document",
                "content": "This is a test document content.",
                "score": 0.95,
            }
        ]
    )
    with patch("docvault.mcp.server.search", search_mock):
        yield search_mock


@pytest.fixture
def mock_lookup_library_docs():
    lookup_mock = AsyncMock(
        return_value=[
            {
                "id": 789,
                "title": "Library Documentation",
                "url": "https://example.com/library",
            }
        ]
    )
    with patch("docvault.mcp.server.lookup_library_docs", lookup_mock):
        yield lookup_mock


@pytest.fixture
def mock_get_document():
    document = {
        "id": 123,
        "title": "Test Document",
        "url": "https://example.com/doc",
        "html_path": "/path/to/html",
        "markdown_path": "/path/to/markdown",
        "scraped_at": "2025-04-12T12:00:00Z",
    }
    with patch("docvault.db.operations.get_document", return_value=document):
        yield document


@pytest.fixture
def mock_list_documents():
    documents = [
        {
            "id": 123,
            "title": "Test Document",
            "url": "https://example.com/doc",
            "scraped_at": "2025-04-12T12:00:00Z",
        }
    ]
    with patch("docvault.db.operations.list_documents", return_value=documents):
        yield documents


@pytest.fixture
def mock_read_markdown():
    with patch(
        "docvault.core.storage.read_markdown",
        return_value="# Test Document\n\nThis is a test document content.",
    ):
        yield


@pytest.fixture
def mock_read_html():
    with patch(
        "docvault.core.storage.read_html",
        return_value="<h1>Test Document</h1><p>This is a test document content.</p>",
    ):
        yield


# Test the server creation and tools
@pytest.mark.asyncio
async def test_create_server():
    """Test that the server can be created"""
    server = create_server()
    assert server is not None
    assert server.name == "DocVault"

    # Check that all tools are registered
    tools = await server.list_tools()
    tool_names = [tool.name for tool in tools]

    assert "scrape_document" in tool_names
    assert "search_documents" in tool_names
    assert "read_document" in tool_names
    assert "lookup_library_docs" in tool_names
    assert "list_documents" in tool_names


# Test individual tools
@pytest.mark.asyncio
async def test_scrape_document_tool(mock_get_scraper):
    """Test the scrape_document tool"""
    server = create_server()

    # Get the scrape_document tool
    tools = await server.list_tools()
    scrape_tool = next((tool for tool in tools if tool.name == "scrape_document"), None)
    assert scrape_tool is not None

    # Create a tool handler function
    tool_handler = server._tool_manager._tools.get("scrape_document").fn
    assert tool_handler is not None

    # Call the tool with a URL
    result = await tool_handler(url="https://example.com/doc", depth=2)

    # Check that the scraper was called with the correct parameters
    mock_get_scraper.scrape_url.assert_called_once_with(
        "https://example.com/doc", depth=2
    )

    # Check the result
    assert isinstance(result, types.ToolResult)
    assert len(result.content) == 1
    assert result.content[0].type == "text"
    assert "Successfully scraped document: Test Document" in result.content[0].text
    assert result.metadata["document_id"] == 123
    assert result.metadata["title"] == "Test Document"
    assert result.metadata["url"] == "https://example.com/doc"
    assert result.metadata["success"] is True


@pytest.mark.asyncio
async def test_search_documents_tool(mock_search):
    """Test the search_documents tool"""
    server = create_server()

    # Get the search_documents tool handler
    tool_handler = server._tool_manager._tools.get("search_documents").fn
    assert tool_handler is not None

    # Call the tool with a query
    result = await tool_handler(query="test query", limit=10)

    # Check that the search function was called with the correct parameters
    mock_search.assert_called_once_with("test query", limit=10)

    # Check the result
    assert isinstance(result, types.ToolResult)
    assert len(result.content) == 1
    assert result.content[0].type == "text"
    assert "Document: Test Document" in result.content[0].text
    assert "Score: 0.95" in result.content[0].text
    assert "Content: This is a test document content." in result.content[0].text
    assert result.metadata["success"] is True
    assert result.metadata["result_count"] == 1
    assert result.metadata["query"] == "test query"


@pytest.mark.asyncio
async def test_read_document_tool(mock_get_document, mock_read_markdown):
    """Test the read_document tool"""
    server = create_server()

    # Get the read_document tool handler
    tool_handler = server._tool_manager._tools.get("read_document").fn
    assert tool_handler is not None

    # Call the tool with a document ID
    result = await tool_handler(document_id=123, format="markdown")

    # Check the result
    assert isinstance(result, types.ToolResult)
    assert len(result.content) == 1
    assert result.content[0].type == "text"
    assert "# Test Document" in result.content[0].text
    assert "This is a test document content." in result.content[0].text
    assert result.metadata["success"] is True
    assert result.metadata["document_id"] == 123
    assert result.metadata["title"] == "Test Document"
    assert result.metadata["format"] == "markdown"


@pytest.mark.asyncio
async def test_lookup_library_docs_tool(mock_lookup_library_docs):
    """Test the lookup_library_docs tool"""
    server = create_server()

    # Get the lookup_library_docs tool handler
    tool_handler = server._tool_manager._tools.get("lookup_library_docs").fn
    assert tool_handler is not None

    # Call the tool with a library name
    result = await tool_handler(library_name="test_library", version="latest")

    # Check that the lookup function was called with the correct parameters
    mock_lookup_library_docs.assert_called_once_with("test_library", "latest")

    # Check the result
    assert isinstance(result, types.ToolResult)
    assert len(result.content) == 1
    assert result.content[0].type == "text"
    assert (
        "Documentation for test_library latest is available" in result.content[0].text
    )
    assert "Library Documentation" in result.content[0].text
    assert result.metadata["success"] is True
    assert result.metadata["document_count"] == 1
    assert result.metadata["documents"][0]["id"] == 789
    assert result.metadata["documents"][0]["title"] == "Library Documentation"


@pytest.mark.asyncio
async def test_list_documents_tool(mock_list_documents):
    """Test the list_documents tool"""
    server = create_server()

    # Get the list_documents tool handler
    tool_handler = server._tool_manager._tools.get("list_documents").fn
    assert tool_handler is not None

    # Call the tool
    result = await tool_handler(filter="", limit=20)

    # Check the result
    assert isinstance(result, types.ToolResult)
    assert len(result.content) == 1
    assert result.content[0].type == "text"
    assert "Found 1 documents in the vault" in result.content[0].text
    assert "ID 123: Test Document" in result.content[0].text
    assert result.metadata["success"] is True
    assert result.metadata["document_count"] == 1
    assert result.metadata["documents"][0]["id"] == 123
    assert result.metadata["documents"][0]["title"] == "Test Document"


# Test error handling
@pytest.mark.asyncio
async def test_scrape_document_error_handling():
    """Test error handling in the scrape_document tool"""
    server = create_server()

    # Mock the scraper to raise an exception
    scraper_mock = AsyncMock()
    scraper_mock.scrape_url = AsyncMock(side_effect=Exception("Test error"))

    with patch("docvault.mcp.server.get_scraper", return_value=scraper_mock):
        # Get the scrape_document tool handler
        tool_handler = server._tool_manager._tools.get("scrape_document").fn
        assert tool_handler is not None

        # Call the tool with a URL
        result = await tool_handler(url="https://example.com/doc")

        # Check the error result
        assert isinstance(result, types.ToolResult)
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert "Error scraping document: Test error" in result.content[0].text
        assert result.metadata["success"] is False
        assert result.metadata["error"] == "Test error"


@pytest.mark.asyncio
async def test_search_documents_error_handling():
    """Test error handling in the search_documents tool"""
    server = create_server()

    # Mock the search function to raise an exception
    with patch("docvault.mcp.server.search", side_effect=Exception("Search error")):
        # Get the search_documents tool handler
        tool_handler = server._tool_manager._tools.get("search_documents").fn
        assert tool_handler is not None

        # Call the tool with a query
        result = await tool_handler(query="test query")

        # Check the error result
        assert isinstance(result, types.ToolResult)
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert "Error searching documents: Search error" in result.content[0].text
        assert result.metadata["success"] is False
        assert result.metadata["error"] == "Search error"


@pytest.mark.asyncio
async def test_read_document_not_found():
    """Test read_document when the document is not found"""
    server = create_server()

    # Mock get_document to return None (document not found)
    with patch("docvault.db.operations.get_document", return_value=None):
        # Get the read_document tool handler
        tool_handler = server._tool_manager._tools.get("read_document").fn
        assert tool_handler is not None

        # Call the tool with a document ID
        result = await tool_handler(document_id=999)

        # Check the error result
        assert isinstance(result, types.ToolResult)
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert "Document not found: 999" in result.content[0].text
        assert result.metadata["success"] is False
        assert result.metadata["error"] == "Document not found: 999"


@pytest.mark.asyncio
async def test_lookup_library_docs_not_found():
    """Test lookup_library_docs when no documents are found"""
    server = create_server()

    # Mock lookup_library_docs to return an empty list
    with patch("docvault.mcp.server.lookup_library_docs", AsyncMock(return_value=[])):
        # Get the lookup_library_docs tool handler
        tool_handler = server._tool_manager._tools.get("lookup_library_docs").fn
        assert tool_handler is not None

        # Call the tool with a library name
        result = await tool_handler(library_name="nonexistent_library")

        # Check the error result
        assert isinstance(result, types.ToolResult)
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert (
            "Could not find documentation for nonexistent_library latest"
            in result.content[0].text
        )
        assert result.metadata["success"] is False
        assert (
            "Could not find documentation for nonexistent_library latest"
            in result.metadata["message"]
        )


@pytest.mark.asyncio
async def test_list_documents_empty():
    """Test list_documents when no documents are found"""
    server = create_server()

    # Mock list_documents to return an empty list
    with patch("docvault.db.operations.list_documents", return_value=[]):
        # Get the list_documents tool handler
        tool_handler = server._tool_manager._tools.get("list_documents").fn
        assert tool_handler is not None

        # Call the tool
        result = await tool_handler()

        # Check the result
        assert isinstance(result, types.ToolResult)
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert "No documents found in the vault." in result.content[0].text
        assert result.metadata["success"] is True
        assert result.metadata["document_count"] == 0


# Test transport functions
@pytest.mark.skip("Integration test - requires running server")
def test_stdio_transport():
    """Test the stdio transport"""
    # This is an integration test that would require actually running the server
    # and communicating with it via stdin/stdout, which is beyond the scope of unit tests
    pass


@pytest.mark.skip("Integration test - requires running server")
def test_sse_transport():
    """Test the SSE transport"""
    # This is an integration test that would require starting a web server
    # and making HTTP requests to it, which is beyond the scope of unit tests
    pass
