"""
Tree display utilities for hierarchical data visualization.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class TreeNode:
    """Represents a node in the section tree."""

    id: str
    title: str
    level: int
    path: str
    parent_id: str | None = None
    children: list["TreeNode"] = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.metadata is None:
            self.metadata = {}


def build_section_tree(sections: list[dict[str, Any]]) -> list[TreeNode]:
    """
    Build a tree structure from flat section data.

    Args:
        sections: List of section dictionaries with path, title, level, etc.

    Returns:
        List of root TreeNode objects
    """
    # Create nodes
    nodes = {}
    for section in sections:
        path = section.get("section_path", "0")
        node = TreeNode(
            id=path,
            title=section.get("section_title", "Introduction"),
            level=section.get("section_level", 1),
            path=path,
            metadata=section,
        )
        nodes[path] = node

    # Build parent-child relationships based on paths
    roots = []
    for path, node in nodes.items():
        if "." in path:
            # Find parent by removing last segment
            parent_path = ".".join(path.split(".")[:-1])
            if parent_path in nodes:
                nodes[parent_path].children.append(node)
                node.parent_id = parent_path
            else:
                roots.append(node)
        else:
            roots.append(node)

    # Sort children at each level
    def sort_tree(node: TreeNode):
        node.children.sort(key=lambda n: tuple(map(int, n.path.split("."))))
        for child in node.children:
            sort_tree(child)

    for root in roots:
        sort_tree(root)

    return sorted(roots, key=lambda n: tuple(map(int, n.path.split("."))))


def render_tree(
    nodes: list[TreeNode],
    prefix: str = "",
    is_last: list[bool] = None,
    show_metadata: bool = False,
) -> list[str]:
    """
    Render a tree structure as text lines.

    Args:
        nodes: List of root TreeNode objects
        prefix: Current line prefix for indentation
        is_last: Stack tracking if each level is the last child
        show_metadata: Whether to show additional metadata

    Returns:
        List of formatted strings representing the tree
    """
    if is_last is None:
        is_last = []

    lines = []

    for i, node in enumerate(nodes):
        is_last_node = i == len(nodes) - 1

        # Build the tree connector
        # Add connectors if this is not the root level (is_last is not empty)
        if is_last:  # We're in a recursive call, not the initial call
            connector = "└── " if is_last_node else "├── "
            lines.append(f"{prefix}{connector}{node.title}")
        else:
            lines.append(node.title)

        # Add metadata if requested
        if show_metadata and node.metadata:
            metadata_prefix = prefix + ("    " if is_last_node else "│   ")
            if "match_count" in node.metadata:
                lines.append(
                    f"{metadata_prefix}[{node.metadata['match_count']} matches]"
                )

        # Render children
        if node.children:
            # For direct children of root (is_last is empty), don't add prefix
            # But still need to track the structure for their children
            if not is_last:  # Root level
                child_prefix = ""
            else:
                child_prefix = prefix + ("    " if is_last_node else "│   ")
            lines.extend(
                render_tree(
                    node.children, child_prefix, is_last + [is_last_node], show_metadata
                )
            )

    return lines


def render_tree_with_style(
    nodes: list[TreeNode], show_paths: bool = False, show_counts: bool = True
) -> list[tuple[str, str]]:
    """
    Render a tree with Rich styling information.

    Returns list of (line, style) tuples for Rich console printing.
    """
    styled_lines = []

    def render_node(
        node: TreeNode,
        prefix: str = "",
        is_last: bool = True,
        parent_is_last: list[bool] = None,
    ):
        if parent_is_last is None:
            parent_is_last = []

        # Determine the connector
        # Add connectors if this is not the root level (parent_is_last is not empty)
        if parent_is_last:  # We're rendering a child, not a root
            connector = "└── " if is_last else "├── "
            line_prefix = prefix + connector
        else:
            line_prefix = ""

        # Build the line
        line = f"{line_prefix}{node.title}"
        style = "bold" if node.level == 1 else ""

        # Add metadata
        metadata_parts = []
        if show_paths:
            metadata_parts.append(node.path)
        if show_counts and "match_count" in node.metadata:
            count = node.metadata["match_count"]
            metadata_parts.append(f"{count} match{'es' if count != 1 else ''}")

        if metadata_parts:
            line += f" ({', '.join(metadata_parts)})"

        styled_lines.append((line, style))

        # Render children
        if node.children:
            for i, child in enumerate(node.children):
                is_last_child = i == len(node.children) - 1
                # For direct children of root (parent_is_last is empty), don't add prefix
                if not parent_is_last:  # Root level
                    child_prefix = ""
                else:
                    child_prefix = prefix + ("    " if is_last else "│   ")
                render_node(
                    child, child_prefix, is_last_child, parent_is_last + [is_last]
                )

    for i, root in enumerate(nodes):
        render_node(root, "", i == len(nodes) - 1)

    return styled_lines


def aggregate_section_data(sections_dict: dict[str, list[dict]]) -> dict[str, dict]:
    """
    Aggregate data for sections (e.g., total match counts).

    Args:
        sections_dict: Dictionary mapping section paths to lists of hits

    Returns:
        Dictionary mapping section paths to aggregated data
    """
    aggregated = {}

    for path, hits in sections_dict.items():
        # Get section info from first hit
        first_hit = hits[0] if hits else {}

        aggregated[path] = {
            "section_title": first_hit.get("section_title", "Unknown"),
            "section_level": first_hit.get("section_level", 1),
            "section_path": path,
            "match_count": len(hits),
            "total_score": sum(h.get("score", 0) for h in hits),
            "avg_score": (
                sum(h.get("score", 0) for h in hits) / len(hits) if hits else 0
            ),
        }

    return aggregated
