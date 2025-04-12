import click
import asyncio
import logging
from rich.console import Console
from rich.table import Table
from datetime import datetime
from pathlib import Path
import os
import shutil

from docvault import config as app_config
from docvault.db import operations
from docvault.db.schema import initialize_database
from docvault.core.embeddings import search as docvault_search, generate_embeddings
from docvault.core.storage import read_markdown, open_html_in_browser
from docvault.core.library_manager import lookup_library_docs

# Export all commands
__all__ = ['scrape', 'search', 'read', 'list_docs', 'lookup',
           'config', 'init_db', 'add', 'delete', 'rm', 'backup', 'import_backup', 'index']

console = Console()

@click.command()
@click.argument("url")
@click.option("--depth", default=1, help="Scraping depth (1=single page)")
@click.option("--max-links", default=None, type=int, help="Maximum number of links to follow per page")
@click.option("--quiet", is_flag=True, help="Reduce output verbosity")
@click.option("--strict-path", is_flag=True, default=True, help="Only follow links within same URL hierarchy")
def scrape(url, depth, max_links, quiet, strict_path):
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
                scraper.scrape_url(url, depth, max_links=max_links, strict_path=strict_path)
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
                str(scraper.stats["pages_scraped"] + scraper.stats["pages_skipped"])
            )
            
            console.print(table)
            console.print(f"✅ Primary document: [bold green]{document['title']}[/] (ID: {document['id']})")
        else:
            console.print("❌ Failed to scrape document", style="bold red")

    except KeyboardInterrupt:
        console.print("\nScraping interrupted by user", style="yellow")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")


@click.command()
@click.pass_context
@click.argument("url")
@click.option("--depth", default=1, help="Scraping depth (1=single page)")
@click.option("--max-links", default=None, type=int, help="Maximum number of links to follow per page")
@click.option("--quiet", is_flag=True, help="Reduce output verbosity")
@click.option("--strict-path", is_flag=True, default=True, help="Only follow links within same URL hierarchy")
def add(ctx, url, depth, max_links, quiet, strict_path):
    """Add (alias for scrape) documentation from URL"""
    # Simply redirect all logic to 'scrape'
    ctx.invoke(scrape, url=url, depth=depth, max_links=max_links, quiet=quiet, strict_path=strict_path)


@click.command()
@click.argument("document_ids", nargs=-1, type=int, required=True)
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def delete(document_ids, force):
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
    
    if not force and not click.confirm("Are you sure you want to delete these documents?", default=False):
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
            console.print(f"❌ Error deleting document {doc['id']}: {e}", style="bold red")
    
    console.print(f"Deleted {len(documents_to_delete)} document(s)")


@click.command()
@click.pass_context
@click.argument("document_ids", nargs=-1, type=int, required=True)
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def rm(ctx, document_ids, force):
    """Remove documents from the vault (alias for delete)"""
    # Simply redirect all logic to 'delete'
    ctx.invoke(delete, document_ids=document_ids, force=force)


