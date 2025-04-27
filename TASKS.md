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

- [x] **CLI canonical/alias refactor**: Refactored CLI to use canonical command names with user-friendly aliases (import, remove, list, read, search, etc.). [2025-04-22]
- [ ] **CLI additional commands refactor**: Refactor CLI to use restore instead of import-backup, then add _cmd suffix to backup and restore commands in docvault.cli.commands
- [x] **Search/lookup merge**: Merged `lookup` into `search` as a subcommand and updated all references. [2025-04-22]
- [x] **Default command**: Made `search` the default command when no subcommand is provided. [2025-04-22]
- [x] **CLI help/docs update**: Updated help strings and documentation to reflect new commands, aliases, and usage. [2025-04-22]
- [x] **Test/README update**: Updated all CLI tests and README to match new command structure and aliasing. [2025-04-22]
- [x] **Troubleshooting guidance**: Added troubleshooting notes for dv command availability and alternative invocation methods (e.g., `uv run dv`). [2025-04-22]
- [ ] **Fix README instructions for database initialization**: The README instructs users to run `dv init-db --wipe`, but the `--wipe` option does not exist. Update the README to remove or correct this flag. *(Superseded by CLI refactor: see above tasks)*
- [ ] **Clarify dv command availability**: The `dv` command may not be available in the PATH after installation, depending on how DocVault is installed. The README should emphasize alternative invocation methods (`uv run dv`, `./scripts/dv`) and troubleshooting tips for command-not-found issues. *(Superseded by troubleshooting guidance above)*
- [ ] **Improve error feedback for add command**: When adding a document with `dv add <url>`, a generic "Failed to fetch URL" error is shown. Add more descriptive error messages (e.g., network issues, unsupported site, authentication required) and suggest next steps.
- [ ] **Vector search setup guidance**: If vector search fails due to missing tables or extensions, provide actionable guidance (e.g., how to install sqlite-vec, how to rebuild the index) directly in the CLI output.
- [ ] **AI/Automation-friendly CLI**: Add structured output options (e.g., `--format json`) for all commands to make parsing by AI agents and automation tools easier. Ensure all error messages are machine-readable as well as human-friendly.
- [ ] **Installation troubleshooting section**: Add a section to the README for common installation issues and their solutions, especially for virtual environments, dependency problems, and OS-specific quirks.
- [ ] **Quick test script**: Provide a script or command sequence in the README for users (and AIs) to verify that DocVault is installed and functioning correctly after setup.

- [ ] **Search Results Improvements**:
  - [x] Enhance search result previews to show more complete context instead of truncated snippets [2025-04-27]
  - [x] Add keyword highlighting in search results to quickly identify matched terms [2025-04-27]
  - [ ] Implement navigation aids to jump to specific sections within retrieved documents
  - [ ] Add pagination for search results with many matches
  - [ ] Provide options to filter and refine search results

- [ ] **Document Navigation and Structure**:
  - [ ] Add ability to navigate between related sections in retrieved documents
  - [ ] Better preserve document structure when rendering in different formats
  - [ ] Implement a "related content" suggestion feature based on current viewing history
  - [ ] Add document history tracking to easily return to previously viewed documents

- [ ] **Metadata Utilization**:
  - [ ] Improve integration of document metadata into search functionality
  - [ ] Display document timestamps and version information in results
  - [ ] Add metadata-based filtering options (e.g., by date, source, type)

- [ ] **Official Docs Registry**: Maintain local references to official documentation URLs for libraries, frameworks, and APIs (e.g., Hexdocs for Elixir, PyPI for Python). Automatically update registry as new docs are discovered.
- [ ] **Interactive Mode**: Add an interactive shell mode where users can navigate documentation with keyboard shortcuts
- [ ] **Documentation Comparison**: Add features to compare different versions of the same library to identify changes
- [ ] **Better Discovery**: Implement a recommendation system that suggests related libraries or frameworks
- [ ] **Integration with Development Environments**: Create plugins for popular IDEs to access documentation directly from the editor
- [ ] **Import from Project Files**: Add ability to scan project files (package.json, mix.exs, requirements.txt, etc.) to fetch documentation for all dependencies automatically
- [ ] **User-Friendly Installation**: Simplify the installation process and dependencies

## Suggestions to Improve the Utility of docvault for Coding

1. **Context-Aware Searching and Tagging**
   - [ ] Allow tagging documents with keywords related to specific projects or libraries (e.g., "pygame", "networking", "GUI").
   - [ ] Enable searching within specific tags or categories to quickly find relevant documentation.

2. **Incremental and Sectioned Storage**
   - [ ] Support scraping and storing only specific sections or pages of documentation rather than entire documents.
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
   - [ ] Allow splitting large documents into smaller, manageable sections for easier recall.
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
   - [ ] Provide automatic summaries or key points from stored documents for quick reference.
     - **Prompt for Summarizing While Preserving Code Snippets:**
       - Sample prompt:
         > "Summarize the following documentation content, highlighting key points and features. Ensure all code snippets and examples are included verbatim and are easily accessible. Present the summary in a clear, concise format."
     - Additional tips:
       - Tag code snippets with their relevant functions or classes.
       - Keep a boolean option to include/exclude code snippets depending on needs.
   - [ ] Highlight relevant code snippets or function explanations based on queries.

4. **Deep Linking and Cross-References**
   - [ ] Enable creating links between related document sections, so I can easily navigate through interconnected concepts.
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
   - [ ] Automatically update stored docs when newer versions are available.
   - [ ] Keep track of different versions of documentation for comparison.

