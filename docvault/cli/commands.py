import click
import asyncio
import sys
import os
import shutil
import time
import zipfile
import logging
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown

from docvault import config as app_config
from docvault.db import operations
from docvault.db.schema import initialize_database
from docvault.core.scraper import scrape_url
from docvault.core.embeddings import search
from docvault.core.storage import read_markdown, read_html, open_html_in_browser
from docvault.core.library_manager import lookup_library_docs

# Create rich console for pretty output
console = Console()

@click.command()
@click.argument("url")
@click.option("--depth", default=1, help="Scraping depth (1=single page)")
@click.option("--max-links", default=None, type=int, help="Maximum number of links to follow per page")
@click.option("--quiet", is_flag=True, help="Reduce output verbosity")
@click.option("--strict-path", is_flag=True, default=True, help="Only follow links within same URL hierarchy")
def scrape(url, depth, max_links, quiet, strict_path):
    """Scrape and store documentation from URL"""
    # Set up logging based on verbosity
    if quiet:
        logging.basicConfig(level=logging.WARNING)
    else:
        console.print(f"Scraping [bold blue]{url}[/] with depth {depth}...")
        logging.basicConfig(level=logging.INFO)
    
    try:
        # Set log level to suppress info/warning messages
        logging.getLogger("docvault").setLevel(logging.ERROR)
        
        # Import the scraper
        from docvault.core.scraper import get_scraper
        
        # Show a spinner while scraping
        with console.status("[bold blue]Scraping documents...[/]", spinner="dots"):
            # Run scraper
            scraper = get_scraper()
            document = asyncio.run(scraper.scrape_url(url, depth, max_links=max_links, strict_path=strict_path))
        
        if document:
            # Create summary table
            table = Table(title=f"Scraping Results for {url}")
            table.add_column("Metric", style="green")
            table.add_column("Count", style="cyan", justify="right")
            
            table.add_row("Pages Scraped", str(scraper.stats["pages_scraped"]))
            table.add_row("Pages Skipped", str(scraper.stats["pages_skipped"]))
            table.add_row("Segments Created", str(scraper.stats["segments_created"]))
            table.add_row("Total Pages", str(scraper.stats["pages_scraped"] + scraper.stats["pages_skipped"]))
            
            console.print(table)
            console.print(f"✅ Primary document: [bold green]{document['title']}[/] (ID: {document['id']})")
        else:
            console.print("❌ Failed to scrape document", style="bold red")
    except KeyboardInterrupt:
        console.print("\nScraping interrupted by user", style="yellow")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")

@click.command()
@click.argument("url")
@click.option("--depth", default=1, help="Scraping depth (1=single page)")
@click.option("--max-links", default=None, type=int, help="Maximum number of links to follow per page")
@click.option("--quiet", is_flag=True, help="Reduce output verbosity")
@click.option("--strict-path", is_flag=True, default=True, help="Only follow links within same URL hierarchy")
def add(url, depth, max_links, quiet, strict_path):
    """Add (alias for scrape) documentation from URL"""
    # Create the same function body as scrape
    # Set up logging based on verbosity
    if quiet:
        logging.basicConfig(level=logging.WARNING)
    else:
        console.print(f"Scraping [bold blue]{url}[/] with depth {depth}...")
        logging.basicConfig(level=logging.INFO)
        
    # Set log level to suppress info/warning messages
    logging.getLogger("docvault").setLevel(logging.ERROR)
    
    # Import the scraper
    from docvault.core.scraper import get_scraper
    
    try:
        # Show a spinner while scraping
        with console.status("[bold blue]Scraping documents...[/]", spinner="dots"):
            # Run scraper
            scraper = get_scraper()
            document = asyncio.run(scraper.scrape_url(url, depth, max_links=max_links, strict_path=strict_path))
        
        if document:
            # Create summary table
            table = Table(title=f"Scraping Results for {url}")
            table.add_column("Metric", style="green")
            table.add_column("Count", style="cyan", justify="right")
            
            table.add_row("Pages Scraped", str(scraper.stats["pages_scraped"]))
            table.add_row("Pages Skipped", str(scraper.stats["pages_skipped"]))
            table.add_row("Segments Created", str(scraper.stats["segments_created"]))
            table.add_row("Total Pages", str(scraper.stats["pages_scraped"] + scraper.stats["pages_skipped"]))
            
            console.print(table)
            console.print(f"✅ Primary document: [bold green]{document['title']}[/] (ID: {document['id']})")
        else:
            console.print("❌ Failed to scrape document", style="bold red")
    except KeyboardInterrupt:
        console.print("\nScraping interrupted by user", style="yellow")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")

