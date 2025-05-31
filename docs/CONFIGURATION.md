# DocVault Configuration Guide

This guide covers all configuration options available in DocVault, from basic setup to advanced customization.

## Table of Contents

1. [Configuration Overview](#configuration-overview)
2. [Configuration Methods](#configuration-methods)
3. [Environment Variables Reference](#environment-variables-reference)
4. [Configuration Examples](#configuration-examples)
5. [Advanced Scenarios](#advanced-scenarios)
6. [Troubleshooting](#troubleshooting)

## Configuration Overview

DocVault uses environment variables for configuration, providing flexibility and security. Configuration can be set at multiple levels:

1. **System environment variables** - Highest priority
2. **`.env` file in current directory** - Project-specific settings
3. **`.env` file in `~/.docvault/`** - User-wide settings
4. **Default values** - Built-in defaults

## Configuration Methods

### Method 1: Environment Variables

Set environment variables in your shell:

```bash
export DOCVAULT_DB_PATH=/path/to/database.db
export BRAVE_API_KEY=your-api-key-here
dv search "python async"
```

### Method 2: .env File (Recommended)

Create a `.env` file in your project directory or `~/.docvault/`:

```bash
# Create user-wide configuration
cat > ~/.docvault/.env << EOF
# API Keys
BRAVE_API_KEY=your-brave-api-key
GITHUB_TOKEN=your-github-token

# Database
DOCVAULT_DB_PATH=~/.docvault/docvault.db

# Logging
LOG_LEVEL=INFO
EOF
```

### Method 3: Docker/Container Environment

```dockerfile
FROM python:3.9
ENV DOCVAULT_DB_PATH=/data/docvault.db
ENV LOG_LEVEL=WARNING
ENV MAX_CONCURRENT_REQUESTS=5
```

### Method 4: Shell Configuration

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# DocVault Configuration
export BRAVE_API_KEY="your-api-key"  # pragma: allowlist secret
export EMBEDDING_MODEL="nomic-embed-text"
export LOG_LEVEL="DEBUG"
```

## Environment Variables Reference

### Core Settings

#### Database Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCVAULT_DB_PATH` | `~/.docvault/docvault.db` | Path to SQLite database file |
| `USE_CONNECTION_POOL` | `false` | Enable database connection pooling (opt-in) |
| `DB_POOL_SIZE` | `5` | Connection pool size (when enabled) |

Example:
```bash
# Use custom database location
DOCVAULT_DB_PATH=/var/lib/docvault/main.db

# Use in-memory database (testing only)
DOCVAULT_DB_PATH=:memory:

# Enable connection pooling for better performance
USE_CONNECTION_POOL=true
DB_POOL_SIZE=10
```

#### Storage Paths

| Variable | Default | Description |
|----------|---------|-------------|
| `STORAGE_PATH` | `~/.docvault/storage` | Base directory for document storage |
| `HTML_PATH` | `{STORAGE_PATH}/html` | Directory for HTML documents |
| `MARKDOWN_PATH` | `{STORAGE_PATH}/markdown` | Directory for Markdown documents |

Example:
```bash
# Use separate drive for storage
STORAGE_PATH=/mnt/documents/docvault

# Network storage
STORAGE_PATH=/nfs/shared/docvault
```

### API Keys and External Services

#### Search APIs

| Variable | Default | Description |
|----------|---------|-------------|
| `BRAVE_API_KEY` | `""` | Brave Search API key for library lookups |
| `GITHUB_TOKEN` | `""` | GitHub personal access token for scraping |

Example:
```bash
# Brave Search API (get from https://brave.com/search/api/)
BRAVE_API_KEY=BSA-xxxxxxxxxxxxxxxxxxxxx

# GitHub token with public repo access
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

#### Embedding Service

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Model for generating embeddings |

Example:
```bash
# Remote Ollama server
OLLAMA_URL=http://gpu-server:11434

# Alternative embedding models
EMBEDDING_MODEL=mxbai-embed-large  # Higher quality
EMBEDDING_MODEL=all-minilm         # Faster, lower quality
```

### Server Configuration

#### MCP Server Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `127.0.0.1` | Server bind address (SSE/web mode) |
| `PORT` | `8000` | Server port (SSE/web mode) |
| `SERVER_HOST` | `127.0.0.1` | Legacy server address (stdio mode) |
| `SERVER_PORT` | `8000` | Legacy server port (stdio mode) |
| `SERVER_WORKERS` | `4` | Number of worker processes |

Example:
```bash
# Allow external connections
HOST=0.0.0.0
PORT=8080

# Production settings
SERVER_WORKERS=8
```

### Security Configuration

#### URL Validation

| Variable | Default | Description |
|----------|---------|-------------|
| `URL_ALLOWED_DOMAINS` | `""` | Comma-separated whitelist of domains |
| `URL_BLOCKED_DOMAINS` | `""` | Comma-separated blacklist of domains |

Example:
```bash
# Only allow specific documentation sites
URL_ALLOWED_DOMAINS=docs.python.org,docs.djangoproject.com,numpy.org

# Block problematic domains
URL_BLOCKED_DOMAINS=malware-site.com,phishing.net
```

#### Request Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `REQUEST_TIMEOUT` | `30` | Request timeout in seconds |
| `MAX_RESPONSE_SIZE` | `10485760` | Max response size in bytes (10MB) |
| `MAX_SCRAPING_DEPTH` | `5` | Maximum scraping recursion depth |
| `MAX_PAGES_PER_DOMAIN` | `100` | Max pages to scrape per domain |

Example:
```bash
# Longer timeout for slow sites
REQUEST_TIMEOUT=60

# Larger responses for documentation sites
MAX_RESPONSE_SIZE=52428800  # 50MB

# Shallow scraping for large sites
MAX_SCRAPING_DEPTH=2
```

#### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-domain requests per minute |
| `RATE_LIMIT_PER_HOUR` | `1000` | Per-domain requests per hour |
| `RATE_LIMIT_BURST_SIZE` | `10` | Burst size for rate limiting |
| `GLOBAL_RATE_LIMIT_PER_MINUTE` | `300` | Global requests per minute |
| `GLOBAL_RATE_LIMIT_PER_HOUR` | `5000` | Global requests per hour |

Example:
```bash
# Conservative rate limiting
RATE_LIMIT_PER_MINUTE=30
RATE_LIMIT_PER_HOUR=500

# Aggressive scraping (be careful!)
RATE_LIMIT_PER_MINUTE=120
GLOBAL_RATE_LIMIT_PER_MINUTE=600
```

#### Resource Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_CONCURRENT_REQUESTS` | `10` | Maximum concurrent HTTP requests |
| `MAX_MEMORY_MB` | `1024` | Maximum memory usage in MB |
| `MAX_PROCESSING_TIME_SECONDS` | `300` | Max processing time per operation |

Example:
```bash
# Limited resources
MAX_CONCURRENT_REQUESTS=3
MAX_MEMORY_MB=512

# High-performance server
MAX_CONCURRENT_REQUESTS=50
MAX_MEMORY_MB=8192
```

### Proxy Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HTTP_PROXY` | `""` | HTTP proxy URL |
| `HTTPS_PROXY` | `""` | HTTPS proxy URL |
| `NO_PROXY` | `""` | Comma-separated list of no-proxy domains |

Example:
```bash
# Corporate proxy
HTTP_PROXY=http://proxy.company.com:8080
HTTPS_PROXY=http://proxy.company.com:8080
NO_PROXY=localhost,127.0.0.1,internal.company.com
```

### Logging Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_DIR` | `~/.docvault/logs` | Directory for log files |
| `LOG_FILE` | `docvault.log` | Log file name |
| `LOG_LEVEL` | `INFO` | Logging level |

Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

Example:
```bash
# Verbose logging for debugging
LOG_LEVEL=DEBUG

# Quiet logging for production
LOG_LEVEL=ERROR

# Custom log location
LOG_DIR=/var/log/docvault
LOG_FILE=docvault-$(date +%Y%m%d).log
```

## Configuration Examples

### Example 1: Development Setup

```bash
# ~/.docvault/.env for development
# Enable debug logging
LOG_LEVEL=DEBUG

# Use local paths
DOCVAULT_DB_PATH=./dev.db
STORAGE_PATH=./dev-storage

# Relaxed limits for testing
MAX_SCRAPING_DEPTH=10
RATE_LIMIT_PER_MINUTE=120

# Local Ollama
OLLAMA_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
```

### Example 2: Production Server

```bash
# /etc/docvault/.env for production
# Security first
URL_ALLOWED_DOMAINS=docs.python.org,docs.djangoproject.com,fastapi.tiangolo.com
REQUEST_TIMEOUT=30
MAX_RESPONSE_SIZE=20971520  # 20MB

# Performance tuning
SERVER_WORKERS=8
MAX_CONCURRENT_REQUESTS=20
MAX_MEMORY_MB=4096

# Rate limiting
RATE_LIMIT_PER_MINUTE=60
GLOBAL_RATE_LIMIT_PER_HOUR=10000

# Logging
LOG_LEVEL=WARNING
LOG_DIR=/var/log/docvault

# API keys (use secrets management in production!)  # pragma: allowlist secret
BRAVE_API_KEY=${BRAVE_API_KEY_FROM_SECRETS}
GITHUB_TOKEN=${GITHUB_TOKEN_FROM_SECRETS}
```

### Example 3: Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.9-slim

# Set production defaults
ENV LOG_LEVEL=INFO \
    SERVER_WORKERS=4 \
    MAX_CONCURRENT_REQUESTS=10 \
    DOCVAULT_DB_PATH=/data/docvault.db \
    STORAGE_PATH=/data/storage

# Mount volume for persistence
VOLUME /data

# Run server
CMD ["dv", "serve", "--mcp"]
```

### Example 4: CI/CD Pipeline

```yaml
# .github/workflows/test.yml
env:
  DOCVAULT_DB_PATH: ":memory:"
  LOG_LEVEL: "ERROR"
  MAX_CONCURRENT_REQUESTS: "2"
  REQUEST_TIMEOUT: "10"
```

### Example 5: Shared Team Environment

```bash
# /opt/docvault/.env for shared server
# Shared database
DOCVAULT_DB_PATH=/opt/docvault/shared.db

# Network storage
STORAGE_PATH=/nfs/docvault/storage

# Conservative limits
MAX_PAGES_PER_DOMAIN=50
RATE_LIMIT_PER_MINUTE=30

# Allow team domains
URL_ALLOWED_DOMAINS=docs.company.com,wiki.company.com

# Moderate logging
LOG_LEVEL=INFO
LOG_DIR=/var/log/docvault
```

## Advanced Scenarios

### Multi-Environment Setup

Create environment-specific configurations:

```bash
# dev.env
LOG_LEVEL=DEBUG
DOCVAULT_DB_PATH=./dev.db

# staging.env
LOG_LEVEL=INFO
DOCVAULT_DB_PATH=/opt/docvault/staging.db

# prod.env
LOG_LEVEL=WARNING
DOCVAULT_DB_PATH=/opt/docvault/prod.db

# Usage
export $(cat dev.env | xargs) && dv search "test"
```

### Secrets Management

Never commit sensitive data! Use secret management tools:

```bash
# Using environment variables from secrets manager
export BRAVE_API_KEY=$(vault kv get -field=api_key secret/docvault/brave)
export GITHUB_TOKEN=$(aws secretsmanager get-secret-value --secret-id github-token --query SecretString --output text)

# Using .env.local (git-ignored)
cp .env.example .env.local
# Edit .env.local with real values
```

### Performance Tuning

For high-performance scenarios:

```bash
# High-performance configuration
SERVER_WORKERS=16                    # Match CPU cores
MAX_CONCURRENT_REQUESTS=50          # High concurrency
MAX_MEMORY_MB=8192                  # 8GB RAM
RATE_LIMIT_PER_MINUTE=120          # Aggressive scraping
GLOBAL_RATE_LIMIT_PER_MINUTE=1000  # High throughput

# Database optimization
DOCVAULT_DB_PATH=/ssd/docvault.db  # Use SSD for database
USE_CONNECTION_POOL=true            # Enable connection pooling
DB_POOL_SIZE=20                     # Larger pool for high traffic
```

### Security Hardening

For maximum security:

```bash
# Strict security settings
URL_ALLOWED_DOMAINS=docs.python.org,docs.djangoproject.com
URL_BLOCKED_DOMAINS=evil.com,malware.net
REQUEST_TIMEOUT=15                   # Short timeout
MAX_RESPONSE_SIZE=5242880           # 5MB max
MAX_SCRAPING_DEPTH=2                # Shallow scraping
RATE_LIMIT_PER_MINUTE=30            # Conservative rate
MAX_CONCURRENT_REQUESTS=5           # Limited concurrency
```

### Cache Configuration

Configure document freshness thresholds:

```bash
# Note: These are configured via CLI, not environment variables
dv cache-config --fresh-days 3      # Very fresh
dv cache-config --stale-days 14     # Quicker staleness
dv cache-config --auto-check        # Enable auto-checking
```

## Troubleshooting

### Configuration Not Loading

1. **Check file location**:
   ```bash
   # DocVault checks these locations in order:
   ls -la ./.env                      # Current directory
   ls -la ~/.docvault/.env           # User directory
   ```

2. **Verify syntax**:
   ```bash
   # No spaces around '='
   GOOD_VAR=value
   BAD_VAR = value  # Won't work!
   
   # Quote values with spaces
   LOG_FILE="my log file.log"
   ```

3. **Check permissions**:
   ```bash
   chmod 600 ~/.docvault/.env  # Secure permissions
   ```

### Debug Configuration Loading

```bash
# Show current configuration
dv config

# Test with explicit env var
LOG_LEVEL=DEBUG dv search "test"

# Check which .env file is loaded
strace -e open dv config 2>&1 | grep "\.env"
```

### Common Issues

1. **API Key Not Working**:
   ```bash
   # Test API key
   echo $BRAVE_API_KEY  # Should show your key
   
   # Try setting directly
   BRAVE_API_KEY=your-key dv search lib requests
   ```

2. **Database Permission Errors**:
   ```bash
   # Check database path
   echo $DOCVAULT_DB_PATH
   
   # Ensure directory exists and is writable
   mkdir -p $(dirname $DOCVAULT_DB_PATH)
   touch $DOCVAULT_DB_PATH
   ```

3. **Embedding Service Connection**:
   ```bash
   # Test Ollama connection
   curl $OLLAMA_URL/api/tags
   
   # Use fallback to text search
   OLLAMA_URL=http://invalid:11434 dv search "test"
   ```

4. **Rate Limiting Issues**:
   ```bash
   # Temporarily increase limits
   RATE_LIMIT_PER_MINUTE=120 dv add https://docs.python.org
   
   # Check current limits
   dv config | grep RATE_LIMIT
   ```

### Environment Variable Precedence

Order of precedence (highest to lowest):
1. Command-line environment: `VAR=value dv command`
2. Shell environment: `export VAR=value`
3. `.env` in current directory
4. `.env` in `~/.docvault/`
5. Built-in defaults

### Validation Script

Create a script to validate your configuration:

```bash
#!/bin/bash
# validate-config.sh

echo "Checking DocVault configuration..."

# Check required directories
for dir in "$HOME/.docvault" "$STORAGE_PATH" "$LOG_DIR"; do
    if [ ! -d "$dir" ]; then
        echo "❌ Missing directory: $dir"
    else
        echo "✅ Directory exists: $dir"
    fi
done

# Check database
if [ -f "$DOCVAULT_DB_PATH" ]; then
    echo "✅ Database exists: $DOCVAULT_DB_PATH"
else
    echo "⚠️  Database not found: $DOCVAULT_DB_PATH"
fi

# Test API keys
if [ -n "$BRAVE_API_KEY" ]; then
    echo "✅ Brave API key is set"
else
    echo "⚠️  Brave API key not set"
fi

# Test Ollama
if curl -s "$OLLAMA_URL/api/tags" > /dev/null; then
    echo "✅ Ollama is accessible at $OLLAMA_URL"
else
    echo "❌ Cannot connect to Ollama at $OLLAMA_URL"
fi
```

## Best Practices

1. **Use .env files** instead of shell exports for persistent configuration
2. **Never commit sensitive data** - use `.gitignore` for `.env` files
3. **Set appropriate rate limits** to avoid being blocked by documentation sites
4. **Use separate databases** for development and production
5. **Enable logging** in production but set appropriate levels
6. **Regular backups** of your database and storage directories
7. **Monitor resource usage** and adjust limits accordingly
8. **Use secrets management** for API keys in production

## Next Steps

- See [QUICK_START.md](QUICK_START.md) for getting started
- Check [README.md](../README.md) for full documentation
- Explore [CLAUDE.md](../CLAUDE.md) for AI integration details