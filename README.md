# DocVault

A document management system with vector search and MCP integration for AI assistants.

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
- **MCP Server**: Expose functionality to AI assistants through Model Context Protocol
- **Library Manager**: Automatically fetch library documentation
- **CLI Interface**: Command-line tool for document management

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

# Install in development mode
uv pip install -e .

# Or simply install the package
uv pip install .
```

### Using Traditional Pip

If you prefer, you can also use traditional pip:

```bash
git clone https://github.com/azmaveth/docvault.git
cd docvault
pip install -e .
```

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

1. Initialize the database:
   ```bash
   dv init-db
   ```

2. Add your first document:
   ```bash
   dv add https://docs.python.org/3/library/sqlite3.html
   ```

3. Search for content:
   ```bash
   dv search "sqlite connection"
   ```

4. Start the MCP server for AI assistant integration:
   ```bash
   dv serve --transport sse
   ```
   This will start a server at http://127.0.0.1:8000 that AI assistants can interact with.

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
dv config --init
```
Then edit the `.env` file in `~/.docvault/`.

## CLI Commands

- `dv add <url>` - Scrape and store a document (supports `--depth` parameter)
- `dv rm <id1> [id2...]` - Delete documents from the vault
- `dv search <query>` - Search documents with semantic search
- `dv read <id>` - Read a document (markdown or HTML)
- `dv list` - List all documents in the vault
- `dv lookup <library_name> [--version <version>]` - Lookup and fetch library documentation
- `dv backup [destination]` - Backup the vault to a zip file
- `dv import-backup <file>` - Import a backup file
- `dv config` - Manage configuration
- `dv init-db` - Initialize or reset the database
- `dv serve` - Start the MCP server
- `dv index` - Index or re-index documents for vector search

### Library Lookup Example

```bash
# Lookup latest version of a library
dv lookup pandas

# Lookup specific version
dv lookup tensorflow --version 2.0.0
```

## AI Integration via MCP

DocVault integrates with AI assistants through the [Model Context Protocol](https://modelcontextprotocol.io) (MCP). This allows AI assistants to directly access documentation through a standardized interface.

### Starting the MCP Server

```bash
dv serve --transport sse
```

This starts a server at http://127.0.0.1:8000 (configurable) that exposes DocVault functionality to AI assistants.

### Available MCP Tools

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
- `SERVER_HOST` - MCP server host
- `SERVER_PORT` - MCP server port
- `LOG_LEVEL` - Logging level (INFO, DEBUG, etc.)

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

## License

MIT
