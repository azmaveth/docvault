import asyncio
import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from docvault.core.storage import read_markdown
from docvault.db import operations
from docvault.project import ProjectManager
from docvault.version import __version__

# Export all commands
__all__ = [
    "version_cmd",
    "_scrape",
    "import_cmd",
    "_delete",
    "remove_cmd",
    "list_cmd",
    "read_cmd",
    "search_cmd",
    "search_lib",
    "search_text",
    "index_cmd",
    "config_cmd",
    "init_cmd",
    "backup",
    "import_backup",
    "import_deps_cmd",
    "serve_cmd",
]

console = Console()


@click.command("version", help="Show DocVault version")
def version_cmd():
    """Show DocVault version"""
    click.echo(f"DocVault version {__version__}")


@click.command("import-deps")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--project-type",
    type=click.Choice(["auto", "python", "nodejs", "rust", "go", "ruby", "php"]),
    default="auto",
    help="Project type (default: auto-detect)",
)
@click.option(
    "--include-dev/--no-include-dev",
    default=False,
    help="Include development dependencies (if supported by project type)",
)
@click.option("--force", is_flag=True, help="Force re-import of existing documentation")
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text)",
)
def import_deps_cmd(path, project_type, include_dev, force, format):
    """Import documentation for all dependencies in a project.

    Automatically detects and parses dependency files in the project directory
    and imports documentation for each dependency.

    Examples:
        # Import dependencies from current directory
        dv import-deps

        # Import dependencies from a specific directory
        dv import-deps /path/to/project

        # Force re-import of all dependencies
        dv import-deps --force

        # Output results as JSON
        dv import-deps --format json
    """
    import json

    from rich.console import Console
    from rich.table import Table

    console = Console()

    try:
        if project_type == "auto":
            project_type = None

        results = ProjectManager.import_documentation(
            path=path, project_type=project_type, include_dev=include_dev, force=force
        )

        if format == "json":
            print(json.dumps(results, indent=2))
            return

        # Print summary
        console.print(
            f"\n[bold green]✓ Successfully imported {len(results['success'])} packages[/]"
        )
        if results["skipped"]:
            console.print(
                f"[yellow]↻ Skipped {len(results['skipped'])} packages (already imported)[/]"
            )
        if results["failed"]:
            console.print(
                f"[red]✗ Failed to import {len(results['failed'])} packages[/]"
            )

        # Show failed imports if any
        if results["failed"]:
            console.print("\n[bold]Failed imports:[/]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Package", style="dim")
            table.add_column("Version")
            table.add_column("Reason")

            for fail in results["failed"]:
                table.add_row(
                    fail["name"],
                    fail.get("version", ""),
                    fail.get("reason", "Unknown error"),
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        if format == "json":
            print(json.dumps({"error": str(e), "status": "error"}, indent=2))
        return 1

    return 0


@click.command()
@click.argument("url")
@click.option("--depth", default=1, help="Scraping depth (1=single page)")
@click.option(
    "--max-links",
    default=None,
    type=int,
    help="Maximum number of links to follow per page",
)
@click.option("--quiet", is_flag=True, help="Reduce output verbosity")
@click.option(
    "--strict-path",
    is_flag=True,
    default=True,
    help="Only follow links within same URL hierarchy",
)
def _scrape(url, depth, max_links, quiet, strict_path):
    """Scrape and store documentation from URL"""
    import socket
    import ssl
    from urllib.parse import urlparse

    import aiohttp

    if quiet:
        logging.basicConfig(level=logging.WARNING)
    else:
        console.print(f"Scraping [bold blue]{url}[/] with depth {depth}...")
        logging.basicConfig(level=logging.INFO)

    # Validate URL format
    try:
        parsed_url = urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            console.print(
                "❌ Error: Invalid URL format. Please provide a complete URL including http:// or https://",
                style="bold red",
            )
            return
    except Exception as e:
        console.print(f"❌ Error: Invalid URL - {str(e)}", style="bold red")
        return

    try:
        logging.getLogger("docvault").setLevel(logging.ERROR)
        from docvault.core.scraper import get_scraper

        with console.status("[bold blue]Scraping documents...[/]", spinner="dots"):
            try:
                scraper = get_scraper()
                document = asyncio.run(
                    scraper.scrape_url(
                        url, depth, max_links=max_links, strict_path=strict_path
                    )
                )
            except aiohttp.ClientError as e:
                if "Cannot connect to host" in str(e):
                    console.print(
                        "❌ Error: Could not connect to the server. Please check your internet connection and try again.",
                        style="bold red",
                    )
                    return
                elif "SSL" in str(e):
                    console.print(
                        "❌ Error: SSL certificate verification failed. The website might be using a self-signed certificate.",
                        style="bold red",
                    )
                    console.print(
                        "  Try using a different URL or check if the website is accessible from your browser.",
                        style="yellow",
                    )
                    return
                else:
                    raise
            except ssl.SSLError as e:
                console.print(
                    "❌ Error: SSL certificate verification failed.", style="bold red"
                )
                console.print(f"  Details: {str(e)}", style="yellow")
                console.print(
                    "  This might happen with self-signed certificates or outdated SSL configurations.",
                    style="yellow",
                )
                return
            except socket.gaierror:
                console.print(
                    "❌ Error: Could not resolve the hostname. Please check the URL and your network connection.",
                    style="bold red",
                )
                return
            except asyncio.TimeoutError:
                console.print(
                    "❌ Error: The request timed out. The server might be taking too long to respond.",
                    style="bold red",
                )
                console.print(
                    "  You can try again later or check if the website is currently available.",
                    style="yellow",
                )
                return
            except Exception as e:
                if "404" in str(e) or "Not Found" in str(e):
                    console.print(
                        "❌ Error: The requested page was not found (404). Please check the URL and try again.",
                        style="bold red",
                    )
                    return
                elif "403" in str(e) or "Forbidden" in str(e):
                    console.print(
                        "❌ Error: Access to this resource is forbidden (403). You might need authentication.",
                        style="bold red",
                    )
                    return
                elif "401" in str(e) or "Unauthorized" in str(e):
                    console.print(
                        "❌ Error: Authentication required. This resource needs credentials.",
                        style="bold red",
                    )
                    return
                elif "429" in str(e) or "Too Many Requests" in str(e):
                    console.print(
                        "❌ Error: Too many requests. The server is rate limiting your connection.",
                        style="bold red",
                    )
                    console.print(
                        "  Please wait a few minutes and try again.", style="yellow"
                    )
                    return
                else:
                    raise

        if document:
            table = Table(title=f"Scraping Results for {url}")
            table.add_column("Metric", style="green")
            table.add_column("Count", style="cyan", justify="right")

            table.add_row("Pages Scraped", str(scraper.stats["pages_scraped"]))
            table.add_row("Pages Skipped", str(scraper.stats["pages_skipped"]))
            table.add_row("Segments Created", str(scraper.stats["segments_created"]))
            table.add_row(
                "Total Pages",
                str(scraper.stats["pages_scraped"] + scraper.stats["pages_skipped"]),
            )

            console.print(table)
            console.print(
                f"✅ Successfully imported: [bold green]{document['title']}[/] (ID: {document['id']})"
            )
        else:
            console.print(
                "❌ Failed to scrape document. The page might not contain any indexable content.",
                style="bold red",
            )
            console.print(
                "  Try checking the URL in a web browser to verify it's accessible.",
                style="yellow",
            )

    except KeyboardInterrupt:
        console.print("\n🛑 Scraping was cancelled by the user", style="yellow")
    except Exception as e:
        console.print(f"❌ An unexpected error occurred: {str(e)}", style="bold red")
        if not quiet:
            import traceback

            console.print("\n[bold]Technical details:[/]")
            console.print(traceback.format_exc(), style="dim")


@click.command(
    name="import", help="Import documentation from a URL (aliases: add, scrape, fetch)"
)
@click.argument("url")
@click.option("--depth", default=1, help="Scraping depth (1=single page)")
@click.option(
    "--max-links",
    default=None,
    type=int,
    help="Maximum number of links to follow per page",
)
@click.option("--quiet", is_flag=True, help="Reduce output verbosity")
@click.option(
    "--strict-path",
    is_flag=True,
    default=True,
    help="Only follow links within same URL hierarchy",
)
def import_cmd(url, depth, max_links, quiet, strict_path):
    """Import documentation from a URL into the vault.

    Examples:
        dv add https://docs.python.org/3/library/
        dv import https://elixir-lang.org/docs --depth=2
    """
    import socket
    import ssl
    from urllib.parse import urlparse

    import aiohttp

    # Set up logging
    if quiet:
        logging.basicConfig(level=logging.WARNING)
    else:
        console.print(f"🌐 Importing [bold blue]{url}[/] with depth {depth}...")
        logging.basicConfig(level=logging.INFO)

    # Validate URL format
    try:
        parsed_url = urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            console.print(
                "❌ Error: Invalid URL format. Please include http:// or https://",
                style="bold red",
            )
            return
    except Exception as e:
        console.print(f"❌ Error: Invalid URL - {str(e)}", style="bold red")
        return

    try:
        logging.getLogger("docvault").setLevel(logging.ERROR)
        from docvault.core.scraper import get_scraper

        with console.status("[bold blue]Importing documents...[/]", spinner="dots"):
            try:
                scraper = get_scraper()
                document = asyncio.run(
                    scraper.scrape_url(
                        url, depth, max_links=max_links, strict_path=strict_path
                    )
                )
            except aiohttp.ClientError as e:
                if "Cannot connect to host" in str(e):
                    console.print(
                        "❌ Error: Could not connect to the server. Please check your internet connection and try again.",
                        style="bold red",
                    )
                    return
                elif "SSL" in str(e):
                    console.print(
                        "❌ Error: SSL certificate verification failed. The website might be using a self-signed certificate.",
                        style="bold red",
                    )
                    console.print(
                        "  Try using a different URL or check if the website is accessible from your browser.",
                        style="yellow",
                    )
                    return
                else:
                    raise
            except ssl.SSLError as e:
                console.print(
                    "❌ Error: SSL certificate verification failed.", style="bold red"
                )
                console.print(f"  Details: {str(e)}", style="yellow")
                console.print(
                    "  This might happen with self-signed certificates or outdated SSL configurations.",
                    style="yellow",
                )
                return
            except socket.gaierror:
                console.print(
                    "❌ Error: Could not resolve the hostname. Please check the URL and your network connection.",
                    style="bold red",
                )
                return
            except asyncio.TimeoutError:
                console.print(
                    "❌ Error: The request timed out. The server might be taking too long to respond.",
                    style="bold red",
                )
                console.print(
                    "  You can try again later or check if the website is currently available.",
                    style="yellow",
                )
                return
            except Exception as e:
                if "404" in str(e) or "Not Found" in str(e):
                    console.print(
                        "❌ Error: The requested page was not found (404). Please check the URL and try again.",
                        style="bold red",
                    )
                    return
                elif "403" in str(e) or "Forbidden" in str(e):
                    console.print(
                        "❌ Error: Access to this resource is forbidden (403). You might need authentication.",
                        style="bold red",
                    )
                    console.print(
                        "  Some documentation sites require authentication or have rate limiting.",
                        style="yellow",
                    )
                    return
                elif "401" in str(e) or "Unauthorized" in str(e):
                    console.print(
                        "❌ Error: Authentication required. This resource needs credentials.",
                        style="bold red",
                    )
                    return
                elif "429" in str(e) or "Too Many Requests" in str(e):
                    console.print(
                        "❌ Error: Too many requests. The server is rate limiting your connection.",
                        style="bold red",
                    )
                    console.print(
                        "  Please wait a few minutes and try again.", style="yellow"
                    )
                    return
                else:
                    raise

        if document:
            table = Table(title=f"Import Results for {url}")
            table.add_column("Metric", style="green")
            table.add_column("Count", style="cyan", justify="right")
            table.add_row("Pages Scraped", str(scraper.stats["pages_scraped"]))
            table.add_row("Pages Skipped", str(scraper.stats["pages_skipped"]))
            table.add_row("Segments Created", str(scraper.stats["segments_created"]))
            table.add_row(
                "Total Pages",
                str(scraper.stats["pages_scraped"] + scraper.stats["pages_skipped"]),
            )
            console.print(table)
            console.print(
                f"✅ Successfully imported: [bold green]{document['title']}[/] (ID: {document['id']})"
            )

            # Provide helpful next steps
            if not quiet:
                console.print("\n[bold]Next steps:[/]")
                console.print(
                    "  • Search content: [cyan]dv search 'your search term'[/]"
                )
                console.print(f"  • View document: [cyan]dv read {document['id']}[/]")
                console.print("  • List all documents: [cyan]dv list[/]")
        else:
            console.print(
                "❌ Failed to import document. The page might not contain any indexable content.",
                style="bold red",
            )
            console.print(
                "  Try checking the URL in a web browser to verify it's accessible.",
                style="yellow",
            )

    except KeyboardInterrupt:
        console.print("\n🛑 Import was cancelled by the user", style="yellow")
    except Exception as e:
        console.print(f"❌ An unexpected error occurred: {str(e)}", style="bold red")
        if not quiet:
            import traceback

            console.print("\n[bold]Technical details:[/]")
            console.print(traceback.format_exc(), style="dim")


@click.command()
@click.argument("document_ids", nargs=-1, type=int, required=True)
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def _delete(document_ids, force):
    """Delete documents from the vault"""
    if not document_ids:
        console.print("❌ No document IDs provided", style="bold red")
        return

    documents_to_delete = []
    for doc_id in document_ids:
        doc = operations.get_document(doc_id)
        if doc:
            documents_to_delete.append(doc)
        else:
            console.print(f"⚠️ Document ID {doc_id} not found", style="yellow")

    if not documents_to_delete:
        console.print("No valid documents to delete")
        return

    table = Table(title=f"Documents to Delete ({len(documents_to_delete)})")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="red")
    table.add_column("URL", style="blue")

    for doc in documents_to_delete:
        table.add_row(str(doc["id"]), doc["title"] or "Untitled", doc["url"])

    console.print(table)

    if not force and not click.confirm(
        "Are you sure you want to delete these documents?", default=False
    ):
        console.print("Deletion cancelled")
        return

    for doc in documents_to_delete:
        try:
            html_path = Path(doc["html_path"])
            md_path = Path(doc["markdown_path"])

            if html_path.exists():
                html_path.unlink()
            if md_path.exists():
                md_path.unlink()

            operations.delete_document(doc["id"])
            console.print(f"✅ Deleted: {doc['title']} (ID: {doc['id']})")
        except Exception as e:
            console.print(
                f"❌ Error deleting document {doc['id']}: {e}", style="bold red"
            )

    console.print(f"Deleted {len(documents_to_delete)} document(s)")


