"""
Tests for tree display functionality.
"""

from docvault.utils.tree_display import (
    TreeNode,
    aggregate_section_data,
    build_section_tree,
    render_tree,
    render_tree_with_style,
)


class TestTreeNode:
    """Test TreeNode data structure."""

    def test_tree_node_creation(self):
        """Test creating a tree node."""
        node = TreeNode(id="1", title="Introduction", level=1, path="1")

        assert node.id == "1"
        assert node.title == "Introduction"
        assert node.level == 1
        assert node.path == "1"
        assert node.parent_id is None
        assert node.children == []
        assert node.metadata == {}

    def test_tree_node_with_metadata(self):
        """Test tree node with metadata."""
        metadata = {"match_count": 5, "score": 0.95}
        node = TreeNode(
            id="2.1", title="API Reference", level=2, path="2.1", metadata=metadata
        )

        assert node.metadata == metadata
        assert node.metadata["match_count"] == 5


class TestBuildSectionTree:
    """Test building tree structure from flat sections."""

    def test_build_simple_tree(self):
        """Test building a simple tree structure."""
        sections = [
            {"section_path": "1", "section_title": "Introduction", "section_level": 1},
            {"section_path": "2", "section_title": "Installation", "section_level": 1},
            {
                "section_path": "2.1",
                "section_title": "Requirements",
                "section_level": 2,
            },
            {"section_path": "2.2", "section_title": "Setup", "section_level": 2},
        ]

        roots = build_section_tree(sections)

        assert len(roots) == 2
        assert roots[0].title == "Introduction"
        assert roots[1].title == "Installation"
        assert len(roots[1].children) == 2
        assert roots[1].children[0].title == "Requirements"
        assert roots[1].children[1].title == "Setup"

    def test_build_deep_tree(self):
        """Test building a tree with multiple levels."""
        sections = [
            {"section_path": "1", "section_title": "Chapter 1", "section_level": 1},
            {"section_path": "1.1", "section_title": "Section 1.1", "section_level": 2},
            {
                "section_path": "1.1.1",
                "section_title": "Subsection 1.1.1",
                "section_level": 3,
            },
            {
                "section_path": "1.1.2",
                "section_title": "Subsection 1.1.2",
                "section_level": 3,
            },
            {"section_path": "1.2", "section_title": "Section 1.2", "section_level": 2},
        ]

        roots = build_section_tree(sections)

        assert len(roots) == 1
        assert roots[0].title == "Chapter 1"
        assert len(roots[0].children) == 2
        assert roots[0].children[0].title == "Section 1.1"
        assert len(roots[0].children[0].children) == 2
        assert roots[0].children[0].children[0].title == "Subsection 1.1.1"

    def test_build_tree_with_metadata(self):
        """Test building tree preserves metadata."""
        sections = [
            {
                "section_path": "1",
                "section_title": "Main",
                "section_level": 1,
                "match_count": 10,
                "custom_field": "value",
            }
        ]

        roots = build_section_tree(sections)

        assert roots[0].metadata["match_count"] == 10
        assert roots[0].metadata["custom_field"] == "value"


class TestRenderTree:
    """Test tree rendering functions."""

    def test_render_simple_tree(self):
        """Test rendering a simple tree."""
        root = TreeNode("1", "Root", 1, "1")
        child1 = TreeNode("1.1", "Child 1", 2, "1.1")
        child2 = TreeNode("1.2", "Child 2", 2, "1.2")
        root.children = [child1, child2]

        lines = render_tree([root])

        assert len(lines) == 3
        assert lines[0] == "Root"
        assert lines[1] == "├── Child 1"
        assert lines[2] == "└── Child 2"

    def test_render_nested_tree(self):
        """Test rendering a nested tree."""
        root = TreeNode("1", "Root", 1, "1")
        child = TreeNode("1.1", "Child", 2, "1.1")
        grandchild = TreeNode("1.1.1", "Grandchild", 3, "1.1.1")
        child.children = [grandchild]
        root.children = [child]

        lines = render_tree([root])

        assert len(lines) == 3
        assert lines[0] == "Root"
        assert lines[1] == "└── Child"
        assert lines[2] == "    └── Grandchild"

    def test_render_tree_with_metadata(self):
        """Test rendering tree with metadata."""
        root = TreeNode("1", "Root", 1, "1", metadata={"match_count": 5})

        lines = render_tree([root], show_metadata=True)

        assert len(lines) == 2
        assert lines[0] == "Root"
        assert "[5 matches]" in lines[1]


