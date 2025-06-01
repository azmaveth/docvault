"""
Comprehensive test definitions for all DocVault commands.
"""

from tests.e2e.test_runner import E2ETestCase

# Test cases for basic commands
BASIC_TESTS = [
    E2ETestCase(
        name="help_command",
        description="Test help command shows all available commands",
        commands=[["dv", "--help"]],
        expected_exit_codes=[0],
        expected_outputs=[["Commands:", "add", "list", "search", "read"]],
    ),
    E2ETestCase(
        name="version_command",
        description="Test version command shows version info",
        commands=[["dv", "--version"]],
        expected_exit_codes=[0],
        expected_outputs=[["DocVault version"]],
    ),
    E2ETestCase(
        name="init_command",
        description="Test database initialization",
        commands=[["dv", "init", "--force"]],
        expected_exit_codes=[0],
        expected_outputs=[["Database initialized successfully"]],
        validations=[{"type": "database", "document_count": 0}],
    ),
]

# Test cases for document management
DOCUMENT_TESTS = [
    E2ETestCase(
        name="add_single_document",
        description="Test adding a single document",
        commands=[["dv", "add", "MOCK_HTML"]],
        expected_exit_codes=[0],
        expected_outputs=[["Importing", "http://localhost:8888/html"]],
        validations=[
            {
                "type": "database",
                "document_count": 1,
                "has_documents": ["HTML Test Page"],
            },
            {"type": "storage", "has_markdown_files": 1, "has_html_files": 1},
        ],
    ),
    E2ETestCase(
        name="add_with_depth",
        description="Test adding documents with depth parameter",
        commands=[["dv", "add", "MOCK_DEPTH", "--depth", "2"]],
        expected_exit_codes=[0],
        expected_outputs=[["Successfully imported", "Pages Scraped"]],
        validations=[
            {
                "type": "database",
                "document_count": 1,  # DocVault treats linked pages as part of same document
                "has_documents": ["Depth Test - Level 0"],
            }
        ],
    ),
    E2ETestCase(
        name="add_with_sections",
        description="Test adding document with section filtering",
        commands=[["dv", "add", "MOCK_PYTHON_DOCS", "--sections", "string-methods"]],
        expected_exit_codes=[0],
        expected_outputs=[["Successfully imported", "Python"]],
        validations=[
            {
                "type": "database",
                "document_count": 1,
                "segment_count": 1,  # Should only have string-methods section
            }
        ],
    ),
    E2ETestCase(
        name="list_documents",
        description="Test listing documents",
        commands=[
            ["dv", "add", "MOCK_HTML"],
            ["dv", "add", "MOCK_PYTHON_DOCS"],
            ["dv", "list"],
        ],
        expected_exit_codes=[0, 0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Successfully imported"],
            ["Documents in Vault", "HTML", "Test", "Page", "Python"],
        ],
        validations=[{"type": "database", "document_count": 2}],
    ),
    E2ETestCase(
        name="read_document",
        description="Test reading a document",
        commands=[["dv", "add", "MOCK_MARKDOWN"], ["dv", "read", "1"]],
        expected_exit_codes=[0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Markdown Test Document", "Easy to read", "Hello, {name}!"],
        ],
    ),
    E2ETestCase(
        name="read_with_format",
        description="Test reading document in different formats",
        commands=[["dv", "add", "MOCK_HTML"], ["dv", "read", "1", "--format", "json"]],
        expected_exit_codes=[0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ['"title":', '"content":', '"url":'],
        ],
    ),
    E2ETestCase(
        name="remove_document",
        description="Test removing a document",
        commands=[["dv", "add", "MOCK_HTML"], ["dv", "rm", "1", "--force"]],
        expected_exit_codes=[0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Deleted", "HTML Test Page", "Deleted 1 document"],
        ],
        validations=[{"type": "database", "document_count": 0}],
    ),
    E2ETestCase(
        name="remove_multiple",
        description="Test removing multiple documents",
        commands=[
            ["dv", "add", "MOCK_HTML"],
            ["dv", "add", "MOCK_PYTHON_DOCS"],
            ["dv", "add", "MOCK_JS_DOCS"],
            ["dv", "rm", "1-3", "--force"],
        ],
        expected_exit_codes=[0, 0, 0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Successfully imported"],
            ["Successfully imported"],
            ["Deleted", "Deleted 3 document"],
        ],
        validations=[{"type": "database", "document_count": 0}],
    ),
]

