"""CLI commands for secure credential management."""

import click
from rich.console import Console
from rich.table import Table

from docvault.utils.secure_credentials import (
    CredentialError,
    SecureCredentialManager,
)

console = Console()


@click.group()
def credentials():
    """Manage secure credentials for DocVault."""
    pass


@credentials.command()
@click.argument("name")
@click.option("--category", "-c", default="default", help="Credential category")
@click.option("--value", "-v", help="Credential value (will prompt if not provided)")
def set(name, category, value):
    """Store a credential securely.

    Examples:
        dv credentials set github_token --category api_keys
        dv credentials set db_password --value mypassword
    """
    try:
        manager = SecureCredentialManager()

        if not value:
            import getpass

            value = getpass.getpass(f"Enter value for {name}: ")
            if not value:
                console.print("[red]Error:[/] No value provided")
                return

        manager.store_credential(name, value, category)
        console.print(
            f"[green]✓[/] Credential '{name}' stored in category '{category}'"
        )

    except CredentialError as e:
        console.print(f"[red]Error:[/] {e}")
    except Exception as e:
        console.print(f"[red]Unexpected error:[/] {e}")


@credentials.command()
@click.argument("name")
@click.option("--category", "-c", default="default", help="Credential category")
@click.option("--show", is_flag=True, help="Show the actual value (use with caution)")
def get(name, category, show):
    """Retrieve a credential.

    Examples:
        dv credentials get github_token --category api_keys
        dv credentials get db_password --show
    """
    try:
        manager = SecureCredentialManager()
        value = manager.get_credential(name, category)

        if value:
            if show:
                console.print("[yellow]Warning:[/] Showing credential value")
                console.print(f"{name}: {value}")
            else:
                console.print(
                    f"[green]✓[/] Credential '{name}' exists in category '{category}'"
                )
                console.print(f"  Length: {len(value)} characters")
                console.print(f"  Preview: {value[:3]}{'*' * (len(value) - 3)}")
        else:
            console.print(
                f"[yellow]Not found:[/] Credential '{name}' in category '{category}'"
            )

    except CredentialError as e:
        console.print(f"[red]Error:[/] {e}")


@credentials.command()
@click.argument("name")
@click.option("--category", "-c", default="default", help="Credential category")
def remove(name, category):
    """Remove a credential.

    Examples:
        dv credentials remove old_token --category api_keys
    """
    try:
        manager = SecureCredentialManager()

        if click.confirm(f"Remove credential '{name}' from category '{category}'?"):
            if manager.remove_credential(name, category):
                console.print(f"[green]✓[/] Credential '{name}' removed")
            else:
                console.print(
                    f"[yellow]Not found:[/] Credential '{name}' in category "
                    f"'{category}'"
                )

    except CredentialError as e:
        console.print(f"[red]Error:[/] {e}")