class TestRenderTreeWithStyle:
    """Test styled tree rendering."""

    def test_render_styled_tree(self):
        """Test rendering tree with Rich styling."""
        root = TreeNode("1", "Chapter", 1, "1", metadata={"match_count": 3})
        child = TreeNode("1.1", "Section", 2, "1.1", metadata={"match_count": 2})
        root.children = [child]

        styled_lines = render_tree_with_style([root], show_counts=True)

        assert len(styled_lines) == 2
        assert styled_lines[0][0] == "Chapter (3 matches)"
        assert styled_lines[0][1] == "bold"  # Level 1 is bold
        assert styled_lines[1][0] == "└── Section (2 matches)"
        assert styled_lines[1][1] == ""  # Level 2 is not bold

    def test_render_styled_tree_with_paths(self):
        """Test rendering tree with path information."""
        root = TreeNode("2.1", "Section", 2, "2.1")

        styled_lines = render_tree_with_style(
            [root], show_paths=True, show_counts=False
        )

        assert len(styled_lines) == 1
        assert "2.1" in styled_lines[0][0]


class TestAggregateSectionData:
    """Test section data aggregation."""

    def test_aggregate_basic(self):
        """Test basic section aggregation."""
        sections_dict = {
            "1": [
                {"section_title": "Intro", "section_level": 1, "score": 0.9},
                {"section_title": "Intro", "section_level": 1, "score": 0.8},
            ],
            "2": [{"section_title": "API", "section_level": 1, "score": 0.95}],
        }

        aggregated = aggregate_section_data(sections_dict)

        assert len(aggregated) == 2
        assert aggregated["1"]["match_count"] == 2
        assert abs(aggregated["1"]["total_score"] - 1.7) < 0.0001
        assert abs(aggregated["1"]["avg_score"] - 0.85) < 0.0001
        assert aggregated["2"]["match_count"] == 1
        assert abs(aggregated["2"]["avg_score"] - 0.95) < 0.0001

    def test_aggregate_empty_sections(self):
        """Test aggregating empty sections."""
        sections_dict = {"1": []}

        aggregated = aggregate_section_data(sections_dict)

        assert aggregated["1"]["match_count"] == 0
        assert aggregated["1"]["avg_score"] == 0


class TestIntegration:
    """Integration tests for tree display."""

    def test_full_workflow(self):
        """Test complete workflow from flat data to rendered tree."""
        # Simulate search results
        sections_dict = {
            "1": [
                {
                    "section_title": "Overview",
                    "section_level": 1,
                    "section_path": "1",
                    "score": 0.9,
                },
                {
                    "section_title": "Overview",
                    "section_level": 1,
                    "section_path": "1",
                    "score": 0.85,
                },
            ],
            "1.1": [
                {
                    "section_title": "Introduction",
                    "section_level": 2,
                    "section_path": "1.1",
                    "score": 0.8,
                }
            ],
            "1.2": [
                {
                    "section_title": "Goals",
                    "section_level": 2,
                    "section_path": "1.2",
                    "score": 0.75,
                }
            ],
            "2": [
                {
                    "section_title": "Installation",
                    "section_level": 1,
                    "section_path": "2",
                    "score": 0.95,
                }
            ],
        }

        # Aggregate data
        section_data = aggregate_section_data(sections_dict)

        # Build tree
        section_list = list(section_data.values())
        tree_nodes = build_section_tree(section_list)

        # Render tree
        lines = render_tree(tree_nodes)

        # Verify structure
        assert len(tree_nodes) == 2  # Two root nodes
        assert tree_nodes[0].title == "Overview"
        assert len(tree_nodes[0].children) == 2  # Two children
        assert tree_nodes[1].title == "Installation"

        # Verify rendering
        assert "Overview" in lines[0]
        assert "Introduction" in lines[1]
        assert "Goals" in lines[2]
        assert "Installation" in lines[3]