@click.command()
@click.argument("query", required=True)
@click.option("--limit", default=5, help="Maximum number of results to return")
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.option("--text-only", is_flag=True, help="Use only text search (no embeddings)")
@click.option("--context", default=2, help="Number of context lines to show")
def search(query, limit, debug, text_only, context):
    """Search documents in the vault
    
    Examples:
      dv search "python database connection"
      dv search --text-only "configuration settings"
      dv search --limit 10 "API endpoints"
      dv search --debug "embedding vector similarity" 
    """
    from docvault.core.embeddings import search as search_docs, generate_embeddings
    import numpy as np
    import asyncio
    import logging
    
    if debug:
        # Set up debug logging
        log_handler = logging.StreamHandler()
        log_handler.setLevel(logging.DEBUG)
        logging.getLogger("docvault").setLevel(logging.DEBUG)
        logging.getLogger("docvault").addHandler(log_handler)
        console.print("[yellow]Debug mode enabled[/]")
    
    try:
        # Check if sqlite-vec is available
        if debug:
            import sqlite3
            conn = sqlite3.connect(":memory:")
            try:
                conn.enable_load_extension(True)
                conn.load_extension("sqlite_vec")
                console.print("[green]sqlite-vec extension is loaded successfully[/]")
            except sqlite3.OperationalError as e:
                console.print(f"[red]sqlite-vec extension cannot be loaded: {e}[/]")
                console.print("[yellow]Will use text-based fallback search[/]")
            finally:
                conn.close()
    except Exception as e:
        if debug:
            console.print(f"[red]Error checking sqlite-vec: {e}[/]")
    
    # Execute query
    with console.status(f"[bold blue]Searching for '{query}'...[/]", spinner="dots"):
        results = asyncio.run(search_docs(query, limit=limit, text_only=text_only))
    
    if not results:
        console.print("No matching documents found")
        return
    
    # Print detailed results
    console.print(f"Found {len(results)} results for '{query}'")
    
    # Show embedding vector info if in debug mode
    if debug and not text_only:
        console.print("[bold]Query embedding diagnostics:[/]")
        try:
            embedding_bytes = asyncio.run(generate_embeddings(query))
            embedding_array = np.frombuffer(embedding_bytes, dtype=np.float32)
            console.print(f"Embedding dimensions: {len(embedding_array)}")
            console.print(f"Embedding sample: {embedding_array[:5]}...")
            console.print(f"Embedding min/max: {embedding_array.min():.4f}/{embedding_array.max():.4f}")
            console.print(f"Embedding mean/std: {embedding_array.mean():.4f}/{embedding_array.std():.4f}")
        except Exception as e:
            console.print(f"[red]Error analyzing embedding: {e}[/]")
    
    # Display results table
    table = Table(title=f"Search Results for '{query}'")
    table.add_column("Score", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("URL", style="blue")
    table.add_column("Content", style="white")
    
    for result in results:
        # Get context for the matched content
        content_preview = result['content']
        if len(content_preview) > 100:
            match_start = max(0, content_preview.lower().find(query.lower()))
            if match_start == -1:  # If exact query not found, show beginning
                match_start = 0
            
            # Calculate context window
            start = max(0, match_start - 50 * context)
            end = min(len(content_preview), match_start + len(query) + 50 * context)
            
            # Add ellipsis if needed
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(content_preview) else ""
            
            content_preview = prefix + content_preview[start:end] + suffix
        
        table.add_row(
            f"{result['score']:.2f}",
            result['title'] or "Untitled",
            result['url'],
            content_preview
        )
    
    console.print(table)

@click.command()
@click.option("--filter", help="Filter documents by title or URL")
def list_docs(filter):
    """List all documents in the vault"""
    from docvault.db.operations import list_documents
    
    docs = list_documents(filter_text=filter)
    if not docs:
        console.print("No documents found")
        return
        
    table = Table(title="Documents in Vault")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="green")
    table.add_column("URL", style="blue")
    table.add_column("Scraped At", style="cyan")
    
    for doc in docs:
        table.add_row(
            str(doc['id']),
            doc['title'] or "Untitled",
            doc['url'],
            doc['scraped_at']
        )
    console.print(table)

@click.command()
@click.argument("library_name", required=True)
@click.option("--version", help="Library version (default: latest)")
def lookup(library_name, version):
    """Look up library documentation"""
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
                doc['title'] or "Untitled",
                doc['url'],
                doc.get('resolved_version', 'unknown')
            )
        console.print(table)
    
    # Run the async function
    asyncio.run(run_lookup())

