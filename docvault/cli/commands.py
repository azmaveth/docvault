import asyncio
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from docvault.core.storage import read_markdown
from docvault.db import operations

# Export all commands
# __all__ removed: no actual exports defined in this file yet.

console = Console()


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
    if quiet:
        logging.basicConfig(level=logging.WARNING)
    else:
        console.print(f"Scraping [bold blue]{url}[/] with depth {depth}...")
        logging.basicConfig(level=logging.INFO)

    try:
        logging.getLogger("docvault").setLevel(logging.ERROR)
        from docvault.core.scraper import get_scraper

        with console.status("[bold blue]Scraping documents...[/]", spinner="dots"):
            scraper = get_scraper()
            document = asyncio.run(
                scraper.scrape_url(
                    url, depth, max_links=max_links, strict_path=strict_path
                )
            )

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
                f"✅ Primary document: [bold green]{document['title']}[/] (ID: {document['id']})"
            )
        else:
            console.print("❌ Failed to scrape document", style="bold red")

    except KeyboardInterrupt:
        console.print("\nScraping interrupted by user", style="yellow")
    except Exception as e:
        import traceback

        console.print(f"❌ Error: {e}", style="bold red")
        console.print(traceback.format_exc(), style="yellow")


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
    """Import documentation from a URL into the vault."""
    if quiet:
        logging.basicConfig(level=logging.WARNING)
    else:
        console.print(f"Importing [bold blue]{url}[/] with depth {depth}...")
        logging.basicConfig(level=logging.INFO)
    try:
        logging.getLogger("docvault").setLevel(logging.ERROR)
        from docvault.core.scraper import get_scraper

        with console.status("[bold blue]Importing documents...[/]", spinner="dots"):
            scraper = get_scraper()
            document = asyncio.run(
                scraper.scrape_url(
                    url, depth, max_links=max_links, strict_path=strict_path
                )
            )
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
                f"✅ Primary document: [bold green]{document['title']}[/] (ID: {document['id']})"
            )
        else:
            console.print("❌ Failed to import document", style="bold red")
    except KeyboardInterrupt:
        console.print("\nImport interrupted by user", style="yellow")
    except Exception as e:
        import traceback

        console.print(f"❌ Error: {e}", style="bold red")
        console.print(traceback.format_exc(), style="yellow")


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
@click.argument("library_name", required=True)
@click.option("--version", help="Library version (default: latest)")
def search_lib(library_name, version):
    """Search library documentation (formerly 'lookup')."""
    import asyncio

    from docvault.core.library_manager import LibraryManager

    async def run_lookup():
        manager = LibraryManager()
        docs = await manager.get_library_docs(library_name, version or "latest")
        if not docs:
            console.print(f"No documentation found for {library_name}")
            return
        table = Table(title=f"Documentation for {library_name}")
        table.add_column("Title", style="green")
        table.add_column("URL", style="blue")
        table.add_column("Version", style="cyan")
        for doc in docs:
            table.add_row(
                doc["title"] or "Untitled",
                doc["url"],
                doc.get("resolved_version", "unknown"),
            )
        console.print(table)

    asyncio.run(run_lookup())


@search_cmd.command("text")
@click.argument("query", required=True)
@click.option("--limit", default=5, help="Maximum number of results to return")
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.option("--text-only", is_flag=True, help="Use only text search (no embeddings)")
@click.option("--context", default=2, help="Number of context lines to show")
def search_text(query, limit, debug, text_only, context):
    import sys

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
    with console.status(f"[bold blue]Searching for '{query}'...[/]", spinner="dots"):
        results = asyncio.run(search_docs(query, limit=limit, text_only=text_only))
    if not results:
        console.print("No matching documents found")
        return
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
    table = Table(title=f"Search Results for '{query}'")
    table.add_column("Score", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("URL", style="blue")
    table.add_column("Content", style="white")
    for result in results:
        content_preview = result["content"]
        if len(content_preview) > 100:
            match_start = max(0, content_preview.lower().find(query.lower()))
            if match_start == -1:
                match_start = 0
            start = max(0, match_start - 50 * context)
            end = min(len(content_preview), match_start + len(query) + 50 * context)
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(content_preview) else ""
            content_preview = prefix + content_preview[start:end] + suffix
        table.add_row(
            f"{result['score']:.2f}",
            result["title"] or "Untitled",
            result["url"],
            content_preview,
        )
    console.print(table)


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
    import sys

    from docvault.mcp.server import run_server

    logging.basicConfig(level=logging.INFO)
    try:
        run_server(host=host, port=port, transport=transport)
    except Exception as e:
        click.echo(f"[bold red]Failed to start MCP server: {e}[/]", err=True)
        sys.exit(1)


# ... (rest of your commands unchanged) ...
