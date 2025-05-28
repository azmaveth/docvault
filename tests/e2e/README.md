# DocVault End-to-End Test Suite

This directory contains comprehensive end-to-end tests for DocVault that test every command and feature from a user's perspective.

## Structure

- `test_runner.py` - Main test runner framework with isolation and reporting
- `test_definitions.py` - All test case definitions (94 tests)
- `fixtures/` - Test data files
- `benchmark.py` - Performance benchmarking extension

## Running Tests

```bash
# Run all tests
./scripts/run-e2e-tests.sh

# Run specific tests by filter
./scripts/run-e2e-tests.sh -f "init"
./scripts/run-e2e-tests.sh -f "search"

# Run with verbose output
./scripts/run-e2e-tests.sh -v

# Generate JSON report
./scripts/run-e2e-tests.sh -r results.json

# Run performance benchmarks
python -m tests.e2e.benchmark
```

## Test Categories

1. **BASIC_COMMAND_TESTS** - Help, version, bare command
2. **INITIALIZATION_TESTS** - Database initialization
3. **DOCUMENT_MANAGEMENT_TESTS** - Add, list, read, remove, export
4. **SEARCH_TESTS** - Text search, library search, filters
5. **ORGANIZATION_TESTS** - Tags and collections
6. **PACKAGE_MANAGER_TESTS** - PyPI, npm, RubyGems, etc.
7. **FRESHNESS_TESTS** - Document freshness tracking
8. **ADVANCED_FEATURE_TESTS** - Stats, config, backup/restore, etc.
9. **ERROR_HANDLING_TESTS** - Error cases and edge conditions

## Known Issues

1. **Network-dependent tests** may timeout when external services are slow
2. **Search tests** require proper indexing and may fail initially
3. **Package manager tests** depend on external registries

## Test Environment

Tests run in isolated temporary directories with:
- Separate database for each test run
- Environment variables set to prevent interference
- Automatic cleanup after tests

## Writing New Tests

Add new test cases to `test_definitions.py`:

```python
TestCase(
    name="test_name",
    command=["dv", "command", "arg"],
    description="What this tests",
    expected_output_contains=["expected", "output"],
    expected_exit_code=0,
    setup_commands=[["dv", "init"]],
    timeout=30
)
```

## CI/CD Integration

The test suite is integrated with GitHub Actions:
- Runs on push/PR to main branches
- Tests on Ubuntu, macOS, Windows
- Multiple Python versions (3.11, 3.12)