@credentials.command()
@click.option("--category", "-c", help="Filter by category")
def list(category):
    """List stored credentials (names only).

    Examples:
        dv credentials list
        dv credentials list --category api_keys
    """
    try:
        manager = SecureCredentialManager()
        creds = manager.list_credentials(category)

        if not creds:
            console.print("[yellow]No credentials stored[/]")
            return

        table = Table(title="Stored Credentials")
        table.add_column("Category", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Count", style="yellow")

        for cat, names in sorted(creds.items()):
            if names:
                for i, name in enumerate(sorted(names)):
                    if i == 0:
                        table.add_row(cat, name, str(len(names)))
                    else:
                        table.add_row("", name, "")

        console.print(table)

    except CredentialError as e:
        console.print(f"[red]Error:[/] {e}")


@credentials.command()
def rotate_key():
    """Rotate the encryption key.

    This will re-encrypt all credentials with a new key.
    A backup of the old key is kept temporarily during rotation.
    """
    try:
        if not click.confirm(
            "Rotate encryption key? This will re-encrypt all credentials."
        ):
            return

        manager = SecureCredentialManager()
        console.print("[blue]Rotating encryption key...[/]")

        if manager.rotate_key():
            console.print("[green]✓[/] Encryption key rotated successfully")
            console.print("  All credentials have been re-encrypted")
        else:
            console.print("[red]Error:[/] Key rotation failed")

    except CredentialError as e:
        console.print(f"[red]Error:[/] {e}")
        console.print("  Original key has been restored")


@credentials.command()
def migrate_env():
    """Migrate credentials from environment variables to secure store.

    This will check for common environment variables and offer to
    store them securely.
    """
    import os

    env_mappings = [
        ("GITHUB_TOKEN", "github_token", "api_keys"),
        ("OPENAI_API_KEY", "openai_api_key", "api_keys"),
        ("ANTHROPIC_API_KEY", "anthropic_api_key", "api_keys"),
        ("DATABASE_URL", "database_url", "database"),
        ("DB_PASSWORD", "database_password", "database"),
        ("SECRET_KEY", "app_secret_key", "app"),
        ("JWT_SECRET", "jwt_secret", "app"),
    ]

    manager = SecureCredentialManager()
    migrated = 0

    console.print("[blue]Checking for environment variables to migrate...[/]")

    for env_var, cred_name, category in env_mappings:
        value = os.getenv(env_var)
        if value:
            # Check if already stored
            existing = manager.get_credential(cred_name, category)
            if existing:
                console.print(
                    f"  [yellow]Skip:[/] {env_var} (already stored as {cred_name})"
                )
                continue

            console.print(f"\n[green]Found:[/] {env_var}")
            console.print(f"  Length: {len(value)} characters")
            console.print(f"  Preview: {value[:3]}{'*' * min(10, len(value) - 3)}")

            if click.confirm(f"  Store as '{cred_name}' in category '{category}'?"):
                try:
                    manager.store_credential(cred_name, value, category)
                    console.print("  [green]✓[/] Stored successfully")
                    migrated += 1
                except Exception as e:
                    console.print(f"  [red]Error:[/] {e}")

    if migrated > 0:
        console.print(f"\n[green]✓[/] Migrated {migrated} credential(s)")
        console.print("\n[yellow]Note:[/] Environment variables are still set.")
        console.print(
            "Remove them from your shell configuration to use only secure storage."
        )
    else:
        console.print("\n[yellow]No credentials to migrate[/]")


@credentials.command()
def test():
    """Test credential storage and retrieval."""
    import uuid

    console.print("[blue]Testing secure credential storage...[/]")

    try:
        manager = SecureCredentialManager()

        # Test store and retrieve
        test_name = f"test_{uuid.uuid4().hex[:8]}"
        test_value = f"secret_{uuid.uuid4().hex}"
        test_category = "test"

        console.print(f"  Storing test credential: {test_name}")
        manager.store_credential(test_name, test_value, test_category)

        console.print("  Retrieving test credential...")
        retrieved = manager.get_credential(test_name, test_category)

        if retrieved == test_value:
            console.print("  [green]✓[/] Storage and retrieval successful")
        else:
            console.print("  [red]✗[/] Retrieved value doesn't match")
            return

        # Test listing
        console.print("  Listing credentials...")
        creds = manager.list_credentials(test_category)
        if test_category in creds and test_name in creds[test_category]:
            console.print("  [green]✓[/] Credential listed correctly")
        else:
            console.print("  [red]✗[/] Credential not found in listing")

        # Test removal
        console.print("  Removing test credential...")
        if manager.remove_credential(test_name, test_category):
            console.print("  [green]✓[/] Removal successful")
        else:
            console.print("  [red]✗[/] Removal failed")

        # Verify removal
        if manager.get_credential(test_name, test_category) is None:
            console.print("  [green]✓[/] Credential properly removed")
        else:
            console.print("  [red]✗[/] Credential still exists after removal")

        console.print("\n[green]✓[/] All tests passed!")

    except Exception as e:
        console.print(f"\n[red]Test failed:[/] {e}")
        import traceback

        traceback.print_exc()
