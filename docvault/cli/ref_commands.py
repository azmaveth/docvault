"""Cross-reference navigation commands for DocVault CLI."""

import click
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from docvault.db import operations
from docvault.models import cross_references

console = Console()


@click.group(name="ref")
def ref_cmd():
    """Navigate cross-references and related sections."""
    pass


@ref_cmd.command("show")
@click.argument("document_id", type=int)
@click.option(
    "--type", help="Filter by reference type (function, class, method, module)"
)
def show_refs(document_id, type):
    """Show all cross-references for a document.

    Examples:
        dv ref show 1
        dv ref show 1 --type function
    """
    doc = operations.get_document(document_id)
    if not doc:
        console.print(f"[red]Error:[/] Document {document_id} not found")
        return

    console.print(f"\n[bold]Cross-References for:[/] {doc['title']}\n")

    # Build reference graph
    graph = cross_references.build_reference_graph(document_id)

    if not graph["edges"]:
        console.print("[yellow]No cross-references found in this document.[/]")
        return

    # Group references by source segment
    refs_by_segment = {}
    for edge in graph["edges"]:
        source_id = edge["source_segment_id"]
        if source_id not in refs_by_segment:
            refs_by_segment[source_id] = []
        if not type or edge["reference_type"] == type:
            refs_by_segment[source_id].append(edge)

    # Display references
    segments_map = {s["id"]: s for s in graph["nodes"]}

    for segment_id, refs in refs_by_segment.items():
        if not refs:
            continue

        segment = segments_map.get(segment_id, {})
        console.print(
            f"[yellow]From: {segment.get('section_title', 'Unknown Section')}[/]"
        )

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Type", style="cyan", width=10)
        table.add_column("Reference", style="green", width=25)
        table.add_column("Target", style="blue")
        table.add_column("Resolved", style="dim")

        for ref in refs:
            target = "Not resolved"
            resolved = "❌"

            if ref.get("target_segment_id"):
                target_seg = segments_map.get(ref["target_segment_id"], {})
                target = target_seg.get(
                    "section_title", f"Segment {ref['target_segment_id']}"
                )
                resolved = "✅"

            table.add_row(
                ref["reference_type"], ref["reference_text"], target, resolved
            )

        console.print(table)
        console.print()


@ref_cmd.command("graph")
@click.argument("document_id", type=int)
def show_graph(document_id):
    """Show reference graph as a tree structure.

    Examples:
        dv ref graph 1
    """
    doc = operations.get_document(document_id)
    if not doc:
        console.print(f"[red]Error:[/] Document {document_id} not found")
        return

    console.print(f"\n[bold]Reference Graph for:[/] {doc['title']}\n")

    # Build reference graph
    graph = cross_references.build_reference_graph(document_id)

    # Create a tree view
    tree = Tree(f"[bold cyan]{doc['title']}[/]")

    # Build adjacency list
    refs_from = {}
    refs_to = {}
    for edge in graph["edges"]:
        source = edge["source_segment_id"]
        target = edge.get("target_segment_id")

        if target:
            if source not in refs_from:
                refs_from[source] = []
            refs_from[source].append(
                (target, edge["reference_text"], edge["reference_type"])
            )

            if target not in refs_to:
                refs_to[target] = []
            refs_to[target].append(
                (source, edge["reference_text"], edge["reference_type"])
            )

    # Create segment map
    segments_map = {s["id"]: s for s in graph["nodes"]}

    # Add nodes to tree
    for segment in graph["nodes"]:
        seg_id = segment["id"]
        title = segment.get("section_title", "Unknown")

        # Count references
        out_refs = len(refs_from.get(seg_id, []))
        in_refs = len(refs_to.get(seg_id, []))

        if out_refs > 0 or in_refs > 0:
            node_text = f"{title} [dim](→{out_refs} ←{in_refs})[/]"
            node = tree.add(node_text)

            # Add outgoing references
            if out_refs > 0:
                out_branch = node.add("[green]References to:[/]")
                for target_id, ref_text, ref_type in refs_from[seg_id]:
                    target_seg = segments_map.get(target_id, {})
                    out_branch.add(
                        f"[cyan]{ref_text}[/] → {target_seg.get('section_title', 'Unknown')} [dim]({ref_type})[/]"
                    )

            # Add incoming references
            if in_refs > 0:
                in_branch = node.add("[blue]Referenced by:[/]")
                for source_id, ref_text, ref_type in refs_to[seg_id]:
                    source_seg = segments_map.get(source_id, {})
                    in_branch.add(
                        f"{source_seg.get('section_title', 'Unknown')} → [cyan]{ref_text}[/] [dim]({ref_type})[/]"
                    )

    console.print(tree)


@ref_cmd.command("find")
@click.argument("reference_name")
@click.option(
    "--type", help="Filter by reference type (function, class, method, module)"
)
def find_reference(reference_name, type):
    """Find where a specific identifier is defined and referenced.

    Examples:
        dv ref find MyClass
        dv ref find process_data --type function
    """
    import sqlite3

    from docvault import config

    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Find anchors (definitions)
        query = """
            SELECT da.*, d.title as doc_title, d.id as doc_id,
                   ds.section_title
            FROM document_anchors da
            JOIN documents d ON da.document_id = d.id
            JOIN document_segments ds ON da.segment_id = ds.id
            WHERE da.anchor_name = ?
        """
        params = [reference_name]

        if type:
            query += " AND da.anchor_type = ?"
            params.append(type)

        cursor = conn.cursor()
        cursor.execute(query, params)
        definitions = cursor.fetchall()

        if definitions:
            console.print(f"\n[bold green]Definitions of '{reference_name}':[/]\n")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Document", style="cyan")
            table.add_column("Section", style="green")
            table.add_column("Type", style="yellow")
            table.add_column("Signature", style="blue")

            for defn in definitions:
                table.add_row(
                    f"{defn['doc_title']} (ID: {defn['doc_id']})",
                    defn["section_title"],
                    defn["anchor_type"],
                    defn["anchor_signature"] or defn["anchor_name"],
                )

            console.print(table)
        else:
            console.print(f"[yellow]No definitions found for '{reference_name}'[/]")

        # Find references
        query = """
            SELECT cr.*, d.title as doc_title, d.id as doc_id,
                   ds.section_title as source_section
            FROM cross_references cr
            JOIN document_segments ds ON cr.source_segment_id = ds.id
            JOIN documents d ON ds.document_id = d.id
            WHERE cr.reference_text = ?
        """
        params = [reference_name]

        if type:
            query += " AND cr.reference_type = ?"
            params.append(type)

        cursor.execute(query, params)
        references = cursor.fetchall()

        if references:
            console.print(f"\n[bold blue]References to '{reference_name}':[/]\n")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Document", style="cyan")
            table.add_column("Section", style="green")
            table.add_column("Type", style="yellow")
            table.add_column("Context", style="dim", max_width=50)

            for ref in references:
                context = ref["reference_context"]
                if len(context) > 50:
                    context = context[:47] + "..."

                table.add_row(
                    f"{ref['doc_title']} (ID: {ref['doc_id']})",
                    ref["source_section"],
                    ref["reference_type"],
                    context,
                )

            console.print(table)
        else:
            console.print(f"[yellow]No references found to '{reference_name}'[/]")

    finally:
        conn.close()
