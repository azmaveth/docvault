#!/usr/bin/env python3
"""Populate the documentation registry with common sources."""
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from docvault.models.registry import add_documentation_source


def main():
    """Add common documentation sources to the registry."""
    # Python (PyPI)
    add_documentation_source(
        name="Python",
        package_manager="pypi",
        base_url="https://pypi.org/project/{package}/",
        version_url_template="https://pypi.org/project/{package}/{version}/",
        latest_version_url="https://pypi.org/pypi/{package}/json",
    )

    # Node.js (npm)
    add_documentation_source(
        name="Node.js",
        package_manager="npm",
        base_url="https://www.npmjs.com/package/{package}",
        version_url_template="https://www.npmjs.com/package/{package}/v/{version}",
        latest_version_url="https://registry.npmjs.org/{package}/latest",
    )

    # RubyGems
    add_documentation_source(
        name="RubyGems",
        package_manager="gem",
        base_url="https://rubygems.org/gems/{package}",
        version_url_template="https://rubygems.org/gems/{package}/versions/{version}",
        latest_version_url="https://rubygems.org/api/v1/versions/{package}/latest.json",
    )

    # Hex (Elixir/Erlang)
    add_documentation_source(
        name="Hex",
        package_manager="hex",
        base_url="https://hex.pm/packages/{package}",
        version_url_template="https://hex.pm/packages/{package}/{version}",
        latest_version_url="https://hex.pm/api/packages/{package}",
    )

    # Go Modules
    add_documentation_source(
        name="Go Modules",
        package_manager="go",
        base_url="https://pkg.go.dev/{package}",
        version_url_template="https://pkg.go.dev/{package}@v{version}",
        latest_version_url="https://proxy.golang.org/{package}/@latest",
    )

    # Rust (crates.io)
    add_documentation_source(
        name="Crates.io",
        package_manager="cargo",
        base_url="https://crates.io/crates/{package}",
        version_url_template="https://docs.rs/crate/{package}/{version}",
        latest_version_url="https://crates.io/api/v1/crates/{package}",
    )

    print("Successfully populated documentation registry with common sources.")


if __name__ == "__main__":
    # Initialize the database connection
    from docvault.db.schema import initialize_database

    # Ensure the database is initialized
    initialize_database()

    # Run the population script
    main()
