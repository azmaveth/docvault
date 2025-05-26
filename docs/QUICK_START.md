# DocVault Quick Start Guide

Welcome to DocVault! This guide will get you up and running in just a few minutes.

## 🚀 What is DocVault?

DocVault is a powerful CLI tool that helps you:
- 📚 Store and search documentation locally
- 🔍 Find answers quickly across multiple docs
- 🤖 Access docs through AI assistants via MCP
- 📦 Manage documentation for all your dependencies

## 📋 Prerequisites

- Python 3.9 or higher
- Git (for development)
- Unix-like system (macOS, Linux) or WSL on Windows

## ⚡ Installation (30 seconds)

The fastest way to get started:

```bash
# Using pip
pip install docvault

# Or using uv (recommended)
uv pip install docvault

# Or from source
git clone https://github.com/yourusername/docvault.git
cd docvault
./scripts/install-dv.sh
```

## 🎯 First Steps (2 minutes)

### 1. Initialize DocVault

```bash
# Initialize the database
dv init

# Verify installation
dv version
```

### 2. Add Your First Documentation

```bash
# Quick add from package managers
dv add-pypi requests        # Python packages
dv add-npm express         # Node packages
dv add-gem rails           # Ruby gems

# Or add any URL
dv add https://docs.python.org/3/
```

### 3. Search Documentation

```bash
# Simple search
dv search "http request"

# Search in specific library
dv lib requests authentication

# Get function details
dv search "requests.get" --limit 5
```

## 🔥 Essential Commands (3 minutes)

### Adding Documentation

```bash
# From package managers (auto-detects docs)
dv add-pypi django
dv add-npm react
dv add-gem sinatra

# From URLs
dv add https://fastapi.tiangolo.com/
dv add https://docs.djangoproject.com/

# From project dependencies
dv import-deps              # Reads package.json, requirements.txt, etc.
```

### Searching and Reading

```bash
# Search across all docs
dv search "async await"

# Search with filters
dv search "database" --tag python
dv search "api" --version 3.0

# Read specific document
dv read 1                   # By ID
dv read 1 --summarize      # Get AI summary
```

### Managing Documents

```bash
# List all documents
dv list
dv list --tag web          # Filter by tag

# Check document freshness
dv freshness               # See which docs need updates
dv update 1               # Update specific document

# Remove documents
dv rm 1                    # Remove by ID
```

### Organization

```bash
# Tag documents
dv tag add 1 "backend" "api"
dv tag list

# Create collections
dv collection create "My Project"
dv collection add "My Project" 1 2 3
```

## 💡 Power User Tips (2 minutes)

### 1. Default Search
```bash
# Just type your query!
dv async programming       # Searches automatically
```

### 2. Quick Library Lookup
```bash
# Use 'lib' shorthand
dv lib pandas dataframe
```

### 3. Export for AI/Sharing
```bash
# Export as markdown
dv export 1-5 --format markdown

# Export for LLMs
dv export all --format llms
```

### 4. JSON Output for Scripts
```bash
# Get machine-readable output
dv search "api" --format json | jq '.results[0].content'
dv list --format json
```

### 5. Freshness Tracking
```bash
# See document ages at a glance
dv list                    # Shows freshness indicators
dv freshness --suggest-updates  # Find outdated docs
```

## 🔧 Common Workflows

### Workflow 1: Setting Up a New Project

```bash
# 1. Add all project dependencies
cd my-project
dv import-deps

# 2. Tag them by project
dv tag add 1-10 "my-project"

# 3. Create a collection
dv collection create "My Project Docs"
dv collection add "My Project Docs" 1-10
```

### Workflow 2: Research Mode

```bash
# 1. Add multiple related docs
dv add-pypi pytorch scikit-learn numpy
dv add https://pytorch.org/tutorials/

# 2. Tag by topic
dv tag add 1-4 "machine-learning"

# 3. Search across all ML docs
dv search "neural network" --tag machine-learning
```

### Workflow 3: Keeping Docs Fresh

```bash
# 1. Check what needs updating
dv freshness --suggest-updates

# 2. Update stale documents
dv update 5 8 12

# 3. Pin important docs to prevent staleness
dv pin 1 2 3
```

## 🤖 AI Integration

### For Claude (via MCP)

Add to your Claude configuration:

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

### For Scripts/Automation

```bash
# Search and get JSON
RESULTS=$(dv search "database connection" --format json)

# Extract specific fields
echo $RESULTS | jq '.results[].title'
```

## ❓ Troubleshooting

### Command Not Found

```bash
# Try these alternatives
uv run dv search "test"
python -m docvault search "test"
./scripts/install-dv.sh    # Reinstall
```

### Search Not Working

```bash
# Rebuild search index
dv index

# Check for errors
dv stats
```

### Slow Performance

```bash
# Check cache status
dv cache-stats

# Configure cache
dv cache-config --max-age 30
```

## 📚 Next Steps

- Run `dv help` to see all commands
- Check out `dv <command> --help` for detailed options
- Read the [full documentation](../README.md)
- Join our community for tips and support

## 🎉 You're Ready!

You now know enough to use DocVault effectively. Start by adding documentation for your current project:

```bash
dv import-deps
dv search "your topic here"
```

Happy coding with instant documentation at your fingertips! 🚀