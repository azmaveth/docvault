"""Context extraction for usage examples, best practices, and pitfalls."""

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CodeExample:
    """Represents a code example with context."""

    code: str
    language: str
    description: str
    section: str
    is_complete: bool  # Whether it's a complete, runnable example
    complexity: str  # 'basic', 'intermediate', 'advanced'


@dataclass
class BestPractice:
    """Represents a best practice or recommendation."""

    title: str
    description: str
    section: str
    importance: str  # 'low', 'medium', 'high', 'critical'


@dataclass
class CommonPitfall:
    """Represents a common pitfall or warning."""

    title: str
    description: str
    solution: str
    section: str
    severity: str  # 'info', 'warning', 'error', 'critical'


@dataclass
class ContextualInfo:
    """Container for all contextual information extracted from documentation."""

    examples: list[CodeExample]
    best_practices: list[BestPractice]
    pitfalls: list[CommonPitfall]
    related_concepts: list[str]
    prerequisites: list[str]


class ContextExtractor:
    """Extracts contextual information from documentation content."""

    def __init__(self):
        # Patterns for identifying different types of content
        self.example_patterns = [
            r"```(\w+)?\s*\n(.*?)\n```",  # Code blocks
            r"`([^`]+)`",  # Inline code
            r"(?:example|sample|demo):\s*\n(.*?)(?:\n\n|\nNote:|\n[A-Z])",
            # Example sections
        ]

        self.best_practice_indicators = [
            r"(?:best practice|recommendation|tip|note|good practice|should|recommended)",
            r"(?:✓|✅|👍|💡|📝|⭐)",  # Common symbols
            r"(?:pro tip|hint|advice|guideline)",
        ]

        self.pitfall_indicators = [
            r"(?:warning|caution|danger|pitfall|gotcha|trap|avoid|don\'t|never)",
            r"(?:⚠️|❌|🚨|❗|⛔|🛑)",  # Warning symbols
            r"(?:common mistake|error|problem|issue|bug|caveat)",
        ]

        self.complexity_indicators = {
            "basic": [
                r"(?:basic|simple|easy|beginner|intro|getting started)",
                r"hello world",
                r"quick start",
            ],
            "intermediate": [
                r"(?:intermediate|moderate|advanced usage)",
                r"real.world",
                r"production",
            ],
            "advanced": [
                r"(?:advanced|complex|expert|optimization|performance)",
                r"custom|extend",
            ],
        }

    def extract_context(self, content: str, section_title: str = "") -> ContextualInfo:
        """Extract all contextual information from content.

        Args:
            content: The documentation content to analyze
            section_title: Title of the section for context

        Returns:
            ContextualInfo object with extracted information
        """
        examples = self._extract_code_examples(content, section_title)
        best_practices = self._extract_best_practices(content, section_title)
        pitfalls = self._extract_pitfalls(content, section_title)
        related_concepts = self._extract_related_concepts(content)
        prerequisites = self._extract_prerequisites(content)

        return ContextualInfo(
            examples=examples,
            best_practices=best_practices,
            pitfalls=pitfalls,
            related_concepts=related_concepts,
            prerequisites=prerequisites,
        )

    def _extract_code_examples(self, content: str, section: str) -> list[CodeExample]:
        """Extract code examples from content."""
        examples = []

        # Extract fenced code blocks
        for match in re.finditer(r"```(\w+)?\s*\n(.*?)\n```", content, re.DOTALL):
            language = match.group(1) or "text"
            code = match.group(2).strip()

            if len(code) < 10:  # Skip very short snippets
                continue

            # Try to find description before or after the code block
            start = max(0, match.start() - 200)
            end = min(len(content), match.end() + 200)
            context_text = content[start:end]

            description = self._extract_description_near_code(
                context_text, match.group(0)
            )
            is_complete = self._is_complete_example(code, language)
            complexity = self._determine_complexity(code + " " + description)

            examples.append(
                CodeExample(
                    code=code,
                    language=language,
                    description=description,
                    section=section,
                    is_complete=is_complete,
                    complexity=complexity,
                )
            )

        # Extract inline code with context
        for match in re.finditer(r"`([^`\n]+)`", content):
            code = match.group(1)

            # Only include if it looks like a meaningful code snippet
            if any(char in code for char in ["(", ".", "=", "-"]) and len(code) > 3:
                # Get surrounding context
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 100)
                context_text = content[start:end]

                description = self._extract_description_near_code(context_text, code)

                examples.append(
                    CodeExample(
                        code=code,
                        language="inline",
                        description=description,
                        section=section,
                        is_complete=False,
                        complexity="basic",
                    )
                )

        return examples

    def _extract_best_practices(self, content: str, section: str) -> list[BestPractice]:
        """Extract best practices and recommendations."""
        practices = []

        # Look for sections with best practice indicators
        for indicator in self.best_practice_indicators:
            for match in re.finditer(
                rf"({indicator}.*?)(?:\n\n|\n[A-Z]|\n-|\n\*)",
                content,
                re.IGNORECASE | re.DOTALL,
            ):
                text = match.group(1).strip()

                if len(text) < 20:  # Skip very short text
                    continue

                # Extract title and description
                lines = text.split("\n")
                title = lines[0][:100]  # First line as title
                description = "\n".join(lines[1:]) if len(lines) > 1 else title

                importance = self._determine_importance(text)

                practices.append(
                    BestPractice(
                        title=title,
                        description=description,
                        section=section,
                        importance=importance,
                    )
                )

        return practices

    def _extract_pitfalls(self, content: str, section: str) -> list[CommonPitfall]:
        """Extract warnings, pitfalls, and common mistakes."""
        pitfalls = []

        for indicator in self.pitfall_indicators:
            for match in re.finditer(
                rf"({indicator}.*?)(?:\n\n|\n[A-Z]|\n-|\n\*|$)",
                content,
                re.IGNORECASE | re.DOTALL,
            ):
                text = match.group(1).strip()

                if len(text) < 20:
                    continue

                lines = text.split("\n")
                title = lines[0][:100]
                description = "\n".join(lines[1:]) if len(lines) > 1 else title

                # Try to find solution in nearby text
                solution = self._extract_solution_near_pitfall(content, match.end())
                severity = self._determine_severity(text)

                pitfalls.append(
                    CommonPitfall(
                        title=title,
                        description=description,
                        solution=solution,
                        section=section,
                        severity=severity,
                    )
                )

        return pitfalls

    def _extract_related_concepts(self, content: str) -> list[str]:
        """Extract related concepts and cross-references."""
        concepts = set()

        # Look for "see also", "related", "similar" sections
        related_patterns = [
            r"(?:see also|related|similar|compare with|alternatives?):\s*"
            r"(.*?)(?:\n\n|\n[A-Z])",
            r"(?:other|additional|more) (?:functions|methods|classes|modules):\s*(.*?)(?:\n\n|\n[A-Z])",
        ]

        for pattern in related_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE | re.DOTALL):
                related_text = match.group(1)
                # Extract individual items (comma-separated, bullet points, etc.)
                items = re.split(r"[,;\n•\-\*]", related_text)
                for item in items:
                    clean_item = re.sub(r"[^\w\s\.\(\)]", "", item).strip()
                    if len(clean_item) > 3 and len(clean_item) < 50:
                        concepts.add(clean_item)

        # Look for cross-references in parentheses
        for match in re.finditer(
            r"\((?:see|cf\.?|compare|ref\.?)\s+([^)]+)\)", content, re.IGNORECASE
        ):
            concepts.add(match.group(1).strip())

        return list(concepts)[:10]  # Limit to prevent noise

    def _extract_prerequisites(self, content: str) -> list[str]:
        """Extract prerequisites and dependencies."""
        prerequisites = set()

        prereq_patterns = [
            r"(?:prerequisite|requirement|dependency|need|require|must have|before using):\s*(.*?)(?:\n\n|\n[A-Z])",
            r"(?:install|import|include|add):\s*([^\n]+)",
            r"(?:make sure|ensure|verify).*?(?:you have|installed|available):\s*(.*?)(?:\n\n|\n[A-Z])",
        ]

        for pattern in prereq_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE | re.DOTALL):
                prereq_text = match.group(1)
                items = re.split(r"[,;\n•\-\*]", prereq_text)
                for item in items:
                    clean_item = re.sub(r"[^\w\s\.\-]", "", item).strip()
                    if len(clean_item) > 3 and len(clean_item) < 100:
                        prerequisites.add(clean_item)

        return list(prerequisites)[:5]  # Limit to most important

    def _extract_description_near_code(self, context_text: str, code: str) -> str:
        """Extract description text near a code example."""
        # Look for text before the code block
        before_code = context_text[: context_text.find(code)]
        after_code = context_text[context_text.find(code) + len(code) :]

        # Find the most descriptive sentence
        sentences = re.split(r"[.!?]\s+", before_code + " " + after_code)

        best_sentence = ""
        for sentence in sentences:
            # Prefer sentences that describe what the code does
            if any(
                word in sentence.lower()
                for word in [
                    "example",
                    "shows",
                    "demonstrates",
                    "illustrates",
                    "this",
                    "following",
                ]
            ):
                best_sentence = sentence.strip()
                break

        if not best_sentence and sentences:
            # Fall back to the longest nearby sentence
            best_sentence = max(sentences, key=len).strip()

        return best_sentence[:200] if best_sentence else "No description available"

    def _is_complete_example(self, code: str, language: str) -> bool:
        """Determine if a code example is complete and runnable."""
        if language in ["python", "py"]:
            # Check for imports, function definitions, main blocks
            return any(
                pattern in code
                for pattern in ["import ", "def ", "if __name__", "class "]
            )
        elif language in ["javascript", "js"]:
            return any(
                pattern in code
                for pattern in ["function ", "const ", "let ", "var ", "=>"]
            )
        elif language in ["java"]:
            return "public class" in code or "public static void main" in code

        # For other languages, consider complete if it's multi-line and substantial
        return len(code.split("\n")) > 3 and len(code) > 50

    def _determine_complexity(self, text: str) -> str:
        """Determine the complexity level of content."""
        text_lower = text.lower()

        for level, patterns in self.complexity_indicators.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return level

        # Default based on content characteristics
        if len(text) > 500 or any(
            word in text_lower
            for word in ["optimization", "performance", "advanced", "custom"]
        ):
            return "advanced"
        elif len(text) > 200 or any(
            word in text_lower for word in ["configure", "setup", "implement"]
        ):
            return "intermediate"
        else:
            return "basic"

    def _determine_importance(self, text: str) -> str:
        """Determine the importance level of a best practice."""
        text_lower = text.lower()

        if any(
            word in text_lower
            for word in ["critical", "essential", "must", "required", "always"]
        ):
            return "critical"
        elif any(
            word in text_lower
            for word in ["important", "should", "recommended", "strongly"]
        ):
            return "high"
        elif any(
            word in text_lower for word in ["consider", "might", "could", "optional"]
        ):
            return "low"
        else:
            return "medium"

    def _determine_severity(self, text: str) -> str:
        """Determine the severity level of a pitfall."""
        text_lower = text.lower()

        if any(
            word in text_lower
            for word in ["critical", "fatal", "dangerous", "never", "security"]
        ):
            return "critical"
        elif any(
            word in text_lower
            for word in ["error", "fail", "break", "crash", "corrupt"]
        ):
            return "error"
        elif any(
            word in text_lower for word in ["warning", "caution", "careful", "avoid"]
        ):
            return "warning"
        else:
            return "info"

    def _extract_solution_near_pitfall(self, content: str, pitfall_end: int) -> str:
        """Extract solution text near a pitfall description."""
        # Look for solution indicators after the pitfall
        solution_text = content[pitfall_end : pitfall_end + 300]

        solution_patterns = [
            r"(?:solution|fix|resolve|instead|alternative|correct way):\s*(.*?)(?:\n\n|\n[A-Z])",
            r"(?:to fix|to solve|to avoid).*?(.*?)(?:\n\n|\n[A-Z])",
        ]

        for pattern in solution_patterns:
            match = re.search(pattern, solution_text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()[:200]

        return "No solution provided"


def extract_usage_patterns(content: str) -> list[dict[str, Any]]:
    """Extract common usage patterns from documentation.

    Args:
        content: Documentation content to analyze

    Returns:
        List of usage patterns with metadata
    """
    extractor = ContextExtractor()
    context_info = extractor.extract_context(content)

    patterns = []

    # Convert examples to usage patterns
    for example in context_info.examples:
        if example.is_complete and example.complexity in ["basic", "intermediate"]:
            patterns.append(
                {
                    "type": "example",
                    "code": example.code,
                    "description": example.description,
                    "complexity": example.complexity,
                    "language": example.language,
                    "category": "usage_example",
                }
            )

    # Convert best practices to patterns
    for practice in context_info.best_practices:
        if practice.importance in ["high", "critical"]:
            patterns.append(
                {
                    "type": "best_practice",
                    "title": practice.title,
                    "description": practice.description,
                    "importance": practice.importance,
                    "category": "best_practice",
                }
            )

    # Convert pitfalls to anti-patterns
    for pitfall in context_info.pitfalls:
        patterns.append(
            {
                "type": "pitfall",
                "title": pitfall.title,
                "description": pitfall.description,
                "solution": pitfall.solution,
                "severity": pitfall.severity,
                "category": "common_pitfall",
            }
        )

    return patterns
