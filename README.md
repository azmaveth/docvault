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
uv pip install -e .
```

### Using Traditional Pip

If you prefer, you can also use traditional pip:

```bash
git clone https://github.com/azmaveth/docvault.git
cd docvault
pip install -e .
```

### Required Extension

Ensure you have the sqlite-vec extension installed:
https://github.com/asg017/sqlite-vec

## Quick Start

Once installed, you can run DocVault directly using the `dv` command:

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
- `dv search <query>` - Search documents
- `dv read <id>` - Read a document (markdown or HTML)
- `dv list` - List all documents
- `dv lookup <library_name> [--version <version>]` - Lookup and fetch documentation for a library
- `dv config` - Manage configuration
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
- sqlite-vec extension
- Ollama for embeddings
- MCP SDK
- UV (recommended)

## Configuration

DocVault can be configured using environment variables or a `.env` file in `~/.docvault/`:

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
# Build the package
uv build

# Publish to TestPyPI first (recommended)
uv publish --repository testpypi

# Publish to PyPI
uv publish
```

## License

MIT
