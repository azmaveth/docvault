#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.3",
#     "rich>=13.3.1",
#     "python-dotenv>=1.0.0",
#     "requests>=2.28.1",
#     "beautifulsoup4>=4.11.1",
#     "html2text>=2020.1.16",
#     "aiohttp>=3.8.4",
#     "numpy>=1.24.0",
#     "mcp-sdk>=0.1.0"
# ]
# ///

import click
import os
import sys
from pathlib import Path
from datetime import datetime

@click.group()
def main():
    """DocVault: Document management system with vector search"""
    # Ensure app is initialized
    ensure_app_initialized()
    pass

def ensure_app_initialized():
    """Ensure the application is initialized on first run"""
    from docvault.db.schema import initialize_database
    from docvault import config
    
    # Check if database exists and is initialized
    if not os.path.exists(config.DB_PATH):
        click.echo(f"Initializing DocVault in {config.DEFAULT_BASE_DIR}")
        
        # Set up database
        initialize_database()
        
        # Create example .env file for future customization
        env_template = create_env_template()
        env_path = config.DEFAULT_BASE_DIR / ".env.example"
        with open(env_path, "w") as f:
            f.write(env_template)
        
        click.echo(f"✅ DocVault initialized successfully!")
        click.echo(f"📂 Default configuration created in {config.DEFAULT_BASE_DIR}")
        click.echo(f"ℹ️  To customize settings, rename .env.example to .env and edit")

def create_env_template():
    """Create a template .env file with default values and explanations"""
    from docvault import config as conf
    
    template = f"""# DocVault Configuration
# Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}
# You can customize DocVault by modifying this file

# Database Configuration
DOCVAULT_DB_PATH={conf.DB_PATH}

# API Keys
# Add your Brave Search API key here for library documentation search
BRAVE_SEARCH_API_KEY=

# Embedding Configuration
OLLAMA_URL={conf.OLLAMA_URL}
EMBEDDING_MODEL={conf.EMBEDDING_MODEL}

# Storage Configuration
STORAGE_PATH={conf.STORAGE_PATH}

# Server Configuration
SERVER_HOST={conf.SERVER_HOST}
SERVER_PORT={conf.SERVER_PORT}
SERVER_WORKERS={conf.SERVER_WORKERS}

# Logging
LOG_LEVEL={conf.LOG_LEVEL}
LOG_DIR={conf.LOG_DIR}
LOG_FILE={os.path.basename(conf.LOG_FILE)}
"""
    return template

# Add CLI commands
from docvault.cli.commands import cli
main.add_command(cli)

@main.command(name="serve")
@click.option("--host", default=None, help="Host to bind the server to")
@click.option("--port", default=None, type=int, help="Port to bind the server to")
def serve(host, port):
    """Run the MCP server"""
    try:
        from docvault.mcp.server import run_server
        run_server(host=host, port=port)
    except ImportError:
        click.echo("⚠️  MCP SDK not installed. Please install it with 'pip install mcp-sdk'")
        sys.exit(1)

if __name__ == "__main__":
    main()
