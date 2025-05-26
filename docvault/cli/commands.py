import asyncio
import logging
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import aiohttp
import click
from rich.table import Table

from docvault.core.storage import read_markdown
from docvault.db import operations
from docvault.project import ProjectManager
from docvault.utils.console import console
from docvault.utils.logging import get_logger
from docvault.utils.path_security import (
    get_safe_path,
    is_safe_archive_member,
    validate_path,
)
from docvault.utils.validation_decorators import (
    validate_doc_id,
    validate_search_query,
    validate_tags,
    validate_url,
)
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
    "search_batch",
    "search_text",
    "index_cmd",
    "config_cmd",
    "init_cmd",
    "backup_cmd",
    "restore_cmd",
    "import_deps_cmd",
    "serve_cmd",
    "stats_cmd",
]

logger = get_logger(__name__)


def handle_network_error(e: Exception) -> None:
    """Handle network errors with user-friendly messages."""
    error_str = str(e)

    if isinstance(e, aiohttp.ClientConnectorError):
        if "Cannot connect to host" in error_str:
            console.error(
                "Could not connect to the server. Please check your internet connection."
            )
        elif "nodename nor servname provided" in error_str:
            console.error("Invalid domain name. Please check the URL.")
        else:
            console.error("Connection failed. Please check the URL and your network.")
    elif isinstance(e, aiohttp.ClientError):
        if "SSL" in error_str:
            console.error("SSL certificate verification failed.")
            console.warning("The website might be using a self-signed certificate.")
        else:
            console.error(f"Network error: {error_str}")
    elif isinstance(e, asyncio.TimeoutError):
        console.error("Request timed out. The server might be slow or unresponsive.")
    elif isinstance(e, ValueError) and "Failed to fetch URL" in error_str:
        # Extract the clean error message from our scraper
        if "Reason: " in error_str:
            reason = error_str.split("Reason: ", 1)[1]
            console.error(f"Failed to fetch URL: {reason}")
        else:
            console.error(error_str)
    else:
        console.error(f"An error occurred: {error_str}")

    logger.debug(f"Full error details: {e}", exc_info=True)


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
@click.option(
    "--force",
    is_flag=True,
    help="Force re-import of existing documentation, even if version matches",
)
@click.option(
    "--skip-existing",
    is_flag=True,
    help="Skip dependencies that already have documentation (default: true if --force is not set)",
)
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity (can be used multiple times)",
)
def import_deps_cmd(
    path, project_type, include_dev, force, skip_existing, format, verbose
):
    """Import documentation for all dependencies in a project.

    Automatically detects and parses dependency files in the project directory
    and imports documentation for each dependency. When a version is specified
    in the dependency file, that exact version will be used. Otherwise, the
    latest available version will be used.

    Examples:
        # Import dependencies from current directory
        dv import-deps

        # Import dependencies from a specific directory
        dv import-deps /path/to/project

        # Force re-import of all dependencies
        dv import-deps --force

        # Skip dependencies that already have documentation
        dv import-deps --skip-existing

        # Include development dependencies
        dv import-deps --include-dev

        # Output results as JSON
        dv import-deps --format json

        # Show more detailed output
        dv import-deps -v
        dv import-deps -vv  # Even more verbose
    """
    import json
    from pathlib import Path
    from typing import Any, Dict, List

    from rich.progress import Progress, SpinnerColumn, TextColumn

    # Set default for skip_existing if not explicitly set
    if skip_existing is None:
        skip_existing = not force

    try:
        if project_type == "auto":
            project_type = None
            if verbose > 0:
                console.print("[dim]Auto-detecting project type...[/]")

        if verbose > 1:
            console.print(f"[dim]Project path: {Path(path).resolve()}")
            if project_type:
                console.print(f"[dim]Project type: {project_type}")
            console.print(f"[dim]Include dev: {include_dev}")
            console.print(f"[dim]Force: {force}")
            console.print(f"[dim]Skip existing: {skip_existing}")

        if verbose > 0:
            console.print("\n[bold]Scanning for dependencies...[/]")

        # Run the async import_documentation function
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            disable=verbose == 0,
        ) as progress:
            task = progress.add_task("Importing dependencies...", total=1)

            # Run the async import_documentation function
            results = asyncio.run(
                ProjectManager.import_documentation(
                    path=path,
                    project_type=project_type,
                    include_dev=include_dev,
                    force=force,
                    skip_existing=skip_existing,
                    verbose=verbose,
                )
            )
            progress.update(task, completed=1)

        if format == "json":
            print(json.dumps(results, indent=2))
            return 0

        # Print summary
        console.print("\n[bold]Import Summary:[/]")

        # Successful imports
        if results["success"]:
            console.print(
                f"[green]✓ Successfully imported {len(results['success'])} packages:[/]"
            )
            if verbose > 0:
                for success in sorted(
                    results["success"], key=lambda x: x["name"].lower()
                ):
                    version = (
                        f" ({success.get('version', 'latest')})"
                        if success.get("version")
                        else ""
                    )
                    source = (
                        f" from {success.get('source', 'unknown')}"
                        if success.get("source")
                        else ""
                    )
                    console.print(f"  - {success['name']}{version}{source}")

        # Skipped imports
        if results["skipped"]:
            console.print(
                f"[yellow]↻ Skipped {len(results['skipped'])} packages (already imported):[/]"
            )
            if verbose > 0:
                for skip in sorted(results["skipped"], key=lambda x: x["name"].lower()):
                    version = (
                        f" ({skip.get('version', 'latest')})"
                        if skip.get("version")
                        else ""
                    )
                    source = (
                        f" from {skip.get('source', 'unknown')}"
                        if skip.get("source")
                        else ""
                    )
                    console.print(f"  - {skip['name']}{version}{source}")

        # Failed imports
        if results["failed"]:
            console.print(
                f"[red]✗ Failed to import {len(results['failed'])} packages:[/]"
            )

            # Group failures by reason for better reporting
            failures_by_reason: Dict[str, List[Dict[str, Any]]] = {}
            for fail in results["failed"]:
                reason = fail.get("reason", "Unknown error")
                if reason not in failures_by_reason:
                    failures_by_reason[reason] = []
                failures_by_reason[reason].append(fail)

            # Print each failure reason with associated packages
            for reason, fails in failures_by_reason.items():
                pkg_list = ", ".join(
                    sorted(
                        [f"{f['name']} ({f.get('version', 'latest')})" for f in fails]
                    )
                )
                console.print(f"  [dim]{reason}:[/] {pkg_list}")

        # Print a final status message
        if results["success"] or not results["failed"]:
            console.print("\n[bold green]✅ Done![/]")
            return 0
        else:
            console.print("\n[bold yellow]⚠ Some dependencies could not be imported[/]")
            return 1

    except Exception as e:
        error_msg = str(e)
        console.print(f"[red]❌ Error: {error_msg}[/]")

        if verbose > 0:
            import traceback

            console.print("\n[dim]Stack trace:")
            console.print(traceback.format_exc())

        if format == "json":
            print(
                json.dumps(
                    {
                        "error": error_msg,
                        "status": "error",
                        "type": e.__class__.__name__,
                    },
                    indent=2,
                )
            )

        return 1