# Test cases for search functionality
SEARCH_TESTS = [
    E2ETestCase(
        name="search_text_basic",
        description="Test basic text search",
        commands=[
            ["dv", "add", "MOCK_PYTHON_DOCS"],
            ["dv", "add", "MOCK_JS_DOCS"],
            ["dv", "search", "text", "array"],
        ],
        expected_exit_codes=[0, 0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Successfully imported"],
            ["JavaScript Array Methods", "Found"],
        ],
    ),
    E2ETestCase(
        name="search_with_limit",
        description="Test search with result limit",
        commands=[
            ["dv", "add", "MOCK_PYTHON_DOCS"],
            ["dv", "add", "MOCK_JS_DOCS"],
            ["dv", "search", "text", "method", "--limit", "1"],
        ],
        expected_exit_codes=[0, 0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Successfully imported"],
            ["Found 1 result"],  # Should limit to 1 result
        ],
    ),
    E2ETestCase(
        name="search_library",
        description="Test library search",
        commands=[["dv", "search", "lib", "requests"]],
        expected_exit_codes=[0],
        expected_outputs=[["Error fetching documentation"]],
    ),
    E2ETestCase(
        name="search_batch",
        description="Test batch library search",
        commands=[["dv", "search", "batch", "requests", "numpy", "express"]],
        expected_exit_codes=[0],
        expected_outputs=[["Batch Search Summary"]],
    ),
]

# Test cases for organization features
ORGANIZATION_TESTS = [
    E2ETestCase(
        name="tag_add",
        description="Test adding tags to documents",
        commands=[
            ["dv", "add", "MOCK_PYTHON_DOCS"],
            ["dv", "tag", "add", "1", "python", "documentation"],
        ],
        expected_exit_codes=[0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Added tags", "python", "documentation"],
        ],
        validations=[{"type": "database", "has_tags": ["python", "documentation"]}],
    ),
    E2ETestCase(
        name="tag_list",
        description="Test listing tags",
        commands=[
            ["dv", "add", "MOCK_PYTHON_DOCS"],
            ["dv", "tag", "add", "1", "python", "tutorial"],
            ["dv", "tag", "list"],
        ],
        expected_exit_codes=[0, 0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Added tags"],
            ["Document Tags", "python", "tutorial"],
        ],
    ),
    E2ETestCase(
        name="tag_search",
        description="Test searching by tag",
        commands=[
            ["dv", "add", "MOCK_PYTHON_DOCS"],
            ["dv", "add", "MOCK_JS_DOCS"],
            ["dv", "tag", "add", "1", "python"],
            ["dv", "tag", "add", "2", "javascript"],
            ["dv", "tag", "list", "--document", "1"],
        ],
        expected_exit_codes=[0, 0, 0, 0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Successfully imported"],
            ["Added tags"],
            ["Added tags"],
            ["python"],
        ],
    ),
    E2ETestCase(
        name="collection_create",
        description="Test creating collections",
        commands=[
            ["dv", "add", "MOCK_PYTHON_DOCS"],
            ["dv", "add", "MOCK_JS_DOCS"],
            [
                "dv",
                "collection",
                "create",
                "programming",
                "--description",
                "Programming docs",
            ],
            ["dv", "collection", "add", "programming", "1", "2"],
        ],
        expected_exit_codes=[0, 0, 0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Successfully imported"],
            ["Created collection", "programming"],
            ["Added", "document(s) to"],
        ],
        validations=[{"type": "database", "has_collections": ["programming"]}],
    ),
]

