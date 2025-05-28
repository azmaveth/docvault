# Section Navigation Guide

DocVault provides powerful section-based navigation features that allow you to work with documents as hierarchical structures, making it easier to navigate and access specific parts of large documentation.

## Overview

The section navigation system automatically:
- Parses documents into hierarchical sections based on headers
- Maintains parent-child relationships between sections
- Generates navigable tables of contents
- Allows section-specific searches and retrieval
- Supports both HTML and Markdown documents

## Key Features

### 1. Table of Contents Generation

View the hierarchical structure of any document:

```bash
# Display as a tree (default)
dv sections toc <document_id>

# Display as JSON for programmatic use
dv sections toc <document_id> --format json

# Display as a flat list
dv sections toc <document_id> --format flat

# Limit display depth
dv sections toc <document_id> --max-depth 2
```

### 2. Reading Specific Sections

Read a section by its path (e.g., "1.2.3"):

```bash
# Read a section with all its children
dv sections read <document_id> <section_path>

# Read only the section content (no children)
dv sections read <document_id> <section_path> --no-children

# Output as plain text
dv sections read <document_id> <section_path> --format plain

# Output as JSON
dv sections read <document_id> <section_path> --format json
```

### 3. Finding Sections by Title

Search for sections within a document:

```bash
# Find sections matching a pattern
dv sections find <document_id> "installation"

# Show results in tree context
dv sections find <document_id> "api" --format tree

# Get JSON output
dv sections find <document_id> "config" --format json
```

### 4. Section Navigation

Navigate relationships between sections:

```bash
# Show child sections
dv sections navigate <document_id> <section_id> --show children

# Show sibling sections
dv sections navigate <document_id> <section_id> --show siblings

# Show ancestor sections (path to root)
dv sections navigate <document_id> <section_id> --show ancestors

# Show entire subtree
dv sections navigate <document_id> <section_id> --show subtree
```

## Understanding Section Paths

Sections are identified by hierarchical paths that reflect their position in the document:

- `1` - First top-level section
- `1.1` - First subsection of section 1
- `1.1.1` - First sub-subsection of section 1.1
- `2` - Second top-level section
- `2.1` - First subsection of section 2

## Use Cases

### 1. Quick Navigation in Large Documents

For extensive API documentation or user guides:

```bash
# Get overview of document structure
dv sections toc 42 --max-depth 2

# Jump directly to specific section
dv sections read 42 "3.2.1"
```

### 2. Context-Aware Reading

When you need to understand a section in context:

```bash
# See where a section fits in the hierarchy
dv sections navigate 42 156 --show ancestors

# Read related sections
dv sections navigate 42 156 --show siblings
```

### 3. Targeted Search

Find specific topics within a document:

```bash
# Find all sections about authentication
dv sections find 42 "auth" --format tree

# Look for configuration sections
dv sections find 42 "config"
```

### 4. Programmatic Access

Use JSON output for automation:

```bash
# Get structured TOC data
dv sections toc 42 --format json > toc.json

# Extract specific section content
dv sections read 42 "2.3" --format json | jq '.segments[].content'
```

## Technical Details

### Section Detection

The system automatically detects sections using:
- **Markdown**: Headers marked with `#`, `##`, `###`, etc.
- **HTML**: `<h1>`, `<h2>`, `<h3>`, etc. tags

### Section Metadata

Each section includes:
- **Title**: The header text
- **Level**: Header level (1-6)
- **Path**: Hierarchical position (e.g., "1.2.3")
- **Parent ID**: Reference to parent section
- **Content**: Text content of the section

### Smart Splitting

Large sections are automatically split into manageable chunks while preserving:
- Hierarchical relationships
- Content coherence
- Navigation structure

## Examples

### Example 1: Exploring Python Documentation

```bash
# Add Python docs
dv add https://docs.python.org/3/tutorial/

# View table of contents
dv sections toc 1

# Read about functions
dv sections find 1 "functions" --format tree
dv sections read 1 "4.7"

# Explore related topics
dv sections navigate 1 234 --show siblings
```

### Example 2: API Reference Navigation

```bash
# Find all API endpoints
dv sections find 15 "endpoint"

# Read authentication section with examples
dv sections read 15 "3.1" 

# See all authentication-related sections
dv sections navigate 15 89 --show subtree
```

### Example 3: Building Documentation Index

```bash
# Export full TOC as JSON
dv sections toc 20 --format json > api_toc.json

# Extract all method signatures
for path in $(jq -r '.[].children[]?.path' api_toc.json); do
    dv sections read 20 "$path" --format json | \
    jq -r '.segments[] | select(.type == "code") | .content'
done
```

## Tips and Best Practices

1. **Use TOC First**: Always start by viewing the table of contents to understand document structure

2. **Navigate by Path**: Section paths (like "2.3.1") are stable and perfect for bookmarking

3. **Combine with Search**: Use regular search to find content, then use sections to explore context

4. **Leverage JSON Output**: For scripts and automation, JSON format provides structured data

5. **Check Siblings**: When reading a section, check its siblings for related content

## Integration with Other Features

Section navigation works seamlessly with:
- **Tags**: Tag specific sections for categorization
- **Cross-references**: Link related sections across documents
- **Version tracking**: Compare sections across document versions
- **Collections**: Group related sections from multiple documents

## Performance Notes

- Section metadata is indexed for fast retrieval
- Tables of contents are cached after first generation
- Large documents are handled efficiently with lazy loading
- Section paths enable direct access without full document parsing