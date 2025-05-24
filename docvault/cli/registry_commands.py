"""CLI commands for managing the documentation registry."""

import click

from docvault.models.registry import (
    LibraryEntry,
    add_documentation_source,
    add_library_entry,
    find_library,
    get_documentation_source,
    list_documentation_sources,
    search_libraries,
)


@click.group()
def registry():
    """Manage documentation registry."""
    pass


@registry.group()
def source():
    """Manage documentation sources."""
    pass


@source.command("add")
@click.argument("name")
@click.argument("package_manager")
@click.argument("base_url")
@click.option(
    "--version-url",
    "version_url_template",
    required=True,
    help="URL template with {version} placeholder",
)
@click.option("--latest-version-url", help="URL to fetch latest version")
@click.option("--inactive", is_flag=True, help="Add as inactive source")
def add_source(
    name, package_manager, base_url, version_url_template, latest_version_url, inactive
):
    """Add a new documentation source."""
    try:
        source = add_documentation_source(
            name=name,
            package_manager=package_manager,
            base_url=base_url,
            version_url_template=version_url_template,
            latest_version_url=latest_version_url or "",
            is_active=not inactive,
        )
        click.echo(f"Added documentation source: {source.name} (ID: {source.id})")
    except Exception as e:
        click.echo(f"Error adding documentation source: {e}", err=True)
        raise click.Abort()


@source.command("list")
@click.option(
    "--all", "show_all", is_flag=True, help="Show all sources, including inactive"
)
def list_sources(show_all):
    """List documentation sources."""
    sources = list_documentation_sources(active_only=not show_all)

    if not sources:
        click.echo("No documentation sources found.")
        return

    click.echo("Documentation Sources:")
    click.echo("-" * 80)

    for src in sources:
        status = "ACTIVE" if src.is_active else "INACTIVE"
        click.echo(f"ID: {src.id}")
        click.echo(f"Name: {src.name} ({status})")
        click.echo(f"Package Manager: {src.package_manager}")
        click.echo(f"Base URL: {src.base_url}")
        click.echo(f"Version URL Template: {src.version_url_template}")
        if src.latest_version_url:
            click.echo(f"Latest Version URL: {src.latest_version_url}")
        click.echo(f"Last Checked: {src.last_checked or 'Never'}")
        click.echo("-" * 80)


@registry.group()
def lib():
    """Manage library entries."""
    pass


@lib.command("add")
@click.argument("name")
@click.argument("version")
@click.argument("doc_url")
@click.option("--source-id", type=int, help="ID of the documentation source")
@click.option("--package-name", help="Original package name in the registry")
@click.option("--latest-version", help="Latest available version")
@click.option("--description", help="Library description")
@click.option("--homepage", "homepage_url", help="Project homepage URL")
@click.option("--repo", "repository_url", help="Source code repository URL")
@click.option("--unavailable", is_flag=True, help="Mark as unavailable")
def add_lib(
    name,
    version,
    doc_url,
    source_id,
    package_name,
    latest_version,
    description,
    homepage_url,
    repository_url,
    unavailable,
):
    """Add a new library to the registry."""
    try:
        lib = add_library_entry(
            name=name,
            version=version,
            doc_url=doc_url,
            source_id=source_id,
            package_name=package_name or name,
            latest_version=latest_version,
            description=description,
            homepage_url=homepage_url,
            repository_url=repository_url,
            is_available=not unavailable,
        )
        click.echo(f"Added library: {lib.name} {lib.version} (ID: {lib.id})")
    except Exception as e:
        click.echo(f"Error adding library: {e}", err=True)
        raise click.Abort()


@lib.command("find")
@click.argument("query")
@click.option("--version", help="Specific version to find")
@click.option("--source", "source_id", type=int, help="Filter by source ID")
@click.option("--limit", type=int, default=10, help="Maximum number of results")
def find_lib(query, version, source_id, limit):
    """Find libraries matching the query."""
    if version:
        # Exact match for name and version
        lib = find_library(query, version=version, source_id=source_id)
        if not lib:
            click.echo(f"No library found matching '{query}' version {version}")
            return

        print_library_details(lib)
    else:
        # Search by name/description
        results = search_libraries(query, source_id=source_id, limit=limit)
        if not results:
            click.echo(f"No libraries found matching '{query}'")
            return

        click.echo(f"Found {len(results)} libraries:")
        click.echo("-" * 80)

        for lib in results:
            click.echo(f"{lib.name} {lib.version}")
            if lib.description:
                click.echo(
                    f"  {lib.description[:100]}{'...' if len(lib.description) > 100 else ''}"
                )
            click.echo(f"  Documentation: {lib.doc_url}")
            if lib.latest_version and lib.latest_version != lib.version:
                click.echo(f"  Latest version: {lib.latest_version}")
            click.echo("-" * 80)


def print_library_details(lib: LibraryEntry):
    """Print detailed information about a library."""
    click.echo(f"\n{lib.name} {lib.version}")
    click.echo("=" * (len(lib.name) + len(str(lib.version)) + 1))

    if lib.description:
        click.echo(f"\n{lib.description}\n")

    click.echo(f"Documentation: {lib.doc_url}")

    if lib.homepage_url:
        click.echo(f"Homepage: {lib.homepage_url}")

    if lib.repository_url:
        click.echo(f"Repository: {lib.repository_url}")

    if lib.latest_version and lib.latest_version != lib.version:
        click.echo(f"\nLatest version: {lib.latest_version}")

    if lib.source_id:
        source = get_documentation_source(lib.source_id)
        if source:
            click.echo(f"Source: {source.name} ({source.package_manager})")

    click.echo(f"\nLast checked: {lib.last_checked or 'Never'}")