@click.command(name="remove", help="Remove documents from the vault (alias: rm)")
@click.argument("id_ranges", required=True)
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def remove_cmd(id_ranges, force):
    """Remove documents from the vault by ID or range. Examples:
    dv remove 1,2,3        # Remove documents 1, 2, and 3
    dv remove 1-5          # Remove documents 1 through 5
    dv remove 1-5,7,9-11   # Remove documents 1-5, 7, and 9-11
    """
    document_ids = []
    # Parse the id_ranges argument
    ranges = id_ranges.replace(" ", "").split(",")
    for r in ranges:
        if "-" in r:
            try:
                start, end = map(int, r.split("-"))
                document_ids.extend(range(start, end + 1))
            except ValueError:
                console.print(
                    f"⚠️ Invalid range format: {r}. Expected 'start-end'", style="yellow"
                )
                continue
        else:
            try:
                document_ids.append(int(r))
            except ValueError:
                console.print(
                    f"⚠️ Invalid document ID: {r}. Must be an integer.", style="yellow"
                )
                continue
    if not document_ids:
        console.print("❌ No valid document IDs provided", style="bold red")
        return
    documents_to_delete = []
    for doc_id in document_ids:
        doc = operations.get_document(doc_id)
        if doc:
            documents_to_delete.append(doc)
        else:
            console.print(f"⚠️ Document ID {doc_id} not found", style="yellow")
    if not documents_to_delete:
        console.print("No valid documents to delete")
        return
    table = Table(title=f"Documents to Delete ({len(documents_to_delete)})")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="red")
    table.add_column("URL", style="blue")
    for doc in documents_to_delete:
        table.add_row(str(doc["id"]), doc["title"] or "Untitled", doc["url"])
    console.print(table)
    if not force and not click.confirm(
        "Are you sure you want to delete these documents?", default=False
    ):
        console.print("Deletion cancelled")
        return
    for doc in documents_to_delete:
        try:
            html_path = Path(doc["html_path"])
            md_path = Path(doc["markdown_path"])

            if html_path.exists():
                html_path.unlink()
            if md_path.exists():
                md_path.unlink()

            operations.delete_document(doc["id"])
            console.print(f"✅ Deleted: {doc['title']} (ID: {doc['id']})")
        except Exception as e:
            console.print(
                f"❌ Error deleting document {doc['id']}: {e}", style="bold red"
            )
    console.print(f"Deleted {len(documents_to_delete)} document(s)")