@click.command()
@click.argument("document_ids", nargs=-1, type=int, required=True)
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def delete(document_ids, force):
    """Delete documents from the vault"""
    if not document_ids:
        console.print("❌ No document IDs provided", style="bold red")
        return
    
    # Get documents to confirm deletion
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
    
    # Show documents to be deleted
    table = Table(title=f"Documents to Delete ({len(documents_to_delete)})")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="red")
    table.add_column("URL", style="blue")
    
    for doc in documents_to_delete:
        table.add_row(str(doc["id"]), doc["title"] or "Untitled", doc["url"])
    
    console.print(table)
    
    # Confirm deletion
    if not force and not click.confirm("Are you sure you want to delete these documents?", default=False):
        console.print("Deletion cancelled")
        return
    
    # Delete documents
    for doc in documents_to_delete:
        try:
            # Delete the document files
            html_path = Path(doc["html_path"])
            md_path = Path(doc["markdown_path"])
            
            if html_path.exists():
                html_path.unlink()
            
            if md_path.exists():
                md_path.unlink()
            
            # Delete from database (including segments due to CASCADE)
            operations.delete_document(doc["id"])
            
            console.print(f"✅ Deleted: {doc['title']} (ID: {doc['id']})")
        except Exception as e:
            console.print(f"❌ Error deleting document {doc['id']}: {e}", style="bold red")
    
    console.print(f"Deleted {len(documents_to_delete)} document(s)")

@click.command()
@click.argument("document_ids", nargs=-1, type=int, required=True)
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def rm(document_ids, force):
    """Remove documents from the vault (alias for delete)"""
    return delete(document_ids, force)

@click.command()
@click.argument("query")
@click.option("--limit", default=5, help="Maximum number of results")
def search(query, limit):
    """Search for documents using semantic search"""
    console.print(f"Searching for: [bold blue]{query}[/]")
    
    try:
        # Run search
        results = asyncio.run(search(query, limit))
        
        if results:
            table = Table(title=f"Search Results for '{query}'")
            table.add_column("ID", style="dim")
            table.add_column("Document", style="green")
            table.add_column("Score", style="cyan")
            table.add_column("Content Preview", style="yellow")
            
            for result in results:
                doc_id = str(result["document_id"])
                title = result.get("title", "Untitled")
                score = f"{result.get('score', 0):.2f}"
                content = result.get("content", "")
                
                # Truncate content for display
                preview = content[:100] + "..." if len(content) > 100 else content
                preview = preview.replace("\n", " ")
                
                table.add_row(doc_id, title, score, preview)
            
            console.print(table)
            console.print("\nTo view a document: [bold]dv read <ID>[/]")
        else:
            console.print("No results found", style="yellow")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")

@click.command()
@click.argument("document_id", type=int)
@click.option("--format", type=click.Choice(["markdown", "html"]), default="markdown", 
              help="Format to display/open")
def read(document_id, format):
    """Read a document from the vault"""
    try:
        # Get document
        document = operations.get_document(document_id)
        
        if not document:
            console.print(f"❌ Document not found: {document_id}", style="bold red")
            return
        
        title = document["title"]
        console.print(f"Document: [bold green]{title}[/]")
        console.print(f"URL: [blue]{document['url']}[/]")
        
        if format.lower() == "html":
            # Open in browser
            html_path = document["html_path"]
            if open_html_in_browser(html_path):
                console.print(f"✅ Opened HTML document in browser")
            else:
                console.print(f"❌ Failed to open document in browser", style="bold red")
        else:
            # Display markdown
            markdown_path = document["markdown_path"]
            content = read_markdown(markdown_path)
            
            console.print("\n" + "=" * 80)
            console.print(Markdown(content))
            console.print("=" * 80)
    
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")

@click.command()
@click.option("--filter", help="Filter by title or URL")
@click.option("--limit", default=20, help="Maximum number of documents to list")
def list_docs(filter, limit):
    """List documents in the vault"""
    try:
        documents = operations.list_documents(limit=limit, filter_text=filter)
        
        if not documents:
            console.print("No documents found", style="yellow")
            return
        
        table = Table(title="Documents in Vault")
        table.add_column("ID", style="dim")
        table.add_column("Title", style="green")
        table.add_column("URL", style="blue")
        table.add_column("Scraped", style="cyan")
        
        for doc in documents:
            doc_id = str(doc["id"])
            title = doc["title"] or "Untitled"
            url = doc["url"]
            
            # Format date
            scraped_at = doc["scraped_at"]
            if isinstance(scraped_at, str):
                try:
                    scraped_at = datetime.fromisoformat(scraped_at.replace('Z', '+00:00'))
                except:
                    pass
            
            scraped = scraped_at.strftime("%Y-%m-%d %H:%M") if hasattr(scraped_at, 'strftime') else str(scraped_at)
            
            table.add_row(doc_id, title, url, scraped)
        
        console.print(table)
    
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")

