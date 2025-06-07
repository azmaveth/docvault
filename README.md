# DocVault

**⚠️ ALPHA SOFTWARE**: This project is currently in alpha stage (v0.7.0). While functional, it may contain bugs and undergo breaking changes. Use in production at your own risk.

A document management system with vector search and MCP integration for AI assistants.

📚 **[Quick Start Guide](docs/QUICK_START.md)** - Get up and running in 5 minutes!
📖 **[Complete User Guide](docs/USER_GUIDE.md)** - Comprehensive guide to every feature
📖 **[Documentation Index](docs/README.md)** - All guides and references

---

**CLI Command Structure Updated!**

- Canonical commands now have user-friendly aliases.
- `search` is the default command (run `dv <query>` to search).
- Library lookup is now `dv search lib <library>` or `dv search --library <library>`.
- See below for updated usage examples and troubleshooting tips.

---

## Purpose

DocVault is designed to help AI assistants and developers access up-to-date documentation for libraries, frameworks, and tools. It solves key challenges:

- Accessing documentation beyond AI training cutoff dates
- Centralizing technical documentation in a searchable format
- Providing AI agents with structured access to library documentation
- Supporting offline documentation access

## Features

- **Web Scraper**: Fetch and store documentation from URLs with smart depth control
- **Document Storage**: Store HTML and Markdown versions with version tracking
- **Vector Search**: Semantic search using document embeddings (requires Ollama)
- **Organization**: Two-tier system with Tags (attributes) and Collections (projects)
- **Section Navigation**: Hierarchical document sections with cross-references
- **MCP Server**: Expose functionality to AI assistants through Model Context Protocol
- **Library Manager**: Automatically fetch library documentation with registry support
- **Smart Caching**: Document freshness tracking with staleness indicators
- **CLI Interface**: Comprehensive command-line tool for document management
- **Security**: Input validation, secure storage, and terminal output sanitization
- **llms.txt Support**: Automatic detection and parsing of llms.txt files for AI-friendly documentation

## Installation

### Using UV (Recommended)

