"""
CLI commands for llms.txt functionality.
"""

import json
from typing import Optional

import click
from rich.panel import Panel
from rich.table import Table

from docvault.core.llms_txt import LLMsGenerator
from docvault.db import operations
from docvault.db.operations_llms import (
    get_documents_with_llms_txt,
    get_llms_txt_metadata,
    get_llms_txt_resources,
    search_llms_txt_resources,
)
from docvault.utils.console import console


@click.group(name="llms", help="Manage llms.txt functionality")
def llms_commands():
    """Commands for working with llms.txt files."""
    pass


@llms_commands.command(name="list", help="List documents with llms.txt files")
@click.option("--limit", "-l", default=20, help="Maximum number of results")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def list_llms_documents(limit: int, format: str):
    """List all documents that have llms.txt files."""
    try:
        documents = get_documents_with_llms_txt(limit)

        if not documents:
            console.print("[yellow]No documents with llms.txt files found.[/yellow]")
            return

        if format == "json":
            click.echo(json.dumps(documents, indent=2))
            return

        # Table format
        table = Table(title="Documents with llms.txt")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="green")
        table.add_column("LLMs Title", style="yellow")
        table.add_column("Summary", style="dim")
        table.add_column("URL", style="blue")

        for doc in documents:
            table.add_row(
                str(doc["id"]),
                doc.get("title", "N/A"),
                doc.get("llms_title", "N/A"),
                (
                    doc.get("llms_summary", "")[:50] + "..."
                    if doc.get("llms_summary")
                    else ""
                ),
                doc.get("url", "N/A"),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing llms.txt documents: {e}[/red]")


@llms_commands.command(name="show", help="Show llms.txt details for a document")
@click.argument("document_id", type=int)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["rich", "json", "raw"]),
    default="rich",
    help="Output format",
)
def show_llms_details(document_id: int, format: str):
    """Show detailed llms.txt information for a document."""
    try:
        # Get metadata
        metadata = get_llms_txt_metadata(document_id)
        if not metadata:
            console.print(
                f"[yellow]No llms.txt metadata found for document {document_id}[/yellow]"
            )
            return

        # Get resources
        resources = get_llms_txt_resources(document_id)

        if format == "json":
            output = {"metadata": metadata, "resources": resources}
            click.echo(json.dumps(output, indent=2))
            return

        if format == "raw":
            # Reconstruct the llms.txt file
            lines = []
            lines.append(f"# {metadata['llms_title']}")
            lines.append("")

            if metadata.get("llms_summary"):
                lines.append(f"> {metadata['llms_summary']}")
                lines.append("")

            if metadata.get("llms_introduction"):
                lines.append(metadata["llms_introduction"])
                lines.append("")

            # Group resources by section
            sections = {}
            for resource in resources:
                section = resource["section"]
                if section not in sections:
                    sections[section] = []
                sections[section].append(resource)

            for section, section_resources in sections.items():
                lines.append(f"## {section}")
                lines.append("")

                for res in section_resources:
                    line = f"- [{res['title']}]({res['url']})"
                    if res.get("description"):
                        line += f": {res['description']}"
                    lines.append(line)

                lines.append("")

            click.echo("\n".join(lines))
            return

        # Rich format
        panel = Panel(
            f"[bold]{metadata['llms_title']}[/bold]\n\n"
            + (
                f"[italic]{metadata.get('llms_summary', '')}[/italic]\n\n"
                if metadata.get("llms_summary")
                else ""
            )
            + (
                f"{metadata.get('llms_introduction', '')}"
                if metadata.get("llms_introduction")
                else ""
            ),
            title=f"llms.txt for Document #{document_id}",
            border_style="green",
        )
        console.print(panel)

        # Show resources by section
        sections = {}
        for resource in resources:
            section = resource["section"]
            if section not in sections:
                sections[section] = []
            sections[section].append(resource)

        for section, section_resources in sections.items():
            console.print(f"\n[bold yellow]{section}[/bold yellow]")

            for res in section_resources:
                console.print(
                    f"  • [cyan]{res['title']}[/cyan] - [blue]{res['url']}[/blue]"
                )
                if res.get("description"):
                    console.print(f"    [dim]{res['description']}[/dim]")

    except Exception as e:
        console.print(f"[red]Error showing llms.txt details: {e}[/red]")


@llms_commands.command(name="search", help="Search llms.txt resources")
@click.argument("query")
@click.option("--limit", "-l", default=10, help="Maximum number of results")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def search_llms(query: str, limit: int, format: str):
    """Search through llms.txt resources."""
    try:
        results = search_llms_txt_resources(query, limit)

        if not results:
            console.print(
                f"[yellow]No llms.txt resources found matching '{query}'[/yellow]"
            )
            return

        if format == "json":
            click.echo(json.dumps(results, indent=2))
            return

        # Table format
        table = Table(title=f"LLMs.txt Resources matching '{query}'")
        table.add_column("Doc ID", style="cyan", no_wrap=True)
        table.add_column("Document", style="green")
        table.add_column("Section", style="yellow")
        table.add_column("Resource", style="white")
        table.add_column("URL", style="blue")

        for res in results:
            table.add_row(
                str(res["document_id"]),
                res.get("document_title", "N/A"),
                res.get("section", ""),
                res.get("title", ""),
                res.get("url", ""),
            )

        console.print(table)
        console.print(f"\n[dim]Found {len(results)} resources[/dim]")

    except Exception as e:
        console.print(f"[red]Error searching llms.txt resources: {e}[/red]")


