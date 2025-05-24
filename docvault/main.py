#!/usr/bin/env python3

import os
from datetime import datetime

import click

# Import CLI commands directly
from docvault.cli.commands import (
    backup,
    config_cmd,
    import_backup,
    import_cmd,
    import_deps_cmd,
    index_cmd,
    init_cmd,
    list_cmd,
    read_cmd,
    remove_cmd,
    search_cmd,
    serve_cmd,
    version_cmd,
)
from docvault.cli.registry_commands import registry as registry_group

# Import initialization function
# from docvault.core.initialization import ensure_app_initialized


class DefaultGroup(click.Group):
    def __init__(self, *args, default_cmd=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_cmd = default_cmd

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        # If the command is not found, just return None (invoke will handle forwarding)
        return None

    def invoke(self, ctx):
        # If the command is not found, treat all args as a query for the default subcommand
        if ctx.protected_args and self.default_cmd is not None:
            cmd_name = ctx.protected_args[0]
            if click.Group.get_command(self, ctx, cmd_name) is None:
                default_cmd_obj = click.Group.get_command(self, ctx, self.default_cmd)
                if isinstance(default_cmd_obj, click.Group):
                    search_text_cmd = default_cmd_obj.get_command(ctx, "text")
                    query = " ".join(ctx.protected_args + ctx.args)
                    return ctx.invoke(search_text_cmd, query=query)
        return super().invoke(ctx)


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
HOST={conf.HOST}
PORT={conf.PORT}
# (legacy/stdio only)
SERVER_HOST={conf.SERVER_HOST}
SERVER_PORT={conf.SERVER_PORT}
SERVER_WORKERS={conf.SERVER_WORKERS}

# Logging
LOG_LEVEL={conf.LOG_LEVEL}
LOG_DIR={conf.LOG_DIR}
LOG_FILE={os.path.basename(conf.LOG_FILE)}
"""
    return template


@click.group(
    cls=DefaultGroup,
    name="dv",
    default_cmd="search",
    invoke_without_command=True,
    help="DocVault CLI - Manage and search documentation",
    context_settings={"help_option_names": ["-h", "--help", "--version"]},
)
@click.option("--version", is_flag=True, is_eager=True, help="Show version and exit")
@click.pass_context
def create_main(ctx, version):
    if version:
        from docvault.version import __version__

        click.echo(f"DocVault version {__version__}")
        ctx.exit()
    # Call initializer (patched in tests via docvault.core.initialization)
    from docvault.core.initialization import ensure_app_initialized as _ensure_init

    _ensure_init()
    if ctx.invoked_subcommand is None:
        if not ctx.args:
            click.echo(ctx.get_help())
            ctx.exit()
        # Forward all args as a single query to search_cmd.text
        from docvault.cli.commands import search_cmd

        text_cmd = search_cmd.get_command(ctx, "text")
        ctx.invoke(text_cmd, query=" ".join(ctx.args))
        ctx.exit()


# Register commands after definition
create_main.add_command(init_cmd)
create_main.add_command(import_cmd)
create_main.add_command(list_cmd)
create_main.add_command(read_cmd)
create_main.add_command(remove_cmd)
create_main.add_command(search_cmd)
create_main.add_command(index_cmd)
create_main.add_command(config_cmd)
create_main.add_command(serve_cmd)
create_main.add_command(backup)
create_main.add_command(import_backup)
create_main.add_command(version_cmd)


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
    # Add 'lib' as a direct alias to 'search_lib' for 'dv lib <query>'
    from docvault.cli.commands import search_lib

    main.add_command(search_lib, name="lib")

    main.add_command(config_cmd, name="config")

    main.add_command(backup, name="backup")
    main.add_command(import_backup, name="import-backup")
    main.add_command(index_cmd, name="index")
    main.add_command(serve_cmd, name="serve")

    # Add registry commands
    main.add_command(registry_group, name="registry")

    # Add import-deps command with aliases
    main.add_command(import_deps_cmd, name="import-deps")
    main.add_command(import_deps_cmd, name="deps")


# All command aliases are registered manually above to ensure compatibility with Click <8.1.0 and for explicit aliasing.

cli = create_main

# Register all commands
register_commands(cli)

if __name__ == "__main__":
    cli()
