"""Quick add commands for different package managers."""

import asyncio
import json
import logging
from typing import Dict, Optional, Tuple

import click
from rich.progress import Progress, SpinnerColumn, TextColumn

from docvault.core.exceptions import LibraryNotFoundError
from docvault.core.library_manager import LibraryManager
from docvault.models.registry import (
    add_library_entry,
    find_library,
    list_documentation_sources,
)
from docvault.utils.console import console

logger = logging.getLogger(__name__)


# Mapping of package managers to their documentation sources
PACKAGE_MANAGER_ALIASES = {
    "pypi": "pypi",
    "pip": "pypi",
    "python": "pypi",
    "npm": "npm",
    "node": "npm",
    "nodejs": "npm",
    "gem": "gem",
    "ruby": "gem",
    "rubygems": "gem",
    "hex": "hex",
    "elixir": "hex",
    "erlang": "hex",
    "go": "go",
    "golang": "go",
    "cargo": "crates",
    "rust": "crates",
    "crates": "crates",
    "composer": "packagist",
    "php": "packagist",
    "packagist": "packagist",
}


def get_package_manager_info(alias: str) -> Tuple[str, str]:
    """Get package manager name and display name from alias."""
    pm = PACKAGE_MANAGER_ALIASES.get(alias.lower())
    if not pm:
        return None, None

    display_names = {
        "pypi": "PyPI",
        "npm": "npm",
        "gem": "RubyGems",
        "hex": "Hex",
        "go": "Go",
        "crates": "crates.io",
        "packagist": "Packagist",
    }

    return pm, display_names.get(pm, pm)


async def quick_add_package(
    package_manager: str,
    package_name: str,
    version: Optional[str] = None,
    force: bool = False,
) -> Optional[Dict]:
    """Quick add a package from a specific package manager."""
    # Get documentation source by package manager
    sources = list_documentation_sources(active_only=True)
    source = None
    for s in sources:
        if s.package_manager == package_manager:
            source = s
            break

    if not source:
        console.print(
            f"[red]Error:[/] Package manager '{package_manager}' not configured"
        )
        console.print(
            "[dim]Run 'dv registry populate' to add default package managers[/]"
        )
        return None

    # Check if library already exists
    existing = find_library(package_name, version, source.id)
    if existing and not force:
        console.print(
            f"[yellow]Library '{package_name}' already exists in {source.name} registry[/]"
        )
        console.print("[dim]Use --force to re-fetch documentation[/]")

        # Try to fetch docs if they don't exist locally
        manager = LibraryManager()
        try:
            docs = await manager.get_library_docs(package_name, version or "latest")
            if docs:
                console.print("[green]Documentation already available locally[/]")
                return docs[0] if docs else None
        except Exception:
            pass

        return None

    # Try to fetch documentation
    manager = LibraryManager()

    try:
        # First, check if we can find the package documentation
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Searching for {package_name} documentation...",
                total=None,
            )

            # Try to get documentation
            docs = await manager.get_library_docs(package_name, version or "latest")

            if docs:
                progress.update(
                    task, completed=1, description="[green]Found documentation!"
                )

                # Add to registry if not exists or if force update
                if not existing or force:
                    add_library_entry(
                        name=package_name,
                        version=version or "latest",
                        doc_url=docs[0]["url"],
                        source_id=source.id,
                        package_name=package_name,
                    )

                return docs[0]
            else:
                progress.update(
                    task, completed=1, description="[yellow]No documentation found"
                )
                return None

    except LibraryNotFoundError:
        console.print(
            f"[red]Error:[/] Package '{package_name}' not found in {source.name}"
        )
        return None
    except Exception as e:
        console.print(f"[red]Error:[/] Failed to fetch documentation: {e}")
        logger.exception(f"Error fetching {package_name} from {source.name}")
        return None


@click.group(name="add-quick", help="Quick add commands for package managers")
def quick_add_group():
    """Quick add commands for various package managers."""
    pass


