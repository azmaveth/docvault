"""
Collection management commands for DocVault CLI.

Collections are project-based groupings of documents that help organize
documentation for specific purposes. Unlike tags (which are attributes),
collections are curated sets of documents.
"""

import builtins
import json
from typing import Optional

import click
from rich.table import Table

from docvault.models import collections
from docvault.utils.console import console as default_console
from docvault.utils.validation_decorators import validate_doc_id


@click.group()
def collection():
    """Manage document collections (project-based groupings).

    Collections help organize documents for specific projects or purposes.
    Unlike tags (which describe attributes), collections are curated sets
    of documents that work together.

    Examples:
        dv collection create "Python Web Dev" --description "Django + FastAPI docs"
        dv collection add "Python Web Dev" 123 456 789
        dv collection list
        dv collection show "Python Web Dev"
    """
    pass


@collection.command()
@click.argument("name")
@click.option("--description", "-d", help="Collection description")
@click.option(
    "--tags", "-t", multiple=True, help="Default tags for documents in this collection"
)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def create(name: str, description: str | None, tags: list[str], format: str):
    """Create a new collection.

    Examples:
        dv collection create "My SaaS Project"
        dv collection create "ML Pipeline" --description "PyTorch + MLflow docs"
        dv collection create "Web Dev" --tags python django react
    """
    console = default_console

    try:
        collection_id = collections.create_collection(
            name=name,
            description=description,
            default_tags=list(tags) if tags else None,
        )

        if format == "json":
            print(
                json.dumps(
                    {
                        "status": "success",
                        "collection_id": collection_id,
                        "name": name,
                        "description": description,
                        "default_tags": list(tags),
                    }
                )
            )
        else:
            console.print(
                f"[green]✓ Created collection '{name}' (ID: {collection_id})[/]"
            )
            if description:
                console.print(f"  Description: {description}")
            if tags:
                console.print(f"  Default tags: {', '.join(tags)}")

    except ValueError as e:
        if format == "json":
            print(json.dumps({"status": "error", "error": str(e)}))
        else:
            console.error(str(e))


@collection.command()
@click.option("--active/--all", default=True, help="Show only active collections")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def list(active: bool, format: str):
    """List all collections.

    Examples:
        dv collection list
        dv collection list --all
        dv collection list --format json
    """
    console = default_console

    collection_list = collections.list_collections(active_only=active)

    if format == "json":
        print(
            json.dumps(
                {
                    "status": "success",
                    "count": len(collection_list),
                    "collections": collection_list,
                },
                indent=2,
            )
        )
        return

    if not collection_list:
        console.print(
            "No collections found. Create one with: dv collection create <name>"
        )
        return

    # Create table
    table = Table(title=f"Document Collections ({len(collection_list)} total)")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Name", style="green")
    table.add_column("Documents", style="yellow", justify="right")
    table.add_column("Description", style="white", max_width=40)
    table.add_column("Status", style="magenta")

    for coll in collection_list:
        status = "[green]Active[/]" if coll["is_active"] else "[dim]Inactive[/]"
        desc = (
            coll["description"][:37] + "..."
            if coll["description"] and len(coll["description"]) > 40
            else coll["description"] or ""
        )

        table.add_row(
            str(coll["id"]), coll["name"], str(coll["document_count"]), desc, status
        )

    console.print(table)
    console.print(
        "\n💡 Use [cyan]dv collection show <name>[/] to see collection details"
    )


@collection.command()
@click.argument("collection_name")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def show(collection_name: str, format: str):
    """Show details of a collection including its documents.

    Examples:
        dv collection show "Python Web Dev"
        dv collection show "ML Pipeline" --format json
    """
    console = default_console

    # Get collection by name
    coll = collections.get_collection_by_name(collection_name)
    if not coll:
        if format == "json":
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error": f"Collection '{collection_name}' not found",
                    }
                )
            )
        else:
            console.error(f"Collection '{collection_name}' not found")
        return

    # Get documents in collection
    docs = collections.get_collection_documents(coll["id"])

    if format == "json":
        print(
            json.dumps(
                {"status": "success", "collection": coll, "documents": docs}, indent=2
            )
        )
        return

    # Display collection info
    console.print(f"\n[bold green]{coll['name']}[/] (ID: {coll['id']})")
    if coll["description"]:
        console.print(f"Description: {coll['description']}")
    if coll["default_tags"]:
        console.print(f"Default tags: {', '.join(coll['default_tags'])}")
    console.print(f"Status: {'Active' if coll['is_active'] else 'Inactive'}")
    console.print(f"Created: {coll['created_at']}")

    if not docs:
        console.print("\n[yellow]No documents in this collection yet.[/]")
        console.print(
            f'Add documents with: [cyan]dv collection add "{collection_name}" <doc_id>[/]'
        )
        return

    # Display documents table
    console.print(f"\n[bold]Documents ({len(docs)} total):[/]")

    table = Table()
    table.add_column("#", style="dim", width=4)
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Title", style="white")
    table.add_column("URL", style="blue", max_width=40)
    table.add_column("Added", style="dim")

    for i, doc in enumerate(docs, 1):
        url = doc["url"][:37] + "..." if len(doc["url"]) > 40 else doc["url"]
        table.add_row(
            str(i),
            str(doc["id"]),
            doc["title"] or "Untitled",
            url,
            doc["added_at"][:10],  # Just the date
        )

        # Show notes if present
        if doc.get("notes"):
            table.add_row("", "", f"[dim]Note: {doc['notes']}[/]", "", "")

    console.print(table)


