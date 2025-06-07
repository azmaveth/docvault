"""Version control and update management commands for DocVault CLI."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from docvault.db import operations
from docvault.models import version_control

console = Console()


@click.group(name="version")
def version_cmd():
    """Manage document versions and updates."""
    pass


@version_cmd.command("check")
@click.argument("document_id", type=int, required=False)
@click.option("--all", is_flag=True, help="Check all documents for updates")
@click.option("--force", is_flag=True, help="Force check even if recently checked")
def check_updates(document_id, all, force):
    """Check for document updates.

    Examples:
        dv version check 1
        dv version check --all
    """
    if all:
        # Get all documents and check for updates
        docs = operations.list_documents()
        if not docs:
            console.print("[yellow]No documents found[/]")
            return

        console.print(f"[cyan]Checking {len(docs)} documents for updates...[/]\n")

        updates_available = 0
        errors = 0

        table = Table(title="Update Check Results")
        table.add_column("ID", style="dim", width=6)
        table.add_column("Title", style="cyan", width=30)
        table.add_column("Current", style="green", width=12)
        table.add_column("Latest", style="yellow", width=12)
        table.add_column("Status", style="blue")

        for doc in docs:
            result = version_control.check_for_updates(doc["id"])

            if result.get("error"):
                table.add_row(
                    str(doc["id"]),
                    doc["title"] or "Untitled",
                    doc.get("version", "unknown"),
                    "Error",
                    f"[red]Error: {result['error'][:30]}[/]",
                )
                errors += 1
            elif result.get("needs_update"):
                table.add_row(
                    str(doc["id"]),
                    doc["title"] or "Untitled",
                    doc.get("version", "unknown"),
                    result.get("latest_available_version", "unknown"),
                    "[yellow]Update available[/]",
                )
                updates_available += 1
            else:
                table.add_row(
                    str(doc["id"]),
                    doc["title"] or "Untitled",
                    doc.get("version", "unknown"),
                    result.get("latest_available_version", "same"),
                    "[green]Up to date[/]",
                )

        console.print(table)
        console.print(
            f"\n[bold]Summary:[/] {updates_available} updates available, "
            f"{errors} errors"
        )

    elif document_id:
        # Check specific document
        doc = operations.get_document(document_id)
        if not doc:
            console.print(f"[red]Error:[/] Document {document_id} not found")
            return

        console.print(f"[cyan]Checking for updates:[/] {doc['title']}")
        result = version_control.check_for_updates(document_id)

        if result.get("error"):
            console.print(f"[red]Error:[/] {result['error']}")
        elif result.get("needs_update"):
            console.print("[yellow]Update available![/]")
            console.print(f"Current version: {doc.get('version', 'unknown')}")
            console.print(
                f"Latest version: {result.get('latest_available_version', 'unknown')}"
            )
        else:
            console.print("[green]Document is up to date[/]")
            console.print(f"Version: {doc.get('version', 'unknown')}")

        console.print(f"Last checked: {result.get('last_checked', 'never')}")

    else:
        console.print("[red]Error:[/] Please specify a document ID or use --all")


@version_cmd.command("list")
@click.argument("document_id", type=int)
def list_versions(document_id):
    """List all versions of a document.

    Examples:
        dv version list 1
    """
    doc = operations.get_document(document_id)
    if not doc:
        console.print(f"[red]Error:[/] Document {document_id} not found")
        return

    versions = version_control.get_version_history(document_id)

    if not versions:
        console.print(f"[yellow]No version history found for document {document_id}[/]")
        console.print(
            "[dim]Version history is created when documents are updated or when multiple versions are explicitly tracked.[/]"
        )
        return

    console.print(f"\n[bold]Version History for:[/] {doc['title']}\n")

    table = Table(title=f"Versions (Document ID: {document_id})")
    table.add_column("Version", style="cyan")
    table.add_column("Date", style="green")
    table.add_column("Latest", style="yellow", justify="center")
    table.add_column("Changes", style="blue")

    for version in versions:
        is_latest = "✅" if version.get("is_latest") else ""
        changes = version.get("change_summary", "") or "No summary"
        if len(changes) > 50:
            changes = changes[:47] + "..."

        table.add_row(
            version["version_string"],
            version["created_at"][:10],  # Just the date
            is_latest,
            changes,
        )

    console.print(table)


@version_cmd.command("compare")
@click.argument("document_id", type=int)
@click.argument("old_version")
@click.argument("new_version")
@click.option(
    "--format", type=click.Choice(["summary", "diff", "stats"]), default="summary"
)
def compare_versions(document_id, old_version, new_version, format):
    """Compare two versions of a document.

    Examples:
        dv version compare 1 1.0 1.1
        dv version compare 1 1.0 1.1 --format diff
    """
    doc = operations.get_document(document_id)
    if not doc:
        console.print(f"[red]Error:[/] Document {document_id} not found")
        return

    console.print(f"[cyan]Comparing versions {old_version} → {new_version}[/]")
    result = version_control.compare_versions(document_id, old_version, new_version)

    if result.get("error"):
        console.print(f"[red]Error:[/] {result['error']}")
        return

    if format == "summary":
        # Show a summary of changes
        panel = Panel(
            f"""[bold]Document:[/] {doc["title"]}
