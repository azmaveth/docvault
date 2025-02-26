import click
import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown

from docvault import config
from docvault.db import operations
from docvault.db.schema import initialize_database
from docvault.core.scraper import scrape_url
from docvault.core.embeddings import search
from docvault.core.storage import read_markdown, read_html, open_html_in_browser
from docvault.core.library_manager import lookup_library_docs

# Create rich console for pretty output
console = Console()

@click.group()
def cli():
    """DocVault CLI commands"""
    pass

@cli.command()
@click.argument("url")
@click.option("--depth", default=1, help="Scraping depth (1=single page)")
def scrape(url, depth):
    """Scrape and store documentation from URL"""
    console.print(f"Scraping [bold blue]{url}[/] with depth {depth}...")
    
    try:
        # Run scraper
        document = asyncio.run(scrape_url(url, depth))
        
        if document:
            console.print(f"✅ Successfully scraped: [bold green]{document['title']}[/]")
            console.print(f"Document ID: {document['id']}")
        else:
            console.print("❌ Failed to scrape document", style="bold red")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")

@cli.command()
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

@cli.command()
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

@cli.command()
@click.option("--filter", help="Filter by title or URL")
@click.option("--limit", default=20, help="Maximum number of documents to list")
def list(filter, limit):
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

@cli.command()
@click.argument("library_name")
@click.option("--version", default="latest", help="Library version")
def lookup(library_name, version):
    """Lookup and fetch documentation for a library"""
    console.print(f"Looking up documentation for [bold blue]{library_name}[/] {version}...")
    
    try:
        # Run lookup
        documents = asyncio.run(lookup_library_docs(library_name, version))
        
        if documents:
            console.print(f"✅ Found documentation for [bold green]{library_name} {version}[/]")
            console.print(f"Documents: {len(documents)}")
            
            for doc in documents:
                console.print(f"  - {doc['title']} (ID: {doc['id']})")
        else:
            console.print(f"❌ Could not find documentation for {library_name} {version}", style="bold red")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")

@cli.command()
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--init", is_flag=True, help="Initialize default .env file")
@click.option("--reset", is_flag=True, help="Reset to default configuration")
def config(show, init, reset):
    """Manage DocVault configuration"""
    if reset:
        if click.confirm("This will reset your configuration to defaults. Continue?"):
            import shutil
            # Backup existing .env if present
            env_path = config.DEFAULT_BASE_DIR / ".env"
            if env_path.exists():
                backup_path = config.DEFAULT_BASE_DIR / ".env.backup"
                shutil.copy(env_path, backup_path)
                console.print(f"Backed up existing .env to {backup_path}")
                env_path.unlink()
            console.print("Configuration reset to defaults")
    
    if init:
        from docvault.main import create_env_template
        
        env_template = create_env_template()
        env_path = config.DEFAULT_BASE_DIR / ".env"
        
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
    
    table.add_row("Base Directory", str(config.DEFAULT_BASE_DIR))
    table.add_row("Database Path", config.DB_PATH)
    table.add_row("Storage Path", str(config.STORAGE_PATH))
    table.add_row("Log File", str(config.LOG_FILE))
    table.add_row("Embedding Model", config.EMBEDDING_MODEL)
    table.add_row("Ollama URL", config.OLLAMA_URL)
    table.add_row("Server", f"{config.SERVER_HOST}:{config.SERVER_PORT}")
    table.add_row("Brave Search API", "Configured" if config.BRAVE_SEARCH_API_KEY else "Not Configured")
    
    console.print(table)
    
    # Show customization hint
    if not (config.DEFAULT_BASE_DIR / ".env").exists():
        console.print("\nℹ️  Tip: Run 'dv config --init' to create a customizable .env file")

@cli.command(name="init-db")
def init_db():
    """Initialize or reset the database"""
    if click.confirm("This will initialize the database. Continue?"):
        try:
            initialize_database()
            console.print("✅ Database initialized successfully")
        except Exception as e:
            console.print(f"❌ Error initializing database: {e}", style="bold red")