@click.command(name="list", help="List all documents in the vault (alias: ls)")
@click.option("--filter", help="Filter documents by title or URL")
def list_cmd(filter):
    """List all documents in the vault. Use --filter to search titles/URLs."""
    from docvault.db.operations import list_documents

    docs = list_documents(filter_text=filter)
    if not docs:
        console.print("No documents found")
        return
    table = Table(title="Documents in Vault")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="green")
    table.add_column("URL", style="blue")
    table.add_column("Version", style="magenta")
    table.add_column("Content Hash", style="yellow")
    table.add_column("Scraped At", style="cyan")
    for doc in docs:
        table.add_row(
            str(doc["id"]),
            doc["title"] or "Untitled",
            doc["url"],
            doc.get("version", "unknown"),
            doc.get("content_hash", "") or "",
            doc["scraped_at"],
        )
    console.print(table)


@click.command(name="read", help="Read a document from the vault (alias: cat)")
@click.argument("document_id", type=int)
@click.option(
    "--format",
    type=click.Choice(["markdown", "html"]),
    default="markdown",
    help="Output format",
)
def read_cmd(document_id, format):
    """Read a document from the vault. Use --format for markdown or HTML."""
    from docvault.core.storage import open_html_in_browser, read_markdown
    from docvault.db.operations import get_document

    doc = get_document(document_id)
    if not doc:
        console.print(f"❌ Document not found: {document_id}", style="bold red")
        return
    if format == "html":
        open_html_in_browser(doc["html_path"])
    else:
        content = read_markdown(doc["markdown_path"])
        console.print(f"# {doc['title']}\n", style="bold green")
        console.print(content)


