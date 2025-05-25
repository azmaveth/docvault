"""Tag management commands for DocVault CLI."""

import click
from rich.console import Console
from rich.table import Table

from docvault.db import operations
from docvault.models import tags

console = Console()


@click.group(name="tag")
def tag_cmd():
    """Manage document tags."""
    pass


@tag_cmd.command("add")
@click.argument("document_id", type=int)
@click.argument("tag_names", nargs=-1, required=True)
def add_tag(document_id, tag_names):
    """Add tags to a document.

    Examples:
        dv tag add 1 python tutorial
        dv tag add 5 "web-dev" django backend
    """
    # Check if document exists
    doc = operations.get_document(document_id)
    if not doc:
        console.print(f"[red]Error:[/] Document {document_id} not found")
        return

    added = []
    already_exists = []

    for tag_name in tag_names:
        try:
            if tags.add_tag_to_document(document_id, tag_name):
                added.append(tag_name)
            else:
                already_exists.append(tag_name)
        except Exception as e:
            console.print(f"[red]Error adding tag '{tag_name}':[/] {e}")

    if added:
        console.print(f"✅ Added tags to document {document_id}: {', '.join(added)}")
    if already_exists:
        console.print(f"[yellow]Tags already exist:[/] {', '.join(already_exists)}")


@tag_cmd.command("remove")
@click.argument("document_id", type=int)
@click.argument("tag_names", nargs=-1, required=True)
def remove_tag(document_id, tag_names):
    """Remove tags from a document.

    Examples:
        dv tag remove 1 tutorial
        dv tag remove 5 django
    """
    # Check if document exists
    doc = operations.get_document(document_id)
    if not doc:
        console.print(f"[red]Error:[/] Document {document_id} not found")
        return

    removed = []
    not_found = []

    for tag_name in tag_names:
        if tags.remove_tag_from_document(document_id, tag_name):
            removed.append(tag_name)
        else:
            not_found.append(tag_name)

    if removed:
        console.print(
            f"✅ Removed tags from document {document_id}: {', '.join(removed)}"
        )
    if not_found:
        console.print(f"[yellow]Tags not found:[/] {', '.join(not_found)}")


@tag_cmd.command("list")
@click.option("--document", "-d", type=int, help="List tags for a specific document")
def list_tags(document):
    """List all tags or tags for a specific document.

    Examples:
        dv tag list
        dv tag list --document 1
    """
    if document:
        # List tags for specific document
        doc = operations.get_document(document)
        if not doc:
            console.print(f"[red]Error:[/] Document {document} not found")
            return

        doc_tags = tags.get_document_tags(document)
        if doc_tags:
            console.print(f"\n[bold]Tags for document {document}:[/] {doc['title']}")
            for tag in doc_tags:
                console.print(f"  • {tag}")
        else:
            console.print(f"[yellow]No tags for document {document}[/]")
    else:
        # List all tags
        all_tags = tags.list_tags()
        if not all_tags:
            console.print("[yellow]No tags found[/]")
            return

        table = Table(title="Document Tags")
        table.add_column("Tag", style="cyan")
        table.add_column("Documents", justify="right", style="green")
        table.add_column("Description", style="dim")

        for tag in all_tags:
            table.add_row(
                tag["name"],
                str(tag["document_count"]),
                tag.get("description", "") or "",
            )

        console.print(table)


@tag_cmd.command("search")
@click.argument("tag_names", nargs=-1, required=True)
@click.option(
    "--mode",
    type=click.Choice(["any", "all"]),
    default="any",
    help="Search mode: 'any' (OR) or 'all' (AND)",
)
def search_by_tags(tag_names, mode):
    """Search documents by tags.

    Examples:
        dv tag search python            # Documents with 'python' tag
        dv tag search python django     # Documents with 'python' OR 'django'
        dv tag search python django --mode all  # Documents with 'python' AND 'django'
    """
    docs = tags.search_documents_by_tags(list(tag_names), mode)

    if not docs:
        console.print(
            f"[yellow]No documents found with tags: {', '.join(tag_names)}[/]"
        )
        return

    # Display results
    mode_desc = "all of" if mode == "all" else "any of"
    table = Table(title=f"Documents with {mode_desc} tags: {', '.join(tag_names)}")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Title", style="cyan")
    table.add_column("Tags", style="green")

    for doc in docs:
        doc_tags = tags.get_document_tags(doc["id"])
        table.add_row(str(doc["id"]), doc["title"] or "Untitled", ", ".join(doc_tags))

    console.print(table)
    console.print(f"\n[dim]Found {len(docs)} document(s)[/]")


@tag_cmd.command("create")
@click.argument("name")
@click.option("--description", "-d", help="Tag description")
def create_tag(name, description):
    """Create a new tag.

    Examples:
        dv tag create tutorial
        dv tag create "web-dev" --description "Web development resources"
    """
    try:
        tag_id = tags.create_tag(name, description)
        console.print(f"✅ Created tag '{name}' (ID: {tag_id})")
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")


@tag_cmd.command("delete")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def delete_tag(name, force):
    """Delete a tag.

    Examples:
        dv tag delete tutorial
        dv tag delete "old-tag" --force
    """
    tag = tags.get_tag(name)
    if not tag:
        console.print(f"[red]Error:[/] Tag '{name}' not found")
        return

    # Get document count
    doc_count = len(tags.get_documents_by_tag(name))

    if not force and doc_count > 0:
        if not click.confirm(
            f"Tag '{name}' is used by {doc_count} document(s). Delete anyway?"
        ):
            console.print("Deletion cancelled")
            return

    if tags.delete_tag(tag["id"]):
        console.print(f"✅ Deleted tag '{name}'")
    else:
        console.print(f"[red]Error:[/] Failed to delete tag '{name}'")
