# DocVault

A document management system with vector search and MCP integration for AI assistants.

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

- **Web Scraper**: Fetch and store documentation from URLs
- **Document Storage**: Store HTML and Markdown versions
- **Vector Search**: Semantic search using document embeddings
- **Section Navigation**: Hierarchical document sections with parent-child relationships
- **MCP Server**: Expose functionality to AI assistants through Model Context Protocol
- **Library Manager**: Automatically fetch library documentation
- **CLI Interface**: Command-line tool for document management
- **Database Migrations**: Automatic schema updates with versioning

## Installation

### Using UV (Recommended)

DocVault uses [uv](https://github.com/astral-sh/uv) as the preferred installation method for its speed and reliability. If you don't have uv installed, you can get it with:

```bashbash
pip install uv
# or with pipx for isolated installation
pipx install uv
```bash

Then clone and install DocVault:

```bashbash
git clone https://github.com/azmaveth/docvault.git
cd docvault

# Create virtual environment
uv venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install in development mode (runtime deps + sqlite‑vec)
uv pip install -e .

# Or simply install the package
uv pip install .

# Initialise the database (sets up vector tables)
dv init-db --force
```bash

> **Note:** The `--force` flag will clear all existing data and fully reset the database. Use this if you want to start fresh or if you encounter issues with old or corrupted data.

### Using Traditional Pip

If you prefer, you can also use traditional pip:

```bashbash
git clone https://github.com/azmaveth/docvault.git
cd docvault
python -m venv .venv
source .venv/bin/activate
pip install -e .
```bash

### Required Packages

DocVault automatically installs all required dependencies, including:

- `sqlite-vec` - Vector search extension for SQLite
- `modelcontextprotocol` - Model Context Protocol for AI assistant integration
- Various other libraries for web scraping, document processing, etc.

## Quick Start

Once installed, you can run DocVault directly using the `dv` command:

> **Note:** When installing DocVault with pip or UV, the `dv` script will be automatically installed to your PATH. If using from a git clone without installing, you can either:
> 1. Run `./scripts/dv` from the project directory
> 2. Use `uv run dv` which will use the UV dependency resolver
> 3. Copy `scripts/dv` to a location in your PATH

## Verifying Your Installation

To verify that DocVault is installed and working correctly, you can run the following test script:

```bash
#!/bin/bash

# Test basic CLI functionality
echo "Testing DocVault installation..."

# Check if dv command is available
if ! command -v dv &> /dev/null; then
    echo "❌ 'dv' command not found. Make sure to add it to your PATH or use './scripts/dv'"
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

1. **Activate the virtual environment**

   ```bash
   source .venv/bin/activate  # On Unix/macOS
   .venv\Scripts\activate    # On Windows
   ```

2. **Use the full path**

   ```bash
   # From the project root
   ./scripts/dv --help
   ```

3. **Install with pipx for global access**

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

### Running with UV

You can also run DocVault directly with UV without installation:

```bash
./dv add https://docs.python.org/3/
# or
uv run dv add https://docs.python.org/3/
```

All configuration is automatically managed in `~/.docvault/`.
To customize settings, run:

```bash
Then edit the `.env` file in `~/.docvault/`.

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

- `dv import <url>` - Import documentation from a URL (aliases: add, scrape, fetch)
- `dv remove <id1> [id2...]` - Remove documents from the vault (alias: rm)
- `dv list` - List all documents in the vault (alias: ls)
- `dv read <id>` - Read a document (alias: cat)
- `dv search <query>` - Search documents with semantic search (alias: find, default command)
- `dv search lib <library> [--version <version>]` - Lookup and fetch library documentation
- `dv backup [destination]` - Backup the vault to a zip file
- `dv import-backup <file>` - Import a backup file
- `dv config` - Manage configuration
- `dv init [--wipe]` - Initialize the database (alias: init-db, use `--wipe` to clear all data)
- `dv serve` - Start the MCP server
- `dv index` - Index or re-index documents for vector search

### Library Lookup Example

```bash
# Lookup latest version of a library
dv search lib pandas

# Lookup specific version
dv search lib tensorflow --version 2.0.0

# Alternate syntax (option flag):
dv search --library pandas
```## Connecting DocVault to AI Assistants

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
- **dv command not found**: If `dv` is not recognized, use `uv run dv` or run `./scripts/dv` from the project directory. Some shells may require you to activate your virtual environment, or add the scripts directory to your PATH. See troubleshooting above.
- **Failed to fetch URL**: If you see errors like 'Failed to fetch URL' when adding documents, verify the URL is accessible and check your network connection. Some sites may block automated scraping.

## Requirements

- Python 3.12+
- Ollama for embeddings (using `nomic-embed-text` model by default)

## Configuration

DocVault can be configured using environment variables or a `.env` file in `~/.docvault/`:

```bashbash
dv config --init
```bash

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

## Development

We welcome contributions to DocVault! Check out the [TASKS.md](TASKS.md) file for planned improvements and tasks you can help with.

We provide a convenient script to set up a development environment using UV:

```bashbash
# Make the script executable if needed
chmod +x scripts/dev-setup.sh

# Run the setup script
./scripts/dev-setup.sh
```bash

This script creates a virtual environment, installs dependencies with UV, and checks for the sqlite-vec extension.

## License

MIT
