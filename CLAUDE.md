# DocVault Development Guide

## Commands
- Install: `uv pip install -e .`
- Run CLI: `dv [command]` or `./scripts/dv [command]`
- Build package: `python -m build`
- Verify install: `python scripts/verify-install.py`
- Setup dev environment: `./scripts/dev-setup.sh`

## Code Style
- Python 3.12+ with type hints
- Use async/await for I/O operations
- 4-space indentation, PEP 8 conventions
- Group imports: standard lib → third-party → local
- Use click for CLI, rich for terminal output
- Docstrings in triple quotes
- Error handling: use try/except with specific exceptions
- Use pathlib.Path for file operations
- Async with aiohttp for HTTP requests

## Naming Conventions
- snake_case for functions and variables
- PascalCase for classes
- Use descriptive names that reflect purpose
- Prefix private methods/variables with underscore