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
- **MCP Server**: Expose functionality to AI assistants through Model Context Protocol
- **Library Manager**: Automatically fetch library documentation
- **CLI Interface**: Command-line tool for document management

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
dv init-db --wipe
```bash

> **Note:** The `--wipe` flag will clear all existing data and fully reset the database. Use this if you want to start fresh or if you encounter issues with old or corrupted data.

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

1. Initialize the database (recommended for a fresh start):

```bash
dv init --wipe
# or using the alias
dv init-db --wipe
```

If you want to keep existing data, you can omit `--wipe`.

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
