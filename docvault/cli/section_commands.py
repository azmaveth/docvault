"""
CLI commands for section-based document operations.
"""

import json
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from docvault.core.section_navigator import (
    SectionNavigator,
    get_document_toc,
    get_section_content,
)
from docvault.db.operations import get_document
from docvault.utils.console import console as docvault_console

console = Console()


@click.group()
def sections():
    """Manage document sections and navigation."""
    pass


@sections.command("toc")
@click.argument("document_id", type=int)
@click.option(
    "--format",
    type=click.Choice(["tree", "json", "flat"]),
    default="tree",
    help="Output format for table of contents",
)
@click.option("--max-depth", type=int, default=None, help="Maximum depth to display")
def table_of_contents(document_id: int, format: str, max_depth: Optional[int]):
    """Display table of contents for a document."""
    # Verify document exists
    doc = get_document(document_id)
    if not doc:
        docvault_console.error(f"Document {document_id} not found")
        return

    # Get TOC
    navigator = SectionNavigator(document_id)
    toc = navigator.get_table_of_contents()

    if not toc:
        console.print(f"[yellow]No sections found in document {document_id}[/yellow]")
        return

    # Display based on format
    if format == "tree":
        _display_toc_tree(doc["title"], toc, max_depth)
    elif format == "json":
        toc_dict = get_document_toc(document_id)
        console.print_json(json.dumps(toc_dict, indent=2))
    else:  # flat
        _display_toc_flat(doc["title"], toc, max_depth)


@sections.command("read")
@click.argument("document_id", type=int)
@click.argument("section_path", type=str)
@click.option(
    "--include-children/--no-children",
    default=True,
    help="Include child sections in output",
)
@click.option(
    "--format",
    type=click.Choice(["rich", "plain", "json"]),
    default="rich",
    help="Output format",
)
def read_section(
    document_id: int, section_path: str, include_children: bool, format: str
):
    """Read a specific section by its path (e.g., '1.2.3')."""
    # Verify document exists
    doc = get_document(document_id)
    if not doc:
        docvault_console.error(f"Document {document_id} not found")
        return

    # Get section content
    section_data = get_section_content(document_id, section_path)
    if not section_data:
        docvault_console.error(
            f"Section {section_path} not found in document {document_id}"
        )
        return

    if format == "json":
        console.print_json(json.dumps(section_data, indent=2))
        return

    # Display section content
    if format == "rich":
        panel_content = []

        # Add breadcrumb
        navigator = SectionNavigator(document_id)
        ancestors = navigator.get_section_ancestors(section_data["id"])
        if ancestors:
            breadcrumb = " > ".join([a.section_title for a in ancestors])
            breadcrumb += f" > {section_data['title']}"
            panel_content.append(f"[dim]{breadcrumb}[/dim]\n")

        # Add main content
        if include_children:
            for segment in section_data["segments"]:
                if segment["title"]:
                    level_marker = "#" * segment["level"]
                    panel_content.append(
                        f"\n[bold]{level_marker} {segment['title']}[/bold]\n"
                    )
                panel_content.append(segment["content"])
        else:
            # Only show the main section
            main_segment = section_data["segments"][0]
            panel_content.append(main_segment["content"])

        console.print(
            Panel(
                "\n".join(panel_content),
                title=f"[bold]{section_data['title']}[/bold] ({section_path})",
                border_style="blue",
            )
        )
    else:  # plain
        if include_children:
            for segment in section_data["segments"]:
                if segment["title"]:
                    console.print(f"\n{'#' * segment['level']} {segment['title']}\n")
                console.print(segment["content"])
        else:
            console.print(section_data["segments"][0]["content"])


@sections.command("find")
@click.argument("document_id", type=int)
@click.argument("title_pattern", type=str)
@click.option(
    "--format",
    type=click.Choice(["list", "tree", "json"]),
    default="list",
    help="Output format",
)
def find_sections(document_id: int, title_pattern: str, format: str):
    """Find sections by title pattern."""
    # Verify document exists
    doc = get_document(document_id)
    if not doc:
        docvault_console.error(f"Document {document_id} not found")
        return

    # Find matching sections
    navigator = SectionNavigator(document_id)
    matches = navigator.find_sections_by_title(title_pattern)

    if not matches:
        console.print(f"[yellow]No sections found matching '{title_pattern}'[/yellow]")
        return

    console.print(
        f"[green]Found {len(matches)} sections matching '{title_pattern}':[/green]\n"
    )

    if format == "json":
        matches_data = [
            {
                "id": m.id,
                "title": m.section_title,
                "path": m.section_path,
                "level": m.section_level,
                "preview": m.content_preview,
            }
            for m in matches
        ]
        console.print_json(json.dumps(matches_data, indent=2))
    elif format == "tree":
        # Show matches in tree context
        for match in matches:
            # Get ancestors for context
            ancestors = navigator.get_section_ancestors(match.id)
            tree = Tree(f"[bold]{doc['title']}[/bold]")

            current = tree
            for ancestor in ancestors:
                current = current.add(f"[dim]{ancestor.section_title}[/dim]")

            current.add(
                f"[bold green]{match.section_title}[/bold green] ({match.section_path})"
            )
            console.print(tree)
            console.print()
    else:  # list
        for match in matches:
            console.print(f"[bold]{match.section_path}[/bold] {match.section_title}")
            if match.content_preview:
                console.print(f"  [dim]{match.content_preview}[/dim]")
            console.print()