@llms_commands.command(name="export", help="Export documents in llms.txt format")
@click.option("--collection", "-c", help="Export documents from a specific collection")
@click.option("--tag", "-t", help="Export documents with a specific tag")
@click.option("--limit", "-l", default=50, help="Maximum number of documents")
@click.option(
    "--title",
    "-T",
    default="Documentation Collection",
    help="Title for the llms.txt file",
)
@click.option("--summary", "-s", help="Summary for the llms.txt file")
@click.option("--output", "-o", help="Output file path (default: stdout)")
def export_llms(
    collection: str | None,
    tag: str | None,
    limit: int,
    title: str,
    summary: str | None,
    output: str | None,
):
    """Export documents in llms.txt format."""
    try:
        # Build filter for documents
        filter_clause = []
        params = []

        if collection:
            # Get collection ID
            from docvault.models.collections import get_collection_by_name

            coll = get_collection_by_name(collection)
            if not coll:
                console.print(f"[red]Collection '{collection}' not found[/red]")
                return
            filter_clause.append(
                "d.id IN (SELECT document_id FROM collection_documents WHERE collection_id = ?)"
            )
            params.append(coll["id"])

        if tag:
            filter_clause.append(
                "d.id IN (SELECT document_id FROM document_tags WHERE tag_id = (SELECT id FROM tags WHERE name = ?))"
            )
            params.append(tag)

        # Get documents
        where_clause = " AND ".join(filter_clause) if filter_clause else "1=1"
        query = f"""
            SELECT d.id, d.title, d.url, t.name as tag_names
            FROM documents d
            LEFT JOIN document_tags dt ON d.id = dt.document_id
            LEFT JOIN tags t ON dt.tag_id = t.id
            WHERE {where_clause}
            GROUP BY d.id
            ORDER BY d.scraped_at DESC
            LIMIT ?
        """
        params.append(limit)

        conn = operations.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            console.print("[yellow]No documents found matching criteria[/yellow]")
            return

        # Convert to document list
        documents = []
        for row in rows:
            doc = {
                "title": row["title"],
                "url": row["url"],
                "description": (
                    f"Tags: {row['tag_names']}" if row["tag_names"] else None
                ),
            }
            documents.append(doc)

        # Generate llms.txt
        generator = LLMsGenerator()
        llms_content = generator.generate(title, documents, summary)

        if output:
            with open(output, "w") as f:
                f.write(llms_content)
            console.print(f"[green]Exported llms.txt to {output}[/green]")
        else:
            click.echo(llms_content)

    except Exception as e:
        console.print(f"[red]Error exporting llms.txt: {e}[/red]")


@llms_commands.command(
    name="add", help="Add a document specifically for its llms.txt file"
)
@click.argument("url")
@click.option("--depth", "-d", default=0, help="Scraping depth (0 = only llms.txt)")
def add_llms_document(url: str, depth: int):
    """Add a document specifically to retrieve its llms.txt file."""
    try:
        from docvault.core.llms_txt import detect_llms_txt

        # First check if the URL itself is an llms.txt file
        if url.endswith("/llms.txt") or url.endswith("/llms.md"):
            llms_url = url
        else:
            # Otherwise, detect the llms.txt URL
            llms_url = detect_llms_txt(url)

        console.print(f"[cyan]Checking for llms.txt at {llms_url}...[/cyan]")

        # Use the scraper to add the document
        from docvault.core.scraper import get_scraper

        scraper = get_scraper()

        # Run the async scrape operation
        import asyncio

        result = asyncio.run(scraper.scrape(llms_url, depth=depth))

        if result:
            console.print(f"[green]Successfully added document from {llms_url}[/green]")
            console.print(f"Document ID: {result['id']}")

            # Check if llms.txt was found
            metadata = get_llms_txt_metadata(result["id"])
            if metadata:
                console.print("[green]✓ llms.txt metadata stored[/green]")
                console.print(f"  Title: {metadata['llms_title']}")
                if metadata.get("llms_summary"):
                    console.print(f"  Summary: {metadata['llms_summary']}")
            else:
                console.print("[yellow]⚠ No llms.txt metadata found[/yellow]")
        else:
            console.print(f"[red]Failed to add document from {url}[/red]")

    except Exception as e:
        console.print(f"[red]Error adding llms.txt document: {e}[/red]")
