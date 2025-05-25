import pytest

from docvault.core.summarizer import DocumentSummarizer


class TestDocumentSummarizer:
    """Test suite for document summarization functionality"""

    @pytest.fixture
    def summarizer(self):
        """Create a DocumentSummarizer instance"""
        return DocumentSummarizer()

    @pytest.fixture
    def sample_documentation(self):
        """Sample documentation content for testing"""
        return """
# Example Library Documentation

This library provides utilities for working with data structures and algorithms.
It includes efficient implementations of common patterns.

## Installation

To install the library, use pip:

```python
pip install example-library
```

## Classes

### DataProcessor

The DataProcessor class handles data transformation and validation.

```python
class DataProcessor:
    def __init__(self, config):
        self.config = config
    
    def process(self, data):
        # Process the data
        return transformed_data
```

## Functions

### parse_data

Parse data from various formats.

```python
def parse_data(input_string, format='json'):
    '''
    Parse input string based on specified format.
    
    :param input_string: The string to parse
    :param format: Format type (json, xml, csv)
    :return: Parsed data structure
    '''
    if format == 'json':
        return json.loads(input_string)
    # More parsing logic...
```

### validate_schema

Validate data against a schema.

```
def validate_schema(data, schema):
    # Validation logic here
    return is_valid
```

## Examples

### Example 1: Basic Usage

```python
processor = DataProcessor(config)
result = processor.process(raw_data)
print(result)
```

### Example 2: Advanced Features

Here's how to use advanced features:

```python
# Configure with custom settings
config = {
    'strict_mode': True,
    'cache_enabled': False
}
processor = DataProcessor(config)
```

## Important Notes

**Warning**: Always validate input data before processing.

The `parse_data` function supports multiple formats and is **thread-safe**.

## Key Concepts

- **Data Validation**: Ensuring data integrity
- **Schema Validation**: Structure verification
- **Performance**: Optimized for large datasets
"""

    def test_basic_summarization(self, summarizer, sample_documentation):
        """Test basic summarization functionality"""
        summary = summarizer.summarize(sample_documentation)

        # Check that summary contains expected sections
        assert "overview" in summary
        assert "functions" in summary
        assert "classes" in summary
        assert "examples" in summary
        assert "key_concepts" in summary

        # Verify overview is extracted
        assert len(summary["overview"]) > 0
        assert "data structures" in summary["overview"].lower()

        # Verify functions are found
        assert len(summary["functions"]) >= 2
        function_names = [f["name"] for f in summary["functions"]]
        assert "parse_data" in function_names
        assert "validate_schema" in function_names

        # Verify classes are found
        assert len(summary["classes"]) >= 1
        assert summary["classes"][0]["name"] == "DataProcessor"

        # Verify examples are extracted
        assert len(summary["examples"]) >= 2

        # Verify key concepts are found
        assert len(summary["key_concepts"]) > 0

    def test_function_extraction(self, summarizer, sample_documentation):
        """Test extraction of function signatures"""
        summary = summarizer.summarize(sample_documentation)

        # Find parse_data function
        parse_data_func = next(
            (f for f in summary["functions"] if f["name"] == "parse_data"), None
        )
        assert parse_data_func is not None
        assert "format='json'" in parse_data_func["signature"]
        # Description extraction might vary based on format
        assert parse_data_func["description"] is not None

    def test_parameter_extraction(self, summarizer, sample_documentation):
        """Test extraction of function parameters"""
        summary = summarizer.summarize(sample_documentation)

        # Check if parameters are extracted
        params = summary.get("parameters", {})
        if "parse_data" in params:
            parse_params = params["parse_data"]
            param_names = [p["name"] for p in parse_params]
            assert "input_string" in param_names
            assert "format" in param_names

    def test_code_example_extraction(self, summarizer, sample_documentation):
        """Test extraction of code examples"""
        summary = summarizer.summarize(sample_documentation)

        # Verify code examples are found
        code_examples = [ex for ex in summary["examples"] if ex["type"] == "code"]
        assert len(code_examples) >= 2

        # Check that example content is preserved
        example_content = " ".join(ex["content"] for ex in code_examples)
        assert "DataProcessor" in example_content
        assert "processor.process" in example_content

    def test_key_concepts_extraction(self, summarizer, sample_documentation):
        """Test extraction of key concepts"""
        summary = summarizer.summarize(sample_documentation)

        concepts = summary["key_concepts"]
        assert "Data Validation" in concepts
        assert "thread-safe" in concepts
        assert "DataProcessor" in concepts

    def test_format_summary_text(self, summarizer, sample_documentation):
        """Test formatting summary as text"""
        summary = summarizer.summarize(sample_documentation)
        formatted = summarizer.format_summary(summary, format="text")

        assert "OVERVIEW:" in formatted
        assert "FUNCTIONS:" in formatted
        assert "CLASSES:" in formatted
        assert "parse_data" in formatted
        assert "DataProcessor" in formatted

    def test_format_summary_markdown(self, summarizer, sample_documentation):
        """Test formatting summary as markdown"""
        summary = summarizer.summarize(sample_documentation)
        formatted = summarizer.format_summary(summary, format="markdown")

        assert "## Overview" in formatted
        assert "## Functions" in formatted
        assert "## Classes" in formatted
        assert "### parse_data" in formatted
        assert "```" in formatted  # Code blocks

    def test_format_summary_json(self, summarizer, sample_documentation):
        """Test formatting summary as JSON"""
        import json

        summary = summarizer.summarize(sample_documentation)
        formatted = summarizer.format_summary(summary, format="json")

        # Should be valid JSON
        parsed = json.loads(formatted)
        assert "functions" in parsed
        assert "classes" in parsed

    def test_highlight_query_terms(self, summarizer):
        """Test highlighting of query terms"""
        content = "This is a test of the highlighting function in Python code."
        terms = ["test", "Python"]

        highlighted = summarizer.highlight_query_terms(content, terms)

        assert "**test**" in highlighted
        assert "**Python**" in highlighted
        # Original case should be preserved
        assert "This is a **test**" in highlighted

    def test_extract_relevant_snippets(self, summarizer):
        """Test extraction of relevant snippets"""
        content = """
        This is the beginning of the document.
        
        Here we discuss Python programming and its benefits.
        Python is a versatile language used for many purposes.
        
        In another section, we talk about data structures.
        Python provides lists, dictionaries, and sets.
        
        Finally, we cover Python best practices and tips.
        """

        snippets = summarizer.extract_relevant_snippets(
            content, "Python", window_size=100
        )

        assert len(snippets) >= 2  # Should find multiple occurrences
        assert all(
            "**Python**" in snippet for snippet in snippets
        )  # All should be highlighted
        assert all("..." in snippet for snippet in snippets)  # Should have ellipsis

    def test_extract_relevant_snippets_multiple_terms(self, summarizer):
        """Test extraction with multiple query terms"""
        content = """
        Functions in Python are first-class objects.
        You can pass functions as arguments to other functions.
        This makes Python very flexible for functional programming.
        Classes in Python support multiple inheritance.
        """

        snippets = summarizer.extract_relevant_snippets(
            content, "functions Python", window_size=80
        )

        assert len(snippets) >= 1
        # Both terms should be highlighted
        assert any("**Functions**" in s and "**Python**" in s for s in snippets)

    def test_empty_content_handling(self, summarizer):
        """Test handling of empty or minimal content"""
        # Empty content
        summary = summarizer.summarize("")
        assert summary["overview"] == ""
        assert len(summary["functions"]) == 0
        assert len(summary["classes"]) == 0

        # Minimal content
        summary = summarizer.summarize("Just a single line.")
        assert len(summary["functions"]) == 0
        assert len(summary["classes"]) == 0

    def test_max_items_limit(self, summarizer):
        """Test that max_items parameter is respected"""
        # Create content with many functions
        content = "\n".join(f"def function_{i}():\n    pass\n" for i in range(20))

        summary = summarizer.summarize(content, max_items=5)
        assert len(summary["functions"]) <= 5

    def test_malformed_code_handling(self, summarizer):
        """Test handling of malformed code blocks"""
        content = """
        Here's a broken code example:
        
        ```
        def broken_function(
            # Missing closing parenthesis
        ```
        
        And some text after.
        """

        # Should not crash
        summary = summarizer.summarize(content)
        assert isinstance(summary, dict)

    def test_overview_extraction_edge_cases(self, summarizer):
        """Test overview extraction with various edge cases"""
        # Document starting with heading
        content1 = "# Title\n\nThis is the overview."
        summary1 = summarizer.summarize(content1)
        assert "overview" in summary1["overview"]

        # Document with no clear overview
        content2 = "# Title\n\n## Section 1\n\nContent"
        summary2 = summarizer.summarize(content2)
        assert isinstance(summary2["overview"], str)

        # Very long first paragraph
        content3 = "# Title\n\n" + "Long text. " * 100
        summary3 = summarizer.summarize(content3)
        assert len(summary3["overview"]) <= 505  # 500 + "..."
