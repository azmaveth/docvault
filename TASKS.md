# DocVault Improvement Tasks

This document outlines tasks for improving DocVault based on AI evaluation and feedback.

## AI Integration Improvements

- [x] **Model Context Protocol Integration**: Implement MCP tools for AI assistants to access DocVault functionality directly
  - [x] Create MCP server implementation using official Python MCP SDK
  - [x] Implement DocVault lookup tool
  - [x] Implement DocVault search tool
  - [x] Implement DocVault add tool
  - [x] Implement DocVault read tool
  - [x] Add better error handling and logging
  - [ ] ~~Add comprehensive documentation for MCP integration~~ (CLAUDE.md already provides good coverage)
- [x] **Structured Response Format**: Add output formats (--format json/xml/markdown) to make responses more easily parsed by AI systems [2025-05-24]
- [ ] ~~**Contextual Knowledge Retrieval**: Implement feature to automatically identify required libraries from code snippets or project descriptions~~ (Complex feature with limited ROI - import-deps already handles project files)
- [x] **Documentation Summarization**: Add option to generate concise summaries of documentation focusing on method signatures, parameters, and examples [2025-05-24]
- [ ] ~~**Versioning Awareness**: Enhance version tracking to better handle library version compatibility~~ (Already supports library@version syntax and version filtering)
- [x] **Batch Operations**: Add support for batch queries to efficiently retrieve documentation for multiple libraries in a single operation [2025-05-24]
- [x] **llms.txt Support**: Add support for llms.txt files to improve AI accessibility [2025-05-26]
  - [x] Automatically detect and parse llms.txt files when scraping documentation
  - [x] Generate llms.txt format output for stored documents
  - [x] Add CLI command to export documentation in llms.txt format
  - [x] Support llms.txt metadata (tags, description, etc.)
  - [x] Implement llms.txt validation according to spec
  - [x] Add option to prefer llms.txt content when available
  - [x] Store llms.txt metadata in dedicated database tables
  - [x] Add `dv llms` commands for managing llms.txt functionality
  - [x] Integrate llms.txt info into search results display
  - Reference: https://llmstxt.org/

## Scraping Improvements (Added Based on Testing)

- [x] **GitHub Scraping**: Fix issues with scraping GitHub repositories for documentation
  - [x] Implement authentication for GitHub API to avoid rate limiting
  - [x] Add support for scraping README.md via API
  - [x] Add support for wiki pages and other documentation files
  - [x] Handle repository structure to extract meaningful documentation
- [x] **Documentation Website Scraping**: Improve scraping of documentation websites
  - [x] Add support for documentation sites like Read the Docs, Sphinx, and MkDocs
  - [x] Handle pagination and navigation menus
  - [x] Extract structured content (headings, code blocks, examples)
- [x] **API Documentation Scraping**: Add specialized support for API documentation
  - [x] Handle OpenAPI/Swagger specifications
  - [x] Extract method signatures, parameters, and examples

## Human User Experience Improvements

- [x] **CLI canonical/alias refactor**: Refactored CLI to use canonical command names with user-friendly aliases (import, remove, list, read, search, etc.). [2025-04-22]
- [x] **CLI additional commands refactor**: Refactor CLI to use restore instead of import-backup, then add _cmd suffix to backup and restore commands in docvault.cli.commands [2025-05-24]
- [x] **Search/lookup merge**: Merged `lookup` into `search` as a subcommand and updated all references. [2025-04-22]
- [x] **Library Search Improvements**: [2025-05-23]
  - [x] Added support for `library@version` syntax (e.g., `django@4.2`) in search commands
  - [x] Improved error messages and progress indicators for library searches
  - [x] Enhanced version display in search results
  - [x] Updated help text with examples of the new syntax
- [x] **Default command**: Made `search` the default command when no subcommand is provided. [2025-04-22]
- [x] **CLI help/docs update**: Updated help strings and documentation to reflect new commands, aliases, and usage. [2025-04-22]
- [x] **Test/README update**: Updated all CLI tests and README to match new command structure and aliasing. [2025-04-22]
- [x] **Troubleshooting guidance**: Added troubleshooting notes for dv command availability and alternative invocation methods (e.g., `uv run dv`). [2025-04-22]
- [x] **Fix README instructions for database initialization**: The README instructs users to run `dv init-db --wipe`, but the `--wipe` option does not exist. Update the README to remove or correct this flag. [2025-05-23]
- [x] **Clarify dv command availability**: The `dv` command may not be available in the PATH after installation, depending on how DocVault is installed. The README now emphasizes alternative invocation methods (`uv run dv`, `./scripts/install-dv.sh`) and troubleshooting tips for command-not-found issues. *(Completed with install script and updated documentation)* [2025-05-24]
- [x] **Improve error feedback for add command**: When adding a document with `dv add <url>`, a generic "Failed to fetch URL" error is shown. Add more descriptive error messages (e.g., network issues, unsupported site, authentication required) and suggest next steps. [2025-05-23]
- [x] **Vector search setup guidance**: If vector search fails due to missing tables or extensions, provide actionable guidance (e.g., how to install sqlite-vec, how to rebuild the index) directly in the CLI output. [2025-05-23]
- [x] **AI/Automation-friendly CLI**: Add structured output options (e.g., `--format json`) for all commands to make parsing by AI agents and automation tools easier. Ensure all error messages are machine-readable as well as human-friendly. [2025-05-23] - Implemented in search functionality with JSON output format option and machine-readable error messages.
- [x] **Installation troubleshooting section**: Add a section to the README for common installation issues and their solutions, especially for virtual environments, dependency problems, and OS-specific quirks. [2025-05-23]
- [x] **Quick test script**: Provide a script or command sequence in the README for users (and AIs) to verify that DocVault is installed and functioning correctly after setup. [2025-05-23]

