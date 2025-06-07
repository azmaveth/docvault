"""Tests for the document summarizer module."""

import pytest

from docvault.core.summarizer import DocumentSummarizer


@pytest.fixture
def summarizer():
    """Create a DocumentSummarizer instance."""
    return DocumentSummarizer()


@pytest.fixture
def sample_python_doc():
    """Sample Python documentation content."""
    return """
# MyModule Documentation

This module provides utilities for working with data structures.

## Classes

class DataProcessor:
    '''A class for processing various data formats.'''
    pass

class DataValidator:
    '''Validates data according to specified rules.'''
    pass

## Functions

def process_data(data, format='json'):
    '''Process data in the specified format.

    :param data: The data to process
    :param format: The format to use (json, xml, csv)
    :return: Processed data
    '''
    pass

def validate_input(value, rules):
    '''Validate input against a set of rules.

    :param value: The value to validate
    :param rules: List of validation rules
    :return: True if valid, False otherwise
    '''
    pass

## Examples

```python
# Example 1: Processing JSON data
data = {"key": "value"}
result = process_data(data, format='json')
```

```python
# Example 2: Validating input
rules = ['required', 'numeric']
is_valid = validate_input(42, rules)
```

## Key Concepts

- **Data Processing**: Transform data between formats
- **Validation**: Ensure data integrity
- **Format Support**: JSON, XML, CSV
"""


def test_summarizer_init(summarizer):
    """Test summarizer initialization."""
    assert summarizer is not None
    assert "function" in summarizer.patterns
    assert "class" in summarizer.patterns
    assert "example" in summarizer.patterns


def test_extract_overview(summarizer, sample_python_doc):
    """Test overview extraction."""
    overview = summarizer._extract_overview(sample_python_doc)
    assert overview
    assert "utilities for working with data structures" in overview


def test_extract_functions(summarizer, sample_python_doc):
    """Test function extraction."""
    functions = summarizer._extract_functions(sample_python_doc, max_items=10)
    assert len(functions) >= 2

    # Check first function
    assert any(f["name"] == "process_data" for f in functions)
    assert any(f["name"] == "validate_input" for f in functions)

    # Check signatures are captured
    process_func = next(f for f in functions if f["name"] == "process_data")
    assert "format=" in process_func["signature"]


def test_extract_classes(summarizer, sample_python_doc):
    """Test class extraction."""
    classes = summarizer._extract_classes(sample_python_doc, max_items=10)
    assert len(classes) >= 2

    class_names = [c["name"] for c in classes]
    assert "DataProcessor" in class_names
    assert "DataValidator" in class_names


def test_extract_examples(summarizer, sample_python_doc):
    """Test example extraction."""
    examples = summarizer._extract_examples(sample_python_doc, max_items=5)
    assert len(examples) >= 2

    # Check that code examples were found
    code_examples = [e for e in examples if e["type"] == "code"]
    assert len(code_examples) >= 2
    assert any("process_data" in e["content"] for e in code_examples)


def test_extract_key_concepts(summarizer, sample_python_doc):
    """Test key concept extraction."""
    concepts = summarizer._extract_key_concepts(sample_python_doc)
    assert len(concepts) > 0
    assert "Data Processing" in concepts
    assert "Validation" in concepts


def test_full_summarize(summarizer, sample_python_doc):
    """Test full document summarization."""
    summary = summarizer.summarize(sample_python_doc)

    assert "functions" in summary
    assert "classes" in summary
    assert "examples" in summary
    assert "overview" in summary
    assert "key_concepts" in summary

    assert len(summary["functions"]) >= 2
    assert len(summary["classes"]) >= 2
    assert len(summary["examples"]) >= 2
    assert len(summary["key_concepts"]) > 0


def test_format_summary_text(summarizer, sample_python_doc):
    """Test text format output."""
    summary = summarizer.summarize(sample_python_doc)
    formatted = summarizer.format_summary(summary, format="text")

    assert "OVERVIEW:" in formatted
    assert "FUNCTIONS:" in formatted
    assert "CLASSES:" in formatted
    assert "KEY CONCEPTS:" in formatted


def test_format_summary_markdown(summarizer, sample_python_doc):
    """Test markdown format output."""
    summary = summarizer.summarize(sample_python_doc)
    formatted = summarizer.format_summary(summary, format="markdown")

    assert "## Overview" in formatted
    assert "## Functions" in formatted
    assert "## Classes" in formatted
    assert "## Key Concepts" in formatted
    assert "```" in formatted  # Code blocks


def test_format_summary_json(summarizer, sample_python_doc):
    """Test JSON format output."""
    import json

    summary = summarizer.summarize(sample_python_doc)
    formatted = summarizer.format_summary(summary, format="json")

    # Should be valid JSON
    parsed = json.loads(formatted)
    assert "functions" in parsed
    assert "classes" in parsed
