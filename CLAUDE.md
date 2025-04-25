# DocVault Instructions for AI Assistants

## Overview

DocVault is a tool for searching, fetching, and managing documentation for libraries, frameworks, and tools. It's designed to help AI assistants access up-to-date documentation that might be beyond their training cutoff date. This document provides guidance on how to use DocVault effectively.

## MCP Integration

DocVault integrates with AI assistants via the Model Context Protocol (MCP). The server exposes tools that can be used to search for and retrieve documentation.

**Note:** For web/SSE mode, set the server bind address using `HOST` and `PORT` in your `.env` file. `SERVER_HOST` and `SERVER_PORT` are only used for legacy stdio/AI mode.

### Available MCP Tools

1. **scrape_document**: Adds documentation from a URL to the vault
   - Parameters: `url` (string), `depth` (integer, default: 1)
   - Returns: Document ID, title, and URL

2. **search_documents**: Searches documents in the vault
   - Parameters: `query` (string), `limit` (integer, default: 5)
   - Returns: Search results with document_id, segment_id, title, content, and score

3. **read_document**: Retrieves a document from the vault
   - Parameters: `document_id` (integer), `format` (string, default: "markdown")
   - Returns: Document content, title, and URL

4. **lookup_library_docs**: Looks up documentation for a specific library
   - Parameters: `library_name` (string), `version` (string, default: "latest")
   - Returns: Available documentation for the requested library

5. **list_documents**: Lists all documents in the vault
   - Parameters: `filter` (string, default: ""), `limit` (integer, default: 20)
   - Returns: List of documents with their IDs, titles, URLs, and scrape dates

## Usage Tips

1. **Context-Aware Responses**: When using documentation from DocVault, remember to include proper citations and acknowledge the source.

2. **Handling Missing Documentation**: If the documentation you need isn't in the vault, suggest using `scrape_document` to add it. Be specific about the URL and appropriate depth.

3. **Fallback Strategy**: If DocVault fails to provide necessary documentation, consider other approaches like:
   - Looking for similar libraries or tools that might have documentation in the vault
   - Using general knowledge to provide best-effort guidance
   - Suggesting the user add the documentation using the CLI: `dv add <url>`

4. **Library Lookups**: When a user asks about a specific library, use `lookup_library_docs` to find available documentation.

5. **Search First**: Use `search_documents` to find relevant documentation before trying more specific queries.

## Known Limitations

1. **GitHub Scraping**: DocVault may struggle with scraping GitHub repositories effectively. When recommending scraping from GitHub, suggest using documentation-specific URLs rather than repository root URLs.

2. **Documentation Websites**: Some documentation websites might not be scraped properly. If search fails to find documentation for well-known libraries, this could be the reason.

3. **Vector Search Issues**: If search results mention "falling back to text search," the vector search functionality might be experiencing issues. Text search will still work but might not be as accurate.

4. **Depth Parameter**: When using `scrape_document`, be cautious with the depth parameter. Higher depths may result in unrelated content being scraped.

5. **Response Formatting**: Responses from DocVault are primarily designed for human readability. AI assistants should parse and format the content appropriately for user responses.

## Best Practices

1. **Cite Sources**: Always cite the document ID, title, and relevant section when using information from DocVault.

2. **Handle Errors Gracefully**: If DocVault returns errors, provide a helpful explanation to the user and suggest alternatives.

3. **Use Multiple Tools**: Combine multiple DocVault tools for the best results. For example, first `list_documents` to see what's available, then `search_documents` for specific information.

4. **Library Recommendations**: When suggesting libraries to users, prioritize those with documentation available in DocVault.

5. **Feedback Collection**: If you identify issues with DocVault (missing documentation, scraping problems, etc.), suggest the user report these issues for improvement.

## Example Workflow

When helping a user with a programming task:

1. Identify required libraries/frameworks
2. Use `lookup_library_docs` to check if documentation is available
3. If available, use `search_documents` to find relevant sections
4. Use `read_document` to retrieve detailed information
5. Incorporate the documentation into your response, with proper citation
6. If documentation is not available, suggest adding it with `scrape_document`

By following these guidelines, you'll be able to provide more accurate and up-to-date assistance to users through DocVault.
