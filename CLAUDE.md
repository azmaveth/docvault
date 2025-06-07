# DocVault Instructions for AI Assistants

## Version and Quality Notice

**Current Version**: 0.7.0 (Alpha Quality Software)

**Important**: DocVault is currently in alpha stage. While functional, you may encounter bugs or unexpected behavior. Please report any issues you find.

## Versioning Directives

### Semantic Versioning

DocVault follows [Semantic Versioning](https://semver.org/):
- MAJOR version for incompatible API changes
- MINOR version for backwards-compatible functionality additions
- PATCH version for backwards-compatible bug fixes

### CHANGELOG.md Tracking

**Critical**: All changes MUST be documented in CHANGELOG.md:
- New features go under "Added"
- Breaking changes go under "Changed" with BREAKING prefix
- Bug fixes go under "Fixed"
- Deprecated features go under "Deprecated"
- Removed features go under "Removed"
- Security fixes go under "Security"

When making changes:
1. Update the version in `docvault/version.py`
2. Add entry to CHANGELOG.md under "Unreleased" section
3. Follow conventional commit format for commit messages
4. On release, move "Unreleased" items to new version section with date

## Overview

DocVault is a tool for searching, fetching, and managing documentation for libraries, frameworks, and tools. It's designed to help AI assistants access up-to-date documentation that might be beyond their training cutoff date. This document provides guidance on how to use DocVault effectively.

## MCP Integration

DocVault integrates with AI assistants via the Model Context Protocol (MCP). The server exposes tools that can be used to search for and retrieve documentation.

**Note:** For web/SSE mode, set the server bind address using `HOST` and `PORT` in your `.env` file. `SERVER_HOST` and `SERVER_PORT` are only used for legacy stdio/AI mode.

### Available MCP Tools

#### Document Management
1. **scrape_document**: Adds documentation from a URL to the vault
   - Parameters: `url` (string), `depth` (integer/string, default: 1), `sections` (list), `filter_selector` (string), `depth_strategy` (string), `force_update` (boolean)
   - Returns: Document ID, title, and URL

2. **search_documents**: Searches documents in the vault with contextual retrieval support
   - Parameters: `query` (string), `limit` (integer, default: 5), `min_score` (float), `version` (string), `library` (boolean), `title_contains` (string), `updated_after` (string)
   - Returns: Search results with document_id, segment_id, title, content, score, and contextual indicators

3. **read_document**: Retrieves a document from the vault with summarization/chunking
   - Parameters: `document_id` (integer), `format` (string, default: "markdown"), `mode` (string: "summary"/"full"/"chunk"), `chunk_size` (integer), `chunk_number` (integer), `summary_method` (string), `chunking_strategy` (string)
   - Returns: Document content, title, and URL

4. **lookup_library_docs**: Looks up documentation for a specific library
   - Parameters: `library_name` (string), `version` (string, default: "latest")
   - Returns: Available documentation for the requested library

5. **list_documents**: Lists all documents in the vault
   - Parameters: `filter` (string, default: ""), `limit` (integer, default: 20)
   - Returns: List of documents with their IDs, titles, URLs, and scrape dates

#### Contextual Retrieval Tools
6. **enable_contextual_retrieval**: Enable contextual retrieval for enhanced search accuracy
   - No parameters
   - Returns: Success status

7. **disable_contextual_retrieval**: Disable contextual retrieval
   - No parameters
   - Returns: Success status

8. **get_contextual_retrieval_status**: Get status and statistics of contextual retrieval
   - No parameters
   - Returns: Enabled status, provider info, coverage statistics

9. **process_document_with_context**: Process a specific document with contextual retrieval
   - Parameters: `document_id` (integer), `force` (boolean, default: false)
   - Returns: Processing status and segments processed

10. **configure_contextual_retrieval**: Configure the LLM provider for contextual retrieval
    - Parameters: `provider` (string: "ollama"/"openai"/"anthropic"), `model` (string, optional)
    - Returns: Configuration status

11. **find_similar_by_context**: Find similar content using contextual metadata
    - Parameters: `document_id` (integer), `segment_id` (integer, optional), `limit` (integer, default: 5)
    - Returns: Similar content with similarity scores

#### Organization and Navigation
12. **add_tags**: Add tags to a document for better organization
    - Parameters: `document_id` (integer), `tags` (list of strings)
    - Returns: Success status

13. **search_by_tags**: Search documents by tags
    - Parameters: `tags` (list of strings), `match_all` (boolean), `limit` (integer)
    - Returns: Matching documents

14. **get_document_sections**: Get table of contents and section structure
    - Parameters: `document_id` (integer), `max_depth` (integer, default: 3)
    - Returns: Section hierarchy

15. **read_document_section**: Read a specific section from a document
    - Parameters: `document_id` (integer), `section_path` (string), `section_id` (integer), `include_subsections` (boolean)
    - Returns: Section content

16. **search_sections**: Search for specific sections within a document
    - Parameters: `document_id` (integer), `query` (string), `search_type` (string), `limit` (integer)
    - Returns: Section paths and chunk numbers

#### Utility Tools
17. **check_freshness**: Check document freshness status
    - Parameters: `document_id` (integer, optional), `stale_only` (boolean)
    - Returns: Freshness status and recommendations

18. **add_from_package_manager**: Quickly add documentation from package managers
    - Parameters: `package` (string), `manager` (string), `version` (string), `force` (boolean)
    - Returns: Added document info

19. **suggest**: Get AI-powered suggestions for functions and classes
    - Parameters: `query` (string), `limit` (integer), `task_based` (boolean), `complementary` (string)
    - Returns: Suggested functions/classes

20. **get_chunk_info**: Get information about available chunks for a document
    - Parameters: `document_id` (integer), `chunk_size` (integer), `chunking_strategy` (string)
    - Returns: Total chunks and navigation hints

## Enhanced CLI Features for AI Assistance

In addition to the MCP tools, DocVault v0.7.0 includes powerful CLI features that AI assistants should recommend to users:

### Contextual Retrieval for Enhanced RAG

DocVault now supports contextual retrieval, which improves search accuracy by up to 49%:

1. **Enable Contextual Retrieval**: Recommend users enable this feature:
   - `dv context enable` - Turn on contextual retrieval
   - `dv context status` - Check current status and coverage
   - `dv context process-all` - Process all documents with context

2. **Search with Contextual Embeddings**: Search now automatically uses contextual embeddings:
   - Look for `[ctx]` indicators in search results
   - Use `--verbose` to see context descriptions
   - Results with contextual embeddings are prioritized

3. **Configure LLM Providers**: Help users set up their preferred LLM:
   - `dv context config --provider ollama --model llama2` (local, default)
   - `dv context config --provider openai --model gpt-3.5-turbo` (cloud)
   - `dv context config --provider anthropic --model claude-3-haiku` (best quality)

### Context-Aware Documentation Access

When helping users with coding tasks, recommend these enhanced commands:

1. **Rich Contextual Information**: Use `dv read <id> --context` to get:
   - Code examples with language detection and complexity analysis
   - Best practices with importance levels
   - Common pitfalls with solutions and severity indicators
   - Related concepts and prerequisites

2. **Intelligent Suggestions**: Use `dv suggest` for:
   - Task-based suggestions: `dv suggest "database queries" --task-based`
   - Complementary functions: `dv suggest --complementary "open" query`
   - JSON output for automation: `dv suggest "error handling" --format json`

3. **Enhanced Search with Suggestions**: Use `dv search "topic" --suggestions` to get related functions and classes alongside search results.

### Document Organization and Navigation

For better documentation management:

1. **Tagging System**: Organize documents with `dv tag add <id> "tag1" "tag2"`
2. **Cross-References**: Navigate related sections with `dv read <id> --show-refs`
3. **Version Tracking**: Check for updates with `dv versions check <id>`

### Automation and Integration

For AI assistants and automation tools:

1. **Structured Output**: Most commands support `--format json` for machine-readable output
2. **Batch Operations**: Process multiple libraries with `dv search batch lib1 lib2 lib3`
3. **Comprehensive Stats**: Get vault health info with `dv stats`

## Usage Tips

1. **Context-Aware Responses**: When using documentation from DocVault, remember to include proper citations and acknowledge the source.
2. **Recommend Enhanced Features**: Suggest users try `--context`, `--suggestions`, and `dv suggest` commands for richer information.
3. **Handling Missing Documentation**: If the documentation you need isn't in the vault, suggest using `scrape_document` to add it. Be specific about the URL and appropriate depth.
4. **Fallback Strategy**: If DocVault fails to provide necessary documentation, consider other approaches like:
   - Looking for similar libraries or tools that might have documentation in the vault
   - Using general knowledge to provide best-effort guidance
   - Suggesting the user add the documentation using the CLI: `dv add <url>`

## Troubleshooting: sqlite-vec Extension and Vector Search

If you see errors like:

```text
sqlite-vec extension cannot be loaded: dlopen(sqlite_vec.dylib, ...): ... Falling back to text search.
```

or

```text
ModuleNotFoundError: No module named 'sqlite_vec'
```

**Follow these steps:**

1. **Ensure the Python package is installed:**

   - Run: `uv pip install sqlite-vec`
   - This installs both the Python wrapper and the native extension for your platform.

2. **Always use `uv run ...` to execute scripts or commands:**

   - Example: `uv run python -c "import sqlite_vec; ..."`
   - This ensures the correct environment and libraries are used.

3. **Verify installation:**

   - Test in a shell:

     ```sh
     uv run python -c "import sqlite3; import sqlite_vec; db = sqlite3.connect(':memory:'); db.enable_load_extension(True); sqlite_vec.load(db); print('sqlite-vec loaded successfully')"
     ```

   - If you see `sqlite-vec loaded successfully`, the extension is available.

4. **No need to manually manage `.dylib` files:**

   - The Python package handles loading the native extension if installed via `uv` or `pip`.

5. **If you still have issues:**

   - Double-check your environment with `uv pip list` and ensure you are not mixing environments.
   - Reinstall with `uv pip install --force-reinstall sqlite-vec` if necessary.

**Summary:**

- Use `uv` for all dependency management and execution.
- Install `sqlite-vec` via `uv pip`.
- The Python package will load the extension; no manual copying of files is needed.

### Best Practices for sqlite-vec

- Use `uv` for all dependency management and execution.
- Install `sqlite-vec` via `uv pip`.
- The Python package will load the extension; no manual copying of files is needed.

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

## Security Features

DocVault implements comprehensive security measures to protect against common vulnerabilities:

### URL Validation and SSRF Prevention

When using `scrape_document` or adding URLs via CLI:
- Only HTTP/HTTPS URLs are allowed
- Private IP ranges are blocked (10.x, 172.16-31.x, 192.168.x)
- Localhost and loopback addresses are blocked
- Cloud metadata services are blocked (AWS, GCP, Azure)
- Common internal service ports are blocked (SSH, RDP, etc.)
- URL length is limited to 2048 characters

### Domain Control

Users can configure allowed/blocked domains via environment variables:
- `URL_ALLOWED_DOMAINS` - Whitelist specific domains
- `URL_BLOCKED_DOMAINS` - Blacklist specific domains

### Resource Limits

DocVault enforces the following limits (configurable):
- Request timeout: 30 seconds (REQUEST_TIMEOUT)
- Max response size: 10MB (MAX_RESPONSE_SIZE)
- Max scraping depth: 5 levels (MAX_SCRAPING_DEPTH)
- Max pages per domain: 100 (MAX_PAGES_PER_DOMAIN)

### Rate Limiting

DocVault includes comprehensive rate limiting to prevent abuse:

**Per-Domain Limits:**
- 60 requests per minute (RATE_LIMIT_PER_MINUTE)
- 1000 requests per hour (RATE_LIMIT_PER_HOUR)
- Burst detection: 10 requests (RATE_LIMIT_BURST_SIZE)

**Global Limits:**
- 300 requests per minute across all domains (GLOBAL_RATE_LIMIT_PER_MINUTE)
- 5000 requests per hour across all domains (GLOBAL_RATE_LIMIT_PER_HOUR)

**Resource Management:**
- Max concurrent requests: 10 (MAX_CONCURRENT_REQUESTS)
- Max memory usage: 1024MB (MAX_MEMORY_MB)
- Max processing time: 300 seconds per operation (MAX_PROCESSING_TIME_SECONDS)

When rate limits are exceeded, DocVault will:
- Return clear error messages explaining the limit
- Implement cooldown periods for burst protection
- Track and limit concurrent operations
- Monitor memory usage to prevent system overload

### Other Security Features

- SQL injection prevention via parameterized queries
- Path traversal prevention for file operations
- Archive security validation for backup/restore
- Secure defaults for all operations

## Contributing and Version Updates

When contributing to DocVault:

1. **Version Bumps**: Update `docvault/version.py` according to semantic versioning rules
2. **Changelog Updates**: Always update CHANGELOG.md with your changes
3. **Alpha Quality Notice**: Remember this is alpha software - be conservative with changes
4. **Testing**: Run the full test suite before submitting changes
5. **Documentation**: Update this file and README.md as needed for new features