- [x] **Search Results Improvements**: [2025-05-23]
  - [x] Enhance search result previews to show more complete context instead of truncated snippets [2025-04-27]
  - [x] Add keyword highlighting in search results to quickly identify matched terms [2025-04-27]
  - [x] Add section navigation to search results [2025-05-23]
  - [x] Highlight matching terms in search results [2025-05-23]
  - [x] Add context around matches (snippets) [2025-05-23]
  - [x] Support filtering by document type/source [2025-05-23]
  - [ ] ~~Add relevance feedback mechanism~~ (Complex feature requiring ML/user tracking)
  - [ ] ~~Implement keyboard navigation for search results~~ (CLI doesn't support interactive navigation)
  - [x] Add section hierarchy visualization [2025-05-26]
  - [ ] ~~Support jumping to specific sections in documents~~ (Would require interactive UI)

- [x] **Document Navigation and Structure**:
  - [x] Add ability to navigate between related sections in retrieved documents (2025-05-23)
  - [ ] Better preserve document structure when rendering in different formats
  - [ ] ~~Implement a "related content" suggestion feature based on current viewing history~~ (Requires session/history tracking)
  - [ ] ~~Add document history tracking to easily return to previously viewed documents~~ (CLI is stateless)

- [x] **Metadata Utilization**: [2025-05-23]
  - [x] Improve integration of document metadata into search functionality
  - [x] Display document timestamps and version information in results
  - [x] Add metadata-based filtering options (by date, source, type, version)

- [ ] ~~**Official Docs Registry**: Maintain local references to official documentation URLs for libraries, frameworks, and APIs~~ (Already implemented with registry commands)
- [ ] **Interactive Mode**: Add an interactive shell mode where users can navigate documentation with keyboard shortcuts
- [ ] **Documentation Comparison**: Add features to compare different versions of the same library to identify changes
- [ ] ~~**Better Discovery**: Implement a recommendation system that suggests related libraries or frameworks~~ (Complex ML feature with limited ROI)
- [ ] **Integration with Development Environments**: Create plugins for popular IDEs to access documentation directly from the editor
- [x] **Import from Project Files**: Add ability to scan project files (package.json, mix.exs, requirements.txt, etc.) to fetch documentation for all dependencies automatically [2025-05-23]
- [ ] ~~**User-Friendly Installation**: Simplify the installation process and dependencies~~ (Already simple with uv/pip)

## Suggestions to Improve the Utility of docvault for Coding

1. **Context-Aware Searching and Tagging**
   - [x] Allow tagging documents with keywords related to specific projects or libraries (e.g., "pygame", "networking", "GUI"). [2025-05-24]
   - [x] Enable searching within specific tags or categories to quickly find relevant documentation. [2025-05-24]

2. **Incremental and Sectioned Storage**
   - [x] Support scraping and storing only specific sections or pages of documentation rather than entire documents. [2025-05-25]
     - **Examples of Scraping and Storing Specific Sections:**
       - *What to keep:*
         - Function definitions, signatures, and descriptions
         - Class definitions, inheritance structure, and methods
         - Relevant code snippets demonstrating usage (if concise)
       - *What to leave out:*
         - Overview or introduction sections
         - External links, advertisements, or unrelated topics
         - Large examples that are not directly relevant or too verbose
       - *How to do it:*
         - Schedule scraping with parameters targeting specific HTML headings or sections, e.g., "Functions" or "Classes" in the documentation.
     - **How to Call a Tool for Section-Specific Scraping:**
       - Parameters to send:
         - `url`: The documentation URL
         - `sections`: Array of section headings or identifiers (e.g., `["Functions", "Classes"]`)
         - `depth`: Optional, for limiting nested content
         - `filter_selector`: Optional CSS selector or XPath to target specific parts of the page
       - Example call:

         ```json
         {
           "url": "https://www.pygame.org/docs/",
           "sections": ["Functions", "Classes"],
           "filter_selector": "div.section"
         }
         ```

     - **Prompt for LLM Scraper to Collect Desired Sections:**
       - Sample prompt:
         > "Please extract and store only the sections titled 'Functions' and 'Classes' from the page at [URL]. Include function signatures, descriptions, class details, and relevant code snippets. Omit introductory or unrelated content."
       - Alternatives:
         - Use explicit section headers or CSS selectors in the prompt for deterministic scraping if the structure is consistent.
         - Use heuristics (e.g., headings `h2`, `h3`) to identify sections.
       - Deterministic approach vs. LLM:
         - For highly structured docs, deterministic extraction using CSS selectors or XPath is more reliable.
         - For semi-structured or inconsistent docs, an LLM can interpret headings and decide what to extract, which is more flexible but less predictable.
   - [x] Allow splitting large documents into smaller, manageable sections for easier recall. [COMPLETED - v0.5.3]
     - [✓] Created comprehensive section navigation system in branch `feature/document-sectioning`
     - [✓] SectionNavigator for hierarchical document traversal
     - [✓] Table of contents generation with tree/JSON/flat display
     - [✓] Section-aware CLI commands (toc, read, find, navigate)  
     - [✓] Smart document splitting based on headers
     - [✓] Support for both HTML and Markdown documents
     - [✓] Section relationships (parent/child/sibling navigation)
     - [✓] Path-based section access (e.g., '1.2.3')
     - [✓] Full test coverage and documentation
     - **Status**: MERGED INTO MASTER
     - **Splitting Large Documents:**
       - *Recommended approaches:*
         - By Topic: Use structured headings (`h1`, `h2`, `h3`, etc.) to identify topics.
         - Pre-defined Topics: For documentation, common topics include:
           - Overview / Introduction
           - Installation / Setup
           - Usage / Examples
           - API Reference (Functions, Classes, Methods)
           - Tutorials / Guides
       - *Implementation:*
         - Parse the document HTML or markdown, and split based on headers.
         - Store each section separately, labeled with its heading, for quick access.

3. **Summarization and Highlights**
   - [x] Provide automatic summaries or key points from stored documents for quick reference. [2025-05-25]
     - **Prompt for Summarizing While Preserving Code Snippets:**
       - Sample prompt:
         > "Summarize the following documentation content, highlighting key points and features. Ensure all code snippets and examples are included verbatim and are easily accessible. Present the summary in a clear, concise format."
     - Additional tips:
       - Tag code snippets with their relevant functions or classes.
       - Keep a boolean option to include/exclude code snippets depending on needs.
   - [x] Highlight relevant code snippets or function explanations based on queries. [2025-05-25]

4. **Deep Linking and Cross-References**
   - [x] Enable creating links between related document sections, so I can easily navigate through interconnected concepts. [2025-05-24]
     - **Implementing Deep Links and Cross-References:**
       - *Approach:*
         - Linking topics: When scraping, identify anchor links or headers with unique IDs. Store these IDs as references.
         - Cross-referencing: Maintain a map of related topics, e.g., function `foo()` is referenced in `bar()`; create links in your stored data pointing from `bar()` to `foo()`.
         - Automation: Generate a small index or map of core topics. When a user asks about a concept, provide quick links.
       - *Example:*
         - Append a "Related functions" section with links to other relevant parts of the stored documentation.
         - Use a graph-like structure to connect related entities (functions, classes, modules).
   - [ ] Support cross-referencing between stored documents and our internal notes or projects.

5. **Dynamic Updates & Version Control**
   - [x] Automatically update stored docs when newer versions are available. [2025-05-24]
   - [x] Keep track of different versions of documentation for comparison. [2025-05-24]

6. **Recall with Context and Usage Examples**
   - [x] When recalling documentation, include usage examples, common pitfalls, and best practices. [2025-05-24]
   - [x] Suggest relevant functions, classes, or modules based on the current task. [2025-05-24]

7. **Automatic Context Building for Projects**
   - [ ] When starting a new project, scrape and store related docs automatically based on project goals or libraries.
   - [ ] Build a comprehensive, interconnected knowledge graph of docs and features.

## Technical Improvements

- [x] **Default Registry Population**: Ensure all known package registries (PyPI, npm, RubyGems, Hex, Go, Crates.io) are populated on initial installation, not just PyPI. [2025-05-24] - Added automatic population of default documentation sources during database initialization

- [x] **Document Update-on-Add & Timestamps**: When `dv add <url>` is run on a URL that already exists, update all existing data for that document (re-scrape and overwrite). Ensure the database has a timestamp for each document addition/update and display the date when viewing stored documents. [2025-05-24] - Added `--update` flag to force re-scraping existing documents

- [x] **Comprehensive Logging**: Ensure proper logging is implemented throughout the app. All major operations and failures should log error, warning, and info messages as appropriate, so that users and developers can easily diagnose issues. Replace console.print() with logging. [2025-05-24] - Created logging utilities and console wrapper that logs messages
- [x] **SQLi prevention**: Implement SQL injection prevention measures in database queries. ~~Use SQLAlchemy library to parameterize queries.~~ [2025-05-24] - Verified all database queries already use parameterized statements with ? placeholders
- [ ] ~~**Test dv command on fresh installs**: Ensure the `dv` command is always installed to PATH~~ (Already documented workarounds with uv run)
- [x] **Automated CLI testing**: Implement automated tests or a test harness for the CLI to catch issues like missing options or broken commands after updates. [2025-05-24] - Created comprehensive test suites for all CLI commands including import/add, search, document management, config, init, index, backup/restore, serve, import-deps, and registry commands. Also created integration tests for full workflows.
- [ ] ~~**Improve CLI help output**: Ensure `dv --help` and subcommand help texts are comprehensive~~ (Help is already comprehensive with examples)

- [x] **Fix Critical Bugs Found in QA**:
  - [x] Fix scraper segment unpacking error by updating scraper.py to handle dictionary format from processor
  - [x] Fix SQL syntax error in text search fallback
  - [x] Fix sqlite-vec extension loading issue for direct `dv` command execution
  - [x] Fix Rich progress display conflicts in import-deps command
  - [x] Fix inconsistent return type in processor.py segment_markdown function

- [x] **Fix Vector Search**: Resolve the vector search issue to improve search relevance
  - [x] Properly initialize document_segments_vec table
  - [x] Add index regeneration command
  - [x] Add CLI command (`dv index`) to rebuild vector index if missing/corrupt
  - [x] Add startup check to auto-create `document_segments_vec` if missing
  - [x] Improve error handling and user guidance for missing vector table
  - [x] Add progress notes as improvements are made
  - [x] [Progress] 2025-04-21: Error handling and guidance improvements completed; next: start content extraction improvements.
  - [Progress] 2025-04-21: All vector search improvements completed; proceeding to performance and extraction enhancements.

- [x] **Performance Optimization**: Optimize document scraping and indexing for faster retrieval [COMPLETED - v0.5.3]
  - [✓] Added comprehensive performance optimization system in branch `feature/performance-optimization`
  - [✓] Database connection pooling for SQLite with thread safety
  - [✓] HTTP session pooling for Ollama API requests  
  - [✓] Batch operations for embeddings and database inserts
  - [✓] Intelligent caching system with TTL for embeddings
  - [✓] Performance monitoring and profiling utilities
  - [✓] Database indexes for frequently queried columns
  - [✓] CLI commands for performance management (`dv performance status/benchmark/clear-cache/cleanup`)
  - [✓] Optimized document scraper with async operations and caching
  - [✓] Comprehensive test coverage for all performance features
  - **Status**: MERGED INTO MASTER
- [x] **Content Extraction Improvements**: Enhance scraping to better handle different documentation formats and structures (2025-05-27)
  - [x] Refactor scraper to detect documentation type (Sphinx, MkDocs, OpenAPI)
  - [x] Implement specialized extractors for Sphinx, MkDocs, OpenAPI/Swagger
  - [x] Improve segmentation for navigation/code/structured content
  - [x] Add tests for extraction and segmentation edge cases
  - **Complete**: Implemented DocTypeDetector that identifies documentation formats based on URL patterns, HTML signatures, and content patterns. Created specialized extractors (SphinxExtractor, MkDocsExtractor, OpenAPIExtractor) that extract format-specific metadata like API signatures, navigation structures, code examples, admonitions, etc. Added comprehensive tests and documentation. The scraper now automatically uses the appropriate extractor based on detected type. Branch: `feature/content-extraction-improvements`

- [x] **Scraping Depth Control Enhancements**: [2025-05-25]
  - [x] Improved documentation of the "depth" parameter - now accepts strategies (auto/conservative/aggressive)
  - [x] Added examples in CLI help showing different depth settings and strategies
  - [x] Implemented smart depth detection with DepthAnalyzer that adjusts based on site structure and content quality

- [x] **Caching Strategy**: Implement smart caching with staleness tracking to ensure documentation stays up-to-date [2025-05-25]
  - [x] Added document staleness tracking (fresh/stale/outdated) based on configurable time thresholds
  - [x] Implemented `dv check-updates` command to list stale documents
  - [x] Added `dv update` command to re-scrape stale documents with change detection
  - [x] Created `dv pin` command to prevent specific documents from becoming stale
  - [x] Added visual indicators in `dv read` showing document freshness
  - [x] Implemented HTTP caching with ETag/Last-Modified support for efficient updates
  - [x] Added `dv cache-stats` for monitoring cache health
  - [ ] Future: Implement diff view for comparing document versions
  - [ ] Future: Add automatic update scheduling with cron-like configuration
- [ ] ~~**Offline Mode**: Enhance offline capabilities to ensure reliability without internet connection~~ (DocVault already works offline for stored docs)
- [ ] **Documentation Filtering**: Add options to filter documentation by type (functions, modules, examples, etc.)
- [ ] ~~**Expanded Language Support**: Ensure good support for a wide range of programming languages~~ (Not language-specific, works with any documentation)

## MCP Server Improvements

- [x] **Official SDK Integration**: Refactored MCP server implementation to use official Python MCP SDK
  - [x] Implemented FastMCP-based server with decorator syntax
  - [x] Updated all tools to return standardized ToolResult objects
  - [x] Improved error handling and logging in each tool
- [x] **Tool Schema Refinement**: Enhanced JSON schema for each DocVault tool
  - [x] Added better parameter descriptions
  - [x] Implemented proper validation using FastMCP type annotations
  - [x] Added examples in schema definitions
- [x] **Enhanced Error Handling**: Implemented more robust error handling for MCP tools
  - [x] Added detailed error messages
  - [x] Implemented graceful error recovery
  - [x] Added logging for server errors
- [x] **Production-Ready Enhancements**: Made MCP server more robust for production use (2025-05-30)
  - [x] Added database retry logic with exponential backoff for lock errors
  - [x] Enabled connection pooling with WAL mode for better concurrency
  - [x] Set more conservative rate limits to prevent overwhelming servers
  - [x] Added wait mechanism for rate-limited requests (up to 60s)
  - [x] Fixed read_document_section parameter validation with new read_section tool
  - [x] Improved error messages with actionable advice
  - [x] Added force parameter to add_from_package_manager
  - [x] Fixed SphinxExtractor to return Dict instead of List
  - [x] Added metadata cleaning to prevent JSON serialization errors
- [x] **Additional MCP Tools**: Added 7 new tools for better LLM integration (2025-05-30)
  - [x] suggest - AI-powered code suggestions with task-based and complementary modes
  - [x] add_tags - Document tagging for organization
  - [x] search_by_tags - Tag-based document search
  - [x] check_freshness - Document freshness status checking
  - [x] add_from_package_manager - Quick package documentation addition
  - [x] get_document_sections - Document navigation and table of contents
  - [x] read_document_section - Section-specific reading with workaround for parameter issues
- [ ] ~~**Authentication**: Add authentication for MCP server~~ (MCP typically relies on system-level security)
- [ ] **Extended Server Configuration**: Create additional configuration options for the MCP server
  - [x] Rate limiting implemented with configurable limits
  - [ ] ~~Configure caching behavior~~ (Already caches documents)
  - [ ] ~~Add custom response formatting~~ (MCP has standard response format)
- [x] **Testing**: Develop comprehensive tests for the MCP server
  - [x] Comprehensive tests implemented and passing
  - [x] Fixed test compatibility issues with asyncio and new parameter signatures (2025-05-30)
- [ ] **Deployment Documentation**: Document deployment options for the MCP server

## Issues Addressed

1. **Package Compatibility**: Resolved by implementing official MCP SDK with FastMCP
2. **GitHub Scraping Issues**: DocVault has difficulties scraping content from GitHub repositories.
3. **Documentation Website Scraping**: The current scraper has trouble with specialized documentation websites.
4. **Vector Search Issues**: There's a vector search issue showing "no such table: document_segments_vec" during search operations.
5. **Installation Complexity**: There are challenges with environment setup and dependency management.

## Bugs Found During QA Testing (2025-05-24)

### Critical Bugs

1. **Scraper Segment Unpacking Error**: The scraper fails with `ValueError: too many values to unpack (expected 2)` when trying to add documents. This appears to be due to a mismatch between the processor returning dictionaries and the scraper expecting tuples after the section support feature was added. (File: docvault/core/scraper.py:369)

2. **SQL Syntax Error in Text Search**: Text search fails with `sqlite3.OperationalError: near "END": syntax error` when falling back from vector search. (File: docvault/db/operations.py:503)

### Medium Priority Bugs

1. **sqlite-vec Extension Loading Issue**: The sqlite-vec extension fails to load even when installed, causing vector search to fail. The extension works when using `uv run` but not when calling `dv` directly. This affects the search and index commands.

2. **Rich Progress Display Conflict**: The import-deps command fails with `rich.errors.LiveError: Only one live display may be active at once` when using verbose mode. (File: docvault/project.py:485)

### Minor Issues

1. **Inconsistent Return Type in processor.py**: The `segment_markdown` function returns a list of dictionaries normally but falls back to returning a list of tuples `[(current_type, markdown_content)]` on line 206, causing type inconsistency.

### Fixed Issues

- [x] **Registry commands missing database tables**: Fixed by adding registry migration to v2 in migrations.py
  - Error: "sqlite3.OperationalError: no such column: package_name"
  - Solution: Added _migrate_to_v2 function to create documentation_sources table and add missing columns to libraries table
  - Also fixed Click help option conflicts in registry_commands.py

## QA Testing Summary (2025-05-24)

### Edge Cases Tested and Results

1. **Invalid URL handling**: ✅ Properly catches and reports invalid URL formats
2. **Non-existent URL handling**: ⚠️ Works but error output is too verbose with full stack traces
3. **Non-existent document operations**: ✅ Graceful error messages for rm/read operations
4. **Empty database searches**: ✅ Works correctly (fixed debug print issue)
5. **Concurrent operations**: ✅ Successfully handles multiple simultaneous add operations
6. **Command parsing edge cases**: ✅ Default search command works well

### Recommendations

1. **Reduce error verbosity**: ✅ Network errors now show cleaner messages without full stack traces [2025-05-24]
2. **Debug cleanup**: ✅ Removed debug print statement in search_text command [2025-05-24]
3. **Help option conflicts**: ✅ Fixed registry command help conflicts with VERSION argument [2025-05-24]

## Documentation and Onboarding

- [ ] ~~**Improved Help Messages**: Enhance command help messages with more examples~~ (Already comprehensive)
- [x] **Quick Start Guide**: Create a quick start guide focusing on common usage patterns
- [x] **AI Integration Guide**: Created comprehensive documentation for AI assistants using DocVault via MCP (see CLAUDE.md)
- [x] **Configuration Guide**: Create comprehensive documentation for configuration options
- [x] **Comprehensive User Guide**: Complete guide covering every feature in DocVault with examples and best practices
- [ ] ~~**Custom Scrapers Guide**: Document how to create custom scrapers~~ (Would expose internal APIs)

## Additional Features

- [ ] **Documentation Health Checks**: Add feature to periodically check if cached documentation is still current
- [ ] ~~**Resource Usage Monitoring**: Implement monitoring for storage and performance metrics~~ (Low priority for a CLI tool)
- [ ] ~~**Intelligent Preprocessing**: Develop preprocessing options to optimize content~~ (Too vague)
- [ ] **Cross-referencing**: Implement intelligent cross-referencing between related documentation
- [ ] **Export Features**: Add ability to export documentation in various formats (PDF, Markdown, etc.)

## JavaScript-Rendered Documentation Scraping (Added 2025-05-28)

Based on analysis of MCP specification site (<https://modelcontextprotocol.io/specification/2025-03-26>), identified major limitations in scraping modern documentation sites that use client-side rendering:

### Issues Discovered

- **Content Extraction Gap**: DocVault only extracts ~5KB from 140KB HTML on Next.js sites
- **Detection Failure**: Sites with 0.00 confidence detection fall back to generic extraction
- **Client-Side Rendering**: MDX content compiled to JavaScript not accessible via static HTML parsing
- **Next.js Data Source**: Actual content stored in **\_\_NEXT_DATA\_\_** script as compiled MDX requires JavaScript execution

### High Priority Tasks

- [x] **Next.js Documentation Support**: Add specialized extractor for Next.js-based documentation sites [2025-05-28]
  - [x] Implement NextJSExtractor that parses `__NEXT_DATA__` script content
  - [x] Extract MDX content from compiled JavaScript functions
  - [x] Parse pageProps.mdxSource.compiledSource for actual documentation text
  - [x] Handle mdxExtracts (tableOfContents, codeExamples) for structured content
  - [x] Add Next.js site detection patterns (scripts containing "next", **\_\_NEXT_DATA\_\_** presence)
  - [x] Create tests using MCP specification site as reference
  - **Complete**: Successfully implemented NextJSExtractor that addresses the major limitation where DocVault only extracted ~5KB from 140KB HTML on Next.js sites. The new extractor detects Next.js sites with 100% confidence, extracts content from compiled MDX sources, combines static navigation with dynamic content, and achieves 1.8x content extraction improvement over the generic extractor. Comprehensive test suite validates functionality using the Model Context Protocol specification site. Branch: `feature/nextjs-documentation-support`

- [ ] **JavaScript Rendering Support**: Add optional JavaScript execution for documentation extraction
  - [ ] Integrate headless browser support (Playwright/Selenium) as optional dependency
  - [ ] Add `--render-js` flag to enable JavaScript rendering for static HTML extraction
  - [ ] Implement fallback strategy: try static extraction first, then JS if content is insufficient
  - [ ] Add configuration for JS rendering timeout and resource limits
  - [ ] Create browser pool management for efficient resource usage

- [ ] **React/SPA Documentation Patterns**: Enhance detection for modern documentation frameworks
  - [ ] Add detection patterns for React-based documentation (Docusaurus, Gitiles, etc.)
  - [ ] Implement content extraction from client-side rendered applications
  - [ ] Add support for documentation sites using Gatsby, Nuxt.js, and similar frameworks
  - [ ] Create specialized extractors for popular documentation generators

- [ ] **Enhanced Content Discovery**: Improve extraction completeness for complex sites
  - [ ] Implement content completeness validation (compare extracted vs total text length)
  - [ ] Add warnings when extraction appears incomplete (< 50% of available text)
  - [ ] Create fallback strategies for sites with minimal static content
  - [ ] Add option to extract from multiple content sources (static HTML + JSON data + JS execution)

### Medium Priority Tasks

- [ ] **Documentation Site Framework Detection**: Expand site type detection beyond current patterns
  - [ ] Add detection for Nuxt.js, Gatsby, Docusaurus, GitBook, and other modern doc platforms
  - [ ] Implement confidence scoring improvements for better extractor selection
  - [ ] Create framework-specific extraction strategies
  - [ ] Add user agent and request header optimization for different platforms

- [ ] **Performance Optimization for JS Rendering**: Optimize JavaScript execution overhead
  - [ ] Implement smart caching for rendered content
  - [ ] Add selective JS rendering (only when static extraction fails)
  - [ ] Create lightweight content extraction without full page rendering
  - [ ] Implement parallel processing for bulk operations with JS rendering

### Testing and Validation

- [ ] **Create Test Suite for Modern Documentation Sites**:
  - [ ] Add test cases for MCP specification site extraction
  - [ ] Create fixtures for Next.js, React, and SPA documentation patterns
  - [ ] Implement content completeness validation tests
  - [ ] Add performance benchmarks for JS vs static extraction

## New High-Priority Features

- [x] **Search Within Document**: Add ability to search within a specific document [2025-05-25]
  - [x] Added `--in-doc` flag to search command to scope search to specific document ID
  - [x] Integrated with existing search infrastructure using document_ids filter
  - [x] Enhanced status messages and output to indicate document scope
  - [x] Added search_scope information to JSON output for API consumers
  - [x] Includes document validation to ensure target document exists
  - [x] Works with both vector and text-only search modes
  - [x] Compatible with all other search filters (version, tags, etc.)
- [x] **Bulk Export**: Add command to export multiple documents at once (e.g., `dv export 1-10 --format markdown --output ./docs/`) [2025-05-26]
- [x] **Document Stats Command**: Add `dv stats` to show database size, document count, index health, etc. [2025-05-24]
- [ ] **Partial Document Updates**: Allow updating specific sections of a document without re-scraping everything
- [ ] **Search History**: Store recent searches locally for quick re-execution
- [x] **Document Collections**: Allow grouping documents into named collections [2025-05-25]
  - [x] Created project-based collections system distinct from tags
  - [x] Collections are curated document sets for specific purposes/projects
  - [x] Documents can belong to multiple collections with optional notes
  - [x] Collections can maintain document order (for learning paths)
  - [x] Collections can suggest default tags for consistency
  - [x] Full CLI commands: create, list, show, add, remove, update, delete, find
  - [x] Integrated with search: `dv search --collection "My Project"`
  - [x] Works seamlessly with tags for powerful filtering combinations
  - [x] Comprehensive documentation explaining tags vs collections distinction
  - [x] Example workflows showing tags+collections power
- [x] **Quick Add from Package Manager**: Add shortcuts like `dv add-pypi requests` that automatically finds and adds PyPI docs
- [x] **Document Freshness Indicator**: Show how old documents are and suggest updates for stale ones
- [ ] **Backup Scheduling**: Add ability to schedule automatic backups
- [ ] **Search Result Export**: Allow exporting search results to JSON/CSV for analysis

## CLI UX Improvements - Remaining Items

Most CLI UX improvements have been completed. Remaining nice-to-have features:

- [ ] Add `--long` or `-l` flag to list command for more detailed output
- [ ] Allow multiple URLs at once in import command (e.g., `dv add url1 url2 url3`)
- [ ] Add `--yes` or `-y` flag to skip confirmation prompts in remove command
- [ ] Add `dv help <command>` subcommand for detailed command help
- [ ] Add `dv status` command to show database health, document count, storage usage
- [ ] Support config profiles with `dv config --profile <name>`
- [ ] Add shell completion scripts for bash/zsh/fish

## Security Improvements (2025-05-25)

### Completed Security Tasks

1. **SQL Injection Prevention** ✅
   - [x] Created QueryBuilder class for safe query construction
   - [x] Fixed SQL injection vulnerabilities in operations.py
   - [x] Fixed SQL injection vulnerabilities in version_commands.py
   - [x] Added SQL query logging capability
   - [x] Created SQL security audit script
   - [x] Fixed all instances of filter_clause injection

2. **Path Traversal Prevention** ✅
   - [x] Created comprehensive path_security.py module with validation functions
   - [x] Fixed path traversal vulnerabilities in storage.py (save_html, save_markdown)
   - [x] Fixed vulnerabilities in backup/restore commands in commands.py
   - [x] Added URL validation to scraper.py to prevent SSRF attacks
   - [x] Validated file operations in apply_migrations.py
   - [x] Added comprehensive tests for path security module

3. **URL Validation and SSRF Prevention** ✅
   - [x] Enhanced URL validation with comprehensive SSRF protection
   - [x] Added cloud metadata service blocking (AWS, GCP, Azure)
   - [x] Implemented domain allowlist/blocklist functionality
   - [x] Added blocked ports for internal services
   - [x] Implemented request timeouts and size limits
   - [x] Added proxy configuration support
   - [x] Enforced scraping depth and pages-per-domain limits
   - [x] Created comprehensive tests for all URL security features

### Pending Security Tasks

1. **Authentication and Authorization**
   - [ ] Implement MCP server authentication (temporarily deferred)
   - [ ] Add role-based access control for sensitive operations
   - [ ] Implement API key management for external services

2. **Input Validation and Sanitization**
   - [ ] Implement comprehensive input validation for all user inputs
   - [ ] Add HTML/JavaScript sanitization for stored content
   - [ ] Validate and sanitize metadata before storage

3. **Secure Communication**
   - [ ] Implement TLS/SSL for MCP server communications
   - [ ] Add certificate validation for scraped URLs
   - [ ] Implement secure key storage for API credentials

4. **Data Protection**
   - [ ] Add encryption for sensitive configuration data
   - [ ] Implement secure deletion of temporary files
   - [ ] Add data retention policies and automatic cleanup

5. **Monitoring and Auditing**
   - [ ] Implement comprehensive security logging
   - [ ] Add intrusion detection for suspicious patterns
   - [ ] Create security audit reports

6. **Additional Security Hardening**
   - [ ] Implement rate limiting for API endpoints
   - [ ] Add resource usage limits to prevent DoS
   - [ ] Implement secure defaults for all configurations
   - [ ] Regular security dependency updates

## AI Accessibility Features

- [x] **llms.txt Support**: Add support for llms.txt files to make documentation more accessible to AI assistants [2025-05-26]
  - [x] Add `llms.txt` scraping capability to detect and parse llms.txt files from documentation sites
  - [x] Create `dv llms` command to list discovered llms.txt endpoints
  - [x] Add `--llms-only` flag to `add` command to specifically target llms.txt files
  - [x] Store llms.txt metadata separately for quick AI access
  - [x] Add llms.txt content to search results when available
  - [x] Support llms.txt format in export functionality
  - [x] Document llms.txt integration in CLAUDE.md for AI assistants

## End-to-End Testing

- [x] **Comprehensive End-to-End Test Suite**: Create automated testing framework for all features [2025-05-26]
  - [x] Design test runner framework with proper isolation and reporting
  - [x] Create test cases for all 60+ commands and their argument combinations
  - [x] Test all core features: initialization, document management, search, organization
  - [x] Test package manager integration for all supported platforms
  - [x] Test freshness tracking and cache management features
  - [x] Test advanced features: tags, collections, cross-references, version control
  - [x] Test error handling and edge cases
  - [x] Create test fixtures and data generators
  - [x] Add CI/CD integration with GitHub Actions
  - [x] Create performance benchmarking extension
  - [x] Support multiple output formats (console, JSON)
  - [x] Enable parallel test execution for faster runs
  - [x] Create shell script wrapper for easy test execution

## Contextual Retrieval Implementation

- [x] **Implement Contextual Retrieval for Enhanced RAG**: Improve retrieval accuracy by adding context to chunks before embedding [2025-06-06]
  - [x] Add LLM integration for context generation (Claude API or local LLM)
    - [x] Created llm_context.py with support for Ollama, OpenAI, and Anthropic
    - [x] Implemented context caching and batch processing
    - [x] Added configurable prompt templates for different document types
  - [x] Modify chunk processing pipeline to generate contextual descriptions
    - [x] Created ContextualChunkProcessor that integrates with existing pipeline
    - [x] Implemented hierarchical context generation using document structure
    - [x] Added semantic role detection (code example, API reference, etc.)
  - [x] Update embedding generation to use contextualized chunks
    - [x] Modified processor to prepend context before embedding
    - [x] Store contextualized embeddings separately from original
  - [x] Store both original and contextualized content in database
    - [x] Keep original content intact for fallback
    - [x] Store contextualized embeddings in context_embedding column
  - [x] Add database columns for contextual descriptions and metadata
    - [x] Added context_description, context_metadata, context_embedding columns
    - [x] Created chunk_relationships and context_templates tables
    - [x] Implemented migration as v9 in migration system
  - [x] Implement hybrid approach: context in embeddings + metadata storage
    - [x] Context included in embeddings for better semantic search
    - [x] Context stored as metadata for filtering and navigation
    - [x] Created separate metadata embeddings table for similarity search
  - [x] Create hierarchical context using DocVault's section structure
    - [x] Build section hierarchy from document structure
    - [x] Include parent sections in context for better understanding
  - [x] Add semantic role context (code example, parameter docs, etc.)
    - [x] Detect content type and assign semantic roles
    - [x] Use role-specific prompt templates for context generation
  - [x] Implement metadata similarity search for finding related chunks
    - [x] find_similar_by_metadata method in ContextualChunkProcessor
    - [x] CLI command `dv context similar` for finding related content
  - [x] Add configuration options for context generation (LLM model, prompt templates)
    - [x] Configurable via `dv context config` command
    - [x] Support for different providers and models
    - [x] Customizable batch size and token limits
  - [ ] Create benchmarks to measure retrieval improvement
  - [x] Add "More Like This" feature using metadata similarity
    - [x] Implemented in find_similar_by_metadata method
    - [x] Can filter by semantic role
  - [x] Enable cross-document navigation based on context similarity
    - [x] Metadata similarity works across all documents
    - [x] Returns document IDs for navigation
  - [ ] Build learning paths using progressive complexity metadata
  - [ ] Create topic clustering across documents
  - Reference: https://www.anthropic.com/engineering/contextual-retrieval

## Knowledge Graph Integration (Low Priority)

- [ ] **Add Knowledge Graph for Relationship Discovery**: Enhance DocVault with explicit entity relationships and graph-based navigation
  - [ ] Phase 1: Basic Infrastructure
    - [ ] Add knowledge_nodes and knowledge_edges tables to schema
    - [ ] Create indices for efficient graph traversal
    - [ ] Implement basic relationship extraction during scraping (function calls, cross-references)
    - [ ] Add `--related` flag to search command for finding related content
    - [ ] Extract "See also" sections as explicit relationships
  - [ ] Phase 2: Entity Recognition (if Phase 1 proves valuable)
    - [ ] Extract entities: functions, classes, concepts, errors
    - [ ] Build relationship types: calls, inherits, implements, throws, related-to
    - [ ] Add "find similar" feature across documents
    - [ ] Implement `dv graph` command for relationship queries
  - [ ] Phase 3: Advanced Features (only if actively used)
    - [ ] Learning path generation based on prerequisites
    - [ ] Pattern mining across documentation
    - [ ] API migration assistant (find equivalent functions)
    - [ ] Concept clustering and visualization
    - [ ] Integration with NetworkX for complex graph algorithms
  - [ ] Keep graph features optional and additive
  - [ ] Monitor usage metrics before expanding
  - Reference: See KNOWLEDGE_GRAPH_ANALYSIS.md for detailed implementation strategy

## MCP QA Issues to Address (DocVault 0.7.1)

Based on comprehensive QA testing of all MCP tools, the following issues need attention:

### High Priority Issues

- [ ] **Fix read_document_section Parameter Validation Error** (Critical)
  - [ ] Issue: MCP tool interface validation fails with "Input should be a valid string [type=string_type, input_value=1, input_type=int]"
  - [ ] Root cause: Parameter validation in MCP tool interface incorrectly handles string parameters
  - [ ] Impact: Cannot read specific document sections via MCP, blocking partial document access
  - [ ] File: `/Users/azmaveth/code/docvault/docvault/mcp/tools.py` or `/Users/azmaveth/code/docvault/docvault/mcp/handlers.py`
  - [ ] Solution: Fix parameter type conversion in read_document_section tool definition
  - [ ] Test: Verify `read_document_section(document_id=107, section_path="1")` works correctly

- [ ] **Improve Suggestion Engine Quality** (High)
  - [ ] Issue: `suggest` tool returns low-relevance suggestions (Node.js functions for "python requests" query)
  - [ ] Root cause: Suggestion algorithm lacks proper query context understanding
  - [ ] Impact: Reduced utility of AI-powered suggestions for developers
  - [ ] File: `/Users/azmaveth/code/docvault/docvault/core/suggestion_engine.py`
  - [ ] Solution: Enhance algorithm to better match query context and programming language
  - [ ] Test: Query "python requests" should return relevant Python HTTP library suggestions

### Medium Priority Issues

- [x] **Enhance Package Manager Integration Coverage** (Medium) [2025-06-07]
  - [x] Issue: `add_from_package_manager` fails for common packages like pytest
  - [x] Root cause: Limited coverage of package documentation sources  
  - [x] Impact: Reduced automation of documentation acquisition
  - [x] File: `/Users/azmaveth/code/docvault/docvault/core/library_manager.py`
  - [x] Solution: Expand documentation source mapping and improve error handling
  - [x] Test: `add_from_package_manager("pytest", "pypi")` now succeeds
  - **Improvements Made**:
    - Fixed URL pattern formatting for non-versioned URLs (e.g., fastapi.tiangolo.com)
    - Expanded hardcoded patterns from 12 to 70+ popular Python packages
    - Enhanced PyPI metadata extraction with multiple documentation URL keys
    - Added common pattern detection (readthedocs.io, github.io, etc.)
    - Added comprehensive logging for troubleshooting

- [x] **Improve Section Content Extraction** (Medium) [2025-06-07]
  - [x] Issue: `read_section` returns minimal content ("# Section" only)
  - [x] Root cause: Section reading implementation may not extract full content
  - [x] Impact: Incomplete section access reduces navigation utility
  - [x] File: `/Users/azmaveth/code/docvault/docvault/mcp/server.py`
  - [x] Solution: Enhanced section content extraction to return complete section text from segments
  - [x] Test: Section reading now extracts full content from segments structure
  - **Fix Applied**: Updated MCP server to properly extract content from segments structure in multiple tools (read_document_section, read_section_by_number, read_section)

### AI Usability Improvements

- [x] **Add Contextual Search Hints** (Medium) [2025-06-07]
  - [x] Issue: Search results don't provide enough context for AI assistants to understand relevance
  - [x] Enhancement: Add snippet previews and relevance explanations in MCP search results
  - [x] Impact: Better AI decision-making about which documents to read
  - [x] File: `/Users/azmaveth/code/docvault/docvault/mcp/server.py`
  - [x] Solution: Include content snippets and relevance scores in search metadata
  - **Improvements Made**:
    - Added visual relevance indicators (🟢 High, 🟡 Medium, 🔵 Basic)
    - Implemented content type detection (API Reference, Tutorial/Guide, Examples, etc.)
    - Added complexity indicators (Beginner, Intermediate, Advanced, Technical)
    - Enhanced content previews (300 characters vs 200)
    - Added AI usage hints with specific recommendations for each result
    - Enhanced metadata with relevance distribution and content type analysis
    - Added summary statistics for AI decision-making

- [ ] **Implement Progressive Content Discovery** (Medium)
  - [ ] Issue: AI assistants lack guidance on how to navigate large documents efficiently
  - [ ] Enhancement: Add "suggested next sections" and "related content" to read operations
  - [ ] Impact: More efficient AI exploration of documentation
  - [ ] File: `/Users/azmaveth/code/docvault/docvault/core/section_navigator.py`
  - [ ] Solution: Implement content relationship mapping and navigation suggestions

- [ ] **Add Document Difficulty/Complexity Indicators** (Low)
  - [ ] Issue: AI assistants can't assess document complexity before reading
  - [ ] Enhancement: Add metadata indicating beginner/intermediate/advanced content
  - [ ] Impact: Better content prioritization for AI responses
  - [ ] File: `/Users/azmaveth/code/docvault/docvault/core/processor.py`
  - [ ] Solution: Analyze content complexity during scraping and store as metadata

- [ ] **Enhance Error Messages for AI Consumption** (Low)
  - [ ] Issue: Error messages are human-focused and may not provide actionable guidance for AI
  - [ ] Enhancement: Include structured error codes and suggested remediation steps
  - [ ] Impact: Better AI error handling and user guidance
  - [ ] File: `/Users/azmaveth/code/docvault/docvault/mcp/handlers.py`
  - [ ] Solution: Standardize error response format with actionable guidance

### Testing and Validation

- [ ] **Create MCP Tool Integration Tests** (High)
  - [ ] Add automated tests for all 20 MCP tools to prevent regressions
  - [ ] Include parameter validation and error handling tests
  - [ ] File: `/Users/azmaveth/code/docvault/tests/test_mcp_integration.py`
  - [ ] Ensure tests cover the specific issues found in QA testing

- [ ] **Add AI Assistant Usage Analytics** (Low)
  - [ ] Track which tools are most/least used by AI assistants
  - [ ] Monitor error patterns to identify common issues
  - [ ] File: `/Users/azmaveth/code/docvault/docvault/utils/usage_analytics.py`
  - [ ] Help prioritize future improvements based on actual usage

## AI Assistant Workflow Improvements

Based on QA testing from an AI perspective, these enhancements would improve DocVault's utility for AI assistants:

### Enhanced Content Understanding

- [ ] **Add Content Type Classification** (Medium)
  - [ ] Automatically classify content as: tutorial, reference, example, troubleshooting, concept
  - [ ] Help AI assistants select appropriate content for different user queries
  - [ ] Store classification metadata and expose via MCP tools

- [ ] **Implement Code Example Extraction** (Medium)  
  - [ ] Automatically identify and index code examples separately
  - [ ] Make code examples searchable by programming language and functionality
  - [ ] Add `search_code_examples` MCP tool for targeted code search

### Improved Navigation Assistance

- [ ] **Add Learning Path Suggestions** (Low)
  - [ ] Suggest logical reading order for complex topics
  - [ ] Identify prerequisite and follow-up content
  - [ ] Help AI assistants guide users through structured learning

- [ ] **Implement Smart Content Chunking** (Low)
  - [ ] Break large documents into conceptually coherent chunks
  - [ ] Preserve logical boundaries (complete functions, examples, explanations)
  - [ ] Improve AI's ability to provide focused, complete answers

### Enhanced Metadata for AI Decision Making

- [ ] **Add Content Confidence Scores** (Low)
  - [ ] Score content based on completeness, accuracy indicators, and freshness
  - [ ] Help AI assistants prioritize high-quality sources
  - [ ] Include scores in MCP tool responses

- [ ] **Implement Usage Pattern Analysis** (Low)
  - [ ] Track which content is most useful for different types of queries
  - [ ] Surface popular/recommended sections for common topics
  - [ ] Help AI assistants identify the most valuable content first