@collection.command()
@click.argument("collection_name")
@click.argument("document_ids", nargs=-1, type=int, required=True)
@click.option("--notes", "-n", help="Notes about why these documents are included")
@validate_doc_id
def add(collection_name: str, document_ids: builtins.list[int], notes: str | None):
    """Add documents to a collection.

    Examples:
        dv collection add "Python Web Dev" 123 456 789
        dv collection add "ML Pipeline" 42 --notes "Core PyTorch documentation"
    """
    console = default_console

    # Get collection
    coll = collections.get_collection_by_name(collection_name)
    if not coll:
        console.error(f"Collection '{collection_name}' not found")
        return

    # Add each document
    added = 0
    already_exists = 0

    for doc_id in document_ids:
        if collections.add_document_to_collection(coll["id"], doc_id, notes=notes):
            added += 1
        else:
            already_exists += 1

    # Report results
    if added > 0:
        console.print(f"[green]✓ Added {added} document(s) to '{collection_name}'[/]")
    if already_exists > 0:
        console.print(
            f"[yellow]⚠️  {already_exists} document(s) already in collection[/]"
        )

    # Suggest tagging if collection has default tags
    if coll.get("default_tags") and added > 0:
        console.print(
            f"\n💡 Consider tagging these documents with: {', '.join(coll['default_tags'])}"
        )
        console.print(
            f"   [cyan]dv tag add {' '.join(map(str, document_ids))} {' '.join(coll['default_tags'])}[/]"
        )


@collection.command()
@click.argument("collection_name")
@click.argument("document_ids", nargs=-1, type=int, required=True)
def remove(collection_name: str, document_ids: builtins.list[int]):
    """Remove documents from a collection.

    Examples:
        dv collection remove "Python Web Dev" 123 456
    """
    console = default_console

    # Get collection
    coll = collections.get_collection_by_name(collection_name)
    if not coll:
        console.error(f"Collection '{collection_name}' not found")
        return

    # Remove each document
    removed = 0
    not_found = 0

    for doc_id in document_ids:
        if collections.remove_document_from_collection(coll["id"], doc_id):
            removed += 1
        else:
            not_found += 1

    # Report results
    if removed > 0:
        console.print(
            f"[green]✓ Removed {removed} document(s) from '{collection_name}'[/]"
        )
    if not_found > 0:
        console.print(f"[yellow]⚠️  {not_found} document(s) not found in collection[/]")


@collection.command()
@click.argument("collection_name")
@click.option("--name", "-n", help="New collection name")
@click.option("--description", "-d", help="New description")
@click.option("--activate/--deactivate", default=None, help="Change active status")
def update(
    collection_name: str,
    name: str | None,
    description: str | None,
    activate: bool | None,
):
    """Update collection properties.

    Examples:
        dv collection update "Old Name" --name "New Name"
        dv collection update "My Project" --description "Updated description"
        dv collection update "Archived" --deactivate
    """
    console = default_console

    # Get collection
    coll = collections.get_collection_by_name(collection_name)
    if not coll:
        console.error(f"Collection '{collection_name}' not found")
        return

    # Update collection
    updated = collections.update_collection(
        coll["id"], name=name, description=description, is_active=activate
    )

    if updated:
        console.print(f"[green]✓ Updated collection '{collection_name}'[/]")
        if name:
            console.print(f"  New name: {name}")
        if description is not None:
            console.print(f"  New description: {description}")
        if activate is not None:
            console.print(f"  Status: {'Active' if activate else 'Inactive'}")
    else:
        console.print("[yellow]No changes made[/]")


@collection.command()
@click.argument("collection_name")
@click.confirmation_option(prompt="Are you sure you want to delete this collection?")
def delete(collection_name: str):
    """Delete a collection (documents remain in vault).

    Examples:
        dv collection delete "Old Project"
    """
    console = default_console

    # Get collection
    coll = collections.get_collection_by_name(collection_name)
    if not coll:
        console.error(f"Collection '{collection_name}' not found")
        return

    # Delete collection
    if collections.delete_collection(coll["id"]):
        console.print(f"[green]✓ Deleted collection '{collection_name}'[/]")
        console.print("[dim]Note: Documents remain in the vault[/]")
    else:
        console.error("Failed to delete collection")


@collection.command()
@click.argument("document_id", type=int)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@validate_doc_id
def find(document_id: int, format: str):
    """Find which collections contain a document.

    Examples:
        dv collection find 123
        dv collection find 456 --format json
    """
    console = default_console

    colls = collections.get_document_collections(document_id)

    if format == "json":
        print(
            json.dumps(
                {
                    "status": "success",
                    "document_id": document_id,
                    "count": len(colls),
                    "collections": colls,
                },
                indent=2,
            )
        )
        return

    if not colls:
        console.print(f"Document {document_id} is not in any collections")
        return

    console.print(f"\nDocument {document_id} is in {len(colls)} collection(s):\n")

    for coll in colls:
        console.print(f"• [green]{coll['name']}[/]")
        if coll.get("notes"):
            console.print(f"  Note: {coll['notes']}")
        console.print(f"  Position: {coll['position']}, Added: {coll['added_at'][:10]}")


# Export the click group
__all__ = ["collection"]
