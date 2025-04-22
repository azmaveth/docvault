#!/usr/bin/env python3
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
#     "modelcontextprotocol>=0.1.0"
# ]
# ///

import os
from datetime import datetime

import click

# Import CLI commands directly
from docvault.cli.commands import (
    backup,
    config_cmd,
    import_backup,
    import_cmd,
    index_cmd,
    init_cmd,
    list_cmd,
    read_cmd,
    remove_cmd,
    search_cmd,
)

# Import initialization function
from docvault.core.initialization import ensure_app_initialized


def create_main():
    @click.group(invoke_without_command=True)
    @click.pass_context
    def main(ctx, *args, **kwargs):
        """DocVault: Document management system

        If no command is given, defaults to 'search'.
        """
        ensure_app_initialized()
        if ctx.invoked_subcommand is None:
            # If no subcommand, treat as 'search'
            # Forward arguments to search_cmd
            ctx.forward(search_cmd)

    register_commands(main)
    return main


def create_env_template():
    """Create a template .env file with default values and explanations"""
    from docvault import config as conf

    template = f"""# DocVault Configuration
# Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}
# You can customize DocVault by modifying this file

# Database Configuration
DOCVAULT_DB_PATH={conf.DB_PATH}

# API Keys
# Add your Brave API key here for library documentation search
BRAVE_API_KEY=

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


def register_commands(main):
    main.add_command(import_cmd, name="import")
    main.add_command(import_cmd, name="add")
    main.add_command(import_cmd, name="scrape")
    main.add_command(import_cmd, name="fetch")

    main.add_command(init_cmd, name="init")
    main.add_command(init_cmd, name="init-db")

    main.add_command(remove_cmd, name="remove")
    main.add_command(remove_cmd, name="rm")

    main.add_command(list_cmd, name="list")
    main.add_command(list_cmd, name="ls")

    main.add_command(read_cmd, name="read")
    main.add_command(read_cmd, name="cat")

    main.add_command(search_cmd, name="search")
    main.add_command(search_cmd, name="find")

    main.add_command(config_cmd, name="config")

    main.add_command(backup, name="backup")
    main.add_command(import_backup, name="import-backup")
    main.add_command(index_cmd, name="index")


# All command aliases are registered manually above to ensure compatibility with Click <8.1.0 and for explicit aliasing.

if __name__ == "__main__":
    main = create_main()
    main()