def create_quick_add_command(package_manager: str, display_name: str):
    """Create a quick add command for a specific package manager."""

    @click.command(
        name=f"add-{package_manager}",
        help=f"Quick add documentation from {display_name}",
    )
    @click.argument("package_name")
    @click.option("--version", "-v", help="Package version (default: latest)")
    @click.option("--force", "-f", is_flag=True, help="Force re-fetch even if exists")
    @click.option(
        "--format",
        type=click.Choice(["text", "json"], case_sensitive=False),
        default="text",
        help="Output format",
    )
    def quick_add_cmd(package_name, version, force, format):
        """Quick add a package from a specific package manager."""
        # Run the async function
        doc = asyncio.run(
            quick_add_package(package_manager, package_name, version, force)
        )

        if format == "json":
            if doc:
                print(
                    json.dumps(
                        {
                            "status": "success",
                            "package": package_name,
                            "package_manager": display_name,
                            "version": version or "latest",
                            "document": {
                                "id": doc.get("id"),
                                "title": doc.get("title"),
                                "url": doc.get("url"),
                            },
                        },
                        indent=2,
                    )
                )
            else:
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "package": package_name,
                            "package_manager": display_name,
                            "error": "Documentation not found",
                        },
                        indent=2,
                    )
                )
        else:
            if doc:
                console.print(
                    f"[green]✓[/] Successfully added {package_name} documentation from {display_name}"
                )
                console.print(f"  Document ID: {doc.get('id')}")
                console.print(f"  Title: {doc.get('title')}")
                console.print(f"  URL: {doc.get('url')}")
                console.print(f"\n[dim]View with:[/] [cyan]dv read {doc.get('id')}[/]")
            else:
                console.print(
                    f"[red]✗[/] Failed to add {package_name} documentation from {display_name}"
                )

    # Set the function name to avoid conflicts
    quick_add_cmd.__name__ = f"add_{package_manager}_cmd"
    return quick_add_cmd


# Create commands for each package manager
for pm_alias, pm_name in [
    ("pypi", "PyPI"),
    ("npm", "npm"),
    ("gem", "RubyGems"),
    ("hex", "Hex"),
    ("go", "Go"),
    ("crates", "crates.io"),
    ("composer", "Packagist"),
]:
    cmd = create_quick_add_command(pm_alias, pm_name)
    quick_add_group.add_command(cmd)


@click.command(name="add-pm", help="Quick add from any package manager")
@click.argument("package_spec")
@click.option("--version", "-v", help="Package version (default: latest)")
@click.option("--force", "-f", is_flag=True, help="Force re-fetch even if exists")
@click.option(
    "--format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format",
)
def add_package_manager(package_spec, version, force, format):
    """Quick add from any package manager using pm:package syntax.

    Examples:
        dv add-pm pypi:requests
        dv add-pm npm:express
        dv add-pm gem:rails --version 7.0
        dv add-pm rust:tokio
    """
    # Parse package spec
    if ":" not in package_spec:
        console.print("[red]Error:[/] Invalid format. Use 'pm:package' syntax")
        console.print("[dim]Examples: pypi:requests, npm:express, gem:rails[/]")
        return

    pm_alias, package_name = package_spec.split(":", 1)
    pm_name, display_name = get_package_manager_info(pm_alias)

    if not pm_name:
        console.print(f"[red]Error:[/] Unknown package manager '{pm_alias}'")
        console.print("[dim]Supported: pypi, npm, gem, hex, go, crates, composer[/]")
        return

    # Run the async function
    doc = asyncio.run(quick_add_package(pm_name, package_name, version, force))

    if format == "json":
        if doc:
            print(
                json.dumps(
                    {
                        "status": "success",
                        "package": package_name,
                        "package_manager": display_name,
                        "version": version or "latest",
                        "document": {
                            "id": doc.get("id"),
                            "title": doc.get("title"),
                            "url": doc.get("url"),
                        },
                    },
                    indent=2,
                )
            )
        else:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "package": package_name,
                        "package_manager": display_name,
                        "error": "Documentation not found",
                    },
                    indent=2,
                )
            )
    else:
        if doc:
            console.print(
                f"[green]✓[/] Successfully added {package_name} documentation from {display_name}"
            )
            console.print(f"  Document ID: {doc.get('id')}")
            console.print(f"  Title: {doc.get('title')}")
            console.print(f"  URL: {doc.get('url')}")
            console.print(f"\n[dim]View with:[/] [cyan]dv read {doc.get('id')}[/]")
        else:
            console.print(
                f"[red]✗[/] Failed to add {package_name} documentation from {display_name}"
            )