class DefaultGroup(click.Group):
    def get_command(self, ctx, cmd_name):
        import logging

        logging.getLogger(__name__).debug(
            f"[search.DefaultGroup] cmd_name={cmd_name!r}, ctx.args={ctx.args!r}, ctx.protected_args={getattr(ctx, 'protected_args', None)!r}"
        )
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        # If the command is not found, treat as the default subcommand
        if self.name == "search" and cmd_name:
            if cmd_name in self.commands:
                return click.Group.get_command(self, ctx, cmd_name)
            # Else treat as free-form query for the default 'text' subcommand
            query = " ".join([cmd_name] + ctx.args)
            logging.getLogger(__name__).debug(
                f"[search.DefaultGroup] forwarding to 'text' with query={query!r}"
            )
            ctx.protected_args = ["text"]
            ctx.args = [query]
            return click.Group.get_command(self, ctx, "text")
        return None


@click.group(
    cls=DefaultGroup,
    name="search",
    help="Search documents in the vault (alias: find, default command)",
    invoke_without_command=True,
)
@click.pass_context
def search_cmd(ctx):
    """Search documents or libraries. Usage:
    dv search <query>
    dv search lib <library>
    dv search --library <library>
    """
    if ctx.invoked_subcommand is None and not ctx.args:
        click.echo(ctx.get_help())