# Test cases for advanced features
ADVANCED_TESTS = [
    E2ETestCase(
        name="export_document",
        description="Test exporting documents",
        commands=[
            ["dv", "add", "MOCK_MARKDOWN"],
            ["dv", "export", "1", "--output", "exported_doc.md"],
        ],
        expected_exit_codes=[0, 0],
        expected_outputs=[["Successfully imported"], ["Exported", "exported_doc.md"]],
        validations=[],  # File is exported to test_dir, not storage_path
    ),
    E2ETestCase(
        name="backup_restore",
        description="Test backup and restore functionality",
        commands=[
            ["dv", "add", "MOCK_HTML"],
            ["dv", "add", "MOCK_PYTHON_DOCS"],
            ["dv", "backup", "test_backup.zip"],
            ["dv", "rm", "1-2", "--force"],
            ["dv", "restore", "test_backup.zip"],
        ],
        expected_exit_codes=[0, 0, 0, 0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Successfully imported"],
            ["Backup created"],
            ["Successfully deleted"],
            ["Restore completed"],
        ],
        validations=[
            {
                "type": "database",
                "document_count": 2,  # Should be restored
                "has_documents": ["HTML Test Page", "Python Documentation"],
            }
        ],
        skip=True,
        skip_reason="Backup/restore has issues in test environment",
    ),
    E2ETestCase(
        name="freshness_check",
        description="Test document freshness checking",
        commands=[["dv", "add", "MOCK_HTML"], ["dv", "freshness"]],
        expected_exit_codes=[0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Document Freshness Report", "Fresh"],
        ],
    ),
    E2ETestCase(
        name="suggest_command",
        description="Test suggestion feature",
        commands=[
            ["dv", "add", "MOCK_PYTHON_DOCS"],
            ["dv", "add", "MOCK_JS_DOCS"],
            ["dv", "suggest", "arrays"],
        ],
        expected_exit_codes=[0, 0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Successfully imported"],
            ["Suggestions for", "arrays"],
        ],
    ),
    E2ETestCase(
        name="context_extraction",
        description="Test context extraction features",
        commands=[["dv", "add", "MOCK_PYTHON_DOCS"], ["dv", "read", "1", "--context"]],
        expected_exit_codes=[0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Python Documentation", "String Methods"],  # Shows document content
        ],
    ),
]

# Test cases for error handling
ERROR_TESTS = [
    E2ETestCase(
        name="invalid_url",
        description="Test handling of invalid URLs",
        commands=[["dv", "add", "not-a-valid-url"]],
        expected_exit_codes=[1],
        expected_outputs=[["Invalid URL", "Error"]],
    ),
    E2ETestCase(
        name="nonexistent_document",
        description="Test reading nonexistent document",
        commands=[["dv", "read", "999"]],
        expected_exit_codes=[0],
        expected_outputs=[["Document not found"]],
    ),
    E2ETestCase(
        name="network_timeout",
        description="Test handling network timeouts",
        commands=[["dv", "add", "MOCK_TIMEOUT", "--timeout", "2"]],
        expected_exit_codes=[2],
        expected_outputs=[["Failed to fetch URL"]],
        skip=True,
        skip_reason="--timeout option not available in dv add command",
    ),
    E2ETestCase(
        name="duplicate_tags",
        description="Test handling duplicate tags",
        commands=[
            ["dv", "add", "MOCK_HTML"],
            ["dv", "tag", "add", "1", "test"],
            ["dv", "tag", "add", "1", "test"],
        ],
        expected_exit_codes=[0, 0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Added tags"],
            ["Tags already exist"],  # Should handle duplicate gracefully
        ],
    ),
]

# Test cases for configuration and settings
CONFIG_TESTS = [
    E2ETestCase(
        name="config_display",
        description="Test configuration display",
        commands=[["dv", "config"]],
        expected_exit_codes=[0],
        expected_outputs=[["Current Configuration", "Database"]],
    ),
    E2ETestCase(
        name="stats_command",
        description="Test statistics display",
        commands=[
            ["dv", "add", "MOCK_HTML"],
            ["dv", "add", "MOCK_PYTHON_DOCS"],
            ["dv", "stats"],
        ],
        expected_exit_codes=[0, 0, 0],
        expected_outputs=[
            ["Successfully imported"],
            ["Successfully imported"],
            ["DocVault Statistics", "Total Documents", "2"],
        ],
    ),
]

# Combine all test cases
ALL_TESTS = (
    BASIC_TESTS
    + DOCUMENT_TESTS
    + SEARCH_TESTS
    + ORGANIZATION_TESTS
    + ADVANCED_TESTS
    + ERROR_TESTS
    + CONFIG_TESTS
)