DocVault uses [uv](https://github.com/astral-sh/uv) as the preferred installation method for its speed and reliability. If you don't have uv installed, you can get it with:

```bash
pip install uv
# or with pipx for isolated installation
pipx install uv
```

Then clone and install DocVault:

```bash
git clone https://github.com/azmaveth/docvault.git
cd docvault

# Create virtual environment
uv venv .venv

# Install DocVault (this installs all dependencies including sqlite-vec)
uv pip install -e .

# Set up the 'dv' command for easy access
./scripts/install-dv.sh

# Initialize the database
dv init-db
```

> **Note:** The `install-dv.sh` script will help you set up the `dv` command to work directly from your terminal without environment activation or bytecode compilation messages.

### Using Traditional Pip

If you prefer, you can also use traditional pip:

```bash
git clone https://github.com/azmaveth/docvault.git
cd docvault
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Set up the 'dv' command
./scripts/install-dv.sh
```

### Setting up the `dv` Command

After installation, run the installation helper to set up easy access to the `dv` command:

```bash
./scripts/install-dv.sh
```

This script offers several options:

1. **Add an alias** to your shell configuration (recommended)
2. **Create a wrapper script** in `~/bin` or `/usr/local/bin`
3. **Show manual instructions** for custom setups

The alias method is recommended as it's the simplest and doesn't require additional files in your PATH.

### Required Packages

DocVault automatically installs all required dependencies, including:

- `sqlite-vec` - Vector search extension for SQLite
- `modelcontextprotocol` - Model Context Protocol for AI assistant integration
- Various other libraries for web scraping, document processing, etc.

## Quick Start

After installation and running `./scripts/install-dv.sh`, you can use DocVault with the `dv` command:

## Verifying Your Installation

To verify that DocVault is installed and working correctly, you can run the following test script:

```bash
#!/bin/bash

# Test basic CLI functionality
echo "Testing DocVault installation..."

# Check if dv command is available
if ! command -v dv &> /dev/null; then
    echo "❌ 'dv' command not found. Please run './scripts/install-dv.sh' to set up the command"
    exit 1
fi

# Test --version flag
echo -n "Checking version... "
dv --version

# Test database initialization
echo -n "Initializing database... "
dv init-db --force

# Test search with no documents
echo -n "Testing search (no documents yet)... "
if ! dv search "test" &> /dev/null; then
    echo "❌ Search test failed"
    exit 1
else
    echo "✅ Search working"
fi

# Test adding a test document
echo -n "Adding test document... "
TEST_URL="https://raw.githubusercontent.com/azmaveth/docvault/main/README.md"
if ! dv add "$TEST_URL" &> /dev/null; then
    echo "❌ Failed to add test document"
    exit 1
else
    echo "✅ Test document added"
fi

# Test search with the added document
echo -n "Testing search with documents... "
if ! dv search "DocVault" &> /dev/null; then
    echo "❌ Search with documents failed"
    exit 1
else
    echo "✅ Search with documents working"
fi

echo "\n🎉 All tests passed! DocVault is installed and working correctly."
echo "Try running 'dv search \"your query\"' to search your documents."
```

Save this script as `test_docvault.sh`, make it executable with `chmod +x test_docvault.sh`, and run it to verify your installation.

## Troubleshooting

### Command Not Found: `dv`

If you get a "command not found" error when running `dv`, try these solutions:

1. **Run the installation helper**

   ```bash
   ./scripts/install-dv.sh
   ```

2. **Source your shell configuration** (if you chose the alias option)

   ```bash
   source ~/.bashrc  # or ~/.zshrc for zsh users
   ```

3. **Use the direct path**

   ```bash
   /path/to/docvault/.venv/bin/dv --help
   ```

4. **Install with pipx for global access**

   ```bash
   pipx install git+https://github.com/azmaveth/docvault.git
   ```

### Database Connection Issues

If you encounter database-related errors:

1. **Check file permissions**

   ```bash
   ls -la ~/.docvault/docvault.db
   ```

2. **Rebuild the database**

   ```bash
   dv init-db --force
   ```

### Missing Dependencies

If you see import errors or missing modules:

1. **Reinstall dependencies**

   ```bash
   uv pip install -r requirements.txt
   ```

2. **Check Python version** (requires Python 3.8+)

   ```bash
   python --version
   ```

### Vector Search Not Working

If vector search fails or falls back to text search:

1. **Verify sqlite-vec installation**

   ```bash
   python -c "import sqlite_vec; print('sqlite-vec version:', sqlite_vec.__version__)"
   ```

2. **Rebuild the vector index**

   ```bash
   dv init-db --force
   ```

### Network Issues

If you experience timeouts or connection errors:

1. **Check your internet connection**
2. **Set HTTP proxy if needed**

   ```bash
   export HTTP_PROXY=http://your-proxy:port
   export HTTPS_PROXY=http://your-proxy:port
   ```

### Getting Help

If you're still having issues:

1. Check the [GitHub Issues](https://github.com/azmaveth/docvault/issues) for similar problems
2. Run with `--debug` flag for more detailed error messages:

   ```bash
   dv --debug <command>
   ```

3. Create a new issue with your error message and environment details

## Database Initialization

Before using DocVault, you need to initialize the database:

```bash
dv init-db --force
```

This will create a new SQLite database at `~/.docvault/docvault.db` with the necessary tables and vector index.

> **Note**: Use the `--force` flag to recreate the database if it already exists.

## Vector Search Setup

DocVault uses vector embeddings for semantic search. For optimal search functionality, you'll need to ensure the `sqlite-vec` extension is properly installed.

### Verifying Vector Search

To check if vector search is working:

```bash
dv search "your search query" --debug
```

If you see a warning about `sqlite-vec` not being loaded, you'll need to install it.

### Installing sqlite-vec

1. Install the Python package:

   ```bash
   pip install sqlite-vec
   ```

2. Or install from source:

   ```bash
   git clone https://github.com/asg017/sqlite-vec
   cd sqlite-vec
   make
   make loadable
   ```

3. Ensure the extension is in your `LD_LIBRARY_PATH` or provide the full path when loading.

### Common Issues

1. **Missing Extension**: If you see `sqlite-vec extension cannot be loaded`, ensure the package is installed in your Python environment.

2. **Vector Table Not Found**: If you get errors about missing vector tables, try recreating the database with `dv init-db --force`.

3. **Performance**: For large document collections, consider increasing SQLite's cache size:

   ```bash
   export SQLITE_CACHE_SIZE=1000000  # 1GB cache
   ```

4. **Text-Only Fallback**: If vector search isn't available, DocVault will automatically fall back to text search. You can force text-only search with:

   ```bash
   dv search "query" --text-only
   ```

## Adding Documents

### From a URL

To add a document from a URL:

```bash
dv add https://example.com/document
```

### From a Local File

To add a document from a local file:

```bash
dv add /path/to/document.pdf
```

### From a Directory

To add all documents from a directory:

```bash
dv add /path/to/documents/
```

1. Initialize the database (recommended for a fresh start):

```bash
dv init --force
# or using the alias
dv init-db --force
```

If you want to keep existing data, you can omit `--force`.

1. Import your first document:

```bash
dv import https://docs.python.org/3/library/sqlite3.html
# or use an alias:
dv add https://docs.python.org/3/library/sqlite3.html
dv scrape https://docs.python.org/3/library/sqlite3.html
dv fetch https://docs.python.org/3/library/sqlite3.html
```

1. Search for content (or just type your query, since 'search' is default):

```bash
dv search "sqlite connection"
# or simply
dv "sqlite connection"
# or use alias
dv find "sqlite connection"
```

1. Start the MCP server for AI assistant integration:

```bash
dv serve --transport sse
```

This will start a server at [http://127.0.0.1:8000](http://127.0.0.1:8000) that AI assistants can interact with.

## Organizing Your Documentation: Tags vs Collections

DocVault provides two powerful ways to organize your documentation:

### Tags (Descriptive Attributes)
Tags are labels that describe what a document is about. Use them for categorization and filtering.

```bash
# Add tags to documents
dv tag add 123 python async security

# Search by tags only
dv search --tags python security

# Combine text search with tags (very powerful!)
dv search "authentication" --tags python security

# List all documents with a tag
dv tag list python
```

**Good tags:** `python`, `javascript`, `authentication`, `tutorial`, `api-reference`, `deprecated`

### Collections (Project Groupings)
Collections are curated sets of documents organized for specific projects or purposes.

```bash
# Create a project collection
dv collection create "My SaaS App" --description "All docs for my startup"

# Add documents to collection
dv collection add "My SaaS App" 123 456 789

# Search within a collection
dv search authentication --collection "My SaaS App"

# View collection contents
dv collection show "My SaaS App"
```

**Good collections:** "Python Web Project", "Learning React", "Security Best Practices"

### Using Both Together
The real power comes from combining tags and collections:

```bash
# Create a collection with default tags
dv collection create "Django Project" --tags python django web

# Search for Python security docs in your project
dv search --collection "Django Project" --tags python security

# Find which collections contain a document
dv collection find 123
```

See [COLLECTIONS_VS_TAGS.md](COLLECTIONS_VS_TAGS.md) for a comprehensive guide.

### Powerful Search Combinations

DocVault's search is extremely flexible - combine text queries with any filters:

```bash
# Text search with tags
dv search "async functions" --tags python

# Search within a collection
dv search "authentication" --collection "My SaaS Project"

# Combine everything!
dv search "database models" --tags django orm --collection "Web App"

# Filter by tags only (no text query)
dv search --tags security oauth2

# Multiple tag modes
dv search "api" --tags rest graphql --tag-mode any   # Match ANY tag
dv search "api" --tags python rest --tag-mode all    # Must have ALL tags

# View results in hierarchical tree structure
dv search "database" --tree                          # Shows section hierarchy
dv search --collection "My Project" --tree           # Tree view for collection
```

### Section Hierarchy Visualization

DocVault can display search results in a hierarchical tree structure, showing how sections are organized within documents:

```bash
# Display search results as a tree
dv search "authentication" --tree

# Tree view works with all search filters
dv search "api" --tags python --tree
dv search --collection "Web App" --tree

# JSON output also supports tree format
dv search "database" --tree --format json
```

The tree view shows:
- Document structure with parent-child relationships
- Number of matches in each section
- Visual hierarchy using tree connectors (├── and └──)
- Section nesting levels

This is particularly useful for:
- Understanding document organization
- Finding related content in nearby sections
- Navigating large documentation files
- Getting an overview of where matches occur

### llms.txt Support

DocVault automatically detects and parses [llms.txt](https://llmstxt.org/) files when scraping websites. These files provide AI-friendly documentation that can be easily consumed by language models.

#### Viewing llms.txt Documents

```bash
# List all documents with llms.txt files
dv llms list

# Show llms.txt details for a specific document
dv llms show <document_id>

# Search through llms.txt resources
dv llms search "installation"
```

#### Adding llms.txt Documents

```bash
# Add a document and detect its llms.txt file
dv add https://example.com

# Add a document specifically for its llms.txt
dv llms add https://example.com/llms.txt
```

#### Exporting in llms.txt Format

```bash
# Export documents as llms.txt
dv llms export --title "My Project Docs" --output llms.txt

# Export from a specific collection
dv llms export --collection "My Project" --title "Project Documentation"

# Export documents with specific tags
dv llms export --tag python --tag api --title "Python API Docs"
```

When searching, documents with llms.txt files are marked with ✨ in the results:

```bash
dv search "documentation"
# Results show: "✨ has llms.txt" for documents with llms.txt metadata
```

## CLI Commands

### Import Dependencies from Project Files

DocVault can automatically detect and import documentation for all dependencies in your project. This works with various project types including Python, Node.js, Rust, Go, Ruby, and PHP.

```bash
# Import dependencies from the current directory
dv import-deps

# Import dependencies from a specific directory
dv import-deps /path/to/project

# Force re-import of all dependencies (even if they exist)
dv import-deps --force

# Include development dependencies (if supported by project type)
dv import-deps --include-dev

# Specify project type (auto-detected by default)
dv import-deps --project-type python

# Output results in JSON format
dv import-deps --format json
```

#### Supported Project Types

- **Python**: `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile`, `setup.cfg`
- **Node.js**: `package.json`, `yarn.lock`, `package-lock.json`
- **Rust**: `Cargo.toml`
- **Go**: `go.mod`
- **Ruby**: `Gemfile`, `Gemfile.lock`
- **PHP**: `composer.json`, `composer.lock`

## Pre-commit Hooks

To ensure code and documentation quality, DocVault uses [pre-commit](https://pre-commit.com/) hooks for Python formatting, linting, markdown linting, YAML linting, and secret detection.

### Setup

1. Install pre-commit (once per system):

   ```bash
   pip install pre-commit
   ```

1. Install the hooks (once per clone):

   ```bash
   pre-commit install
   ```

1. This will automatically run checks on staged files before each commit.
   To manually run all hooks on all files:

   ```bash
   pre-commit run --all-files
   ```

### Basic Commands

- `dv import <url>` - Import documentation from a URL (aliases: add, scrape, fetch)
- `dv remove <id1> [id2...]` - Remove documents from the vault (alias: rm)
- `dv list` - List all documents in the vault (alias: ls)
- `dv read <id>` - Read a document (alias: cat)
- `dv export <ids>` - Export multiple documents at once (e.g., `1-10`, `1,3,5`, or `all`)
- `dv search <query>` - Search documents with semantic search (alias: find, default command)
- `dv search lib <library> [--version <version>]` - Lookup and fetch library documentation
- `dv backup [destination]` - Backup the vault to a zip file
- `dv restore <file>` - Restore from a backup file (alias: import-backup)
- `dv config` - Manage configuration
- `dv init [--wipe]` - Initialize the database (alias: init-db, use `--wipe` to clear all data)
- `dv serve` - Start the MCP server
- `dv index` - Index or re-index documents for vector search
- `dv stats` - Show database statistics and health information

### Advanced Features

#### Contextual Retrieval (NEW)

DocVault now supports contextual retrieval to enhance RAG accuracy by adding context to chunks before embedding them. This technique can reduce retrieval failures by up to 49%.

```bash
# Enable contextual retrieval for new documents
dv context enable

# Check status and statistics
dv context status

# Process a document with contextual augmentation
dv context process <document_id>

# Process all documents (or only those without context)
dv context process-all [--limit 10]

# Find similar segments using metadata
dv context similar <segment_id> [--role "code_example"]

# Configure LLM settings
dv context config --provider openai --model gpt-3.5-turbo
```

Contextual retrieval works by:
1. Generating contextual descriptions for each chunk using an LLM
2. Prepending context to chunks before creating embeddings
3. Storing context as metadata for filtering and navigation
4. Enabling similarity search based on semantic roles

Supported LLM providers:
- **Ollama** (default) - Local models like llama2
- **OpenAI** - GPT-3.5/GPT-4 models
- **Anthropic** - Claude models

#### Context-Aware Documentation

DocVault can extract and display rich contextual information from documentation including usage examples, best practices, and common pitfalls:

```bash
# Show contextual information with code examples and best practices
dv read 1 --context

# Get suggestions for related functions while searching
dv search "file operations" --suggestions

# Get task-based suggestions for programming tasks
dv suggest "database queries" --task-based

# Find complementary functions (e.g., find 'close' when you know 'open')
dv suggest --complementary "open" query

# Get suggestions in JSON format for automation
dv suggest "error handling" --format json
```

#### Document Tagging and Organization

Organize your documentation with tags for better discoverability:

```bash
# Add tags to documents
dv tag add 1 "python" "database" "beginner"

# Search by tags
dv search --tags "python" "database"

# List all tags
dv tag list

# Create and manage custom tags
dv tag create "web-dev" "Web Development Resources"
```

#### Cross-References and Navigation

Navigate between related documentation sections:

```bash
# Show cross-references in a document
dv read 1 --show-refs

# Show reference graph for a document
dv ref graph 1

# Find all references to a specific topic
dv ref find "async functions"
```

#### Version Control and Updates

Track and manage documentation versions:

```bash
# Check for document updates
dv versions check 1

# List all document versions
dv versions list

# Compare different versions
dv versions compare 1 2

# Show documents that need updates
dv versions pending
```

#### Bulk Export

Export multiple documents at once in various formats:

```bash
# Export a range of documents
dv export 1-10 --output ./docs/

# Export specific documents
dv export 1,3,5,7 --format json --output ./exports/

# Export all documents
dv export all --format markdown --output ./all-docs/

# Export to a single combined file
dv export 1-5 --single-file --output ./combined.md

# Export with metadata included
dv export 1-10 --include-metadata --output ./docs-with-meta/

# Export in different formats
dv export 1-3 --format html --output ./html-docs/
dv export 1-3 --format xml --output ./xml-docs/
dv export 1-3 --format llms --output ./llms-docs/

# Export raw HTML without conversion
dv export 1 --format html --raw --output ./raw-html/
```

Supported formats:
- `markdown` (default) - Clean markdown files
- `html` - HTML files (converted to text by default, use --raw for original)
- `json` - JSON format with content and metadata
- `xml` - XML format with structured data
- `llms` - llms.txt format for AI consumption

#### Batch Operations

Process multiple documents efficiently:

```bash
# Search multiple libraries at once
dv search batch pandas numpy matplotlib --format json

# Import multiple dependencies
dv import-deps --format json
```

#### Structured Output Formats

Get machine-readable output for automation and AI integration:

```bash
# JSON output for various commands
dv list --format json
dv read 1 --format json
dv search "python" --format json
dv import https://example.com/doc --format json

# XML output where supported
dv list --format xml
dv read 1 --format xml
```

#### Document Freshness Indicators

DocVault tracks document age and displays freshness indicators to help you identify potentially outdated documentation:

```bash
# List documents with freshness indicators
dv list

# Example output:
# ID: 1  📘 Python SQLite3 Documentation  🌐 https://docs.python.org/3/library/sqlite3.html  📅 2024-01-15 ✅
# ID: 2  📘 Django ORM Guide  🌐 https://docs.djangoproject.com/orm/  📅 2023-12-01 🟡 (2 months old)
# ID: 3  📘 Flask Tutorial  🌐 https://flask.palletsprojects.com/  📅 2023-06-15 🔴 (7 months old)
```

Freshness indicators:

- **✅ Fresh** - Less than 30 days old
- **🟡 Getting stale** - 30-90 days old (may need updating)
- **🔴 Stale** - Over 90 days old (likely outdated)

Use these indicators to:

- Identify documents that may need refreshing
- Prioritize which documentation to update
- Ensure you're working with current information

To refresh stale documents:

```bash
# Re-scrape a stale document
dv add https://example.com/doc --force

# Check specific document age
dv read 3 --show-metadata
```

### Library Lookup Example

```bash
# Lookup latest version of a library
dv search lib pandas

# Lookup specific version
dv search lib tensorflow --version 2.0.0

# Alternate syntax (option flag):
dv search --library pandas
```

### Quick Add from Package Managers

DocVault provides shortcuts to quickly add documentation for packages from various package managers:

```bash
# Quick add from specific package managers
dv add-pypi requests              # Add from PyPI
dv add-npm express                # Add from npm
dv add-gem rails --version 7.0    # Add from RubyGems with version
dv add-hex phoenix                # Add from Hex (Elixir)
dv add-go gin                     # Add from Go
dv add-crates tokio               # Add from crates.io (Rust)
dv add-composer laravel           # Add from Packagist (PHP)

# Universal syntax using package manager prefix
dv add-pm pypi:requests
dv add-pm npm:@angular/core
dv add-pm rust:serde
dv add-pm php:symfony/framework-bundle

# Force re-fetch even if already exists
dv add-pypi django --force

# Get JSON output for automation
dv add-npm react --format json
```

These commands automatically:

- Find the package's documentation URL
- Scrape and store the documentation
- Add the package to the registry for future reference
- Show the document ID for immediate viewing

## Connecting DocVault to AI Assistants

### What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io) (MCP) is a standardized interface for AI assistants to interact with external tools and data sources. DocVault implements MCP to allow AI assistants to search for and retrieve documentation.

### Starting the MCP Server

DocVault supports two transport methods:

1. **stdio** - Used when running DocVault directly from an AI assistant
2. **SSE (Server-Sent Events)** - Used when running DocVault as a standalone server

#### Option 1: Using stdio Transport (Recommended for Claude Desktop)

For Claude Desktop, use stdio transport which is the most secure option and recommended by the MCP specification. Claude Desktop will launch DocVault as a subprocess and communicate directly with it:

1. In Claude Desktop, navigate to Settings > External Tools
2. Click "Add Tool"
3. Fill in the form:
   - **Name**: DocVault
   - **Description**: Documentation search and retrieval tool
   - **Command**: The full path to your DocVault executable, e.g., `/usr/local/bin/dv` or the full path to your Python executable plus the path to the DocVault script
   - **Arguments**: `serve`

This will start DocVault in stdio mode, where Claude Desktop will send commands directly to DocVault's stdin and receive responses from stdout.

### Claude Desktop Configuration Example

You can configure DocVault in Claude Desktop by adding it to your configuration file. Here's a JSON example you can copy and paste:

```bashjson
{
  "mcpServers": {
    "docvault": {
      "command": "dv",
      "args": ["serve"]
    }
  }
}
```bash

> **Note:** If `dv` is not in your PATH, you need to use the full path to the executable, e.g.:
> ```bashjson
> {
>   "mcpServers": {
>     "docvault": {
>       "command": "/usr/local/bin/dv",
>       "args": ["serve"]
>     }
>   }
> }
> ```bash
> You can find the full path by running `which dv` in your terminal.

#### Option 2: Using SSE Transport (For Web-Based AI Assistants)

For web-based AI assistants or when you want to run DocVault as a persistent server:

1. Start the DocVault MCP server with SSE transport:
   ```bashbash
   dv serve --transport sse --host 127.0.0.1 --port 8000
   ```bash

2. The server will start on the specified host and port (defaults to 127.0.0.1:8000).

3. For AI assistants that support connecting to MCP servers via SSE:
   - Configure the MCP client with the URL: `http://127.0.0.1:8000`
   - The AI assistant will connect to the SSE endpoint and receive the message endpoint in the initial handshake

> **Security Note**: When using SSE transport, bind to localhost (127.0.0.1) to prevent external access to your DocVault server. The MCP protocol recommends stdio transport for desktop applications due to potential security concerns with network-accessible endpoints.

### Example: Using DocVault with mcp-inspector

For testing and debugging, you can use the [mcp-inspector](https://github.com/modelcontextprotocol/inspector) tool:

1. Start DocVault with SSE transport:
   ```bashbash
   dv serve --transport sse
   ```bash

2. Install and run mcp-inspector:
   ```bashbash
   npx @modelcontextprotocol/inspector
   ```bash

3. In the inspector interface, connect to `http://localhost:8000`

4. You'll be able to explore available tools, resources, and test interactions with your DocVault server.

## Document Sections

DocVault now supports hierarchical document sections, making it easier to navigate and reference specific parts of your documents. This feature is particularly useful for large documentation sets.

### Key Features

- **Section Hierarchy**: Documents are automatically divided into sections with parent-child relationships
- **Automatic Section Detection**: Headings (h1, h2, etc.) are automatically detected and used to create the section structure
- **Section Metadata**: Each section includes:
  - Title
  - Level (1-6, corresponding to HTML heading levels)
  - Path (e.g., "1.2.3" for the third subsection of the second section)
  - Parent section reference

### Using Sections in Queries

When searching documents, you can now include section information in your results:

```python
# Get all sections for a document
sections = get_document_sections(document_id)

# Each section includes:
# - id: Unique identifier
# - document_id: Parent document ID
# - section_title: The section title
# - section_level: The heading level (1-6)
# - section_path: The hierarchical path (e.g., "1.2.3")
# - parent_segment_id: ID of the parent section (None for top-level sections)
```

### Database Schema

The section information is stored in the `document_segments` table with these additional columns:

- `section_title`: The title of the section (usually from the heading text)
- `section_level`: The heading level (1-6)
- `section_path`: A path-like string representing the section's position in the hierarchy
- `parent_segment_id`: Foreign key to the parent segment (for nested sections)

## Available MCP Tools

DocVault exposes the following tools via MCP:

- `scrape_document` - Add documentation from a URL to the vault
- `search_documents` - Search documents using semantic search
- `read_document` - Retrieve document content
- `lookup_library_docs` - Get documentation for a library
- `list_documents` - List available documents

For detailed instructions for AI assistants using DocVault, see [CLAUDE.md](CLAUDE.md).

## Known Limitations and Troubleshooting

- **Vector Search Issues**: If you encounter "no such table: document_segments_vec" errors, run `dv index` to rebuild the search index.
- **GitHub Scraping**: DocVault may have difficulty scraping GitHub repositories. Try using specific documentation URLs instead of repository root URLs.
- **Documentation Websites**: Some documentation websites with complex structures may not be scraped correctly. Try adjusting the depth parameter (`--depth`).
- **Embedding Model**: The default embedding model is `nomic-embed-text` via Ollama. Ensure Ollama is running and has this model available.
- **dv command not found**: If `dv` is not recognized, use `uv run dv` or run `./scripts/install-dv.sh` to set up the command. Some shells may require you to activate your virtual environment. See troubleshooting above.
- **Failed to fetch URL**: If you see errors like 'Failed to fetch URL' when adding documents, verify the URL is accessible and check your network connection. Some sites may block automated scraping.

## Requirements

- Python 3.12+
- Ollama for embeddings (using `nomic-embed-text` model by default)

## Configuration

DocVault can be configured using environment variables or a `.env` file in `~/.docvault/`:

```bash
dv config --init
```

This will create a `.env` file with default settings. You can then edit this file to customize DocVault.

Available configuration options include:

- `DOCVAULT_DB_PATH` - Path to SQLite database
- `BRAVE_SEARCH_API_KEY` - API key for Brave Search (optional)
- `OLLAMA_URL` - URL for Ollama API
- `EMBEDDING_MODEL` - Embedding model to use
- `STORAGE_PATH` - Path for document storage
- `HOST` - MCP server host (for SSE/web mode, required by Uvicorn)
- `PORT` - MCP server port (for SSE/web mode, required by Uvicorn)
- `SERVER_HOST` - [legacy/stdio mode only] MCP server host (not used by Uvicorn)
- `SERVER_PORT` - [legacy/stdio mode only] MCP server port (not used by Uvicorn)
- `LOG_LEVEL` - Logging level (INFO, DEBUG, etc.)

For a comprehensive guide on all configuration options including security settings, rate limiting, and advanced configurations, see [CONFIGURATION.md](CONFIGURATION.md).

## Development

We welcome contributions to DocVault! Check out the [TASKS.md](TASKS.md) file for planned improvements and tasks you can help with.

We provide a convenient script to set up a development environment using UV:

```bash
# Make the script executable if needed
chmod +x scripts/dev-setup.sh

# Run the setup script
./scripts/dev-setup.sh
```

This script creates a virtual environment, installs dependencies with UV, and checks for the sqlite-vec extension.

### Running Tests

DocVault includes a comprehensive test suite. You can run tests using the provided test runner script or make commands:

```bash
# Run all tests
./scripts/run-tests.sh
# or
make test

# Run specific test suites
./scripts/run-tests.sh unit      # Unit tests only
./scripts/run-tests.sh cli       # CLI tests only
./scripts/run-tests.sh mcp       # MCP server tests only
./scripts/run-tests.sh quick     # Quick smoke tests

# Run with coverage
./scripts/run-tests.sh -c all
# or
make test-coverage

# Run with verbose output
./scripts/run-tests.sh -v all

# See all options
./scripts/run-tests.sh --help
```

### Code Quality

```bash
# Run linting
make lint

# Format code
make format
```

### Continuous Integration

DocVault uses GitHub Actions for CI/CD. Tests are automatically run on:

- Push to main/master/develop branches
- Pull requests
- Multiple OS (Ubuntu, macOS, Windows)
- Multiple Python versions (3.11, 3.12)

## Version Management

### Current Version

DocVault is at version 0.7.0 (Alpha). See [CHANGELOG.md](CHANGELOG.md) for version history.

### Versioning Policy

We follow [Semantic Versioning](https://semver.org/):

- MAJOR.MINOR.PATCH (e.g., 0.5.0)
- Breaking changes bump MAJOR (after 1.0.0)
- New features bump MINOR
- Bug fixes bump PATCH

### Contributing

When contributing:

1. Update version in `docvault/version.py`
2. Document changes in CHANGELOG.md
3. Follow conventional commit format
4. Run full test suite before submitting

## Documentation

All project documentation is organized in the `docs/` directory for easy access and maintenance:

### User Documentation

- **[Quick Start Guide](docs/QUICK_START.md)** - Get up and running in 5 minutes
- **[User Guide](docs/USER_GUIDE.md)** - Comprehensive guide covering all features
- **[Configuration Guide](docs/CONFIGURATION.md)** - Detailed configuration options and examples

### Feature Guides

- **[Collections vs Tags](docs/COLLECTIONS_VS_TAGS.md)** - Understanding DocVault's organization system
- **[AI Assistant Instructions](docs/CLAUDE.md)** - Guide for AI assistants using DocVault

### Development Documentation

- **[Project Rules](docs/PROJECT_RULES.md)** - Development standards and practices
- **[Tasks](docs/TASKS.md)** - Current roadmap and task tracking
- **[Version Management](docs/VERSION_MANAGEMENT.md)** - Versioning policies and procedures
- **[Threat Model](docs/THREAT_MODEL.md)** - Security considerations and mitigations

### Documentation Index

- **[Documentation Overview](docs/README.md)** - Complete index of all documentation

> **Note for Automated Tools**: The `CLAUDE.md` and `TASKS.md` files are maintained in the project root directory for easy access by AI assistants and automation tools, while the rest of the documentation is organized in the `docs/` directory.

## License

MIT