@search_cmd.command("lib")
@click.argument("library_spec", required=True)
@click.option("--version", help="Library version (default: latest)")
@click.option(
    "--format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (text or json)",
)
@click.option(
    "--timeout", type=int, default=30, help="Timeout in seconds for the search"
)
def search_lib(library_spec, version, format, timeout):
    """Search library documentation (formerly 'lookup').

    The library can be specified with an optional version using the @ symbol:
      dv search lib requests@2.31.0
      dv search lib django@4.2

    Or you can use the --version flag:
      dv search lib django --version 4.2

    Or just the library name for the latest version:
      dv search lib fastapi

    Examples:
        # Different ways to specify versions
        dv search lib requests
        dv search lib django@4.2
        dv search lib "django" --version 4.2

        # Output formats
        dv search lib fastapi --format json

        # With timeout
        dv search lib numpy --timeout 60
    """
    import asyncio
    import json
    from typing import Any, Dict, List, Tuple

    from rich.progress import Progress, SpinnerColumn, TextColumn

    def parse_library_spec(spec: str) -> Tuple[str, str]:
        """Parse library specification into (name, version) tuple.

        Supports formats:
        - library
        - library@version
        """
        if "@" in spec:
            name, version = spec.split("@", 1)
            return name.strip(), version.strip()
        return spec.strip(), "latest"

    from docvault.core.exceptions import LibraryNotFoundError, VersionNotFoundError
    from docvault.core.library_manager import LibraryManager

    # Parse the library specification and handle version overrides
    library_name, version_from_spec = parse_library_spec(library_spec)
    version = version or version_from_spec

    # If version is still None or empty, default to 'latest'
    version = version or "latest"

    async def fetch_documentation() -> List[Dict[str, Any]]:
        """Fetch documentation with progress indication."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            # Show version in the progress message if it's not 'latest'
            version_display = f" {version}" if version != "latest" else ""
            task = progress.add_task(
                f"[cyan]Searching for {library_name}{'@' + version_display if version_display else ''} documentation...",
                total=None,
            )

            try:
                manager = LibraryManager()
                docs = await manager.get_library_docs(library_name, version or "latest")
                progress.update(task, completed=1, description="[green]Done!")
                return docs
            except LibraryNotFoundError:
                progress.stop()
                error_msg = f"Library '{library_name}' not found"
                if version != "latest":
                    error_msg += f" (version: {version})"
                console.print(f"[red]Error:[/] {error_msg}")
                return []
            except VersionNotFoundError as e:
                progress.stop()
                error_msg = str(e)
                if "@" in error_msg and version != "latest":
                    error_msg = error_msg.replace("version", f"version {version}")
                console.print(f"[red]Error:[/] {error_msg}")
                return []
            except Exception as e:
                progress.stop()
                error_msg = str(e)
                console.print(f"[red]Error fetching documentation:[/] {error_msg}")
                if format == "json":
                    print(
                        json.dumps(
                            {
                                "status": "error",
                                "error": error_msg,
                                "library": library_name,
                                "version": version,
                            },
                            indent=2,
                        )
                    )
                return []

    def format_json_output(docs: List[Dict[str, Any]]) -> None:
        """Format and print results in JSON format."""
        json_results = [
            {
                "title": doc.get("title") or "Untitled",
                "url": doc.get("url", ""),
                "version": doc.get("resolved_version", "unknown"),
                "description": doc.get("description", ""),
            }
            for doc in docs
        ]

        output = {
            "status": "success",
            "count": len(json_results),
            "library": library_name,
            "version": version or "latest",
            "results": json_results,
        }
        print(json.dumps(output, indent=2))

    def format_text_output(docs: List[Dict[str, Any]]) -> None:
        """Format and print results in a table."""
        if not docs:
            console.print(f"[yellow]No documentation found for {library_name}[/]")
            return

        from urllib.parse import urlparse

        from rich.table import Table

        # Create a more informative title with version if specified
        title_parts = [f"Documentation for {library_name}"]
        if version != "latest":
            title_parts.append(f"(version {version})")

        table = Table(
            title=" ".join(title_parts).strip(),
            show_header=True,
            header_style="bold magenta",
            expand=True,
        )

        table.add_column("Title", style="green", no_wrap=True)
        table.add_column("URL", style="blue")
        table.add_column("Version", style="cyan", justify="right")

        for doc in docs:
            title = doc.get("title", "Untitled")
            url = doc.get("url", "")

            # Truncate long URLs for display
            if len(url) > 50:
                parsed = urlparse(url)
                short_url = f"{parsed.netloc}...{parsed.path[-30:]}"
            else:
                short_url = url

            table.add_row(title, short_url, doc.get("resolved_version", "unknown"))

        console.print(table)

        if len(docs) > 0 and "url" in docs[0]:
            console.print(
                "\n[dim]Tip: Use 'dv add <url>' to import documentation locally[/]"
            )

    try:
        # Run the async function with timeout
        docs = asyncio.run(asyncio.wait_for(fetch_documentation(), timeout=timeout))

        if format == "json":
            format_json_output(docs)
        else:
            format_text_output(docs)

    except asyncio.TimeoutError:
        console.print(
            f"[red]Error:[/] Search timed out after {timeout} seconds. "
            "Try increasing the timeout with --timeout"
        )
        if format == "json":
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error": f"Search timed out after {timeout} seconds",
                        "library": library_name,
                        "version": version or "latest",
                    },
                    indent=2,
                )
            )


@search_cmd.command("text")
@click.argument("query", required=False)
@click.option("--limit", default=5, help="Maximum number of results to return")
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.option("--text-only", is_flag=True, help="Use only text search (no embeddings)")
@click.option("--context", default=2, help="Number of context lines to show")
@click.option(
    "--format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (text or json)",
)
@click.option(
    "--min-score", type=float, default=0.0, help="Minimum similarity score (0.0 to 1.0)"
)
@click.option("--version", help="Filter by document version")
@click.option("--library", is_flag=True, help="Only show library documentation")
@click.option("--title-contains", help="Filter by document title containing text")
@click.option("--updated-after", help="Filter by last updated after date (YYYY-MM-DD)")
def search_text(
    query,
    limit,
    debug,
    text_only,
    context,
    format,
    min_score,
    version,
    library,
    title_contains,
    updated_after,
):
    """Search documents in the vault with metadata filtering.

    Examples:
        dv search "python sqlite" --version 3.10
        dv search --library --title-contains "API"
        dv search --updated-after 2023-01-01

    If no query is provided, returns random documents matching the filters.
    """

    print(f"[DEBUG search_text] query={query!r} sys.argv={sys.argv}")
    """Search documents in the vault (default subcommand)."""
    import asyncio
    import logging

    import numpy as np

    from docvault.core.embeddings import generate_embeddings
    from docvault.core.embeddings import search as search_docs

    if debug:
        log_handler = logging.StreamHandler()
        log_handler.setLevel(logging.DEBUG)
        logging.getLogger("docvault").setLevel(logging.DEBUG)
        logging.getLogger("docvault").addHandler(log_handler)
        console.print("[yellow]Debug mode enabled[/]")
    try:
        conn = sqlite3.connect(":memory:")
        try:
            conn.enable_load_extension(True)
            conn.load_extension("sqlite_vec")
            logging.getLogger(__name__).info("sqlite-vec extension loaded successfully")
        except sqlite3.OperationalError as e:
            logging.getLogger(__name__).warning(
                "sqlite-vec extension cannot be loaded: %s. Falling back to text search.",
                e,
            )
        finally:
            conn.close()
    except Exception as e:
        if debug:
            logging.getLogger(__name__).exception("Error checking sqlite-vec: %s", e)
    # Prepare document filters
    doc_filter = {}
    if version:
        doc_filter["version"] = version
    if library:
        doc_filter["is_library_doc"] = True
    if title_contains:
        doc_filter["title_contains"] = title_contains
    if updated_after:
        try:
            from datetime import datetime

            # Parse and reformat date to ensure it's in the correct format
            parsed_date = datetime.strptime(updated_after, "%Y-%m-%d")
            doc_filter["updated_after"] = parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            console.print(
                "[red]Error:[/] Invalid date format. Use YYYY-MM-DD", style="bold"
            )
            return

    status_msg = (
        f"[bold blue]Searching for '{query}'...[/]"
        if query
        else "[bold blue]Searching documents...[/]"
    )
    with console.status(status_msg, spinner="dots"):
        results = asyncio.run(
            search_docs(
                query,
                limit=limit,
                text_only=text_only,
                min_score=min_score,
                doc_filter=doc_filter if doc_filter else None,
            )
        )
    if not results:
        if format == "json":
            import json

            print(
                json.dumps(
                    {"status": "success", "count": 0, "results": [], "query": query}
                )
            )
        else:
            console.print("No matching documents found")
        return

    if format == "json":
        import json

        # Prepare results for JSON output
        json_results = []
        for result in results:
            json_results.append(
                {
                    "score": float(f"{result['score']:.2f}"),
                    "title": result["title"] or "Untitled",
                    "url": result["url"],
                    "content": result["content"],
                    "content_preview": result["content"][:200]
                    + ("..." if len(result["content"]) > 200 else ""),
                    "document_id": result.get("document_id"),
                    "segment_id": result.get("segment_id"),
                }
            )

        print(
            json.dumps(
                {
                    "status": "success",
                    "count": len(json_results),
                    "query": query,
                    "results": json_results,
                },
                indent=2,
            )
        )
        return

    # Default text output
    console.print(f"Found {len(results)} results for '{query}'")
    if debug and not text_only:
        console.print("[bold]Query embedding diagnostics:[/]")
        try:
            embedding_bytes = asyncio.run(generate_embeddings(query))
            embedding_array = np.frombuffer(embedding_bytes, dtype=np.float32)
            console.print(f"Embedding dimensions: {len(embedding_array)}")
            console.print(f"Embedding sample: {embedding_array[:5]}...")
            console.print(
                f"Embedding min/max: {embedding_array.min():.4f}/{embedding_array.max():.4f}"
            )
            console.print(
                f"Embedding mean/std: {embedding_array.mean():.4f}/{embedding_array.std():.4f}"
            )
        except Exception as e:
            console.print(f"[red]Error analyzing embedding: {e}")

    from collections import defaultdict

    # Group results by document and section
    doc_results = defaultdict(
        lambda: {
            "title": None,
            "url": None,
            "version": None,
            "updated_at": None,
            "is_library_doc": False,
            "library_name": None,
            "sections": defaultdict(list),
        }
    )

    for result in results:
        doc_id = result["document_id"]
        doc = doc_results[doc_id]
        doc["title"] = result.get("title") or "Untitled"
        doc["url"] = result.get("url", "")
        doc["version"] = result.get("version")
        doc["updated_at"] = result.get("updated_at")
        doc["is_library_doc"] = result.get("is_library_doc", False)
        doc["library_name"] = result.get("library_name")

        # Group by section path to avoid duplicate sections
        section_path = result.get("section_path", "0")
        doc["sections"][section_path].append(result)

    # Display results by document and section
    for doc_id, doc_info in doc_results.items():
        doc_title = doc_info["title"]
        doc_url = doc_info["url"]

        # Document header with total matches and metadata
        total_matches = sum(
            len(section_hits) for section_hits in doc_info["sections"].values()
        )

        # Build metadata line
        metadata_parts = []
        if doc_info["version"]:
            metadata_parts.append(f"v{doc_info['version']}")
        if doc_info["updated_at"]:
            updated = doc_info["updated_at"]
            if isinstance(updated, str):
                updated = updated.split("T")[0]  # Just show date part
            metadata_parts.append(f"updated: {updated}")
        if doc_info["is_library_doc"] and doc_info["library_name"]:
            metadata_parts.append(f"library: {doc_info['library_name']}")

        console.print(f"\n[bold green]📄 {doc_title}[/]")
        console.print(f"[blue]{doc_url}[/]")
        if metadata_parts:
            console.print(f"[dim]{' • '.join(metadata_parts)}[/]")
        console.print(
            f"[dim]Found {total_matches} matches in {len(doc_info['sections'])} sections[/]"
        )

        # Sort sections by their path for logical ordering
        sorted_sections = sorted(
            doc_info["sections"].items(),
            key=lambda x: tuple(map(int, x[0].split("."))) if x[0].isdigit() else (0,),
        )

        # Display each section with its matches
        for section_idx, (section_path, section_hits) in enumerate(sorted_sections, 1):
            # Get the best hit for section info (usually the first one)
            section_hit = section_hits[0]
            section_title = section_hit.get("section_title", "Introduction")
            section_level = section_hit.get("section_level", 1)
            indent = "  " * (section_level - 1) if section_level > 1 else ""

            # Section header with match count
            console.print(f"\n{indent}📂 [bold]{section_title}[/]")
            console.print(
                f"{indent}[dim]  {len(section_hits)} matches • Section {section_path}[/]"
            )

            # Show top 3 matches in this section
            for hit in sorted(
                section_hits, key=lambda x: x.get("score", 0), reverse=True
            )[:3]:
                content_preview = hit["content"]
                score = hit.get("score", 0)

                # Truncate and highlight the content
                if len(content_preview) > 200:
                    match_start = max(0, content_preview.lower().find(query.lower()))
                    if match_start == -1:
                        match_start = 0
                    start = max(0, match_start - 50)
                    end = min(len(content_preview), match_start + len(query) + 50)

                    # Get context around the match
                    prefix = "..." if start > 0 else ""
                    suffix = "..." if end < len(content_preview) else ""
                    content = content_preview[start:end]

                    # Highlight all query terms
                    query_terms = query.lower().split()
                    content_lower = content.lower()
                    highlighted = []
                    last_pos = 0

                    # Find and highlight each term
                    for term in query_terms:
                        pos = content_lower.find(term, last_pos)
                        if pos >= 0:
                            highlighted.append(content[last_pos:pos])
                            highlighted.append(
                                f"[bold yellow]{content[pos:pos+len(term)]}[/]"
                            )
                            last_pos = pos + len(term)

                    highlighted.append(content[last_pos:])
                    content_preview = prefix + "".join(highlighted) + suffix

                # Display the match with score
                console.print(f"{indent}  • [dim]({score:.2f})[/] {content_preview}")

            # Show navigation hints
            if section_idx < len(sorted_sections):
                next_section = sorted_sections[section_idx][1][0].get(
                    "section_title", "Next section"
                )
                console.print(f"{indent}  [dim]↓ Next: {next_section}[/]")

            console.print("")  # Add spacing between sections

        # Document footer with navigation options
        console.print("[dim]────────────────────────────────────────[/]")
        console.print(
            f"[dim]Document: {doc_title} • {len(doc_info['sections'])} sections with matches • [bold]d[/] to view document[/]"
        )

        # Add keyboard navigation hints
        if len(doc_results) > 1:
            console.print(
                "[dim]Press [bold]n[/] for next document, [bold]q[/] to quit[/]"
            )
        else:
            console.print("[dim]Press [bold]q[/] to quit[/]")

        console.print("")  # Add spacing between documents


@click.command(name="index", help="Index or re-index documents for improved search")
@click.option("--verbose", is_flag=True, help="Show detailed output")
@click.option("--force", is_flag=True, help="Force re-indexing of all documents")
@click.option(
    "--batch-size", default=10, help="Number of segments to process in one batch"
)
@click.option(
    "--rebuild-table",
    is_flag=True,
    help="Drop and recreate the vector table before indexing",
)
def index_cmd(verbose, force, batch_size, rebuild_table):
    """Index or re-index documents for improved search

    This command generates or updates embeddings for existing documents to improve search.
    Use this if you've imported documents from a backup or if search isn't working well.
    """
    from docvault.core.embeddings import generate_embeddings
    from docvault.db.operations import get_connection, list_documents

    # Ensure vector table exists (and optionally rebuild)
    conn = get_connection()
    try:
        if rebuild_table:
            try:
                conn.execute("DROP TABLE IF EXISTS document_segments_vec;")
                logging.getLogger(__name__).info(
                    "Dropped existing document_segments_vec table."
                )
            except Exception as e:
                logging.getLogger(__name__).warning(
                    "Error dropping vector table: %s", e
                )
        # Try to create the vector table if missing
        conn.execute(
            """
        CREATE VIRTUAL TABLE IF NOT EXISTS document_segments_vec USING vec(
            id INTEGER PRIMARY KEY,
            embedding BLOB,
            dims INTEGER,
            distance TEXT
        );
        """
        )
        conn.commit()
    except Exception as e:
        logging.getLogger(__name__).error(
            "Error initializing vector table.\nMake sure the sqlite-vec extension is installed and enabled."
        )
        logging.getLogger(__name__).error("Details: %s", e)
        logging.getLogger(__name__).warning("Try: pip install sqlite-vec && dv init-db")
        return
    finally:
        conn.close()

    # Get all documents
    docs = list_documents(limit=9999)  # Get all documents

    if not docs:
        console.print("No documents found to index")
        return

    console.print(f"Found {len(docs)} documents to process")

    # Process each document
    total_segments = 0
    indexed_segments = 0

    for doc in docs:
        # Get the content
        try:
            with console.status(
                f"Processing [bold blue]{doc['title']}[/]", spinner="dots"
            ):
                # Read document content
                content = read_markdown(doc["markdown_path"])

                # Split into reasonable segments
                segments = []
                current_segment = ""
                for line in content.split("\n"):
                    current_segment += line + "\n"
                    if len(current_segment) > 500 and len(current_segment.split()) > 50:
                        segments.append(current_segment)
                        current_segment = ""

                # Add final segment if not empty
                if current_segment.strip():
                    segments.append(current_segment)

                total_segments += len(segments)

                # Generate embeddings for each segment
                for i, segment in enumerate(segments):
                    # Check if we already have this segment
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id, embedding FROM document_segments WHERE document_id = ? AND content = ?",
                        (doc["id"], segment),
                    )
                    existing = cursor.fetchone()
                    conn.close()

                    if existing and not force:
                        if verbose:
                            console.print(
                                f"  Segment {i+1}/{len(segments)} already indexed"
                            )
                        continue

                    # Generate embedding
                    embedding = asyncio.run(generate_embeddings(segment))

                    # Store in database
                    if existing:
                        # Update
                        operations.update_segment_embedding(existing[0], embedding)
                    else:
                        # Create new
                        operations.add_document_segment(
                            doc["id"],
                            segment,
                            embedding,
                            segment_type="text",
                            position=i,
                        )

                    indexed_segments += 1

                    if verbose:
                        console.print(f"  Indexed segment {i+1}/{len(segments)}")

                    # Batch commit
                    if i % batch_size == 0:
                        conn = get_connection()
                        conn.commit()
                        conn.close()

            if indexed_segments > 0:
                console.print(
                    f"✅ Indexed {indexed_segments} segments for [bold green]{doc['title']}[/]"
                )

        except Exception as e:
            console.print(
                f"❌ Error processing document {doc['id']}: {e}", style="bold red"
            )

    console.print(
        f"\nIndexing complete! {indexed_segments}/{total_segments} segments processed."
    )
    console.print("You can now use improved search functionality.")
    if total_segments > 0:
        console.print(f"Coverage: {indexed_segments/total_segments:.1%}")


# Add the update_segment_embedding function to operations.py
operations.update_segment_embedding = (
    lambda segment_id, embedding: operations.get_connection()
    .execute(
        "UPDATE document_segments SET embedding = ? WHERE id = ?",
        (embedding, segment_id),
    )
    .connection.commit()
)


@click.command(name="config", help="Manage DocVault configuration")
@click.option(
    "--init", is_flag=True, help="Create a new .env file with default settings"
)
def config_cmd(init):
    """Manage DocVault configuration."""
    from docvault import config as app_config

    if init:
        env_path = Path(app_config.DEFAULT_BASE_DIR) / ".env"
        if env_path.exists():
            if not click.confirm(
                f"Configuration file already exists at {env_path}. Overwrite?"
            ):
                return
        from docvault.main import create_env_template

        template = create_env_template()
        env_path.write_text(template)
        console.print(f"✅ Created configuration file at {env_path}")
        console.print("Edit this file to customize DocVault settings")
    else:
        table = Table(title="Current Configuration")
        table.add_column("Setting", style="green")
        table.add_column("Value", style="blue")
        config_items = [
            ("Database Path", app_config.DB_PATH),
            ("Storage Path", app_config.STORAGE_PATH),
            ("Log Directory", app_config.LOG_DIR),
            ("Log Level", app_config.LOG_LEVEL),
            ("Embedding Model", app_config.EMBEDDING_MODEL),
            ("Ollama URL", app_config.OLLAMA_URL),
            ("Server Host (HOST)", app_config.HOST),
            ("Server Port (PORT)", str(app_config.PORT)),
        ]
        for name, value in config_items:
            table.add_row(name, str(value))
        console.print(table)


def make_init_cmd(name, help_text):
    @click.command(name=name, help=help_text)
    @click.option("--force", is_flag=True, help="Force recreation of database")
    def _init_cmd(force):
        """Initialize the DocVault database."""
        try:
            from docvault.db.schema import (  # late import for patching
                initialize_database,
            )

            initialize_database(force_recreate=force)
            console.print("✅ Database initialized successfully")
        except Exception as e:
            console.print(f"❌ Error initializing database: {e}", style="bold red")
            raise click.Abort()

    return _init_cmd


init_cmd = make_init_cmd("init", "Initialize the database (aliases: init-db)")


@click.command()
@click.argument("destination", type=click.Path(), required=False)
def backup(destination):
    """Backup the vault to a zip file"""
    from docvault import config

    # Default backup name with timestamp
    if not destination:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = f"docvault_backup_{timestamp}.zip"

    try:
        # Create a zip file containing the database and storage
        with console.status("[bold blue]Creating backup...[/]"):
            shutil.make_archive(
                destination.removesuffix(".zip"),  # Remove .zip as make_archive adds it
                "zip",
                root_dir=config.DEFAULT_BASE_DIR,
                base_dir=".",
            )

        console.print(f"✅ Backup created at: [bold green]{destination}[/]")
    except Exception as e:
        console.print(f"❌ Error creating backup: {e}", style="bold red")
        raise click.Abort()


@click.command()
@click.argument("backup_file", type=click.Path(exists=True))
@click.option("--force", is_flag=True, help="Overwrite existing data")
def import_backup(backup_file, force):
    """Import a backup file"""
    from docvault import config

    if not force and any(
        [Path(config.DB_PATH).exists(), any(Path(config.STORAGE_PATH).iterdir())]
    ):
        if not click.confirm("Existing data found. Overwrite?", default=False):
            console.print("Import cancelled")
            return

    try:
        # Extract backup to temporary directory
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            with console.status("[bold blue]Importing backup...[/]"):
                # Extract backup
                shutil.unpack_archive(backup_file, temp_dir, "zip")

                # Copy database
                db_backup = Path(temp_dir) / Path(config.DB_PATH).name
                if db_backup.exists():
                    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(db_backup, config.DB_PATH)

                # Copy storage directory
                storage_backup = Path(temp_dir) / "storage"
                if storage_backup.exists():
                    if Path(config.STORAGE_PATH).exists():
                        shutil.rmtree(config.STORAGE_PATH)
                    shutil.copytree(storage_backup, config.STORAGE_PATH)

        console.print("✅ Backup imported successfully")
    except Exception as e:
        console.print(f"❌ Error importing backup: {e}", style="bold red")
        raise click.Abort()


@click.command(name="serve", help="Start the DocVault MCP server")
@click.option("--host", default=None, help="Host for SSE server (default from config)")
@click.option(
    "--port", type=int, default=None, help="Port for SSE server (default from config)"
)
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    show_default=True,
    help="Transport type: stdio (for AI clients) or sse (for web clients)",
)
def serve_cmd(host, port, transport):
    """Start the DocVault MCP server (stdio for AI, sse for web clients)"""
    import logging

    from docvault.mcp.server import run_server

    logging.basicConfig(level=logging.INFO)
    try:
        run_server(host=host, port=port, transport=transport)
    except Exception as e:
        click.echo(f"[bold red]Failed to start MCP server: {e}[/]", err=True)
        sys.exit(1)
