#!/usr/bin/env python3
"""
DocVault End-to-End Test Runner
Tests all commands with mock server and validates stored data.
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.e2e.mock_server import MockServer


@dataclass
class E2ETestCase:
    """Definition of a test case."""

    name: str
    description: str
    commands: list[list[str]]  # Multiple commands to run in sequence
    validations: list[dict[str, Any]] = field(default_factory=list)
    expected_exit_codes: list[int] = field(default_factory=list)
    expected_outputs: list[list[str]] = field(default_factory=list)
    skip: bool = False
    skip_reason: str = ""
    cleanup_commands: list[list[str]] = field(default_factory=list)
    mock_routes: dict[str, str] = field(default_factory=dict)  # Custom mock responses


@dataclass
class E2ETestResult:
    """Result of a test execution."""

    test_name: str
    success: bool
    duration: float
    error_message: str | None = None
    outputs: list[str] = field(default_factory=list)
    exit_codes: list[int] = field(default_factory=list)
    validation_results: dict[str, bool] = field(default_factory=dict)


class E2ETestRunner:
    """End-to-end test runner for DocVault."""

    def __init__(self, verbose: bool = False, mock_port: int = 8888):
        self.verbose = verbose
        self.mock_port = mock_port
        self.console = Console()
        self.mock_server = None
        self.test_dir = None
        self.db_path = None
        self.storage_path = None

    def setup(self):
        """Set up test environment."""
        # Create temporary directory
        self.test_dir = tempfile.mkdtemp(prefix="docvault_e2e_")
        self.db_path = Path(self.test_dir) / "docvault.db"
        self.storage_path = Path(self.test_dir) / "storage"

        # Set environment variables
        os.environ["DOCVAULT_HOME"] = self.test_dir
        os.environ["DOCVAULT_DB_PATH"] = str(self.db_path)
        os.environ["STORAGE_PATH"] = str(self.storage_path)
        os.environ["LOG_LEVEL"] = "ERROR" if not self.verbose else "INFO"
        os.environ["DOCVAULT_TEST_MODE"] = "1"
        os.environ["NO_ANALYTICS"] = "1"

        # Allow localhost for testing
        os.environ["URL_ALLOWED_DOMAINS"] = "localhost,127.0.0.1"
        os.environ["DOCVAULT_ALLOW_LOCALHOST"] = "1"  # Special test flag

        # Disable connection pooling for tests (can cause issues in test environment)
        os.environ["USE_CONNECTION_POOL"] = "false"

        # Disable credential requirements for testing
        os.environ["GITHUB_TOKEN"] = "test_token"
        os.environ["DISABLE_CREDENTIAL_CHECK"] = "1"

        # Start mock server
        self.mock_server = MockServer(port=self.mock_port)
        self.mock_server.start()

        if self.verbose:
            self.console.print(f"[green]Test environment set up in {self.test_dir}[/]")
            self.console.print(
                f"[green]Mock server running on port {self.mock_port}[/]"
            )

    def teardown(self):
        """Clean up test environment."""
        # Stop mock server
        if self.mock_server:
            self.mock_server.stop()

        # Remove test directory
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

        # Clear environment variables
        for key in [
            "DOCVAULT_HOME",
            "DOCVAULT_DB_PATH",
            "STORAGE_PATH",
            "DOCVAULT_TEST_MODE",
            "NO_ANALYTICS",
            "URL_ALLOWED_DOMAINS",
            "DOCVAULT_ALLOW_LOCALHOST",
        ]:
            os.environ.pop(key, None)

    def run_command(self, command: list[str]) -> tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr."""
        # Replace mock URLs in commands
        command = [self._replace_mock_url(arg) for arg in command]

        # Ensure we're using the installed dv command
        if command[0] == "dv":
            dv_path = shutil.which("dv")
            if dv_path:
                command[0] = dv_path
            else:
                # Fallback to python module
                command = [sys.executable, "-m", "docvault.main"] + command[1:]

        result = subprocess.run(
            command, capture_output=True, text=True, cwd=self.test_dir
        )

        return result.returncode, result.stdout, result.stderr

    def _replace_mock_url(self, arg: str) -> str:
        """Replace placeholder URLs with mock server URLs."""
        replacements = {
            "MOCK_URL": self.mock_server.get_url(),
            "MOCK_PYTHON_DOCS": self.mock_server.get_url("/docs/python"),
            "MOCK_JS_DOCS": self.mock_server.get_url("/docs/javascript"),
            "MOCK_HTML": self.mock_server.get_url("/html"),
            "MOCK_MARKDOWN": self.mock_server.get_url("/markdown"),
            "MOCK_API": self.mock_server.get_url("/api/library"),
            "MOCK_DEPTH": self.mock_server.get_url("/depth/0"),
            "MOCK_TIMEOUT": self.mock_server.get_url("/timeout"),
            "MOCK_LARGE": self.mock_server.get_url("/large"),
        }

        for placeholder, url in replacements.items():
            arg = arg.replace(placeholder, url)

        return arg

    def validate_database(self, validation: dict[str, Any]) -> dict[str, bool]:
        """Validate database state."""
        results = {}

        if not self.db_path.exists():
            results["database_exists"] = False
            return results

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Check document count
            if "document_count" in validation:
                cursor.execute("SELECT COUNT(*) as count FROM documents")
                count = cursor.fetchone()["count"]
                results["document_count"] = count == validation["document_count"]

            # Check for specific documents
            if "has_documents" in validation:
                for doc_title in validation["has_documents"]:
                    cursor.execute(
                        "SELECT id FROM documents WHERE title LIKE ?",
                        (f"%{doc_title}%",),
                    )
                    results[f"has_doc_{doc_title}"] = cursor.fetchone() is not None

            # Check segment count
            if "segment_count" in validation:
                cursor.execute("SELECT COUNT(*) as count FROM document_segments")
                count = cursor.fetchone()["count"]
                results["segment_count"] = count >= validation["segment_count"]

            # Check for tags
            if "has_tags" in validation:
                for tag in validation["has_tags"]:
                    cursor.execute("SELECT id FROM tags WHERE name = ?", (tag,))
                    results[f"has_tag_{tag}"] = cursor.fetchone() is not None

            # Check collections
            if "has_collections" in validation:
                for collection in validation["has_collections"]:
                    cursor.execute(
                        "SELECT id FROM collections WHERE name = ?", (collection,)
                    )
                    results[f"has_collection_{collection}"] = (
                        cursor.fetchone() is not None
                    )

        finally:
            conn.close()

        return results

    def validate_storage(self, validation: dict[str, Any]) -> dict[str, bool]:
        """Validate storage state."""
        results = {}

        if not self.storage_path.exists():
            results["storage_exists"] = False
            return results

        # Check markdown files
        if "has_markdown_files" in validation:
            markdown_files = list(self.storage_path.glob("**/*.md"))
            results["has_markdown_files"] = (
                len(markdown_files) >= validation["has_markdown_files"]
            )

        # Check HTML files
        if "has_html_files" in validation:
            html_files = list(self.storage_path.glob("**/*.html"))
            results["has_html_files"] = len(html_files) >= validation["has_html_files"]

        # Check specific file content
        if "file_contains" in validation:
            for file_pattern, expected_content in validation["file_contains"].items():
                files = list(self.storage_path.glob(file_pattern))
                if files:
                    content = files[0].read_text()
                    results[f"file_contains_{file_pattern}"] = (
                        expected_content in content
                    )
                else:
                    results[f"file_contains_{file_pattern}"] = False

        return results

    def run_test(self, test_case: E2ETestCase) -> E2ETestResult:
        """Run a single test case."""
        start_time = time.time()
        outputs = []
        exit_codes = []
        validation_results = {}

        try:
            # Initialize database for each test
            init_cmd = ["dv", "init", "--force"]
            exit_code, stdout, stderr = self.run_command(init_cmd)
            if exit_code != 0:
                raise Exception(f"Failed to initialize database: {stderr}")

            # Run test commands
            for i, command in enumerate(test_case.commands):
                exit_code, stdout, stderr = self.run_command(command)

                outputs.append(stdout + stderr)
                exit_codes.append(exit_code)

                # Check expected exit code
                if test_case.expected_exit_codes and i < len(
                    test_case.expected_exit_codes
                ):
                    if exit_code != test_case.expected_exit_codes[i]:
                        raise Exception(
                            f"Command {i + 1} failed: expected exit code "
                            f"{test_case.expected_exit_codes[i]}, got {exit_code}"
                        )

                # Check expected output
                if test_case.expected_outputs and i < len(test_case.expected_outputs):
                    output = stdout + stderr
                    for expected in test_case.expected_outputs[i]:
                        if expected not in output:
                            if self.verbose:
                                self.console.print(
                                    f"[yellow]Command output:[/]\n{output}"
                                )
                            raise Exception(
                                f"Command {i + 1} output missing expected text: {expected}"
                            )

            # Run validations
            for validation in test_case.validations:
                if validation["type"] == "database":
                    db_results = self.validate_database(validation)
                    validation_results.update(db_results)
                elif validation["type"] == "storage":
                    storage_results = self.validate_storage(validation)
                    validation_results.update(storage_results)

            # Check all validations passed
            all_passed = (
                all(validation_results.values()) if validation_results else True
            )

            # Run cleanup commands
            for cleanup_cmd in test_case.cleanup_commands:
                self.run_command(cleanup_cmd)

            duration = time.time() - start_time

            return E2ETestResult(
                test_name=test_case.name,
                success=all_passed,
                duration=duration,
                outputs=outputs,
                exit_codes=exit_codes,
                validation_results=validation_results,
                error_message=None if all_passed else "Some validations failed",
            )

        except Exception as e:
            duration = time.time() - start_time
            return E2ETestResult(
                test_name=test_case.name,
                success=False,
                duration=duration,
                error_message=str(e),
                outputs=outputs,
                exit_codes=exit_codes,
                validation_results=validation_results,
            )

    def run_tests(self, test_cases: list[E2ETestCase]) -> list[E2ETestResult]:
        """Run all test cases."""
        results = []

        # Filter out skipped tests
        active_tests = [tc for tc in test_cases if not tc.skip]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        ) as progress:
            task = progress.add_task("Running tests...", total=len(active_tests))

            for test_case in active_tests:
                progress.update(task, description=f"Running: {test_case.name}")

                result = self.run_test(test_case)
                results.append(result)

                # Show immediate feedback
                if result.success:
                    if self.verbose:
                        self.console.print(f"✅ {test_case.name}")
                else:
                    self.console.print(f"❌ {test_case.name}: {result.error_message}")
                    if self.verbose and result.validation_results:
                        for check, passed in result.validation_results.items():
                            if not passed:
                                self.console.print(f"   ❌ {check}")

                progress.update(task, advance=1)

        return results

    def print_summary(self, results: list[E2ETestResult]):
        """Print test summary."""
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed
        total_duration = sum(r.duration for r in results)

        # Create summary table
        table = Table(title="Test Results Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Total Tests", str(total))
        table.add_row("Passed", f"[green]{passed}[/]")
        table.add_row("Failed", f"[red]{failed}[/]" if failed > 0 else "0")
        if total > 0:
            table.add_row("Success Rate", f"{(passed / total * 100):.1f}%")
        else:
            table.add_row("Success Rate", "N/A")
        table.add_row("Total Duration", f"{total_duration:.2f}s")

        self.console.print("\n")
        self.console.print(table)

        # Show failed tests
        if failed > 0:
            self.console.print("\n[red]Failed Tests:[/]")
            for result in results:
                if not result.success:
                    self.console.print(f"\n❌ {result.test_name}")
                    self.console.print(f"   Error: {result.error_message}")
                    if self.verbose and result.outputs:
                        self.console.print(
                            f"   Last output: {result.outputs[-1][:200]}..."
                        )

        return failed == 0


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--filter", "-f", "name_filter", help="Filter tests by name")
@click.option(
    "--list", "-l", "list_only", is_flag=True, help="List tests without running"
)
@click.option("--port", "-p", default=8888, help="Mock server port")
def main(verbose, name_filter, list_only, port):
    """Run DocVault end-to-end tests."""
    from tests.e2e.test_definitions import ALL_TESTS

    console = Console()

    # Filter tests if requested
    test_cases = ALL_TESTS
    if name_filter:
        test_cases = [tc for tc in test_cases if name_filter.lower() in tc.name.lower()]

    if list_only:
        console.print(f"\n[cyan]Available tests ({len(test_cases)}):[/]\n")
        for tc in test_cases:
            status = "[yellow]SKIP[/]" if tc.skip else "[green]ACTIVE[/]"
            console.print(f"{status} {tc.name}: {tc.description}")
        return

    # Run tests
    runner = E2ETestRunner(verbose=verbose, mock_port=port)

    try:
        runner.setup()
        results = runner.run_tests(test_cases)
        success = runner.print_summary(results)
        sys.exit(0 if success else 1)
    finally:
        runner.teardown()


if __name__ == "__main__":
    main()