@click.command()
@click.option("--verbose", is_flag=True, help="Show detailed output")
@click.option("--force", is_flag=True, help="Force re-indexing of all documents")
@click.option("--batch-size", default=10, help="Number of segments to process in one batch")
def index(verbose, force, batch_size):
    """Index or re-index documents for improved search
    
    This command generates or updates embeddings for existing documents to improve search.
    Use this if you've imported documents from a backup or if search isn't working well.
    """
    from docvault.db.operations import list_documents, search_segments
    from docvault.core.embeddings import generate_embeddings
    
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
            with console.status(f"Processing [bold blue]{doc['title']}[/]", spinner="dots"):
                # Read document content
                content = read_markdown(doc['markdown_path'])
                
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
                    conn = operations.get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id, embedding FROM document_segments WHERE document_id = ? AND content = ?", 
                        (doc['id'], segment)
                    )
                    existing = cursor.fetchone()
                    conn.close()
                    
                    if existing and not force:
                        if verbose:
                            console.print(f"  Segment {i+1}/{len(segments)} already indexed")
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
                            doc['id'], 
                            segment,
                            embedding,
                            segment_type="text",
                            position=i
                        )
                    
                    indexed_segments += 1
                    
                    if verbose:
                        console.print(f"  Indexed segment {i+1}/{len(segments)}")
                    
                    # Batch commit
                    if i % batch_size == 0:
                        conn = operations.get_connection()
                        conn.commit()
                        conn.close()
            
            if indexed_segments > 0:
                console.print(f"✅ Indexed {indexed_segments} segments for [bold green]{doc['title']}[/]")
        
        except Exception as e:
            console.print(f"❌ Error processing document {doc['id']}: {e}", style="bold red")
    
    console.print(f"\nIndexing complete! {indexed_segments}/{total_segments} segments processed.")
    console.print("You can now use improved search functionality.")
    if total_segments > 0:
        console.print(f"Coverage: {indexed_segments/total_segments:.1%}")

# Add the update_segment_embedding function to operations.py
operations.update_segment_embedding = lambda segment_id, embedding: operations.get_connection().execute(
    "UPDATE document_segments SET embedding = ? WHERE id = ?", (embedding, segment_id)
).connection.commit()

# Make sure the read command is defined before it's imported
@click.command()
@click.argument("document_id", type=int)
@click.option("--format", type=click.Choice(['markdown', 'html']), default='markdown',
              help="Output format")
def read(document_id, format):
    """Read a document from the vault"""
    from docvault.db.operations import get_document
    from docvault.core.storage import read_markdown, open_html_in_browser
    
    doc = get_document(document_id)
    if not doc:
        console.print(f"❌ Document not found: {document_id}", style="bold red")
        return
    
    if format == 'html':
        open_html_in_browser(doc['html_path'])
    else:
        content = read_markdown(doc['markdown_path'])
        console.print(f"# {doc['title']}\n", style="bold green")
        console.print(content)

@click.command()
@click.option("--init", is_flag=True, help="Create a new .env file with default settings")
def config(init):
    """Manage DocVault configuration"""
    from docvault import config as app_config
    
    if init:
        # Create .env file from template
        env_path = Path(app_config.DEFAULT_BASE_DIR) / ".env"
        if env_path.exists():
            if not click.confirm(f"Configuration file already exists at {env_path}. Overwrite?"):
                return
        
        # Create the template
        from docvault.main import create_env_template
        template = create_env_template()
        
        # Write the file
        env_path.write_text(template)
        console.print(f"✅ Created configuration file at {env_path}")
        console.print("Edit this file to customize DocVault settings")
    else:
        # Show current configuration
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
            ("Server Host", app_config.SERVER_HOST),
            ("Server Port", str(app_config.SERVER_PORT))
        ]
        
        for name, value in config_items:
            table.add_row(name, str(value))
        
        console.print(table)

@click.command()
@click.option("--force", is_flag=True, help="Force recreation of database")
def init_db(force):
    """Initialize the database"""
    from docvault.db.schema import initialize_database
    
    try:
        initialize_database(force_recreate=force)
        console.print("✅ Database initialized successfully")
    except Exception as e:
        console.print(f"❌ Error initializing database: {e}", style="bold red")
        raise click.Abort()

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
                destination.removesuffix('.zip'),  # Remove .zip as make_archive adds it
                'zip',
                root_dir=config.DEFAULT_BASE_DIR,
                base_dir='.'
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
    
    if not force and any([
        Path(config.DB_PATH).exists(),
        any(Path(config.STORAGE_PATH).iterdir())
    ]):
        if not click.confirm("Existing data found. Overwrite?", default=False):
            console.print("Import cancelled")
            return
    
    try:
        # Extract backup to temporary directory
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            with console.status("[bold blue]Importing backup...[/]"):
                # Extract backup
                shutil.unpack_archive(backup_file, temp_dir, 'zip')
                
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

# ... (rest of your commands unchanged) ...