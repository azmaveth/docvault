"""
Cache management commands for DocVault CLI.
"""

import asyncio
import json
from datetime import datetime
from typing import List

import click
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from docvault.core.caching import StalenessStatus, get_cache_manager
from docvault.core.scraper import get_scraper
from docvault.db.operations import get_connection
from docvault.utils.console import console as default_console


@click.command()
@click.option("--limit", default=20, help="Maximum number of documents to show")
@click.option(
    "--status",
    type=click.Choice(["all", "stale", "outdated"]),
    default="all",
    help="Filter by staleness status",
)
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def check_updates(limit: int, status: str, format: str):
    """Check for stale documents that may need updating."""
    cache_manager = get_cache_manager()
    console = default_console

    # Determine which statuses to check
    if status == "all":
        documents = cache_manager.get_stale_documents(limit=limit)
    elif status == "stale":
        documents = cache_manager.get_stale_documents(
            StalenessStatus.STALE, limit=limit
        )
    else:  # outdated
        documents = cache_manager.get_stale_documents(
            StalenessStatus.OUTDATED, limit=limit
        )

    if format == "json":
        print(json.dumps(documents, indent=2))
        return

    if not documents:
        console.print("[green]✓ All documents are fresh![/]")
        return

    # Create table
    table = Table(title=f"Documents Needing Updates ({len(documents)} found)")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Title", style="white", max_width=40)
    table.add_column("Status", style="yellow")
    table.add_column("Last Checked", style="dim")
    table.add_column("Age", style="magenta")

    for doc in documents:
        # Calculate age
        if doc["last_checked"]:
            last_checked = datetime.fromisoformat(
                doc["last_checked"].replace("Z", "+00:00")
            )
            age_days = (datetime.now(last_checked.tzinfo) - last_checked).days
            age_str = f"{age_days}d ago"
            last_checked_str = last_checked.strftime("%Y-%m-%d")
        else:
            age_str = "Never"
            last_checked_str = "Never"

        # Status with emoji
        status_emoji = {"stale": "⚠️  Stale", "outdated": "❌ Outdated"}.get(
            doc["staleness_status"], doc["staleness_status"]
        )

        table.add_row(
            str(doc["id"]),
            doc["title"] or doc["url"][:40] + "...",
            status_emoji,
            last_checked_str,
            age_str,
        )

    console.print(table)
    console.print(
        "\n💡 Run [cyan]dv update --all-stale[/] to update all stale documents"
    )


@click.command()
@click.argument("document_ids", nargs=-1, type=int)
@click.option("--all-stale", is_flag=True, help="Update all stale documents")
@click.option("--all-outdated", is_flag=True, help="Update all outdated documents")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be updated without doing it"
)
@click.option("--force", is_flag=True, help="Force update even if no changes detected")
def update(
    document_ids: List[int],
    all_stale: bool,
    all_outdated: bool,
    dry_run: bool,
    force: bool,
):
    """Update stale documents by re-scraping them."""
    cache_manager = get_cache_manager()
    console = default_console

    # Determine which documents to update
    if all_stale:
        documents = cache_manager.get_stale_documents()
    elif all_outdated:
        documents = cache_manager.get_stale_documents(StalenessStatus.OUTDATED)
    elif document_ids:
        # Get specific documents
        with get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(document_ids))
            cursor.execute(
                f"""
                    SELECT id, url, title, version, last_checked, staleness_status
                    FROM documents 
                    WHERE id IN ({placeholders})
                """,
                document_ids,
            )

            documents = []
            for row in cursor.fetchall():
                documents.append(
                    {
                        "id": row[0],
                        "url": row[1],
                        "title": row[2],
                        "version": row[3],
                        "last_checked": row[4],
                        "staleness_status": row[5],
                    }
                )
    else:
        console.error("Please specify document IDs or use --all-stale/--all-outdated")
        return

    if not documents:
        console.print("[green]✓ No documents to update[/]")
        return

    if dry_run:
        console.print(f"[yellow]Would update {len(documents)} documents:[/]")
        for doc in documents[:10]:  # Show first 10
            console.print(f"  - {doc['title'] or doc['url']}")
        if len(documents) > 10:
            console.print(f"  ... and {len(documents) - 10} more")
        return

    # Perform updates
    updated = 0
    skipped = 0
    failed = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Updating documents...", total=len(documents))

        for doc in documents:
            progress.update(
                task, description=f"Checking {doc['title'] or doc['url'][:30]}..."
            )

            try:
                # Check if update is needed
                if not force:
                    has_updates, reason = asyncio.run(
                        cache_manager.check_for_updates(doc["id"])
                    )

                    if not has_updates:
                        skipped += 1
                        progress.update(task, advance=1)
                        continue

                # Re-scrape the document
                progress.update(
                    task, description=f"Updating {doc['title'] or doc['url'][:30]}..."
                )
                scraper = get_scraper()

                # Get current etag and last-modified
                result = asyncio.run(
                    scraper.scrape_url(doc["url"], depth=1, force_update=True)
                )

                if result:
                    updated += 1
                    console.print(f"[green]✓[/] Updated: {doc['title'] or doc['url']}")
                else:
                    failed += 1

            except Exception as e:
                console.print(f"[red]✗[/] Failed to update {doc['id']}: {str(e)}")
                failed += 1

            progress.update(task, advance=1)

    # Summary
    console.print("\n[bold]Update Summary:[/]")
    console.print(f"  [green]✓ Updated: {updated}[/]")
    if skipped > 0:
        console.print(f"  [yellow]↻ Skipped (no changes): {skipped}[/]")
    if failed > 0:
        console.print(f"  [red]✗ Failed: {failed}[/]")


