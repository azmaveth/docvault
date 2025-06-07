#!/usr/bin/env python3
"""
SQL Security Audit Script for DocVault
Finds potential SQL injection vulnerabilities
"""

import os
import re
import sys
from pathlib import Path


def find_sql_vulnerabilities(root_dir):
    """Find potential SQL injection vulnerabilities in Python files."""
    vulnerabilities = []

    # Patterns that might indicate SQL injection vulnerabilities
    patterns = [
        # String formatting in execute
        (r"\.execute\s*\([^)]*%[^)]*\)", "String formatting in execute()"),
        (r"\.execute\s*\([^)]*\.format[^)]*\)", ".format() in execute()"),
        (r'\.execute\s*\([^)]*f["\'][^)]*\)', "f-string in execute()"),
        # String concatenation in execute
        (r"\.execute\s*\([^)]*\+[^)]*\)", "String concatenation in execute()"),
        # Direct string interpolation
        (
            r'\.execute\s*\(\s*["\'].*\{[^}]+\}.*["\']',
            "Brace interpolation in execute()",
        ),
        # SQL keywords with concatenation
        (
            r'(SELECT|INSERT|UPDATE|DELETE|WHERE|FROM|JOIN).*\+.*["\']',
            "SQL keyword with concatenation",
        ),
        (
            r"(SELECT|INSERT|UPDATE|DELETE|WHERE|FROM|JOIN).*%\s*[^(]",
            "SQL keyword with % formatting",
        ),
        # Dynamic table/column names
        (r'(FROM|JOIN|UPDATE)\s*["\']?\s*\+\s*\w+', "Dynamic table name"),
        (r'(SELECT|WHERE|ORDER BY)\s*["\']?\s*\+\s*\w+', "Dynamic column name"),
    ]

    # Walk through all Python files
    for root, dirs, files in os.walk(root_dir):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for file in files:
            if file.endswith(".py"):
                filepath = Path(root) / file

                try:
                    with open(filepath, encoding="utf-8") as f:
                        content = f.read()

                    # Check each pattern
                    for pattern, description in patterns:
                        for match in re.finditer(
                            pattern, content, re.IGNORECASE | re.MULTILINE
                        ):
                            line_num = content[: match.start()].count("\n") + 1
                            line = content.split("\n")[line_num - 1].strip()

                            vulnerabilities.append(
                                {
                                    "file": str(filepath.relative_to(root_dir)),
                                    "line": line_num,
                                    "type": description,
                                    "code": (
                                        line[:100] + "..." if len(line) > 100 else line
                                    ),
                                }
                            )

                except Exception as e:
                    print(f"Error reading {filepath}: {e}")

    return vulnerabilities


def main():
    # Get the docvault directory
    script_dir = Path(__file__).parent
    docvault_dir = script_dir.parent / "docvault"

    print("SQL Security Audit for DocVault")
    print("=" * 50)
    print(f"Scanning directory: {docvault_dir}")
    print()

    vulnerabilities = find_sql_vulnerabilities(docvault_dir)

    if not vulnerabilities:
        print("✅ No SQL injection vulnerabilities found!")
        return 0

    print(f"⚠️  Found {len(vulnerabilities)} potential SQL injection vulnerabilities:\n")

    # Group by file
    by_file = {}
    for vuln in vulnerabilities:
        if vuln["file"] not in by_file:
            by_file[vuln["file"]] = []
        by_file[vuln["file"]].append(vuln)

    # Print results
    for file, file_vulns in sorted(by_file.items()):
        print(f"\n📄 {file}")
        print("-" * (len(file) + 4))

        for vuln in sorted(file_vulns, key=lambda x: x["line"]):
            print(f"  Line {vuln['line']:4d}: {vuln['type']}")
            print(f"           {vuln['code']}")

    print(f"\n\nTotal issues: {len(vulnerabilities)}")
    print("\nRecommendations:")
    print("1. Use parameterized queries (?, :name) instead of string formatting")
    print("2. Never concatenate user input into SQL queries")
    print("3. Use the QueryBuilder class for dynamic query construction")
    print("4. Validate and sanitize all inputs before using in queries")

    return 1 if vulnerabilities else 0


if __name__ == "__main__":
    sys.exit(main())
