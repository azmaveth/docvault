# DocVault

A document management system with vector search and MCP integration for LLMs.

## Features

- **Web Scraper**: Fetch and store documentation from URLs
- **Document Storage**: Store HTML and Markdown versions
- **Vector Search**: Semantic search using document embeddings
- **MCP Server**: Expose functionality to LLMs
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
- `mcp` - Model Context Protocol for LLM integration
- Various other libraries for web scraping, document processing, etc.

## Quick Start

Once installed, you can run DocVault directly using the `dv` command:

> **Note:** When installing DocVault with pip or UV, the `dv` script will be automatically installed to your PATH. If using from a git clone without installing, you can either:
> 1. Run `./scripts/dv` from the project directory
> 2. Use `uv run dv` which will use the UV dependency resolver
> 3. Copy `scripts/dv` to a location in your PATH
>
> The first time you run DocVault commands, you may see a message like "Bytecode compiled X files in XXXms". This is normal behavior as Python compiles dependencies to improve performance. This only happens once after installation and will be much faster on subsequent runs.

1. Initialize the database:
   ```bash
   dv init-db
   ```

2. Scrape your first document:
   ```bash
   dv scrape https://docs.python.org/3/library/sqlite3.html
   ```

3. Search for content:
   ```bash
   dv search "sqlite connection"
   ```

4. Start the MCP server for LLM integration:
   ```bash
   dv serve
   ```

### Running with UV

You can also run DocVault directly with UV without installation:

```bash
./dv scrape https://docs.python.org/3/
# or
uv run dv scrape https://docs.python.org/3/
```

This uses UV's dependency resolution while running the script.

All configuration is automatically managed in `~/.docvault/`. 
To customize settings, run:
```bash
dv config --init
```
Then edit the `.env` file in `~/.docvault/`.

## CLI Commands

- `dv scrape <url>` - Scrape and store a document
- `dv add <url>` - Alias for scrape
- `dv delete <id1> [id2...]` - Delete documents from the vault
- `dv search <query>` - Search documents with semantic search
- `dv read <id>` - Read a document (markdown or HTML)
- `dv list` - List all documents in the vault
- `dv lookup <library_name> [--version <version>]` - Lookup and fetch library documentation
- `dv backup [destination]` - Backup the vault to a zip file
- `dv import-backup <file>` - Import a backup file
- `dv config` - Manage configuration
- `dv init-db` - Initialize or reset the database
- `dv serve` - Start the MCP server

### Library Lookup Example

```bash
# Lookup latest version of a library
dv lookup pandas

# Lookup specific version
dv lookup tensorflow --version 2.0.0
```

## MCP Tools for LLMs

- `scrape_document` - Scrape a document from a URL
- `search_documents` - Search documents using semantic search
- `read_document` - Retrieve document content
- `lookup_library_docs` - Get documentation for a library
- `list_documents` - List available documents

## Requirements

- Python 3.12+
- Ollama for embeddings (using `nomic-embed-text` model by default)

## Configuration

DocVault can be configured using environment variables or a `.env` file in `~/.docvault/`:

```bash
dv config --init
```

This will create a `.env` file with default settings. You can then edit this file to customize DocVault.

Alternatively, you can copy the included `.env.example` file to your DocVault directory:

```bash
cp .env.example ~/.docvault/.env
```

Available configuration options include:

- `DOCVAULT_DB_PATH` - Path to SQLite database
- `BRAVE_SEARCH_API_KEY` - API key for Brave Search (optional)
- `OLLAMA_URL` - URL for Ollama API
- `EMBEDDING_MODEL` - Embedding model to use
- `STORAGE_PATH` - Path for document storage
- `SERVER_HOST` - MCP server host
- `SERVER_PORT` - MCP server port

## Development

We provide a convenient script to set up a development environment using UV:

```bash
# Make the script executable if needed
chmod +x scripts/dev-setup.sh

# Run the setup script
./scripts/dev-setup.sh
```

This script creates a virtual environment, installs dependencies with UV, and checks for the sqlite-vec extension.

## Publishing to PyPI

To build and publish DocVault to PyPI:

```bash
# Install build dependencies
pip install build twine

# Build the package
python -m build

# Publish to TestPyPI first (recommended)
twine upload --repository testpypi dist/*

# Publish to PyPI
twine upload dist/*
```

## License

MIT
