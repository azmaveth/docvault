"""Commands for checking document freshness and staleness."""

import json

import click
from rich.console import Console
from rich.table import Table

from docvault.db.operations import list_documents as db_list_documents
from docvault.utils.freshness import (
    FRESHNESS_COLORS,
    FRESHNESS_ICONS,
    FreshnessLevel,
    get_freshness_info,
    get_update_suggestion,
    should_suggest_update,
)

console = Console()


@click.command(name="freshness", help="Check freshness status of all documents")
@click.option(
    "--filter",
    type=click.Choice(
        ["all", "fresh", "recent", "stale", "outdated"], case_sensitive=False
    ),
    default="all",
    help="Filter documents by freshness level",
)
@click.option(
    "--threshold",
    type=int,
    default=90,
    help="Days threshold for update suggestions (default: 90)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "list"], case_sensitive=False),
    default="table",
    help="Output format",
)
@click.option(
    "--suggest-updates",
    is_flag=True,
    help="Only show documents that need updating",
)
def freshness_check(
    filter: str, threshold: int, output_format: str, suggest_updates: bool
):
    """Check the freshness status of all documents in the vault.

    This command helps you identify which documents might need updating
    based on their age. Documents are categorized as:

    - Fresh: Less than 7 days old
    - Recent: Less than 30 days old
    - Stale: Less than 90 days old
    - Outdated: More than 90 days old

    Examples:
        dv freshness
        dv freshness --filter stale
        dv freshness --suggest-updates
        dv freshness --format json
    """
    # Get all documents
    docs = db_list_documents()

    if not docs:
        console.print("❌ No documents in vault", style="bold red")
        return 1

    # Process documents and calculate freshness
    processed_docs = []
    for doc in docs:
        freshness_level, formatted_age, icon = get_freshness_info(doc["scraped_at"])

        # Apply filters
        if filter != "all" and freshness_level.value != filter:
            continue

        if suggest_updates and not should_suggest_update(doc["scraped_at"], threshold):
            continue

        processed_docs.append(
            {
                "id": doc["id"],
                "title": doc["title"] or "Untitled",
                "url": doc["url"],
                "scraped_at": doc["scraped_at"],
                "freshness_level": freshness_level,
                "formatted_age": formatted_age,
                "icon": icon,
                "needs_update": should_suggest_update(doc["scraped_at"], threshold),
            }
        )

    if not processed_docs:
        console.print(f"No documents found matching filter: {filter}", style="yellow")
        return 0

    # Display results based on format
    if output_format == "json":
        output = []
        for doc in processed_docs:
            output.append(
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "url": doc["url"],
                    "scraped_at": doc["scraped_at"],
                    "age": doc["formatted_age"],
                    "freshness_level": doc["freshness_level"].value,
                    "needs_update": doc["needs_update"],
                }
            )
        print(json.dumps(output, indent=2))

    elif output_format == "list":
        for doc in processed_docs:
            color = FRESHNESS_COLORS[doc["freshness_level"]]
            console.print(
                f"{doc['icon']} [{color}]{doc['id']:3d}[/{color}] {doc['title'][:50]:<50} "
                f"[{color}]{doc['formatted_age']}[/{color}]"
            )
            if doc["needs_update"]:
                console.print("     💡 Update recommended", style="yellow")

    else:  # table format
        table = Table(title="Document Freshness Report")
        table.add_column("ID", style="dim", width=6)
        table.add_column("Title", style="green")
        table.add_column("Age", width=15)
        table.add_column("Status", width=10)
        table.add_column("Action", style="yellow")

        # Statistics
        stats = {
            FreshnessLevel.FRESH: 0,
            FreshnessLevel.RECENT: 0,
            FreshnessLevel.STALE: 0,
            FreshnessLevel.OUTDATED: 0,
        }

        for doc in processed_docs:
            stats[doc["freshness_level"]] += 1

            # Format status with color
            color = FRESHNESS_COLORS[doc["freshness_level"]]
            status = f"[{color}]{doc['icon']} {doc['freshness_level'].value.title()}[/{color}]"

            # Action recommendation
            action = ""
            if doc["needs_update"]:
                action = "Update recommended"

            table.add_row(
                str(doc["id"]),
                doc["title"][:50] + ("..." if len(doc["title"]) > 50 else ""),
                doc["formatted_age"],
                status,
                action,
            )

        console.print(table)

        # Show summary statistics
        console.print("\n📊 Summary:")
        for level, count in stats.items():
            if count > 0:
                color = FRESHNESS_COLORS[level]
                icon = FRESHNESS_ICONS[level]
                console.print(
                    f"  {icon} [{color}]{level.value.title()}[/{color}]: {count} document{'s' if count != 1 else ''}"
                )

        # Show update recommendations
        update_count = sum(1 for doc in processed_docs if doc["needs_update"])
        if update_count > 0:
            console.print(
                f"\n💡 {update_count} document{'s' if update_count != 1 else ''} "
                f"{'are' if update_count != 1 else 'is'} recommended for update",
                style="yellow",
            )
            console.print(
                "   Run [cyan]dv update <id>[/] to refresh individual documents"
            )

    return 0


@click.command(
    name="check-freshness", help="Check if a specific document needs updating"
)
@click.argument("document_id", type=int)
@click.option(
    "--threshold",
    type=int,
    default=90,
    help="Days threshold for update suggestions (default: 90)",
)
def check_document_freshness(document_id: int, threshold: int):
    """Check the freshness status of a specific document.

    Examples:
        dv check-freshness 1
        dv check-freshness 5 --threshold 30
    """
    from docvault.db.operations import get_document

    doc = get_document(document_id)
    if not doc:
        console.print(f"❌ Document not found: {document_id}", style="bold red")
        return 1

    # Get freshness info
    freshness_level, formatted_age, icon = get_freshness_info(doc["scraped_at"])
    color = FRESHNESS_COLORS[freshness_level]

    # Display document info
    console.print(f"\n📄 Document: {doc['title'] or 'Untitled'}", style="bold")
    console.print(f"   URL: {doc['url']}")
    console.print(f"   Scraped: {doc['scraped_at']}")
    console.print(f"   Age: [{color}]{icon} {formatted_age}[/{color}]")
    console.print(f"   Status: [{color}]{freshness_level.value.title()}[/{color}]")

    # Show update suggestion
    suggestion = get_update_suggestion(freshness_level)
    if suggestion:
        console.print(f"\n💡 {suggestion}", style="yellow")
        console.print(
            f"   Run [cyan]dv update {document_id}[/] to refresh this document"
        )
    else:
        console.print("\n✅ This document is up to date", style="green")

    return 0