@click.command()
@click.argument("url")
@click.option(
    "--depth",
    default="1",
    help="Scraping depth: number (1=single page) or strategy (auto/conservative/aggressive)",
)
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
@click.option(
    "--update",
    "-u",
    is_flag=True,
    help="Update existing documents by re-scraping them",
)
@click.option(
    "--sections",
    multiple=True,
    help="Filter by section headings (e.g., 'Installation', 'API Reference'). Can be used multiple times.",
)
@click.option(
    "--filter-selector",
    help="CSS selector to filter specific sections (e.g., '.documentation', '#api-docs')",
)
def _scrape(
    url, depth, max_links, quiet, strict_path, update, sections, filter_selector
):
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
                # Parse depth parameter - try as int first, then as string strategy
                try:
                    depth_param = int(depth)
                    depth_strategy = None
                except ValueError:
                    depth_param = (
                        depth.lower()
                        if depth.lower() in ["auto", "conservative", "aggressive"]
                        else "auto"
                    )
                    depth_strategy = None

                scraper = get_scraper()
                document = asyncio.run(
                    scraper.scrape_url(
                        url,
                        depth=depth_param,
                        max_links=max_links,
                        strict_path=strict_path,
                        force_update=update,
                        sections=list(sections) if sections else None,
                        filter_selector=filter_selector,
                        depth_strategy=depth_strategy,
                    )
                )
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
                handle_network_error(e)
                return
            except ssl.SSLError as e:
                console.error("SSL certificate verification failed.")
                console.warning(f"Details: {str(e)}")
                console.warning(
                    "This might happen with self-signed certificates or outdated SSL configurations."
                )
                return
            except socket.gaierror:
                console.error(
                    "Could not resolve the hostname. Please check the URL and your network connection."
                )
                return
            except Exception as e:
                error_str = str(e)
                if "404" in error_str or "Not Found" in error_str:
                    console.error(
                        "The requested page was not found (404). Please check the URL."
                    )
                elif "403" in error_str or "Forbidden" in error_str:
                    console.error(
                        "Access forbidden (403). You might need authentication."
                    )
                elif "401" in error_str or "Unauthorized" in error_str:
                    console.error("Authentication required (401).")
                elif "429" in error_str or "Too Many Requests" in error_str:
                    console.error("Rate limited (429). Please wait and try again.")
                else:
                    handle_network_error(e)
                return

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
@click.option(
    "--depth",
    default="1",
    help="Scraping depth: number (1=single page) or strategy (auto/conservative/aggressive)",
)
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
@click.option(
    "--update",
    "-u",
    is_flag=True,
    help="Update existing documents by re-scraping them",
)
@click.option(
    "--format",
    type=click.Choice(["text", "json", "xml"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--sections",
    multiple=True,
    help="Filter by section headings (e.g., 'Installation', 'API Reference'). Can be used multiple times.",
)
@click.option(
    "--filter-selector",
    help="CSS selector to filter specific sections (e.g., '.documentation', '#api-docs')",
)
@validate_url
def import_cmd(
    url, depth, max_links, quiet, strict_path, update, format, sections, filter_selector
):
    """Import documentation from a URL into the vault.

    Examples:
        dv add https://docs.python.org/3/library/
        dv import https://elixir-lang.org/docs --depth=2
        dv add https://docs.djangoproject.com --format json
        dv import https://api.example.com/docs --format xml
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
                # Parse depth parameter - try as int first, then as string strategy
                try:
                    depth_param = int(depth)
                    depth_strategy = None
                except ValueError:
                    depth_param = (
                        depth.lower()
                        if depth.lower() in ["auto", "conservative", "aggressive"]
                        else "auto"
                    )
                    depth_strategy = None

                scraper = get_scraper()
                document = asyncio.run(
                    scraper.scrape_url(
                        url,
                        depth=depth_param,
                        max_links=max_links,
                        strict_path=strict_path,
                        force_update=update,
                        sections=list(sections) if sections else None,
                        filter_selector=filter_selector,
                        depth_strategy=depth_strategy,
                    )
                )
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
                handle_network_error(e)
                return
            except ssl.SSLError as e:
                console.error("SSL certificate verification failed.")
                console.warning(f"Details: {str(e)}")
                console.warning(
                    "This might happen with self-signed certificates or outdated SSL configurations."
                )
                return
            except socket.gaierror:
                console.error(
                    "Could not resolve the hostname. Please check the URL and your network connection."
                )
                return
            except Exception as e:
                error_str = str(e)
                if "404" in error_str or "Not Found" in error_str:
                    console.error(
                        "The requested page was not found (404). Please check the URL."
                    )
                elif "403" in error_str or "Forbidden" in error_str:
                    console.error(
                        "Access forbidden (403). You might need authentication."
                    )
                    console.warning(
                        "Some documentation sites require authentication or have rate limiting."
                    )
                elif "401" in error_str or "Unauthorized" in error_str:
                    console.error("Authentication required (401).")
                elif "429" in error_str or "Too Many Requests" in error_str:
                    console.error("Rate limited (429). Please wait and try again.")
                else:
                    handle_network_error(e)
                return

        if document:
            if format == "json":
                # JSON output
                import json

                output = {
                    "status": "success",
                    "document": {
                        "id": document["id"],
                        "title": document["title"],
                        "url": document["url"],
                    },
                    "stats": {
                        "pages_scraped": scraper.stats["pages_scraped"],
                        "pages_skipped": scraper.stats["pages_skipped"],
                        "segments_created": scraper.stats["segments_created"],
                        "total_pages": scraper.stats["pages_scraped"]
                        + scraper.stats["pages_skipped"],
                    },
                }
                print(json.dumps(output, indent=2))

            elif format == "xml":
                # XML output
                from xml.dom import minidom
                from xml.etree.ElementTree import Element, SubElement, tostring

                root = Element("import_result")
                root.set("status", "success")

                doc_elem = SubElement(root, "document")
                doc_elem.set("id", str(document["id"]))

                title_elem = SubElement(doc_elem, "title")
                title_elem.text = document["title"]

                url_elem = SubElement(doc_elem, "url")
                url_elem.text = document["url"]

                stats_elem = SubElement(root, "stats")

                pages_scraped_elem = SubElement(stats_elem, "pages_scraped")
                pages_scraped_elem.text = str(scraper.stats["pages_scraped"])

                pages_skipped_elem = SubElement(stats_elem, "pages_skipped")
                pages_skipped_elem.text = str(scraper.stats["pages_skipped"])

                segments_elem = SubElement(stats_elem, "segments_created")
                segments_elem.text = str(scraper.stats["segments_created"])

                total_elem = SubElement(stats_elem, "total_pages")
                total_elem.text = str(
                    scraper.stats["pages_scraped"] + scraper.stats["pages_skipped"]
                )

                # Pretty print XML
                rough_string = tostring(root, encoding="unicode")
                reparsed = minidom.parseString(rough_string)
                print(reparsed.toprettyxml(indent="  "))

            else:
                # Default text output
                table = Table(title=f"Import Results for {url}")
                table.add_column("Metric", style="green")
                table.add_column("Count", style="cyan", justify="right")
                table.add_row("Pages Scraped", str(scraper.stats["pages_scraped"]))
                table.add_row("Pages Skipped", str(scraper.stats["pages_skipped"]))
                table.add_row(
                    "Segments Created", str(scraper.stats["segments_created"])
                )
                table.add_row(
                    "Total Pages",
                    str(
                        scraper.stats["pages_scraped"] + scraper.stats["pages_skipped"]
                    ),
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
                    console.print(
                        f"  • View document: [cyan]dv read {document['id']}[/]"
                    )
                    console.print("  • List all documents: [cyan]dv list[/]")
        else:
            if format == "json":
                import json

                print(
                    json.dumps(
                        {
                            "status": "error",
                            "error": "Failed to import document. The page might not contain any indexable content.",
                        },
                        indent=2,
                    )
                )
            elif format == "xml":
                from xml.dom import minidom
                from xml.etree.ElementTree import Element, tostring

                root = Element("import_result")
                root.set("status", "error")
                root.text = "Failed to import document. The page might not contain any indexable content."

                rough_string = tostring(root, encoding="unicode")
                reparsed = minidom.parseString(rough_string)
                print(reparsed.toprettyxml(indent="  "))
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
    try:
        # Validate the input format first
        if not re.match(r"^[\d,\s-]+$", id_ranges):
            raise click.ClickException(
                "Invalid ID format. Use numbers, commas, and hyphens only."
            )

        ranges = id_ranges.replace(" ", "").split(",")
        for r in ranges:
            if "-" in r:
                try:
                    start, end = map(int, r.split("-"))
                    # Validate range
                    if start <= 0 or end <= 0:
                        raise ValueError("IDs must be positive")
                    if start > end:
                        raise ValueError("Invalid range")
                    document_ids.extend(range(start, end + 1))
                except ValueError:
                    console.print(
                        f"⚠️ Invalid range format: {r}. Expected 'start-end'",
                        style="yellow",
                    )
                    continue
            else:
                try:
                    document_ids.append(int(r))
                except ValueError:
                    console.print(
                        f"⚠️ Invalid document ID: {r}. Must be an integer.",
                        style="yellow",
                    )
                    continue
    except Exception as e:
        raise click.ClickException(f"Error parsing document IDs: {e}")

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
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed output including content hashes",
)
@click.option(
    "--format",
    type=click.Choice(["text", "json", "xml", "markdown"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
def list_cmd(filter, verbose, format):
    """List all documents in the vault. Use --filter to search titles/URLs.

    By default, content hashes are hidden. Use --verbose to show them.

    Examples:
        dv list
        dv list --filter python
        dv list --format json
        dv list --format xml --verbose
    """
    import json

    from docvault.db.operations import list_documents

    docs = list_documents(filter_text=filter)

    if format == "json":
        # JSON output
        from docvault.models.tags import get_document_tags

        json_docs = []
        for doc in docs:
            doc_tags = get_document_tags(doc["id"])
            json_doc = {
                "id": doc["id"],
                "title": doc["title"] or "Untitled",
                "url": doc["url"],
                "version": doc.get("version", "unknown"),
                "scraped_at": doc["scraped_at"],
                "tags": doc_tags,
            }
            if verbose:
                json_doc["content_hash"] = doc.get("content_hash", "") or None
            json_docs.append(json_doc)

        output = {"status": "success", "count": len(json_docs), "documents": json_docs}
        print(json.dumps(output, indent=2))

    elif format == "xml":
        # XML output
        from xml.dom import minidom
        from xml.etree.ElementTree import Element, SubElement, tostring

        root = Element("documents")
        root.set("count", str(len(docs)))

        for doc in docs:
            doc_elem = SubElement(root, "document")
            doc_elem.set("id", str(doc["id"]))

            title_elem = SubElement(doc_elem, "title")
            title_elem.text = doc["title"] or "Untitled"

            url_elem = SubElement(doc_elem, "url")
            url_elem.text = doc["url"]

            version_elem = SubElement(doc_elem, "version")
            version_elem.text = doc.get("version", "unknown")

            scraped_elem = SubElement(doc_elem, "scraped_at")
            scraped_elem.text = doc["scraped_at"]

            # Add tags
            from docvault.models.tags import get_document_tags

            doc_tags = get_document_tags(doc["id"])
            tags_elem = SubElement(doc_elem, "tags")
            for tag in doc_tags:
                tag_elem = SubElement(tags_elem, "tag")
                tag_elem.text = tag

            if verbose and doc.get("content_hash"):
                hash_elem = SubElement(doc_elem, "content_hash")
                hash_elem.text = doc.get("content_hash", "")

        # Pretty print XML
        rough_string = tostring(root, encoding="unicode")
        reparsed = minidom.parseString(rough_string)
        print(reparsed.toprettyxml(indent="  "))

    elif format == "markdown":
        # Markdown output
        if not docs:
            print("No documents found")
            return

        print("# Documents in Vault\n")
        print(f"**Total documents:** {len(docs)}\n")

        if filter:
            print(f"**Filter:** {filter}\n")

        for doc in docs:
            print(f"## {doc['title'] or 'Untitled'}")
            print(f"- **ID:** {doc['id']}")
            print(f"- **URL:** {doc['url']}")
            print(f"- **Version:** {doc.get('version', 'unknown')}")
            print(f"- **Scraped At:** {doc['scraped_at']}")
            if verbose and doc.get("content_hash"):
                print(f"- **Content Hash:** {doc.get('content_hash', '')}")
            print()  # Empty line between documents

    else:
        # Default text output (table)
        if not docs:
            console.print("No documents found")
            return

        table = Table(title="Documents in Vault")

        # Always show these columns
        table.add_column("ID", style="dim")
        table.add_column("Title", style="green")
        table.add_column("URL", style="blue")
        table.add_column("Version", style="magenta")
        table.add_column("Tags", style="yellow")
        table.add_column("Status", style="cyan", width=8)

        # Only show content hash in verbose mode
        if verbose:
            table.add_column("Content Hash", style="yellow")

        table.add_column("Scraped At", style="cyan")

        # Import tags and version control modules
        from docvault.models.tags import get_document_tags

        # Check for updates in batch (simple check using cached data)
        update_status = {}
        try:
            import sqlite3

            from docvault import config

            conn = sqlite3.connect(config.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT document_id, needs_update FROM update_checks")
            update_status = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()
        except Exception:
            pass  # Ignore errors, just won't show update status

        for doc in docs:
            # Get tags for this document
            doc_tags = get_document_tags(doc["id"])
            tags_str = ", ".join(doc_tags) if doc_tags else ""

            # Determine update status
            needs_update = update_status.get(doc["id"], 0)
            if needs_update:
                status = "[yellow]Update![/]"
            else:
                status = "[green]Current[/]"

            row = [
                str(doc["id"]),
                doc["title"] or "Untitled",
                doc["url"],
                doc.get("version", "unknown"),
                tags_str,
                status,
            ]

            # Only add content hash if in verbose mode
            if verbose:
                row.append(doc.get("content_hash", "") or "")

            row.append(doc["scraped_at"])
            table.add_row(*row)

        console.print(table)


@click.command(name="read", help="Read a document from the vault (alias: cat)")
@click.argument("document_id", type=int)
@click.option(
    "--format",
    type=click.Choice(["markdown", "html", "json", "xml"], case_sensitive=False),
    default="markdown",
    help="Output format",
)
@click.option(
    "--raw",
    is_flag=True,
    help="Show raw content without rendering (works with both markdown and HTML)",
)
@click.option(
    "--browser",
    "use_browser",
    is_flag=True,
    help="Open HTML in browser instead of rendering in terminal",
)
@click.option(
    "--summarize",
    is_flag=True,
    help="Generate a concise summary focusing on functions, classes, and examples",
)
@click.option(
    "--show-refs",
    is_flag=True,
    help="Show cross-references and related sections",
)
@click.option(
    "--context",
    is_flag=True,
    help="Show contextual information including usage examples, best practices, and pitfalls",
)
@validate_doc_id
def read_cmd(document_id, format, raw, use_browser, summarize, show_refs, context):
    """Read a document from the vault.

    By default, markdown is rendered for better readability using Glow (if installed).
    HTML is rendered using html2text by default, or can be opened in a browser.
    Use --raw to see the original source.

    Examples:
        dv read 1
        dv read 1 --format json
        dv read 1 --format xml
        dv read 1 --format html --browser
        dv read 1 --summarize
        dv read 1 --summarize --format markdown
        dv read 1 --context
        dv read 1 --show-refs --context
    """
    import json

    from docvault.core.storage import open_html_in_browser, read_html, read_markdown
    from docvault.db.operations import get_document

    doc = get_document(document_id)
    if not doc:
        if format == "json":
            print(
                json.dumps(
                    {"status": "error", "error": f"Document not found: {document_id}"},
                    indent=2,
                )
            )
        else:
            console.print(f"❌ Document not found: {document_id}", style="bold red")
        return 1

    try:
        # Handle summarization if requested
        if summarize:
            from docvault.core.summarizer import DocumentSummarizer

            # Read the markdown content
            with open(doc["markdown_path"], "r", encoding="utf-8") as f:
                content = f.read()

            # Generate summary
            summarizer = DocumentSummarizer()
            summary = summarizer.summarize(content)

            # Format the summary based on requested format
            if format == "json":
                summary_output = {
                    "status": "success",
                    "document": {
                        "id": doc["id"],
                        "title": doc["title"] or "Untitled",
                        "url": doc["url"],
                        "version": doc.get("version", "unknown"),
                        "scraped_at": doc["scraped_at"],
                    },
                    "summary": summary,
                }
                print(json.dumps(summary_output, indent=2))
                return 0
            elif format == "xml":
                from xml.dom import minidom
                from xml.etree.ElementTree import Element, SubElement, tostring

                root = Element("document_summary")
                root.set("id", str(doc["id"]))

                # Add document metadata
                title_elem = SubElement(root, "title")
                title_elem.text = doc["title"] or "Untitled"

                url_elem = SubElement(root, "url")
                url_elem.text = doc["url"]

                # Add summary elements
                summary_elem = SubElement(root, "summary")

                overview_elem = SubElement(summary_elem, "overview")
                overview_elem.text = summary["overview"]

                if summary["classes"]:
                    classes_elem = SubElement(summary_elem, "classes")
                    for cls in summary["classes"]:
                        class_elem = SubElement(classes_elem, "class")
                        class_elem.set("name", cls["name"])
                        class_elem.text = cls["description"]

                if summary["functions"]:
                    functions_elem = SubElement(summary_elem, "functions")
                    for func in summary["functions"]:
                        func_elem = SubElement(functions_elem, "function")
                        func_elem.set("name", func["name"])
                        sig_elem = SubElement(func_elem, "signature")
                        sig_elem.text = func["signature"]
                        desc_elem = SubElement(func_elem, "description")
                        desc_elem.text = func["description"]

                # Pretty print XML
                rough_string = tostring(root, encoding="unicode")
                reparsed = minidom.parseString(rough_string)
                print(reparsed.toprettyxml(indent="  "))
                return 0
            else:
                # Text or markdown format
                formatted_summary = summarizer.format_summary(
                    summary, format="markdown" if format == "markdown" else "text"
                )

                console.print(f"# Summary: {doc['title']}\n", style="bold green")
                console.print(f"URL: {doc['url']}\n")
                console.print(formatted_summary)
                return 0

        # Normal (non-summarized) output
        if format == "json":
            # JSON output
            with open(doc["markdown_path"], "r", encoding="utf-8") as f:
                content = f.read()

            output = {
                "status": "success",
                "document": {
                    "id": doc["id"],
                    "title": doc["title"] or "Untitled",
                    "url": doc["url"],
                    "version": doc.get("version", "unknown"),
                    "scraped_at": doc["scraped_at"],
                    "content_hash": doc.get("content_hash", "") or None,
                    "content": content if raw else content,
                    "format": "markdown",
                },
            }
            print(json.dumps(output, indent=2))

        elif format == "xml":
            # XML output
            from xml.dom import minidom
            from xml.etree.ElementTree import Element, SubElement, tostring

            with open(doc["markdown_path"], "r", encoding="utf-8") as f:
                content = f.read()

            root = Element("document")
            root.set("id", str(doc["id"]))

            title_elem = SubElement(root, "title")
            title_elem.text = doc["title"] or "Untitled"

            url_elem = SubElement(root, "url")
            url_elem.text = doc["url"]

            version_elem = SubElement(root, "version")
            version_elem.text = doc.get("version", "unknown")

            scraped_elem = SubElement(root, "scraped_at")
            scraped_elem.text = doc["scraped_at"]

            if doc.get("content_hash"):
                hash_elem = SubElement(root, "content_hash")
                hash_elem.text = doc.get("content_hash", "")

            content_elem = SubElement(root, "content")
            content_elem.text = content

            # Pretty print XML
            rough_string = tostring(root, encoding="unicode")
            reparsed = minidom.parseString(rough_string)
            print(reparsed.toprettyxml(indent="  "))

        elif format == "html":
            if use_browser:
                open_html_in_browser(doc["html_path"])
                return 0

            if raw:
                with open(doc["html_path"], "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = read_html(doc["html_path"])

            console.print(f"# {doc['title']}\n", style="bold green")
            console.print(content)
        else:
            # Markdown (default)
            content = read_markdown(doc["markdown_path"], render=not raw)
            if not raw:
                console.print(f"# {doc['title']}\n", style="bold green")
            console.print(content)

            # Show cross-references if requested
            if show_refs:
                from docvault.db.operations import get_document_segments
                from docvault.models import cross_references

                console.print("\n[bold cyan]Cross-References[/]\n")

                # Get all segments for this document
                segments = get_document_segments(document_id)

                has_refs = False
                for segment in segments:
                    # Get references from this segment
                    refs_from = cross_references.get_references_from_segment(
                        segment["id"]
                    )
                    if refs_from:
                        has_refs = True
                        console.print(
                            f"\n[yellow]From section: {segment.get('section_title', 'Unknown')}[/]"
                        )

                        table = Table(show_header=True, header_style="bold magenta")
                        table.add_column("Type", style="cyan", width=10)
                        table.add_column("Reference", style="green", width=20)
                        table.add_column("Target", style="blue")

                        for ref in refs_from:
                            target = "Not resolved"
                            if ref.get("target_section"):
                                target = ref["target_section"]
                                if (
                                    ref.get("target_document_title")
                                    and ref["target_document_id"] != document_id
                                ):
                                    target = (
                                        f"{ref['target_document_title']} → {target}"
                                    )

                            table.add_row(
                                ref["reference_type"], ref["reference_text"], target
                            )

                        console.print(table)

                    # Get references to this segment
                    refs_to = cross_references.get_references_to_segment(segment["id"])
                    if refs_to:
                        has_refs = True
                        console.print("\n[yellow]Referenced by:[/]")

                        table = Table(show_header=True, header_style="bold magenta")
                        table.add_column("From Document", style="cyan", width=30)
                        table.add_column("Section", style="green", width=30)
                        table.add_column("Reference", style="blue")

                        for ref in refs_to:
                            table.add_row(
                                ref.get("source_document_title", "Same document"),
                                ref.get("source_section", "Unknown"),
                                ref["reference_text"],
                            )

                        console.print(table)

                if not has_refs:
                    console.print(
                        "[dim]No cross-references found for this document.[/]"
                    )

            # Show contextual information if requested
            if context:
                from docvault.core.context_extractor import ContextExtractor
                from docvault.core.suggestion_engine import SuggestionEngine

                # Read the content for context extraction
                with open(doc["markdown_path"], "r", encoding="utf-8") as f:
                    content = f.read()

                extractor = ContextExtractor()
                suggestion_engine = SuggestionEngine()

                # Extract contextual information
                context_info = extractor.extract_context(content, doc.get("title", ""))

                console.print("\n[bold cyan]Contextual Information[/]\n")

                # Show code examples
                if context_info.examples:
                    console.print("[bold yellow]Code Examples[/]\n")
                    for i, example in enumerate(context_info.examples[:5], 1):
                        table = Table(show_header=False, box=None, padding=(0, 1))
                        table.add_column("", style="cyan", width=12)
                        table.add_column("", style="white")

                        table.add_row("Language:", example.language or "Unknown")
                        table.add_row("Complexity:", example.complexity)
                        table.add_row(
                            "Complete:", "Yes" if example.is_complete else "No"
                        )
                        if example.description:
                            table.add_row("Description:", example.description)

                        console.print(f"[bold green]Example {i}:[/]")
                        console.print(table)
                        console.print(f"[dim]```{example.language or ''}[/]")
                        console.print(
                            example.code[:500]
                            + ("..." if len(example.code) > 500 else "")
                        )
                        console.print("[dim]```[/]\n")

                # Show best practices
                if context_info.best_practices:
                    console.print("[bold yellow]Best Practices[/]\n")
                    for practice in context_info.best_practices[:5]:
                        importance_color = {
                            "critical": "red",
                            "high": "red",
                            "medium": "yellow",
                            "low": "green",
                        }.get(practice.importance, "white")

                        console.print(f"[{importance_color}]● {practice.title}[/]")
                        if practice.description:
                            console.print(f"  [dim]{practice.description}[/]")
                        console.print()

                # Show common pitfalls
                if context_info.pitfalls:
                    console.print("[bold yellow]Common Pitfalls[/]\n")
                    for pitfall in context_info.pitfalls[:5]:
                        severity_color = {
                            "critical": "red",
                            "error": "red",
                            "warning": "yellow",
                            "info": "blue",
                        }.get(pitfall.severity, "white")

                        console.print(f"[{severity_color}]⚠ {pitfall.title}[/]")
                        if pitfall.solution:
                            console.print(f"  [green]Solution: {pitfall.solution}[/]")
                        console.print()

                # Show related concepts
                if context_info.related_concepts:
                    console.print("[bold yellow]Related Concepts[/]\n")
                    concepts_text = ", ".join(context_info.related_concepts[:10])
                    console.print(f"[blue]{concepts_text}[/]\n")

                # Show suggestions for related functions/classes
                try:
                    suggestions = suggestion_engine.get_suggestions(
                        doc.get("title", ""), current_document_id=document_id, limit=5
                    )
                    if suggestions:
                        console.print("[bold yellow]Related Functions & Classes[/]\n")

                        table = Table(show_header=True, header_style="bold magenta")
                        table.add_column("Type", style="cyan", width=10)
                        table.add_column("Name", style="green", width=25)
                        table.add_column("Reason", style="blue", width=30)
                        table.add_column("Document", style="yellow")

                        for suggestion in suggestions:
                            table.add_row(
                                suggestion.suggestion_type,
                                suggestion.title,
                                suggestion.reason,
                                suggestion.source_title or "Current",
                            )

                        console.print(table)
                        console.print()
                except Exception as e:
                    console.print(f"[dim]Could not load suggestions: {e}[/]\n")

                if not any(
                    [
                        context_info.examples,
                        context_info.best_practices,
                        context_info.pitfalls,
                        context_info.related_concepts,
                    ]
                ):
                    console.print(
                        "[dim]No contextual information found for this document.[/]"
                    )

        return 0
    except Exception as e:
        if format == "json":
            print(json.dumps({"status": "error", "error": str(e)}, indent=2))
        else:
            console.print(f"❌ Error reading document: {e}", style="bold red")
            if (
                not raw and format == "markdown"
            ):  # If not in raw mode, try showing raw content as fallback
                try:
                    with open(doc["markdown_path"], "r", encoding="utf-8") as f:
                        console.print("\n[dim]Falling back to raw content:[/]\n")
                        console.print(f.read())
                except (IOError, OSError) as io_err:
                    console.print(
                        f"❌ Error reading raw content: {io_err}", style="red"
                    )
                    return 1
        return 1


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
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed output including content hashes",
)
def search_lib(library_spec, version, format, timeout, verbose):
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
        json_results = []
        for doc in docs:
            result = {
                "title": doc.get("title") or "Untitled",
                "url": doc.get("url", ""),
                "version": doc.get("resolved_version", "unknown"),
                "description": doc.get("description", ""),
            }
            # Only include content_hash in verbose mode
            if verbose and "content_hash" in doc:
                result["content_hash"] = doc["content_hash"]
            json_results.append(result)

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


@search_cmd.command("batch")
@click.argument("library_specs", nargs=-1, required=True)
@click.option(
    "--version", help="Default version for all libraries (can be overridden with @)"
)
@click.option(
    "--format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (text or json)",
)
@click.option(
    "--timeout", type=int, default=60, help="Timeout in seconds for the entire batch"
)
@click.option("--concurrent", type=int, default=5, help="Number of concurrent searches")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed output including failures",
)
def search_batch(library_specs, version, format, timeout, concurrent, verbose):
    """Search documentation for multiple libraries in a single operation.

    Library specifications can include versions using the @ symbol:
      dv search batch requests django@4.2 numpy flask@2.0

    Or use --version for a default version for all libraries:
      dv search batch requests django numpy --version latest

    Examples:
        # Search multiple libraries
        dv search batch requests flask numpy pandas

        # Mix versioned and unversioned libraries
        dv search batch django@4.2 flask requests@2.31.0

        # JSON output for automation
        dv search batch fastapi pydantic uvicorn --format json

        # Limit concurrent searches
        dv search batch lib1 lib2 lib3 lib4 lib5 --concurrent 2
    """
    import asyncio
    import json
    from typing import Any, Dict, List, Tuple

    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
    )
    from rich.table import Table

    from docvault.core.exceptions import LibraryNotFoundError, VersionNotFoundError
    from docvault.core.library_manager import LibraryManager

    def parse_library_spec(spec: str) -> Tuple[str, str]:
        """Parse library specification into (name, version) tuple."""
        if "@" in spec:
            name, version_spec = spec.split("@", 1)
            return name.strip(), version_spec.strip()
        return spec.strip(), version or "latest"

    async def fetch_library_docs(library_name: str, lib_version: str) -> Dict[str, Any]:
        """Fetch documentation for a single library."""
        try:
            manager = LibraryManager()
            docs = await manager.get_library_docs(library_name, lib_version)
            return {
                "library": library_name,
                "version": lib_version,
                "status": "success",
                "docs": docs,
                "error": None,
            }
        except LibraryNotFoundError:
            return {
                "library": library_name,
                "version": lib_version,
                "status": "not_found",
                "docs": [],
                "error": f"Library '{library_name}' not found",
            }
        except VersionNotFoundError as e:
            return {
                "library": library_name,
                "version": lib_version,
                "status": "version_not_found",
                "docs": [],
                "error": str(e),
            }
        except Exception as e:
            return {
                "library": library_name,
                "version": lib_version,
                "status": "error",
                "docs": [],
                "error": str(e),
            }

    async def fetch_all_documentation() -> List[Dict[str, Any]]:
        """Fetch documentation for all libraries concurrently."""
        # Parse all library specifications
        library_requests = []
        for spec in library_specs:
            lib_name, lib_version = parse_library_spec(spec)
            library_requests.append((lib_name, lib_version))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Searching {len(library_requests)} libraries...",
                total=len(library_requests),
            )

            # Create tasks for concurrent execution
            tasks = []
            semaphore = asyncio.Semaphore(concurrent)

            async def fetch_with_semaphore(
                lib_name: str, lib_version: str
            ) -> Dict[str, Any]:
                async with semaphore:
                    result = await fetch_library_docs(lib_name, lib_version)
                    progress.update(task, advance=1)
                    return result

            for lib_name, lib_version in library_requests:
                tasks.append(fetch_with_semaphore(lib_name, lib_version))

            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks)
            progress.update(
                task, completed=len(library_requests), description="[green]Done!"
            )
            return results

    def format_json_output(results: List[Dict[str, Any]]):
        """Format results as JSON."""
        output = {
            "total": len(results),
            "successful": sum(1 for r in results if r["status"] == "success"),
            "failed": sum(1 for r in results if r["status"] != "success"),
            "results": results,
        }
        print(json.dumps(output, indent=2))

    def format_text_output(results: List[Dict[str, Any]]):
        """Format results as text tables."""
        # Summary table
        summary_table = Table(title="Batch Search Summary")
        summary_table.add_column("Status", style="cyan")
        summary_table.add_column("Count", justify="right")

        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] != "success")

        summary_table.add_row("[green]Successful", str(successful))
        summary_table.add_row("[red]Failed", str(failed))
        summary_table.add_row("[bold]Total", str(len(results)))

        console.print(summary_table)
        console.print()

        # Results by library
        for result in results:
            if result["status"] == "success":
                # Success table for this library
                lib_table = Table(title=f"✅ {result['library']}@{result['version']}")
                lib_table.add_column("Title", style="cyan", width=40)
                lib_table.add_column("URL", style="blue", width=50)
                lib_table.add_column("Version", style="green")

                for doc in result["docs"][:3]:  # Show max 3 docs per library
                    title = doc.get("title", "Untitled")
                    if len(title) > 40:
                        title = title[:37] + "..."

                    url = doc.get("url", "")
                    short_url = url
                    if len(url) > 50:
                        short_url = url[:47] + "..."

                    lib_table.add_row(
                        title, short_url, doc.get("resolved_version", "unknown")
                    )

                console.print(lib_table)

                if len(result["docs"]) > 3:
                    console.print(
                        f"  [dim]... and {len(result['docs']) - 3} more documents[/]"
                    )
                console.print()
            else:
                # Error message for this library
                console.print(
                    f"❌ [bold]{result['library']}@{result['version']}[/]: "
                    f"[red]{result['error']}[/]"
                )
                console.print()

        # Footer tip
        console.print("[dim]Tip: Use 'dv add <url>' to import documentation locally[/]")

    try:
        # Run the async function with timeout
        results = asyncio.run(
            asyncio.wait_for(fetch_all_documentation(), timeout=timeout)
        )

        if format == "json":
            format_json_output(results)
        else:
            format_text_output(results)

    except asyncio.TimeoutError:
        console.print(
            f"[red]Error:[/] Batch search timed out after {timeout} seconds. "
            "Try increasing the timeout with --timeout or reducing concurrency with --concurrent"
        )
        if format == "json":
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error": f"Batch search timed out after {timeout} seconds",
                        "total": len(library_specs),
                        "completed": 0,
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
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed output including content hashes",
)
@click.option(
    "--summarize",
    is_flag=True,
    help="Show summaries of matched documents instead of content snippets",
)
@click.option(
    "--tags",
    multiple=True,
    help="Filter by tags (can be specified multiple times)",
)
@click.option(
    "--tag-mode",
    type=click.Choice(["any", "all"], case_sensitive=False),
    default="any",
    help="How to combine multiple tags: 'any' (OR) or 'all' (AND)",
)
@click.option(
    "--suggestions",
    is_flag=True,
    help="Show related functions and classes based on search query",
)
@validate_search_query
@validate_tags
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
    verbose,
    summarize,
    tags,
    tag_mode,
    suggestions,
):
    """Search documents in the vault with metadata filtering.

    Examples:
        dv search "python sqlite" --version 3.10
        dv search --library --title-contains "API"
        dv search --updated-after 2023-01-01
        dv search "async functions" --summarize
        dv search "database" --summarize --limit 3
        dv search "file operations" --suggestions

    If no query is provided, returns random documents matching the filters.
    """

    # Debug line removed
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
        import sqlite_vec

        conn = sqlite3.connect(":memory:")
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            logging.getLogger(__name__).info("sqlite-vec extension loaded successfully")
        except Exception as e:
            logging.getLogger(__name__).warning(
                "sqlite-vec extension cannot be loaded: %s. Falling back to text search.",
                e,
            )
        finally:
            conn.close()
    except ImportError:
        logging.getLogger(__name__).warning(
            "sqlite-vec Python package not installed. Falling back to text search."
        )
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

    # Filter by tags if specified
    tag_filtered_docs = None
    if tags:
        from docvault.models.tags import search_documents_by_tags

        tag_filtered_docs = search_documents_by_tags(list(tags), tag_mode)
        if not tag_filtered_docs:
            if format == "json":
                import json

                print(
                    json.dumps(
                        {
                            "status": "success",
                            "count": 0,
                            "results": [],
                            "query": query,
                            "tags": list(tags),
                            "tag_mode": tag_mode,
                        }
                    )
                )
            else:
                console.print(f"No documents found with tags: {', '.join(tags)}")
            return
        # Add document IDs to filter
        doc_filter["document_ids"] = [doc["id"] for doc in tag_filtered_docs]

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
                    "content_hash": (
                        result.get("content_hash") if verbose else "[hidden]"
                    ),
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

    # Handle summarization if requested
    if summarize:
        from docvault.core.storage import read_markdown
        from docvault.core.summarizer import DocumentSummarizer

        summarizer = DocumentSummarizer()

        # Display results with summaries
        for doc_id, doc_info in doc_results.items():
            doc_title = doc_info["title"]
            doc_url = doc_info["url"]

            console.print(f"\n[bold green]📄 {doc_title}[/]")
            console.print(f"[blue]{doc_url}[/]")

            # Get the document to summarize it
            from docvault.db.operations import get_document

            doc = get_document(doc_id)
            if doc:
                try:
                    # Read and summarize the document
                    content = read_markdown(doc["markdown_path"])
                    summary = summarizer.summarize(content, max_items=5)

                    # Show a brief summary
                    console.print("\n[bold]Summary:[/]")

                    if summary["overview"]:
                        console.print(f"\n{summary['overview']}\n")

                    if summary["functions"]:
                        console.print("[bold]Key Functions:[/]")
                        for func in summary["functions"][:3]:
                            console.print(
                                f"  • {func['name']}: {func['description'][:100]}"
                            )

                    if summary["classes"]:
                        console.print("\n[bold]Key Classes:[/]")
                        for cls in summary["classes"][:3]:
                            console.print(
                                f"  • {cls['name']}: {cls['description'][:100]}"
                            )

                    if summary["key_concepts"]:
                        console.print("\n[bold]Key Concepts:[/]")
                        console.print(
                            "  "
                            + ", ".join(f"`{c}`" for c in summary["key_concepts"][:10])
                        )

                    # Show match locations
                    total_matches = sum(
                        len(section_hits)
                        for section_hits in doc_info["sections"].values()
                    )
                    console.print(
                        f"\n[dim]Query '{query}' found in {total_matches} locations[/]"
                    )

                except Exception as e:
                    logger.warning(f"Failed to summarize document {doc_id}: {e}")
                    console.print(f"[yellow]Could not generate summary: {e}[/]")

            console.print("[dim]" + "─" * 60 + "[/]")

        return

    # Display results by document and section (normal mode)
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

    # Show suggestions if requested and we have search results
    if suggestions and query:
        try:
            from docvault.core.suggestion_engine import SuggestionEngine

            suggestion_engine = SuggestionEngine()
            suggestions_list = suggestion_engine.get_suggestions(query, limit=8)

            if suggestions_list:
                console.print("\n[bold cyan]Related Functions & Classes[/]\n")

                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Type", style="cyan", width=12)
                table.add_column("Name", style="green", width=25)
                table.add_column("Reason", style="blue", width=35)
                table.add_column("Document", style="yellow")

                for suggestion in suggestions_list:
                    table.add_row(
                        suggestion.type,
                        suggestion.title,
                        suggestion.reason,
                        f"Doc {suggestion.document_id}",
                    )

                console.print(table)
                console.print()
            else:
                console.print("[dim]No suggestions found for this query.[/]\n")
        except Exception as e:
            console.print(f"[dim]Could not load suggestions: {e}[/]\n")


@click.command(
    name="suggest",
    help="Get suggestions for functions/classes related to a task or query",
)
@click.argument("query")
@click.option("--limit", default=10, help="Maximum number of suggestions to return")
@click.option(
    "--task-based",
    is_flag=True,
    help="Get suggestions for common programming tasks (e.g., 'file handling', 'database queries')",
)
@click.option(
    "--complementary",
    help="Find functions that complement the specified function name",
)
@click.option(
    "--format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (text or json)",
)
def suggest_cmd(query, limit, task_based, complementary, format):
    """Get suggestions for functions, classes, or programming tasks.

    This command uses the suggestion engine to recommend related functions
    and classes based on your query or programming task.

    Examples:
        dv suggest "file operations"
        dv suggest "database queries" --task-based
        dv suggest --complementary "open"
        dv suggest "async programming" --limit 15
        dv suggest "error handling" --format json
    """
    import json

    from docvault.core.suggestion_engine import SuggestionEngine

    try:
        suggestion_engine = SuggestionEngine()

        if complementary:
            # Get complementary functions for the specified function
            suggestions = suggestion_engine.get_complementary_functions(
                complementary, limit=limit
            )
        elif task_based:
            # Get task-based suggestions
            suggestions = suggestion_engine.get_task_based_suggestions(
                query, limit=limit
            )
        else:
            # General suggestions based on query
            suggestions = suggestion_engine.get_suggestions(query, limit=limit)

        if format == "json":
            # JSON output
            json_suggestions = []
            for suggestion in suggestions:
                json_suggestions.append(
                    {
                        "type": suggestion.type,
                        "title": suggestion.title,
                        "reason": suggestion.reason,
                        "score": suggestion.relevance_score,
                        "document_id": suggestion.document_id,
                        "identifier": suggestion.identifier,
                        "description": suggestion.description,
                    }
                )

            result = {
                "status": "success",
                "query": complementary or query,
                "mode": (
                    "complementary"
                    if complementary
                    else ("task-based" if task_based else "general")
                ),
                "count": len(json_suggestions),
                "suggestions": json_suggestions,
            }
            print(json.dumps(result, indent=2))
        else:
            # Text output
            if complementary:
                console.print(
                    f"[bold cyan]Functions complementary to '{complementary}':[/]\n"
                )
            elif task_based:
                console.print(f"[bold cyan]Suggestions for task: '{query}'[/]\n")
            else:
                console.print(f"[bold cyan]Suggestions for: '{query}'[/]\n")

            if suggestions:
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Type", style="cyan", width=12)
                table.add_column("Name", style="green", width=25)
                table.add_column("Reason", style="blue", width=35)
                table.add_column("Score", style="yellow", width=8)
                table.add_column("Source", style="magenta")

                for suggestion in suggestions:
                    table.add_row(
                        suggestion.type,
                        suggestion.title,
                        suggestion.reason,
                        f"{suggestion.relevance_score:.2f}",
                        f"Doc {suggestion.document_id}",
                    )

                console.print(table)
                console.print(f"\n[dim]Found {len(suggestions)} suggestions[/]")

                if complementary:
                    console.print(
                        "[dim]Tip: Use 'dv read <document_id>' to see usage examples[/]"
                    )
                elif task_based:
                    console.print(
                        "[dim]Tip: Use 'dv search <function_name>' to find implementation details[/]"
                    )
            else:
                console.print("[yellow]No suggestions found for this query.[/]")
                console.print(
                    "[dim]Try using different keywords or use --task-based for programming tasks[/]"
                )

    except Exception as e:
        if format == "json":
            print(json.dumps({"status": "error", "error": str(e)}, indent=2))
        else:
            console.print(f"❌ Error getting suggestions: {e}", style="bold red")
        return 1


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
        CREATE VIRTUAL TABLE IF NOT EXISTS document_segments_vec USING vec0(
            embedding float[768] distance=cosine
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
def backup_cmd(destination):
    """Backup the vault to a zip file"""
    from docvault import config

    # Default backup name with timestamp
    if not destination:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = f"docvault_backup_{timestamp}.zip"

    try:
        # Validate destination path
        dest_path = Path(destination).resolve()
        # Ensure we're not backing up to a system directory
        validate_path(dest_path.parent, allow_absolute=True)

        # Create a secure zip file containing the database and storage
        with console.status("[bold blue]Creating backup...[/]"):
            # Use zipfile for more control over what gets included
            backup_path = (
                dest_path if dest_path.suffix == ".zip" else Path(f"{dest_path}.zip")
            )

            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # Add database file
                if Path(config.DB_PATH).exists():
                    zipf.write(config.DB_PATH, Path(config.DB_PATH).name)

                # Add storage directory
                storage_path = Path(config.STORAGE_PATH)
                if storage_path.exists():
                    for file_path in storage_path.rglob("*"):
                        if file_path.is_file():
                            # Get relative path from storage root
                            arcname = file_path.relative_to(config.DEFAULT_BASE_DIR)
                            zipf.write(file_path, arcname)

        console.print(f"✅ Backup created at: [bold green]{backup_path}[/]")
    except Exception as e:
        console.print(f"❌ Error creating backup: {e}", style="bold red")
        raise click.Abort()


@click.command()
@click.argument("backup_file", type=click.Path(exists=True))
@click.option("--force", is_flag=True, help="Overwrite existing data")
def restore_cmd(backup_file, force):
    """Restore the vault from a backup file (alias: import-backup)"""
    from docvault import config
    from docvault.utils.path_security import PathSecurityError

    if not force and any(
        [Path(config.DB_PATH).exists(), any(Path(config.STORAGE_PATH).iterdir())]
    ):
        if not click.confirm("Existing data found. Overwrite?", default=False):
            console.print("Import cancelled")
            return

    try:
        # Validate backup file path
        backup_path = validate_path(Path(backup_file), allow_absolute=True)

        # Extract backup to temporary directory with security checks
        with tempfile.TemporaryDirectory() as temp_dir:
            with console.status("[bold blue]Importing backup...[/]"):
                # Safely extract backup with path validation
                with zipfile.ZipFile(backup_path, "r") as zipf:
                    # First, check all archive members for safety
                    for member in zipf.namelist():
                        if not is_safe_archive_member(member):
                            raise PathSecurityError(
                                f"Unsafe archive member detected: {member}"
                            )

                    # Extract to temp directory
                    zipf.extractall(temp_dir)

                # Copy database with validation
                db_backup = Path(temp_dir) / Path(config.DB_PATH).name
                if db_backup.exists():
                    # Validate the backup file is within temp directory
                    validate_path(
                        db_backup, allowed_base_paths=[temp_dir], allow_absolute=True
                    )

                    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(db_backup, config.DB_PATH)

                # Copy storage directory with validation
                storage_backup = Path(temp_dir) / "storage"
                if storage_backup.exists():
                    # Validate storage backup is within temp directory
                    validate_path(
                        storage_backup,
                        allowed_base_paths=[temp_dir],
                        allow_absolute=True,
                    )

                    if Path(config.STORAGE_PATH).exists():
                        shutil.rmtree(config.STORAGE_PATH)

                    # Copy with security checks
                    Path(config.STORAGE_PATH).mkdir(parents=True, exist_ok=True)
                    for root, dirs, files in os.walk(storage_backup):
                        for file in files:
                            src = Path(root) / file
                            rel_path = src.relative_to(storage_backup)
                            dst = get_safe_path(
                                config.STORAGE_PATH, str(rel_path), create_dirs=True
                            )
                            shutil.copy2(src, dst)

        console.print("✅ Backup imported successfully")
    except PathSecurityError as e:
        console.print(f"❌ Security error: {e}", style="bold red")
        raise click.Abort()
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


@click.command(name="stats", help="Show database statistics and health information")
@click.option(
    "--format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed statistics including per-document information",
)
def stats_cmd(format, verbose):
    """Show database statistics and health information.

    Displays:
    - Total document count
    - Database size
    - Storage usage
    - Index health
    - Vector search status
    - Recent activity

    Examples:
        dv stats
        dv stats --format json
        dv stats --verbose
    """
    import json
    from pathlib import Path

    from docvault import config
    from docvault.db.operations import get_connection

    stats = {}

    # Get database file size
    db_path = Path(config.DB_PATH)
    if db_path.exists():
        db_size = db_path.stat().st_size
        stats["database_size_bytes"] = db_size
        stats["database_size_mb"] = round(db_size / (1024 * 1024), 2)
    else:
        stats["database_size_bytes"] = 0
        stats["database_size_mb"] = 0

    # Get storage directory size
    storage_path = Path(config.STORAGE_PATH)
    storage_size = 0
    file_count = 0
    if storage_path.exists():
        for path in storage_path.rglob("*"):
            if path.is_file():
                storage_size += path.stat().st_size
                file_count += 1

    stats["storage_size_bytes"] = storage_size
    stats["storage_size_mb"] = round(storage_size / (1024 * 1024), 2)
    stats["storage_file_count"] = file_count

    # Get document statistics from database
    try:
        conn = get_connection()
        # Document count
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM documents")
        doc_count = cursor.fetchone()[0]
        stats["document_count"] = doc_count

        # Document segments count
        cursor.execute("SELECT COUNT(*) FROM document_segments")
        segment_count = cursor.fetchone()[0]
        stats["segment_count"] = segment_count

        # Check vector search health
        try:
            cursor.execute("SELECT COUNT(*) FROM document_segments_vec")
            vec_count = cursor.fetchone()[0]
            stats["vector_index_count"] = vec_count
            stats["vector_search_enabled"] = True
            stats["vector_index_coverage"] = round(
                (vec_count / segment_count * 100) if segment_count > 0 else 0, 1
            )
        except Exception as e:
            stats["vector_index_count"] = 0
            stats["vector_search_enabled"] = False
            stats["vector_index_coverage"] = 0
            stats["vector_search_error"] = str(e)

        # Get recent documents
        cursor.execute(
            """
            SELECT title, url, scraped_at, version
            FROM documents
            ORDER BY scraped_at DESC
            LIMIT 5
        """
        )
        recent_docs = cursor.fetchall()
        stats["recent_documents"] = [
            {"title": doc[0], "url": doc[1], "scraped_at": doc[2], "version": doc[3]}
            for doc in recent_docs
        ]

        # Get document sources/libraries
        cursor.execute(
            """
            SELECT COUNT(DISTINCT url) as unique_urls
            FROM documents
        """
        )
        unique_urls = cursor.fetchone()[0]
        stats["unique_urls"] = unique_urls

        # Count unique domains more simply
        cursor.execute(
            """
            SELECT DISTINCT url FROM documents
        """
        )
        urls = cursor.fetchall()
        unique_domains = len(
            set(
                url[0].split("/")[2] if len(url[0].split("/")) > 2 else url[0]
                for url in urls
            )
        )
        stats["unique_domains"] = unique_domains

        # Get library statistics
        cursor.execute(
            """
            SELECT COUNT(*) FROM libraries
        """
        )
        library_count = cursor.fetchone()[0]
        stats["library_count"] = library_count

        # Get documentation sources
        cursor.execute(
            """
            SELECT name, package_manager, is_active
            FROM documentation_sources
            ORDER BY name
        """
        )
        sources = cursor.fetchall()
        stats["documentation_sources"] = [
            {"name": src[0], "package_manager": src[1], "is_active": bool(src[2])}
            for src in sources
        ]

        # Get per-document statistics if verbose
        if verbose:
            cursor.execute(
                """
                SELECT d.id, d.title, d.url, 
                       COUNT(ds.id) as segment_count,
                       LENGTH(d.content_hash) as has_content
                FROM documents d
                LEFT JOIN document_segments ds ON d.id = ds.document_id
                GROUP BY d.id
                ORDER BY segment_count DESC
                LIMIT 20
            """
            )
            doc_details = cursor.fetchall()
            stats["document_details"] = [
                {
                    "id": doc[0],
                    "title": doc[1],
                    "url": doc[2],
                    "segment_count": doc[3],
                    "has_content": bool(doc[4]),
                }
                for doc in doc_details
            ]

    except Exception as e:
        # Handle database connection errors gracefully
        stats["document_count"] = 0
        stats["segment_count"] = 0
        stats["vector_index_count"] = 0
        stats["vector_search_enabled"] = False
        stats["vector_index_coverage"] = 0
        stats["recent_documents"] = []
        stats["unique_urls"] = 0
        stats["unique_domains"] = 0
        stats["library_count"] = 0
        stats["documentation_sources"] = []
        stats["database_error"] = str(e)
        doc_count = 0
        segment_count = 0
    finally:
        if "conn" in locals():
            conn.close()

    # Calculate totals
    stats["total_size_mb"] = round(
        stats["database_size_mb"] + stats["storage_size_mb"], 2
    )
    stats["average_segments_per_doc"] = round(
        (
            stats["segment_count"] / stats["document_count"]
            if stats["document_count"] > 0
            else 0
        ),
        1,
    )

    # Output results
    if format == "json":
        print(json.dumps(stats, indent=2))
    else:
        # Text format output
        console.print("\n[bold]DocVault Statistics[/]\n")

        # Database info
        table = Table(title="Database Information")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Database Size", f"{stats['database_size_mb']} MB")
        table.add_row("Storage Size", f"{stats['storage_size_mb']} MB")
        table.add_row("Total Size", f"{stats['total_size_mb']} MB")
        table.add_row("Storage Files", str(stats["storage_file_count"]))

        console.print(table)

        # Document statistics
        table = Table(title="Document Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Total Documents", str(stats["document_count"]))
        table.add_row("Total Segments", str(stats["segment_count"]))
        table.add_row("Avg Segments/Doc", str(stats["average_segments_per_doc"]))
        table.add_row("Unique URLs", str(stats["unique_urls"]))
        table.add_row("Unique Domains", str(stats["unique_domains"]))
        table.add_row("Libraries Tracked", str(stats["library_count"]))

        console.print(table)

        # Vector search status
        table = Table(title="Vector Search Status")
        table.add_column("Metric", style="cyan")
        table.add_column(
            "Value",
            style="green" if stats["vector_search_enabled"] else "red",
            justify="right",
        )

        table.add_row(
            "Status", "Enabled" if stats["vector_search_enabled"] else "Disabled"
        )
        table.add_row("Indexed Vectors", str(stats["vector_index_count"]))
        table.add_row("Index Coverage", f"{stats['vector_index_coverage']}%")
        if not stats["vector_search_enabled"] and "vector_search_error" in stats:
            table.add_row("Error", stats["vector_search_error"][:50] + "...")

        console.print(table)

        # Documentation sources
        if stats["documentation_sources"]:
            table = Table(title="Documentation Sources")
            table.add_column("Name", style="cyan")
            table.add_column("Type", style="yellow")
            table.add_column("Status", style="green")

            for source in stats["documentation_sources"]:
                table.add_row(
                    source["name"],
                    source["package_manager"],
                    "Active" if source["is_active"] else "Inactive",
                )

            console.print(table)

        # Recent documents
        if stats["recent_documents"]:
            table = Table(title="Recent Documents")
            table.add_column("Title", style="cyan", max_width=40)
            table.add_column("URL", style="blue", max_width=40)
            table.add_column("Version", style="yellow")
            table.add_column("Added", style="green")

            for doc in stats["recent_documents"]:
                # Format date
                scraped_at = doc["scraped_at"]
                if isinstance(scraped_at, str):
                    scraped_at = scraped_at.split("T")[0]

                table.add_row(
                    (
                        doc["title"][:40] + "..."
                        if len(doc["title"]) > 40
                        else doc["title"]
                    ),
                    doc["url"][:40] + "..." if len(doc["url"]) > 40 else doc["url"],
                    doc["version"] or "unknown",
                    scraped_at,
                )

            console.print(table)

        # Verbose document details
        if verbose and "document_details" in stats:
            table = Table(title="Top Documents by Segment Count")
            table.add_column("ID", style="dim")
            table.add_column("Title", style="cyan", max_width=40)
            table.add_column("Segments", style="green", justify="right")
            table.add_column("Has Content", style="yellow")

            for doc in stats["document_details"][:10]:
                table.add_row(
                    str(doc["id"]),
                    (
                        doc["title"][:40] + "..."
                        if len(doc["title"]) > 40
                        else doc["title"]
                    ),
                    str(doc["segment_count"]),
                    "Yes" if doc["has_content"] else "No",
                )

            console.print(table)

        # Health summary
        console.print("\n[bold]Health Summary:[/]")
        if stats["document_count"] == 0:
            console.print(
                "  [yellow]⚠ No documents in vault. Use 'dv add <url>' to add documentation.[/]"
            )
        elif stats["vector_search_enabled"]:
            if stats["vector_index_coverage"] < 50:
                console.print(
                    f"  [yellow]⚠ Vector index coverage is low ({stats['vector_index_coverage']}%). Run 'dv index' to improve search.[/]"
                )
            else:
                console.print(
                    "  [green]✓ Database is healthy and vector search is enabled.[/]"
                )
        else:
            console.print(
                "  [yellow]⚠ Vector search is disabled. Run 'dv index' to enable.[/]"
            )

        # Next steps
        if stats["document_count"] < 5:
            console.print("\n[bold]Next Steps:[/]")
            console.print("  • Add documentation: [cyan]dv add <url>[/]")
            console.print("  • Import from project: [cyan]dv import-deps[/]")
            console.print("  • Search for libraries: [cyan]dv search lib <name>[/]")