@sections.command("navigate")
@click.argument("document_id", type=int)
@click.argument("section_id", type=int)
@click.option(
    "--show",
    type=click.Choice(["children", "siblings", "ancestors", "subtree"]),
    default="children",
    help="What to show relative to the section",
)
def navigate_sections(document_id: int, section_id: int, show: str):
    """Navigate section relationships."""
    # Verify document exists
    doc = get_document(document_id)
    if not doc:
        docvault_console.error(f"Document {document_id} not found")
        return

    navigator = SectionNavigator(document_id)

    if show == "children":
        children = navigator.get_section_children(section_id)
        if not children:
            console.print("[yellow]No child sections found[/yellow]")
            return

        console.print("[green]Child sections:[/green]\n")
        for child in children:
            console.print(f"[bold]{child.section_path}[/bold] {child.section_title}")
            if child.content_preview:
                console.print(f"  [dim]{child.content_preview}[/dim]")
            console.print()

    elif show == "siblings":
        siblings = navigator.get_section_siblings(section_id)
        if not siblings:
            console.print("[yellow]No sibling sections found[/yellow]")
            return

        console.print("[green]Sibling sections:[/green]\n")
        for sibling in siblings:
            console.print(
                f"[bold]{sibling.section_path}[/bold] {sibling.section_title}"
            )
            if sibling.content_preview:
                console.print(f"  [dim]{sibling.content_preview}[/dim]")
            console.print()

    elif show == "ancestors":
        ancestors = navigator.get_section_ancestors(section_id)
        if not ancestors:
            console.print(
                "[yellow]No ancestor sections found (this is a root section)[/yellow]"
            )
            return

        console.print("[green]Ancestor sections (from root to parent):[/green]\n")
        for i, ancestor in enumerate(ancestors):
            indent = "  " * i
            console.print(
                f"{indent}[bold]{ancestor.section_path}[/bold] {ancestor.section_title}"
            )

    else:  # subtree
        subtree_root = navigator.get_section_subtree(section_id)
        if not subtree_root:
            console.print("[yellow]Section not found[/yellow]")
            return

        tree = Tree(
            f"[bold]{subtree_root.section_title}[/bold] ({subtree_root.section_path})"
        )
        _build_tree_node(tree, subtree_root.children)
        console.print(tree)


def _display_toc_tree(doc_title: str, toc_nodes, max_depth: Optional[int]):
    """Display TOC as a tree."""
    tree = Tree(f"[bold]{doc_title}[/bold]")
    _build_tree_node(tree, toc_nodes, max_depth=max_depth)
    console.print(tree)


def _build_tree_node(
    parent_node, sections, current_depth: int = 1, max_depth: Optional[int] = None
):
    """Recursively build tree nodes."""
    if max_depth and current_depth > max_depth:
        return

    for section in sections:
        node_text = f"[bold]{section.section_path}[/bold] {section.section_title}"
        if section.content_preview:
            node_text += f"\n    [dim]{section.content_preview}[/dim]"

        child_node = parent_node.add(node_text)

        if section.children and (not max_depth or current_depth < max_depth):
            _build_tree_node(child_node, section.children, current_depth + 1, max_depth)


def _display_toc_flat(doc_title: str, toc_nodes, max_depth: Optional[int]):
    """Display TOC as a flat list."""
    console.print(f"[bold]{doc_title}[/bold]\n")

    def print_sections(sections, current_depth: int = 1):
        if max_depth and current_depth > max_depth:
            return

        for section in sections:
            indent = "  " * (section.section_level - 1)
            console.print(
                f"{indent}[bold]{section.section_path}[/bold] {section.section_title}"
            )

            if section.children and (not max_depth or current_depth < max_depth):
                print_sections(section.children, current_depth + 1)

    print_sections(toc_nodes)
