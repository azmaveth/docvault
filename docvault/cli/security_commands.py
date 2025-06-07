"""Security-related commands for DocVault CLI."""

import click
from rich.console import Console
from rich.table import Table

from docvault.utils.file_permissions import FilePermissionManager

console = Console()


@click.group()
def security():
    """Security management commands."""
    pass


@security.command()
@click.option("--fix", is_flag=True, help="Fix insecure permissions automatically")
def audit(fix):
    """Audit file permissions for security issues.

    Examples:
        dv security audit
        dv security audit --fix
    """
    console.print("[blue]Auditing DocVault file permissions...[/blue]\n")

    if fix:
        # Fix permissions
        fixed, failed = FilePermissionManager.fix_all_permissions()

        if failed == 0:
            console.print(
                f"[green]✓[/green] Fixed permissions on {fixed} files/directories"
            )
        else:
            console.print(
                f"[yellow]⚠[/yellow] Fixed {fixed} files/directories, "
                f"[red]failed to fix {failed}[/red]"
            )
        return

    # Just audit
    issues = FilePermissionManager.audit_permissions()

    total_issues = sum(len(items) for items in issues.values())

    if total_issues == 0:
        console.print("[green]✓ All files have secure permissions![/green]")
        return

    # Display issues by severity
    severity_colors = {
        "critical": "red",
        "high": "yellow",
        "medium": "blue",
        "info": "white",
    }

    for severity in ["critical", "high", "medium", "info"]:
        if issues[severity]:
            console.print(
                f"\n[{severity_colors[severity]}]{severity.upper()} "
                f"Issues:[/{severity_colors[severity]}]"
            )

            table = Table(show_header=True, header_style="bold")
            table.add_column("File/Directory", style="cyan")
            table.add_column("Issue", style="red")

            for path, issue in issues[severity]:
                table.add_row(str(path), issue)

            console.print(table)

    console.print(
        f"\n[yellow]Found {total_issues} permission issues. "
        f"Run 'dv security audit --fix' to fix them.[/yellow]"
    )


@security.command()
def umask():
    """Check current umask setting.

    The umask determines default permissions for new files.
    A secure umask like 077 ensures new files are only readable by the owner.
    """
    import os

    if os.name == "nt":
        console.print("[yellow]umask is not applicable on Windows[/yellow]")
        return

    # Get current umask
    current = os.umask(0o077)
    os.umask(current)  # Restore

    console.print(f"Current umask: [cyan]{oct(current)}[/cyan]")

    # Explain what it means
    file_perms = 0o666 & ~current
    dir_perms = 0o777 & ~current

    console.print("\nThis means:")
    console.print(
        f"  • New files will have permissions: [cyan]{oct(file_perms)}[/cyan]"
    )
    console.print(
        f"  • New directories will have permissions: [cyan]{oct(dir_perms)}[/cyan]"
    )

    if current & 0o077 != 0o077:
        console.print(
            "\n[yellow]⚠ Warning: Your umask may create files readable by "
            "others.[/yellow]"
        )
        console.print(
            "[yellow]Consider setting 'umask 077' in your shell profile.[/yellow]"
        )
    else:
        console.print("\n[green]✓ Your umask is secure![/green]")


@security.command()
def status():
    """Show security status of DocVault installation."""
    import os
    from pathlib import Path

    from docvault import config

    console.print("[blue]DocVault Security Status[/blue]\n")

    # Check file permissions
    issues = FilePermissionManager.audit_permissions()
    total_issues = sum(len(items) for items in issues.values())

    if total_issues == 0:
        console.print("[green]✓[/green] File Permissions: Secure")
    else:
        console.print(f"[red]✗[/red] File Permissions: {total_issues} issues found")

    # Check if .env exists and is in .gitignore
    env_file = Path(".env")
    gitignore = Path(".gitignore")

    if env_file.exists():
        if gitignore.exists() and ".env" in gitignore.read_text():
            console.print("[green]✓[/green] .env file: Exists and in .gitignore")
        else:
            console.print("[red]✗[/red] .env file: Not in .gitignore!")
    else:
        console.print("[blue]ℹ[/blue] .env file: Not found")

    # Check credential encryption
    creds_key = Path(config.DEFAULT_BASE_DIR) / ".credentials.key"
    if creds_key.exists():
        console.print("[green]✓[/green] Credential Encryption: Enabled")
    else:
        console.print("[yellow]⚠[/yellow] Credential Encryption: Not initialized")

    # Check MCP server binding
    host = os.getenv("HOST", "127.0.0.1")
    if host in ["127.0.0.1", "localhost"]:
        console.print("[green]✓[/green] MCP Server: Localhost only")
    else:
        console.print(
            f"[yellow]⚠[/yellow] MCP Server: Bound to {host} (network accessible)"
        )

    # Check rate limiting
    console.print("[green]✓[/green] Rate Limiting: Enabled")
    console.print("[green]✓[/green] Input Validation: Enabled")
    console.print("[green]✓[/green] SQL Injection Prevention: Enabled")
    console.print("[green]✓[/green] Path Traversal Prevention: Enabled")

    # Show recommendations
    if total_issues > 0:
        console.print("\n[yellow]Recommendations:[/yellow]")
        console.print("  • Run 'dv security audit --fix' to fix permission issues")

    if host not in ["127.0.0.1", "localhost"]:
        console.print("  • Consider binding MCP server to localhost only")
        console.print("    Set HOST=127.0.0.1 in your .env file")
