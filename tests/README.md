# DocVault Tests

This directory contains unit tests for the DocVault application.

## Running Tests

To run all tests:

```bash
pytest
```

To run tests with coverage report:

```bash
pytest --cov=docvault
```

To run specific test files:

```bash
pytest tests/test_db_operations.py
```

## Test Structure

- `conftest.py` - Contains common fixtures for tests
- `test_db_operations.py` - Tests for database operations
- `test_embeddings.py` - Tests for embeddings generation and search
- `test_library_manager.py` - Tests for library documentation manager
- `test_scraper.py` - Tests for web scraper functionality
- `test_schema.py` - Tests for database schema initialization
- `test_cli.py` - Tests for CLI commands

## Adding New Tests

When adding new tests:

1. Create a new file named `test_*.py`
2. Import necessary fixtures from `conftest.py`
3. Write test functions prefixed with `test_`
4. Use appropriate pytest decorators (e.g., `@pytest.mark.asyncio` for async tests)
