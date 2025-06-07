# DocVault Complete User Guide

A comprehensive guide to every feature in DocVault - your personal documentation vault.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Core Features](#core-features)
3. [Document Management](#document-management)
4. [Search and Discovery](#search-and-discovery)
5. [Organization Features](#organization-features)
6. [Package Manager Integration](#package-manager-integration)
7. [Document Freshness and Caching](#document-freshness-and-caching)
8. [Advanced Features](#advanced-features)
9. [AI Integration](#ai-integration)
10. [Backup and Maintenance](#backup-and-maintenance)
11. [Security Features](#security-features)
12. [Tips and Best Practices](#tips-and-best-practices)

## Getting Started

### What is DocVault?

DocVault is a command-line tool that helps developers and AI assistants access and manage technical documentation. It creates a local, searchable vault of documentation that you can query instantly.

### Core Benefits

- 🔍 **Instant Search**: Find information across all your documentation in seconds
- 📚 **Centralized Storage**: Keep all your docs in one place
- 🏷️ **Smart Organization**: Use tags and collections to organize docs by project or topic
- 🤖 **AI-Ready**: Integrates with AI assistants via Model Context Protocol (MCP)
- 📦 **Package Integration**: Automatically add docs for your project dependencies
- ⚡ **Offline Access**: Works without internet once docs are stored

### Installation Quick Reference

```bash
# Using pip (recommended)
pip install docvault

# Initialize
dv init

# Verify
dv version
```

For detailed installation instructions, see [QUICK_START.md](QUICK_START.md).

## Core Features

### 1. Adding Documentation

#### Basic URL Import

Add documentation from any URL:

```bash
# Add from URL
dv add https://docs.python.org/3/
dv import https://fastapi.tiangolo.com/  # Same as 'add'

# Add with custom depth
dv add https://docs.django.com/ --depth 3

# Force update existing document
dv add https://docs.python.org/3/ --update
```

**Options:**
- `--depth <number>`: How deep to scrape (default: auto-detected)
- `--update`: Update if document already exists
- `--format json`: Get machine-readable output

#### Smart Depth Detection

DocVault automatically analyzes sites to determine optimal scraping depth:

```bash
# Auto-detect depth (recommended)
dv add https://docs.python.org/3/

# Manual depth control
dv add https://large-site.com/ --depth 2    # Shallow
dv add https://small-site.com/ --depth 5    # Deep
```

#### Project Dependencies

Automatically add documentation for all your project's dependencies:

```bash
# Scan current directory for package files
dv import-deps
dv deps  # Shorthand

# Scan specific directory
dv import-deps /path/to/project

# Show what would be imported without doing it
dv import-deps --dry-run

# Import only specific package managers
dv import-deps --include pypi npm
```

Supports: `package.json`, `requirements.txt`, `Pipfile`, `pyproject.toml`, `mix.exs`, `Cargo.toml`, `go.mod`, `composer.json`

### 2. Searching Documentation

#### Basic Search

```bash
# Simple search (default command)
dv search "async programming"
dv "async programming"  # Shorthand

# Search with more results
dv search "database connection" --limit 10

# Search in specific format
dv search "api" --format json
```

#### Library-Specific Search

```bash
# Search within a specific library
dv lib requests authentication
dv search lib requests auth  # Same thing

# Search with library and version
dv lib django@4.2 models
```

#### Advanced Search Options

```bash
# Search with filters
dv search "testing" --tag python
dv search "api" --version 3.0
dv search "database" --collection "My Project"

# Search within specific document
dv search "authentication" --in-doc 5

# Get suggestions for related content
dv search "requests" --suggestions

# Tree view of search results
dv search "database" --tree

# Verbose output shows contextual information
dv search "error handling" --verbose
```

#### Contextual Search

DocVault now uses contextual retrieval to improve search accuracy by adding context to chunks before embedding them:

```bash
# Search results show [ctx] indicator for contextual embeddings
dv search "authentication"
# Results: (0.95 ctx) - indicates contextual embedding was used

# Verbose mode shows context descriptions
dv search "database connection" --verbose
# Shows: Context: This section discusses database connection pooling...
```

#### Search Output Formats

```bash
# Default table view
dv search "python async"

# JSON for scripts
dv search "api" --format json | jq '.results[0].content'

# Markdown format
dv search "tutorial" --format markdown

# XML format
dv search "examples" --format xml
```

### 3. Reading Documents

#### Basic Reading

```bash
# Read by document ID
dv read 1
dv cat 1  # Shorthand

# Read in different formats
dv read 1 --format html
dv read 1 --format json
dv read 1 --format xml

# Raw content (no rendering)
dv read 1 --raw
```

#### Advanced Reading Features

```bash
# Open HTML in browser
dv read 1 --format html --browser

# Get AI summary of document
dv read 1 --summarize

# Show with context and cross-references
dv read 1 --context --show-refs
```

#### Document Metadata

Every document shows:
- Title and URL
- Age and freshness status
- Update suggestions when stale
- Cross-references to related sections

### 4. Listing Documents

#### Basic Listing

```bash
# List all documents
dv list
dv ls  # Shorthand

# Verbose output with content hashes
dv list --verbose

# Different output formats
dv list --format json
dv list --format markdown
```

#### Filtering Lists

```bash
# Filter by tags
dv list --tag python
dv list --tag "web,api"  # Multiple tags

# Filter by collection
dv list --collection "My Project"

# Filter by version
dv list --version 3.9
```

### 5. Managing Documents

#### Removing Documents

```bash
# Remove by ID
dv remove 1
dv rm 1  # Shorthand

# Remove multiple documents
dv rm 1 3 5

# Remove with confirmation prompt
dv rm 1 --confirm
```

#### Document Statistics

```bash
# Show vault statistics
dv stats

# Detailed breakdown including:
# - Total documents and size
# - Tag and collection counts
# - Search index status
# - Cache health
```

## Document Management

### Version Control

DocVault tracks document versions and helps you manage updates:

```bash
# Check document versions
dv versions list

# Compare versions
dv versions diff 1

# Show version history
dv versions history 1

# Revert to previous version
dv versions revert 1 --to-version 2
```

### Cross-References

Navigate between related document sections:

```bash
# Show cross-references
dv ref show 1

# Navigate to related section
dv ref navigate 1 --to-section "authentication"

# Add manual cross-reference
dv ref add 1 2 --note "Related authentication docs"
```

## Search and Discovery

### Intelligent Suggestions

Get smart suggestions for related content:

```bash
# Get suggestions for a topic
dv suggest "database queries"

# Task-based suggestions
dv suggest "error handling" --task-based

# Find complementary functions
dv suggest --complementary "requests.get"

# JSON output for automation
dv suggest "async" --format json
```

### Content Context

Get richer information about documentation:

```bash
# Enhanced search with context
dv search "authentication" --context

# Show code examples and best practices
dv read 1 --context

# Get implementation suggestions
dv read 1 --show-implementations
```

## Organization Features

### Tags

Tags are flexible labels for categorizing documents by attributes:

```bash
# Add tags to documents
dv tag add 1 "python" "web" "api"

# List all tags
dv tag list

# Show documents with specific tag
dv tag show python

# Remove tags
dv tag remove 1 python

# Rename tags
dv tag rename old-name new-name

# Search by tags
dv search "async" --tag python
```

**Tag Best Practices:**
- Use technology tags: `python`, `javascript`, `rust`
- Use category tags: `web`, `database`, `testing`
- Use difficulty tags: `beginner`, `advanced`
- Use status tags: `stable`, `experimental`

### Collections

Collections are curated document sets for specific projects or learning paths:

```bash
# Create collections
dv collection create "My Web Project"
dv collection create "Machine Learning Study" --description "ML learning path"

# Add documents to collections
dv collection add "My Web Project" 1 2 3
dv collection add "ML Study" 5 --notes "Start here"

# List collections
dv collection list

# Show collection contents
dv collection show "My Web Project"

# Remove documents from collections
dv collection remove "My Web Project" 2

# Update collection metadata
dv collection update "My Web Project" --description "Updated description"

# Delete collections
dv collection delete "Old Project"

# Search within collections
dv search "database" --collection "My Web Project"
```

**Collection vs Tags:**
- **Tags**: Attributes (what it is) - `python`, `web`, `api`
- **Collections**: Projects (what it's for) - `My Website`, `Learning Path`

### Finding Documents

```bash
# Find documents across tags and collections
dv collection find --tag python
dv collection find --keyword "async"

# Complex filtering
dv list --tag python --collection "Web Project"
```

## Package Manager Integration

DocVault integrates with popular package managers to automatically find and add documentation:

### Quick Add Commands

```bash
# Python packages
dv add-pypi requests
dv add-pypi django --version 4.2

# Node.js packages
dv add-npm express
dv add-npm react --version 18

# Ruby gems
dv add-gem rails
dv add-gem sinatra --force  # Force update

# Other package managers
dv add-hex phoenix     # Elixir
dv add-go gin         # Go
dv add-crates serde   # Rust
dv add-composer laravel  # PHP
```

### Universal Package Manager Command

```bash
# Universal syntax: pm:package
dv add-pm pypi:requests
dv add-pm npm:express
dv add-pm gem:rails
dv add-pm hex:phoenix
dv add-pm go:gin
dv add-pm crates:serde
dv add-pm composer:laravel

# With versions
dv add-pm pypi:django@4.2
dv add-pm npm:react@18
```

### Package Manager Features

All package manager commands support:

```bash
# Version specification
dv add-pypi django --version 4.2

# Force update existing docs
dv add-npm react --force

# JSON output
dv add-pypi requests --format json

# Dry run (show what would be added)
dv add-pypi django --dry-run
```

### Supported Package Managers

| Command | Package Manager | Example |
|---------|----------------|---------|
| `add-pypi` | Python (PyPI) | `dv add-pypi requests` |
| `add-npm` | Node.js (npm) | `dv add-npm express` |
| `add-gem` | Ruby (RubyGems) | `dv add-gem rails` |
| `add-hex` | Elixir (Hex) | `dv add-hex phoenix` |
| `add-go` | Go Modules | `dv add-go gin` |
| `add-crates` | Rust (crates.io) | `dv add-crates serde` |
| `add-composer` | PHP (Packagist) | `dv add-composer laravel` |

## Document Freshness and Caching

DocVault tracks document age and helps you keep documentation current:

### Freshness Levels

- **✅ Fresh**: Less than 7 days old
- **🟡 Recent**: 7-30 days old
- **🟠 Stale**: 30-90 days old
- **🔴 Outdated**: More than 90 days old

### Viewing Freshness

```bash
# List with freshness indicators
dv list  # Shows freshness column

# Comprehensive freshness report
dv freshness

# Filter by freshness level
dv freshness --filter stale
dv freshness --filter outdated

# Show only documents needing updates
dv freshness --suggest-updates

# Different output formats
dv freshness --format json
dv freshness --format list
```

### Checking Individual Documents

```bash
# Check specific document freshness
dv check-freshness 1

# Custom staleness threshold
dv check-freshness 1 --threshold 30  # 30 days
```

### Cache Management

```bash
# Configure cache settings
dv cache-config --fresh-days 7
dv cache-config --stale-days 30
dv cache-config --auto-check

# Show cache statistics
dv cache-stats

# Check for updates
dv check-updates

# Update specific documents
dv update 1 3 5

# Update all stale documents
dv update --all-stale

# Pin documents to prevent staleness
dv pin 1 2 3

# Unpin documents
dv pin 1 --unpin
```

### Document Pinning

Prevent important documents from being marked as stale:

```bash
# Pin critical documents
dv pin 1 2 3

# List pinned documents
dv pin --list

# Unpin documents
dv pin 1 --unpin

# Unpin all
dv pin --unpin-all
```

## Advanced Features

### Contextual Retrieval

DocVault uses contextual retrieval to enhance search accuracy by adding context to document chunks before creating embeddings. This reduces retrieval failures by up to 49%.

#### How It Works

1. **Context Generation**: An LLM generates contextual descriptions for each chunk
2. **Augmented Embeddings**: Context is prepended to chunks before embedding
3. **Metadata Storage**: Context is also stored as searchable metadata
4. **Smart Search**: Search automatically uses contextual embeddings when available

#### Managing Contextual Retrieval

```bash
# Enable contextual retrieval
dv context enable

# Check status and statistics
dv context status
# Shows: Documents with context: 45/100 (45%)

# Process documents with context
dv context process 1              # Single document
dv context process-all            # All documents
dv context process-all --limit 10 # First 10 documents

# Configure LLM settings
dv context config --provider openai --model gpt-3.5-turbo
dv context config --provider ollama --model llama2
dv context config --provider anthropic --model claude-3-haiku

# Find similar content by metadata
dv context similar 123            # Find similar to segment 123
dv context similar 123 --role "code_example"
```

#### Supported LLM Providers

1. **Ollama** (default)
   - Local models: llama2, mistral, codellama
   - No API key required
   - Best for privacy

2. **OpenAI**
   - Models: gpt-3.5-turbo, gpt-4
   - Requires API key in environment
   - Good balance of speed and quality

3. **Anthropic**
   - Models: claude-3-haiku, claude-3-sonnet
   - Requires API key in environment
   - Best quality for complex docs

#### Benefits

- **Better Accuracy**: Context disambiguates chunks that are unclear alone
- **Cross-Document Navigation**: Find related content across all documents
- **Semantic Understanding**: Different handling for code, tutorials, API docs
- **Zero Breaking Changes**: Feature is opt-in and backward compatible

### llms.txt Support

DocVault automatically detects and parses llms.txt files for AI-friendly documentation:

```bash
# List documents with llms.txt files
dv llms list

# Show llms.txt content for a document
dv llms show 1

# Export in llms.txt format
dv export 1-5 --format llms

# Search for llms.txt files
dv llms find --tag python
```

### Export Features

Export documents in various formats:

```bash
# Export single document
dv export 1 --format markdown

# Export multiple documents
dv export 1,3,5 --format html
dv export 1-10 --format json
dv export all --format llms

# Export to specific directory
dv export 1-5 --output ./docs/ --format markdown

# Combine into single file
dv export 1-5 --combine --output combined.md

# Include metadata
dv export 1-3 --include-metadata

# Raw content export
dv export 1 --raw --format html
```

**Export Formats:**
- `markdown`: Rendered markdown
- `html`: HTML format
- `json`: Structured JSON
- `xml`: XML format
- `llms`: llms.txt format for AI

### Search Indexing

Manage the search index for optimal performance:

```bash
# Rebuild search index
dv index

# Index specific documents
dv index 1 3 5

# Check index status
dv index --status

# Optimize index
dv index --optimize
```

### Bulk Operations

Work with multiple documents efficiently:

```bash
# Bulk tag operations
dv tag add 1-10 "project-alpha"
dv tag remove 5,7,9 "outdated"

# Bulk collection operations
dv collection add "My Project" 1-20

# Bulk updates
dv update 1-5
dv update --all-stale

# Bulk exports
dv export 1-50 --format markdown --output ./docs/
```

## AI Integration

### Model Context Protocol (MCP)

DocVault integrates with AI assistants via MCP:

#### Starting the MCP Server

```bash
# Start MCP server
dv serve --mcp

# Custom host and port
dv serve --mcp --host 0.0.0.0 --port 8080

# Background mode
dv serve --mcp --daemon
```

#### Claude Integration

Add to your Claude desktop configuration:

```json
{
  "mcpServers": {
    "docvault": {
      "command": "dv",
      "args": ["serve", "--mcp"],
      "env": {}
    }
  }
}
```

#### Available MCP Tools

1. **scrape_document**: Add documentation from URL
2. **search_documents**: Search the vault
3. **read_document**: Read specific documents
4. **list_documents**: List all documents
5. **lookup_library_docs**: Find library documentation

### AI-Friendly Features

```bash
# JSON output for AI consumption
dv search "python async" --format json
dv list --format json
dv freshness --format json

# Structured suggestions
dv suggest "error handling" --format json

# Export for AI training
dv export all --format llms --output ai-docs.txt
```

## Backup and Maintenance

### Database Backup

```bash
# Create backup
dv backup

# Backup to specific location
dv backup --output /path/to/backup.zip

# Include storage files
dv backup --include-storage

# Backup with custom name
dv backup --output "docvault-$(date +%Y%m%d).zip"
```

### Restore from Backup

```bash
# Restore from backup
dv restore backup.zip

# Restore to different location
dv restore backup.zip --target /new/location

# Restore with confirmation
dv restore backup.zip --force
```

### Database Maintenance

```bash
# Initialize/recreate database
dv init
dv init --force  # Recreate existing database

# Show database statistics
dv stats

# Vacuum and optimize database
dv index --optimize

# Check database health
dv config --check-db
```

### Registry Management

Manage the documentation sources registry:

```bash
# List available documentation sources
dv registry list

# Add custom documentation source
dv registry add "Custom API" --base-url "https://api.example.com/docs/"

# Update documentation source
dv registry update "Python" --base-url "https://docs.python.org/"

# Remove documentation source
dv registry remove "Unused Source"

# Reset to defaults
dv registry reset
```

## Security Features

### Credential Management

Securely store API keys and tokens:

```bash
# Set API keys
dv credentials set brave_api_key your-key-here
dv creds set github_token your-token  # Shorthand

# List stored credentials (values hidden)
dv credentials list

# Remove credentials
dv credentials remove brave_api_key

# Use credentials in environment
eval $(dv credentials env)
```

### Security Settings

```bash
# View security settings
dv security status

# Update security configuration
dv security config --max-depth 3 --timeout 30

# Check for security issues
dv security audit

# Reset security settings
dv security reset
```

### URL Validation

DocVault includes comprehensive URL validation:

- Blocks private IP ranges
- Prevents SSRF attacks
- Validates SSL certificates
- Enforces request timeouts
- Limits response sizes

Configure via environment variables (see [CONFIGURATION.md](CONFIGURATION.md)).

## Tips and Best Practices

### Organization Strategy

1. **Use Tags for Attributes**:
   ```bash
   dv tag add 1 "python" "web" "tutorial" "beginner"
   ```

2. **Use Collections for Projects**:
   ```bash
   dv collection create "E-commerce Site"
   dv collection add "E-commerce Site" 1 5 12
   ```

3. **Combine Tags and Collections**:
   ```bash
   dv search "database" --tag python --collection "My Project"
   ```

### Search Optimization

1. **Use Specific Terms**:
   ```bash
   # Good: Specific and targeted
   dv search "django model fields validation"
   
   # Less effective: Too broad
   dv search "python web"
   ```

2. **Leverage Library Search**:
   ```bash
   # Find specific library information
   dv lib requests authentication
   dv lib django@4.2 models
   ```

3. **Use Suggestions**:
   ```bash
   # Get related content
   dv search "requests" --suggestions
   dv suggest --complementary "requests.get"
   ```

### Maintenance Workflow

1. **Regular Freshness Checks**:
   ```bash
   # Weekly freshness review
   dv freshness --suggest-updates
   
   # Update stale documents
   dv update --all-stale
   ```

2. **Backup Schedule**:
   ```bash
   # Monthly backups
   dv backup --output "backup-$(date +%Y%m).zip"
   ```

3. **Index Optimization**:
   ```bash
   # Rebuild index when search feels slow
   dv index --optimize
   ```

### Performance Tips

1. **Use Appropriate Depth**:
   ```bash
   # Let DocVault auto-detect
   dv add https://docs.python.org/3/
   
   # Manual control for large sites
   dv add https://large-docs.com/ --depth 2
   ```

2. **Batch Operations**:
   ```bash
   # Add multiple tags at once
   dv tag add 1-10 "project-alpha"
   
   # Bulk exports
   dv export 1-20 --format markdown
   ```

3. **JSON Output for Scripts**:
   ```bash
   # Parse with jq
   dv search "api" --format json | jq '.results[].title'
   
   # Use in scripts
   DOCS=$(dv list --tag python --format json)
   ```

### Integration Patterns

1. **Project Setup**:
   ```bash
   # New project workflow
   cd my-project
   dv import-deps
   dv tag add $(dv list --format json | jq -r '.[].id') "my-project"
   dv collection create "My Project"
   dv collection add "My Project" $(dv list --format json | jq -r '.[].id')
   ```

2. **Learning Path**:
   ```bash
   # Create learning sequence
   dv collection create "Python Basics" --description "Learning path for Python"
   dv add-pypi python-tutorial
   dv add https://docs.python.org/3/tutorial/
   dv collection add "Python Basics" 1 2 --notes "Start with these"
   ```

3. **Team Sharing**:
   ```bash
   # Export team documentation
   dv export all --format markdown --output team-docs/
   
   # Create team backup
   dv backup --output team-vault.zip --include-storage
   ```

### Troubleshooting Common Issues

1. **Search Not Working**:
   ```bash
   dv index  # Rebuild search index
   dv stats  # Check database health
   ```

2. **Slow Performance**:
   ```bash
   dv index --optimize  # Optimize database
   dv cache-stats       # Check cache health
   ```

3. **Missing Documents**:
   ```bash
   dv list --verbose  # Check what's in vault
   dv freshness       # Check document status
   ```

4. **Connection Issues**:
   ```bash
   dv config          # Check configuration
   dv security status # Check security settings
   ```

## Command Reference Quick Index

### Core Commands
- `dv add <url>` - Add documentation
- `dv search <query>` - Search documents  
- `dv read <id>` - Read document
- `dv list` - List all documents
- `dv remove <id>` - Remove document

### Package Managers
- `dv add-pypi <package>` - Python packages
- `dv add-npm <package>` - Node.js packages
- `dv add-gem <package>` - Ruby gems
- `dv add-pm <pm:package>` - Universal command

### Organization
- `dv tag add <id> <tags>` - Add tags
- `dv collection create <name>` - Create collection
- `dv collection add <name> <ids>` - Add to collection

### Freshness
- `dv freshness` - Check all document freshness
- `dv update <id>` - Update specific documents
- `dv pin <id>` - Pin documents

### Advanced
- `dv serve --mcp` - Start MCP server
- `dv export <ids>` - Export documents
- `dv backup` - Backup vault
- `dv suggest <topic>` - Get suggestions

### Maintenance
- `dv stats` - Show statistics
- `dv index` - Rebuild search index
- `dv config` - Manage configuration

---

## Next Steps

- 📚 Read [QUICK_START.md](QUICK_START.md) for a 5-minute introduction
- ⚙️ See [CONFIGURATION.md](CONFIGURATION.md) for detailed configuration
- 🤖 Check [CLAUDE.md](../CLAUDE.md) for AI integration setup
- 🆘 Run `dv <command> --help` for command-specific help

Happy documenting! 🚀