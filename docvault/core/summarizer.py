"""
Document summarization module for extracting key information from documentation.

This module provides intelligent summarization of documentation while preserving
code snippets, function signatures, and key technical details.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from docvault.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CodeSnippet:
    """Represents a code snippet found in documentation"""

    language: Optional[str]
    code: str
    context: str  # Text around the code snippet
    line_number: int


@dataclass
class Summary:
    """Represents a document summary"""

    key_points: List[str]
    code_snippets: List[CodeSnippet]
    functions: List[Dict[str, str]]  # Function name -> signature
    classes: List[Dict[str, str]]  # Class name -> description
    important_sections: Dict[str, str]  # Section title -> brief content
    total_length: int
    summary_length: int


class DocumentSummarizer:
    """Summarizes documentation focusing on method signatures, parameters, and examples."""

    def __init__(self):
        """Initialize the summarizer with pattern configurations."""
        # Patterns for detecting different documentation elements
        self.patterns = {
            # Function/method signatures
            "function": [
                r"^(?:def|function|func)\s+(\w+)\s*\([^)]*\)",  # Python, JS, etc
                r"^(\w+)\s*\([^)]*\)\s*{",  # C-style
                r"^public\s+(?:static\s+)?(?:\w+\s+)?(\w+)\s*\([^)]*\)",  # Java
                r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)",  # JavaScript
                r"^(\w+)\s*::\s*\([^)]*\)",  # Ruby
            ],
            # Class definitions
            "class": [
                r"^class\s+(\w+)",  # Python, JS, Ruby
                r"^public\s+class\s+(\w+)",  # Java
                r"^struct\s+(\w+)",  # C/C++
                r"^interface\s+(\w+)",  # TypeScript, Java
            ],
            # Parameter documentation
            "param": [
                r"@param\s+(?:\{[^}]+\}\s+)?(\w+)\s+(.+)",  # JSDoc style
                r":param\s+(\w+):\s*(.+)",  # Python docstring
                r"\\param\s+(\w+)\s+(.+)",  # Doxygen
                r"@(\w+)\s+(.+?)(?=@|\n\n|\Z)",  # Generic @ style
            ],
            # Return value documentation
            "return": [
                r"@returns?\s+(?:\{[^}]+\}\s+)?(.+)",  # JSDoc
                r":returns?:\s*(.+)",  # Python
                r"\\returns?\s+(.+)",  # Doxygen
            ],
            # Code examples
            "example": [
                r"```[\w]*\n(.*?)```",  # Markdown code blocks
                r"<code>(.*?)</code>",  # HTML code
                r"(?:Example|Usage):\s*\n((?:(?!^[A-Z]).*\n)*)",  # Example sections
                r">>>\s*(.+?)(?=>>>|\n\n|\Z)",  # Python doctest
            ],
        }

    def summarize(self, content: str, max_items: int = 10) -> Dict[str, any]:
        """
        Generate a summary of the documentation content.

        Args:
            content: The documentation content to summarize
            max_items: Maximum number of items to include per category

        Returns:
            Dictionary containing summary information
        """
        summary = {
            "functions": [],
            "classes": [],
            "parameters": {},
            "examples": [],
            "overview": "",
            "key_concepts": [],
        }

        # Extract overview (first paragraph or section)
        summary["overview"] = self._extract_overview(content)

        # Extract functions and methods
        summary["functions"] = self._extract_functions(content, max_items)

        # Extract classes
        summary["classes"] = self._extract_classes(content, max_items)

        # Extract parameters for functions
        summary["parameters"] = self._extract_parameters(content)

        # Extract code examples
        summary["examples"] = self._extract_examples(content, max_items // 2)

        # Extract key concepts
        summary["key_concepts"] = self._extract_key_concepts(content)

        return summary

    def _extract_overview(self, content: str) -> str:
        """Extract the overview or first meaningful paragraph."""
        lines = content.split("\n")
        overview_lines = []
        in_overview = False
        skip_first_heading = True

        for line in lines:
            line = line.strip()

            # Skip empty lines at the beginning
            if not line and not overview_lines:
                continue

            # Skip the first heading
            if skip_first_heading and line.startswith("#"):
                skip_first_heading = False
                continue

            # Start collecting after first non-empty, non-heading line
            if line and not line.startswith("#") and not in_overview:
                in_overview = True

            # Stop at next heading or after reasonable length
            if in_overview:
                if (
                    line.startswith("#")
                    or line.startswith("==")
                    or len(overview_lines) > 5
                ):
                    break
                if line:
                    overview_lines.append(line)

        result = " ".join(overview_lines)
        return result[:500] + "..." if len(result) > 500 else result

    def _extract_functions(self, content: str, max_items: int) -> List[Dict[str, str]]:
        """Extract function/method signatures."""
        functions = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            for pattern in self.patterns["function"]:
                match = re.match(pattern, line.strip())
                if match:
                    func_name = match.group(1)
                    # Try to get the full signature
                    signature = line.strip()

                    # Look for description in next few lines
                    description = ""
                    for j in range(i + 1, min(i + 4, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and not next_line.startswith(
                            ("#", "//", "/*", "*")
                        ):
                            description = next_line
                            break

                    functions.append(
                        {
                            "name": func_name,
                            "signature": signature,
                            "description": description[:200],
                        }
                    )

                    if len(functions) >= max_items:
                        return functions
                    break

        return functions

    def _extract_classes(self, content: str, max_items: int) -> List[Dict[str, str]]:
        """Extract class definitions."""
        classes = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            for pattern in self.patterns["class"]:
                match = re.match(pattern, line.strip())
                if match:
                    class_name = match.group(1)

                    # Look for description
                    description = ""
                    for j in range(i + 1, min(i + 4, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and not next_line.startswith(
                            ("#", "//", "/*", "*", "class", "def")
                        ):
                            description = next_line
                            break

                    classes.append(
                        {"name": class_name, "description": description[:200]}
                    )

                    if len(classes) >= max_items:
                        return classes
                    break

        return classes

    def _extract_parameters(self, content: str) -> Dict[str, List[Dict[str, str]]]:
        """Extract parameter documentation."""
        parameters = {}
        current_function = None

        lines = content.split("\n")
        for i, line in enumerate(lines):
            # Check if this is a function definition
            for pattern in self.patterns["function"]:
                match = re.match(pattern, line.strip())
                if match:
                    current_function = match.group(1)
                    parameters[current_function] = []
                    break

            # Extract parameters if we're in a function context
            if current_function:
                for pattern in self.patterns["param"]:
                    match = re.search(pattern, line)
                    if match:
                        param_name = match.group(1)
                        param_desc = match.group(2) if match.lastindex >= 2 else ""
                        parameters[current_function].append(
                            {"name": param_name, "description": param_desc.strip()}
                        )
                        break

                # Reset function context if we hit another function or class
                if re.match(r"^(class|def|function)\s+", line.strip()):
                    current_function = None

        # Clean up empty parameter lists
        parameters = {k: v for k, v in parameters.items() if v}

        return parameters

    def _extract_examples(self, content: str, max_items: int) -> List[Dict[str, str]]:
        """Extract code examples."""
        examples = []

        # Extract markdown code blocks
        code_blocks = re.findall(r"```(?:[\w]+)?\n(.*?)```", content, re.DOTALL)
        for code in code_blocks[:max_items]:
            examples.append(
                {"type": "code", "content": code.strip()[:300]}  # Limit length
            )

        # Extract example sections
        example_sections = re.findall(
            r"(?:Example|Usage):\s*\n((?:(?!^[A-Z#]).*\n)*)", content, re.MULTILINE
        )
        for example in example_sections[: max_items - len(examples)]:
            examples.append({"type": "text", "content": example.strip()[:300]})

        return examples

    def _extract_key_concepts(self, content: str) -> List[str]:
        """Extract key concepts and important terms."""
        # Look for emphasized terms
        concepts = set()

        # Bold text
        bold_terms = re.findall(r"\*\*([^*]+)\*\*", content)
        concepts.update(term.strip() for term in bold_terms if len(term.strip()) < 50)

        # Headings (likely important sections)
        headings = re.findall(r"^#+\s+(.+)$", content, re.MULTILINE)
        concepts.update(
            heading.strip()
            for heading in headings
            if len(heading.strip()) < 50 and not heading.strip().isdigit()
        )

        # Technical terms in backticks
        code_terms = re.findall(r"`([^`]+)`", content)
        concepts.update(
            term.strip()
            for term in code_terms
            if len(term.strip()) < 30 and " " not in term.strip()
        )

        return sorted(list(concepts))[:20]

    def format_summary(self, summary: Dict[str, any], format: str = "text") -> str:
        """
        Format the summary for display.

        Args:
            summary: The summary dictionary
            format: Output format ('text', 'markdown', 'json')

        Returns:
            Formatted summary string
        """
        if format == "json":
            import json

            return json.dumps(summary, indent=2)

        elif format == "markdown":
            output = []

            if summary["overview"]:
                output.append(f"## Overview\n\n{summary['overview']}\n")

            if summary["classes"]:
                output.append("## Classes\n")
                for cls in summary["classes"]:
                    output.append(f"- **{cls['name']}**: {cls['description']}")
                output.append("")

            if summary["functions"]:
                output.append("## Functions\n")
                for func in summary["functions"]:
                    output.append(f"### {func['name']}\n")
                    output.append(f"```\n{func['signature']}\n```")
                    if func["description"]:
                        output.append(f"{func['description']}\n")
                output.append("")

            if summary["parameters"]:
                output.append("## Parameters\n")
                for func_name, params in summary["parameters"].items():
                    output.append(f"### {func_name}")
                    for param in params:
                        output.append(f"- **{param['name']}**: {param['description']}")
                    output.append("")

            if summary["examples"]:
                output.append("## Examples\n")
                for i, example in enumerate(summary["examples"], 1):
                    if example["type"] == "code":
                        output.append(
                            f"### Example {i}\n```\n{example['content']}\n```\n"
                        )
                    else:
                        output.append(f"### Example {i}\n{example['content']}\n")

            if summary["key_concepts"]:
                output.append("## Key Concepts\n")
                output.append(
                    ", ".join(f"`{concept}`" for concept in summary["key_concepts"])
                )

            return "\n".join(output)

        else:  # text format
            output = []

            if summary["overview"]:
                output.append("OVERVIEW:")
                output.append(summary["overview"])
                output.append("")

            if summary["classes"]:
                output.append("CLASSES:")
                for cls in summary["classes"]:
                    output.append(f"  - {cls['name']}: {cls['description']}")
                output.append("")

            if summary["functions"]:
                output.append("FUNCTIONS:")
                for func in summary["functions"]:
                    output.append(f"  - {func['name']}")
                    output.append(f"    {func['signature']}")
                    if func["description"]:
                        output.append(f"    {func['description']}")
                output.append("")

            if summary["examples"]:
                output.append(f"EXAMPLES ({len(summary['examples'])} found):")
                for i, example in enumerate(summary["examples"][:3], 1):
                    output.append(f"  Example {i}:")
                    content_lines = example["content"].split("\n")
                    for line in content_lines[:5]:
                        output.append(f"    {line}")
                    if len(content_lines) > 5:
                        output.append("    ...")
                output.append("")

            if summary["key_concepts"]:
                output.append("KEY CONCEPTS:")
                output.append("  " + ", ".join(summary["key_concepts"][:10]))

            return "\n".join(output)

    def highlight_query_terms(self, content: str, query_terms: List[str]) -> str:
        """
        Highlight query terms in the content.

        Args:
            content: The content to highlight
            query_terms: List of terms to highlight

        Returns:
            Content with terms wrapped in highlight markers
        """
        highlighted = content

        for term in query_terms:
            # Case-insensitive highlighting
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            # Use a lambda to preserve the original case
            highlighted = pattern.sub(lambda m: f"**{m.group()}**", highlighted)

        return highlighted

    def extract_relevant_snippets(
        self, content: str, query: str, window_size: int = 200
    ) -> List[str]:
        """
        Extract snippets around query matches.

        Args:
            content: The content to search
            query: The search query
            window_size: Number of characters to include around match

        Returns:
            List of relevant snippets
        """
        snippets = []
        query_terms = query.lower().split()
        content_lower = content.lower()

        # Find all occurrences of any query term
        matches = []
        for term in query_terms:
            start = 0
            while True:
                pos = content_lower.find(term, start)
                if pos == -1:
                    break
                matches.append((pos, len(term)))
                start = pos + 1

        # Sort matches by position
        matches.sort()

        # Merge overlapping windows
        merged_windows = []
        for pos, length in matches:
            window_start = max(0, pos - window_size // 2)
            window_end = min(len(content), pos + length + window_size // 2)

            if merged_windows and window_start <= merged_windows[-1][1]:
                # Merge with previous window
                merged_windows[-1] = (merged_windows[-1][0], window_end)
            else:
                merged_windows.append((window_start, window_end))

        # Extract snippets
        for start, end in merged_windows:
            snippet = content[start:end]

            # Clean up snippet
            if start > 0:
                # Find word boundary
                while start > 0 and content[start - 1] not in " \n\t":
                    start -= 1
                snippet = "..." + content[start:end]
            if end < len(content):
                # Find word boundary
                while end < len(content) and content[end] not in " \n\t":
                    end += 1
                snippet = snippet + "..."

            # Highlight query terms in snippet
            snippet = self.highlight_query_terms(snippet.strip(), query_terms)
            snippets.append(snippet)

        return snippets