6. **Recall with Context and Usage Examples**
   - [ ] When recalling documentation, include usage examples, common pitfalls, and best practices.
   - [ ] Suggest relevant functions, classes, or modules based on the current task.

7. **Automatic Context Building for Projects**
   - [ ] When starting a new project, scrape and store related docs automatically based on project goals or libraries.
   - [ ] Build a comprehensive, interconnected knowledge graph of docs and features.

## Technical Improvements

- [ ] **Document Update-on-Add & Timestamps**: When `dv add <url>` is run on a URL that already exists, update all existing data for that document (re-scrape and overwrite). Ensure the database has a timestamp for each document addition/update and display the date when viewing stored documents.

- [ ] **Comprehensive Logging**: Ensure proper logging is implemented throughout the app. All major operations and failures should log error, warning, and info messages as appropriate, so that users and developers can easily diagnose issues. Replace console.print() with logging.
- [ ] **SQLi prevention**: Implement SQL injection prevention measures in database queries. Use SQLAlchemy library to parameterize queries.
- [ ] **Test dv command on fresh installs**: Ensure the `dv` command is always installed to PATH or provide a reliable fallback method for all supported OSes and shells.
- [ ] **Automated CLI testing**: Implement automated tests or a test harness for the CLI to catch issues like missing options or broken commands after updates.
- [ ] **Improve CLI help output**: Ensure `dv --help` and subcommand help texts are comprehensive and up-to-date, including all options and usage examples.

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

- [ ] **Scraping Depth Control Enhancements**:
  - [ ] Improve documentation of the "depth" parameter for scraping to clearly explain its purpose and impact
  - [ ] Add examples of different depth settings and their effects in the CLI help
  - [ ] Implement smart depth detection that adjusts based on site structure

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

## CLI UX Review & Recommendations

### General Observations

- The CLI is logically organized, with clear commands for core actions (add, list, search, read, etc.).
- Help output is concise and readable.
- Most commands use positional arguments for primary targets (e.g., URL, DOCUMENT_ID), which is good.
- Some commands have inconsistent flag/argument naming or could be made more user-friendly.
- Some command names and argument conventions could be improved for discoverability and clarity.

### Detailed Suggestions

#### 1. Command Naming & Structure

- [x] **`list`**: Aliased as both `list` and `ls`. [2025-04-22]
- [ ] Add a `--long` or `-l` flag for more detailed output (future improvement).
- [x] **`add`**: Now canonical as `import` with aliases `add`, `scrape`, `fetch`. [2025-04-22]
- [ ] Allow multiple URLs at once (future improvement).
- [x] **`rm`**: Now canonical as `remove` with alias `rm`. [2025-04-22]
- [x] **`lookup`**: Merged into `search` as `search lib` and `search --library`. [2025-04-22]
- [x] **`read`**: Aliased as both `read` and `cat`. [2025-04-22]
- [x] **`search`**: Canonical, with alias `find`. Now the default command if no subcommand is given. [2025-04-22]
- [x] **`init-db`**: Now canonical as `init` with alias `init-db`. [2025-04-22]
- [x] **`serve`**: Canonical, help text clarified for MCP server. [2025-04-22]

#### 2. Flags & Arguments

- [x] Used consistent flag naming: `--force`, `--format`, etc. [2025-04-22]
- [ ] Add both positive and negative forms for boolean flags (future improvement).
- [ ] Standardize `--format` and add `--json` shortcut across all commands (future improvement).
- [x] ID ranges and comma-separated lists supported in `remove` (rm), and partially elsewhere. [2025-04-22]
- [ ] Expand ID range/list support to all relevant commands (future improvement).

#### 3. Help & Examples

- [x] Updated help output for all commands to reflect new names, aliases, and usage. [2025-04-22]
- [ ] Add more detailed usage examples to each command's help output (future improvement).
- For `add`, show example with depth, max-links, and strict-path.
- For `search`, show both embedding and text-only examples.
- For `rm`, clarify ID range syntax in help.

#### 4. User Experience

- On errors, suggest next steps (e.g., "Try `dv list` to see available documents").
- Support tab completion (if not already).
- Print summary tables in a more compact format by default; use `--long` for full details.
- For interactive commands (like `rm`), support `--yes` or `-y` to skip confirmation.

#### 5. Advanced Suggestions

- Add a `help` subcommand: `dv help <command>`.
- Support config profiles: `dv config --profile <n>`.
- Add a `status` command to show DB health, number of docs, etc.
- Allow piping and redirection for output (e.g., `dv search ... | jq`).

### Example of Improved Command Set

```markdown
 dv add <url> [--depth N] [--max-links N] [--no-strict-path] [--quiet]
 dv import-backup <file>
 dv backup [destination]
 dv list [--filter <query>] [--long] [--format <fmt>]
 dv search <query> [--limit N] [--text-only] [--format <fmt>]
 dv doc <library> [--version <ver>]
 dv read <doc_id> [--format <fmt>]
 dv rm <ids> [--force]
 dv init [--force]
 dv serve [--host H] [--port P] [--transport <type>]
 dv status
```

---

### [ ] CLI UX Improvements

- Review and refactor command names and aliases for clarity and consistency.
- Standardize flag names and output formatting options.
- Expand help and usage examples for all commands.
- Add support for batch operations, more flexible ID input, and improved error messages.
- Consider adding new commands for status and help.