@click.command()
@click.argument("library_name")
@click.argument("version", required=False, default="latest")
def lookup(library_name, version):
    """Lookup and fetch documentation for a library
    
    Examples:
      dv lookup pandas          # Get latest version
      dv lookup jido 1.1.0-rc.1 # Get specific version
    """
    console.print(f"Looking up documentation for [bold blue]{library_name}[/] {version}...")
    
    try:
        # Run lookup
        documents = asyncio.run(lookup_library_docs(library_name, version))
        
        if documents:
            # Check if we resolved "latest" to an actual version
            actual_version = version
            if version == "latest" and "resolved_version" in documents[0]:
                actual_version = documents[0]["resolved_version"]
                console.print(f"✅ Found documentation for [bold green]{library_name}[/] (version: [yellow]{actual_version}[/])")
                console.print("Note: When requesting 'latest', DocVault finds the most current available version")
            else:
                console.print(f"✅ Found documentation for [bold green]{library_name} {actual_version}[/]")
            
            console.print(f"Documents: {len(documents)}")
            
            for doc in documents:
                console.print(f"  - {doc['title']} (ID: {doc['id']})")
        else:
            console.print(f"❌ Could not find documentation for {library_name} {version}", style="bold red")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")

@click.command()
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--init", is_flag=True, help="Initialize default .env file")
@click.option("--reset", is_flag=True, help="Reset to default configuration")
def config(show, init, reset):
    """Manage DocVault configuration"""
    if reset:
        if click.confirm("This will reset your configuration to defaults. Continue?"):
            import shutil
            # Backup existing .env if present
            env_path = app_config.DEFAULT_BASE_DIR / ".env"
            if env_path.exists():
                backup_path = app_config.DEFAULT_BASE_DIR / ".env.backup"
                shutil.copy(env_path, backup_path)
                console.print(f"Backed up existing .env to {backup_path}")
                env_path.unlink()
            console.print("Configuration reset to defaults")
    
    if init:
        from docvault.main import create_env_template
        
        env_template = create_env_template()
        env_path = app_config.DEFAULT_BASE_DIR / ".env"
        
        # Check if .env.example exists and offer to use that instead
        example_path = app_config.DEFAULT_BASE_DIR / ".env.example"
        package_example = Path(__file__).parent.parent.parent / ".env.example"
        
        if example_path.exists():
            if click.confirm(f"Use the more detailed .env.example template instead of generating basic settings?"):
                import shutil
                shutil.copy(example_path, env_path)
                console.print(f"Copied .env.example to {env_path}")
                return
        elif package_example.exists():
            if click.confirm(f"Use the detailed .env.example template instead of generating basic settings?"):
                import shutil
                shutil.copy(package_example, env_path)
                console.print(f"Copied package .env.example to {env_path}")
                return
        
        if env_path.exists():
            if not click.confirm(f".env already exists at {env_path}. Overwrite?"):
                return
                
        with open(env_path, "w") as f:
            f.write(env_template)
        console.print(f"Created .env file at {env_path}")
        
    if show or not any([init, reset]):
        display_config()
        
def display_config():
    """Display current configuration settings"""
    table = Table(title="DocVault Configuration")
    table.add_column("Setting", style="green")
    table.add_column("Value", style="yellow")
    
    table.add_row("Base Directory", str(app_config.DEFAULT_BASE_DIR))
    table.add_row("Database Path", app_config.DB_PATH)
    table.add_row("Storage Path", str(app_config.STORAGE_PATH))
    table.add_row("Log File", str(app_config.LOG_FILE))
    table.add_row("Embedding Model", app_config.EMBEDDING_MODEL)
    table.add_row("Ollama URL", app_config.OLLAMA_URL)
    table.add_row("Server", f"{app_config.SERVER_HOST}:{app_config.SERVER_PORT}")
    table.add_row("Brave API", "Configured" if app_config.BRAVE_API_KEY else "Not Configured")
    
    console.print(table)
    
    # Show customization hint
    if not (app_config.DEFAULT_BASE_DIR / ".env").exists():
        console.print("\nℹ️  Tip: Run 'dv config --init' to create a customizable .env file")