@click.command()
@click.argument("document_id", type=int)
@click.option("--unpin", is_flag=True, help="Unpin the document")
def pin(document_id: int, unpin: bool):
    """Pin a document to prevent it from becoming stale."""
    cache_manager = get_cache_manager()
    console = default_console

    try:
        cache_manager.pin_document(document_id, not unpin)

        if unpin:
            console.print(f"[yellow]📌 Unpinned document {document_id}[/]")
        else:
            console.print(
                f"[green]📌 Pinned document {document_id} (will never become stale)[/]"
            )

    except Exception as e:
        console.error(f"Failed to {'unpin' if unpin else 'pin'} document: {str(e)}")


@click.command()
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def cache_stats(format: str):
    """Show cache statistics."""
    cache_manager = get_cache_manager()
    console = default_console

    stats = cache_manager.get_cache_statistics()

    if format == "json":
        print(json.dumps(stats, indent=2))
        return

    # Create summary table
    table = Table(title="Document Cache Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Total Documents", str(stats["total_documents"]))
    table.add_row("Fresh Documents", f"[green]{stats['fresh']}[/]")
    table.add_row("Stale Documents", f"[yellow]{stats['stale']}[/]")
    table.add_row("Outdated Documents", f"[red]{stats['outdated']}[/]")
    table.add_row("Pinned Documents", f"[blue]{stats['pinned']}[/]")
    table.add_row("Average Age", f"{stats['average_age_days']} days")

    console.print(table)

    # Show thresholds
    console.print("\n[dim]Freshness Thresholds:[/]")
    console.print(f"  Fresh: < {stats['thresholds']['fresh_days']} days")
    console.print(
        f"  Stale: {stats['thresholds']['fresh_days']}-{stats['thresholds']['stale_days']} days"
    )
    console.print(f"  Outdated: > {stats['thresholds']['stale_days']} days")


@click.command()
@click.argument(
    "setting", type=click.Choice(["fresh-days", "stale-days", "auto-check"])
)
@click.argument("value")
def cache_config(setting: str, value: str):
    """Configure cache settings."""
    console = default_console

    # TODO: Implement persistent configuration storage
    # For now, just show what would be set

    if setting == "fresh-days":
        try:
            days = int(value)
            if days < 1:
                console.error("Fresh days must be at least 1")
                return
            console.print(f"[green]✓ Would set fresh threshold to {days} days[/]")
        except ValueError:
            console.error("Value must be a number")

    elif setting == "stale-days":
        try:
            days = int(value)
            if days < 1:
                console.error("Stale days must be at least 1")
                return
            console.print(f"[green]✓ Would set stale threshold to {days} days[/]")
        except ValueError:
            console.error("Value must be a number")

    elif setting == "auto-check":
        if value.lower() in ["true", "yes", "1", "on"]:
            console.print("[green]✓ Would enable automatic update checks[/]")
        else:
            console.print("[yellow]✓ Would disable automatic update checks[/]")

    console.print(
        "\n[dim]Note: Persistent configuration storage not yet implemented[/]"
    )
