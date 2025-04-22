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
  - [ ] Add comprehensive documentation for MCP integration
- [ ] **Structured Response Format**: Add output formats (--format json/xml/markdown) to make responses more easily parsed by AI systems
- [ ] **Contextual Knowledge Retrieval**: Implement feature to automatically identify required libraries from code snippets or project descriptions
- [ ] **Documentation Summarization**: Add option to generate concise summaries of documentation focusing on method signatures, parameters, and examples
- [ ] **Versioning Awareness**: Enhance version tracking to better handle library version compatibility
- [ ] **Batch Operations**: Add support for batch queries to efficiently retrieve documentation for multiple libraries in a single operation

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

- [ ] **Official Docs Registry**: Maintain local references to official documentation URLs for libraries, frameworks, and APIs (e.g., Hexdocs for Elixir, PyPI for Python). Automatically update registry as new docs are discovered.
- [ ] **Interactive Mode**: Add an interactive shell mode where users can navigate documentation with keyboard shortcuts
- [ ] **Documentation Comparison**: Add features to compare different versions of the same library to identify changes
- [ ] **Better Discovery**: Implement a recommendation system that suggests related libraries or frameworks
- [ ] **Integration with Development Environments**: Create plugins for popular IDEs to access documentation directly from the editor
- [ ] **Import from Project Files**: Add ability to scan project files (package.json, mix.exs, requirements.txt, etc.) to fetch documentation for all dependencies automatically
- [ ] **User-Friendly Installation**: Simplify the installation process and dependencies

## Technical Improvements

- [x] **Fix Vector Search**: Resolve the vector search issue to improve search relevance
  - [x] Properly initialize document_segments_vec table
  - [x] Add index regeneration command
  - [x] Add CLI command (`dv index`) to rebuild vector index if missing/corrupt
  - [x] Add startup check to auto-create `document_segments_vec` if missing
  - [x] Improve error handling and user guidance for missing vector table
  - [x] Add progress notes as improvements are made
  - [x] [Progress] 2025-04-21: Error handling and guidance improvements completed; next: start content extraction improvements.
  - [Progress] 2025-04-21: All vector search improvements completed; proceeding to performance and extraction enhancements.

- [ ] **Performance Optimization**: Optimize document scraping and indexing for faster retrieval
- [ ] **Content Extraction Improvements**: Enhance scraping to better handle different documentation formats and structures
  - [ ] Refactor scraper to detect documentation type (Sphinx, MkDocs, OpenAPI)
  - [ ] Implement specialized extractors for Sphinx, MkDocs, OpenAPI/Swagger
  - [ ] Improve segmentation for navigation/code/structured content
  - [ ] Add tests for extraction and segmentation edge cases
  - [ ] Add progress notes as improvements are made
  - [ ] [Progress] 2025-04-21: Plan drafted. Will begin with adaptive extraction pipeline after vector search CLI command.

- [ ] **Caching Strategy**: Improve caching with time-based invalidation to ensure documentation stays up-to-date
- [ ] **Offline Mode**: Enhance offline capabilities to ensure reliability without internet connection
- [ ] **Documentation Filtering**: Add options to filter documentation by type (functions, modules, examples, etc.)
- [ ] **Expanded Language Support**: Ensure good support for a wide range of programming languages and their documentation styles

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
- [ ] **Authentication**: Add authentication for MCP server (if needed)
- [ ] **Extended Server Configuration**: Create additional configuration options for the MCP server
  - [ ] Add rate limiting
  - [ ] Configure caching behavior
  - [ ] Add custom response formatting
- [x] **Testing**: Develop comprehensive tests for the MCP server
  - [Progress] 2025-04-21: Comprehensive tests implemented and passing.
- [ ] **Deployment Documentation**: Document deployment options for the MCP server

## Issues Addressed

1. **Package Compatibility**: Resolved by implementing official MCP SDK with FastMCP
2. **GitHub Scraping Issues**: DocVault has difficulties scraping content from GitHub repositories.
3. **Documentation Website Scraping**: The current scraper has trouble with specialized documentation websites.
4. **Vector Search Issues**: There's a vector search issue showing "no such table: document_segments_vec" during search operations.
5. **Installation Complexity**: There are challenges with environment setup and dependency management.

## Documentation and Onboarding

- [ ] **Improved Help Messages**: Enhance command help messages with more examples and clearer descriptions
- [ ] **Quick Start Guide**: Create a quick start guide focusing on common usage patterns
- [x] **AI Integration Guide**: Created comprehensive documentation for AI assistants using DocVault via MCP (see CLAUDE.md)
- [ ] **Configuration Guide**: Create comprehensive documentation for configuration options
- [ ] **Custom Scrapers Guide**: Document how to create custom scrapers for specific documentation formats

## Additional Features

- [ ] **Documentation Health Checks**: Add feature to periodically check if cached documentation is still current
- [ ] **Resource Usage Monitoring**: Implement monitoring for storage and performance metrics
- [ ] **Intelligent Preprocessing**: Develop preprocessing options to optimize content for different use cases
- [ ] **Cross-referencing**: Implement intelligent cross-referencing between related documentation
- [ ] **Export Features**: Add ability to export documentation in various formats (PDF, Markdown, etc.)