@click.command(name="init-db")
def init_db():
    """Initialize or reset the database"""
    db_path = Path(app_config.DB_PATH)
    
    if db_path.exists():
        console.print(f"Warning: Database already exists at [bold]{db_path}[/]")
        if not click.confirm("⚠️  This will delete all existing data. Are you sure you want to continue?", default=False):
            console.print("Operation cancelled.")
            return
        
        # Backup the existing database before overwriting
        backup_path = db_path.with_suffix(".db.bak")
        import shutil
        shutil.copy(db_path, backup_path)
        console.print(f"Created backup at [green]{backup_path}[/] before reinitializing")
    
    try:
        # Explicitly use force_recreate to ensure the database is reset
        initialize_database(force_recreate=True)
        console.print("✅ Database initialized successfully")
    except Exception as e:
        console.print(f"❌ Error initializing database: {e}", style="bold red")

@click.command()
@click.argument("destination", required=False, type=click.Path())
@click.option("--filename", help="Custom filename for the backup")
def backup(destination, filename):
    """Backup the docvault database and files"""
    import time
    
    # Set default destination if not provided
    if not destination:
        destination = Path.cwd()
    else:
        destination = Path(destination)
    
    # Create destination if it doesn't exist
    destination.mkdir(parents=True, exist_ok=True)
    
    # Set backup filename
    if not filename:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"docvault_backup_{timestamp}.zip"
    elif not filename.endswith(".zip"):
        filename += ".zip"
    
    backup_path = destination / filename
    
    try:
        # Create a zip file
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add database
            db_path = Path(app_config.DB_PATH)
            if db_path.exists():
                zipf.write(db_path, arcname=db_path.name)
            
            # Add storage files
            for folder in [app_config.HTML_PATH, app_config.MARKDOWN_PATH]:
                if folder.exists():
                    for file in folder.glob("**/*"):
                        if file.is_file():
                            zipf.write(file, arcname=str(file.relative_to(app_config.STORAGE_PATH.parent)))
        
        console.print(f"✅ Backup created successfully at [green]{backup_path}[/]")
    except Exception as e:
        console.print(f"❌ Error creating backup: {e}", style="bold red")

@click.command()
@click.argument("backup_file", type=click.Path(exists=True))
@click.option("--force", is_flag=True, help="Overwrite existing files without confirmation")
def import_backup(backup_file, force):
    """Import a backup file"""
    backup_path = Path(backup_file)
    
    if not backup_path.exists() or not zipfile.is_zipfile(backup_path):
        console.print(f"❌ Invalid backup file: {backup_path}", style="bold red")
        return
    
    # Check if database already exists
    db_path = Path(app_config.DB_PATH)
    if db_path.exists() and not force:
        console.print(f"⚠️ Database already exists at [bold]{db_path}[/]")
        if not click.confirm("This will overwrite your existing vault. Continue?", default=False):
            console.print("Import cancelled.")
            return
    
    try:
        # Create directories if they don't exist
        app_config.STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        app_config.HTML_PATH.mkdir(parents=True, exist_ok=True)
        app_config.MARKDOWN_PATH.mkdir(parents=True, exist_ok=True)
        
        # Extract backup
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            # List files in the backup
            files = zipf.namelist()
            console.print(f"Found {len(files)} files in backup")
            
            # Extract database file
            db_file = next((f for f in files if f.endswith(".db")), None)
            if db_file:
                # Extract to temporary location first
                temp_db = app_config.DEFAULT_BASE_DIR / f"temp_{db_file}"
                zipf.extract(db_file, app_config.DEFAULT_BASE_DIR)
                os.rename(app_config.DEFAULT_BASE_DIR / db_file, temp_db)
                
                # Close any existing connections and replace the database
                if db_path.exists():
                    db_path.unlink()
                os.rename(temp_db, db_path)
                console.print(f"✅ Restored database")
            
            # Extract storage files
            for file in files:
                if file.startswith("storage/"):
                    # Extract to the storage directory
                    zipf.extract(file, app_config.DEFAULT_BASE_DIR.parent)
                    console.print(f"  Restored {file}")
        
        console.print(f"✅ Backup imported successfully")
    except Exception as e:
        console.print(f"❌ Error importing backup: {e}", style="bold red")
