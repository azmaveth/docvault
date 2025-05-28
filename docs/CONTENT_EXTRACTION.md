# Content Extraction Improvements

DocVault v0.5.3 introduces intelligent content extraction that automatically detects documentation types and uses specialized extractors for optimal results.

## Overview

The content extraction system consists of:

1. **Documentation Type Detection** - Automatically identifies the documentation format
2. **Specialized Extractors** - Format-specific extraction logic for different doc types
3. **Metadata Extraction** - Captures additional context like API signatures, navigation, etc.

## Supported Documentation Types

### Sphinx Documentation

Sphinx is the documentation system used by Python and many other projects.

**Detection:**
- URL patterns: `docs.python.org`, `numpy.org/doc`, `scikit-learn.org`
- Generator meta tag: `<meta name="generator" content="Sphinx">`
- HTML classes: `rst-content`, `wy-nav-content`, `sphinx`

**Extracted Elements:**
- API documentation (functions, classes, methods)
- Parameter descriptions and types
- Return value documentation
- Code examples with syntax highlighting
- Cross-references and links

### MkDocs Documentation

MkDocs is a popular static site generator for project documentation.

**Detection:**
- URL patterns: `mkdocs.org`, sites hosted on GitHub Pages
- Generator meta tag: `<meta name="generator" content="MkDocs">`
- HTML classes: `md-content`, `md-nav`, `mkdocs`

**Extracted Elements:**
- Hierarchical navigation structure
- Code examples with language detection
- Admonitions (notes, warnings, tips)
- Table of contents
- Theme-specific features

### OpenAPI/Swagger Documentation

OpenAPI (formerly Swagger) is the standard for REST API documentation.

**Detection:**
- URL patterns: `/swagger`, `/api-docs`, `/openapi`
- UI frameworks: Swagger UI, ReDoc, RapiDoc
- JSON/YAML spec detection

**Extracted Elements:**
- API endpoints with HTTP methods
- Request/response schemas
- Authentication methods
- Parameter descriptions
- Code samples in multiple languages

### Generic Documentation

For documentation that doesn't match specific formats.

**Extracted Elements:**
- Main content area detection
- Code block extraction
- Table extraction
- Navigation elements
- Metadata from HTML headers

## Using Content Extraction

### Automatic Detection

When scraping documentation, DocVault automatically detects the type:

```bash
# Scrape Python documentation (Sphinx)
dv add https://docs.python.org/3/library/os.html

# Scrape MkDocs documentation
dv add https://www.mkdocs.org/user-guide/

# Scrape API documentation
dv add https://petstore.swagger.io/
```

### Viewing Extracted Metadata

Use the `--json` flag to see extracted metadata:

```bash
# View extracted API elements
dv read 123 --format json | jq '.metadata.api_elements'

# View navigation structure
dv read 456 --format json | jq '.metadata.navigation'

# View code examples
dv read 789 --format json | jq '.metadata.code_examples'
```

### Searching Extracted Content

The extracted metadata is searchable:

```bash
# Search for specific API functions
dv search "os.path.join" --type api

# Find code examples in a specific language
dv search "python" --filter "metadata.code_examples[].language"
```

## Benefits

1. **Better Search Results** - Structured extraction improves search accuracy
2. **Rich Context** - API signatures, parameters, and examples are preserved
3. **Format Preservation** - Code formatting and structure are maintained
4. **Cross-Reference Support** - Links between related documentation are preserved
5. **Language-Aware** - Code examples include language information

## Technical Details

### Extractor Architecture

Each extractor inherits from `BaseExtractor` and implements:

```python
def extract(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    """Extract content and metadata from documentation."""
    return {
        'content': str,      # Markdown content
        'metadata': dict     # Structured metadata
    }
```

### Adding New Extractors

To support a new documentation format:

1. Create a new extractor in `docvault/core/extractors/`
2. Add detection logic to `DocTypeDetector`
3. Register the extractor in the scraper

Example:

```python
from docvault.core.extractors.base import BaseExtractor

class MyDocsExtractor(BaseExtractor):
    """Extractor for MyDocs format."""
    
    def extract(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        # Custom extraction logic
        content = self._extract_main_content(soup)
        metadata = self._extract_metadata(soup)
        
        return {
            'content': content,
            'metadata': metadata
        }
```

### Metadata Storage

Extracted metadata is stored in the `documents` table:

- `doc_type` - The detected documentation type
- `metadata` - JSON field containing extracted metadata

This allows for rich queries and filtering based on documentation structure.

## Future Improvements

- Support for more documentation formats (JSDoc, Doxygen, etc.)
- Extraction of diagrams and images
- Better handling of versioned documentation
- Extraction of example projects and tutorials
- Support for interactive documentation elements