#!/usr/bin/env python3
"""
Demonstration of the Search Within Document feature in DocVault.

This script shows how to use the --in-doc flag to search within a specific document.
"""

import subprocess


def run_command(command):
    """Run a shell command and return the output."""
    print(f"\n$ {command}")
    print("=" * 60)

    try:
        result = subprocess.run(
            command.split(), capture_output=True, text=True, check=False
        )

        if result.stdout:
            print(result.stdout)
        if result.stderr and result.returncode != 0:
            print(f"Error: {result.stderr}")

        return result.returncode == 0

    except Exception as e:
        print(f"Failed to run command: {e}")
        return False


def main():
    """Demonstrate search within document functionality."""

    print("DocVault Search Within Document Demo")
    print("====================================")
    print()
    print(
        "This demo shows how to search within a specific document using the "
        "--in-doc flag."
    )
    print()

    # First, let's see what documents we have
    print("1. List available documents:")
    run_command("dv list --limit 5")

    print("\n2. Example: Search for 'function' across all documents:")
    run_command("dv search function --limit 3")

    print("\n3. Example: Search for 'function' within document ID 1 only:")
    run_command("dv search function --in-doc 1")

    print("\n4. Example: Search within document with JSON output:")
    run_command("dv search function --in-doc 1 --format json")

    print("\n5. Example: Text-only search within specific document:")
    run_command("dv search function --in-doc 1 --text-only")

    print("\n6. Example: Search within non-existent document (error handling):")
    run_command("dv search function --in-doc 999")

    print("\n7. Example: Combine --in-doc with other filters:")
    run_command("dv search function --in-doc 1 --limit 2 --min-score 0.1")

    print("\nKey Benefits of Search Within Document:")
    print("======================================")
    print("✅ Focus search on specific document content")
    print("✅ Faster searches when you know the document")
    print("✅ Reduce noise from other documents")
    print("✅ Perfect for exploring large documents")
    print("✅ Works with all search modes (vector + text)")
    print("✅ Compatible with other search filters")
    print("✅ Machine-readable JSON output includes scope info")

    print("\nUsage Patterns:")
    print("==============")
    print("dv search 'python functions' --in-doc 123")
    print("dv search 'error handling' --in-doc 456 --format json")
    print("dv search 'API reference' --in-doc 789 --text-only")
    print("dv search --in-doc 123  # Browse document without specific query")


if __name__ == "__main__":
    main()