[bold]Old Version:[/] {result["old_version"]}
[bold]New Version:[/] {result["new_version"]}
[bold]Similarity:[/] {result["similarity_score"]:.1%}
[bold]Changes:[/] {result["summary"]}

[green]Added:[/] {result["added_lines_count"]} lines
[red]Removed:[/] {result["removed_lines_count"]} lines""",
            title="Version Comparison",
            border_style="cyan",
        )
        console.print(panel)

    elif format == "stats":
        # Show detailed statistics
        table = Table(title="Change Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Similarity Score", f"{result['similarity_score']:.1%}")
        table.add_row("Lines Added", str(result["added_lines_count"]))
        table.add_row("Lines Removed", str(result["removed_lines_count"]))
        table.add_row(
            "Net Change",
            str(result["added_lines_count"] - result["removed_lines_count"]),
        )

        console.print(table)
        console.print(f"\n[bold]Summary:[/] {result['summary']}")

    elif format == "diff":
        # Show the actual diff
        console.print(f"\n[bold]Diff ({old_version} → {new_version}):[/]\n")

        diff_lines = result["diff"].split("\n")
        for line in diff_lines[:100]:  # Limit to first 100 lines
            if line.startswith("+++") or line.startswith("---"):
                console.print(line, style="bold")
            elif line.startswith("+"):
                console.print(line, style="green")
            elif line.startswith("-"):
                console.print(line, style="red")
            elif line.startswith("@@"):
                console.print(line, style="cyan")
            else:
                console.print(line, style="dim")

        if len(diff_lines) > 100:
            console.print(f"\n[dim]... and {len(diff_lines) - 100} more lines[/]")


@version_cmd.command("pending")
def show_pending_updates():
    """Show all documents with pending updates.

    Examples:
        dv version pending
    """
    docs_needing_updates = version_control.get_documents_needing_updates()

    if not docs_needing_updates:
        console.print("[green]All documents are up to date![/]")
        return

    console.print(
        f"[yellow]{len(docs_needing_updates)} document(s) have pending updates:[/]\n"
    )

    table = Table(title="Documents with Pending Updates")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", style="cyan", width=40)
    table.add_column("Current", style="green", width=12)
    table.add_column("Latest", style="yellow", width=12)
    table.add_column("Last Checked", style="blue")

    for doc in docs_needing_updates:
        table.add_row(
            str(doc["id"]),
            doc["title"] or "Untitled",
            doc.get("version", "unknown"),
            doc.get("latest_available_version", "unknown"),
            doc.get("last_checked", "never")[:10],  # Just the date
        )

    console.print(table)
    console.print(
        "\n[dim]Use 'dv version check <id>' to check for updates or 'dv add <url> --update' to update a document.[/]"
    )


@version_cmd.command("auto-check")
@click.option("--enable", is_flag=True, help="Enable automatic update checking")
@click.option("--disable", is_flag=True, help="Disable automatic update checking")
@click.option("--frequency", type=int, help="Set check frequency in days")
@click.argument("document_id", type=int, required=False)
def configure_auto_check(enable, disable, frequency, document_id):
    """Configure automatic update checking.

    Examples:
        dv version auto-check --enable 1
        dv version auto-check --frequency 7 1
        dv version auto-check --disable --all
    """
    import sqlite3

    from docvault import config

    if not any([enable, disable, frequency]):
        console.print(
            "[red]Error:[/] Please specify --enable, --disable, or --frequency"
        )
        return

    if not document_id:
        console.print("[red]Error:[/] Please specify a document ID")
        return

    doc = operations.get_document(document_id)
    if not doc:
        console.print(f"[red]Error:[/] Document {document_id} not found")
        return

    conn = sqlite3.connect(config.DB_PATH)
    try:
        cursor = conn.cursor()

        updates = []
        values = []

        if enable:
            updates.append("check_for_updates = ?")
            values.append(True)
            console.print(
                f"[green]Enabled automatic update checking for document {document_id}[/]"
            )

        if disable:
            updates.append("check_for_updates = ?")
            values.append(False)
            console.print(
                f"[yellow]Disabled automatic update checking for document {document_id}[/]"
            )

        if frequency:
            updates.append("update_frequency = ?")
            values.append(frequency)
            console.print(
                f"[blue]Set update check frequency to {frequency} days for document {document_id}[/]"
            )

        if updates:
            # Build the query safely - we control the column names
            if enable is not None:
                cursor.execute(
                    """
                    UPDATE documents
                    SET version_check_enabled = ?
                    WHERE id = ?
                    """,
                    (1 if enable else 0, document_id),
                )

            if frequency is not None:
                cursor.execute(
                    """
                    UPDATE documents
                    SET check_frequency_days = ?
                    WHERE id = ?
                    """,
                    (frequency, document_id),
                )

            conn.commit()

    finally:
        conn.close()
