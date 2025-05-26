#!/usr/bin/env python3
"""
Demonstration of DocVault's flexible search combinations.

This script shows how to combine text queries with tags, collections,
and other filters for powerful search capabilities.
"""

import subprocess


def run_command(command):
    """Run a shell command and show the output."""
    print(f"\n$ {command}")
    print("=" * 70)

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, check=False
        )

        if result.stdout:
            print(result.stdout)
        if result.stderr and result.returncode != 0:
            print(f"Error: {result.stderr}")

    except Exception as e:
        print(f"Failed to run command: {e}")


def main():
    """Demonstrate various search combinations."""

    print("DocVault Search Combinations Demo")
    print("=================================")
    print()
    print("DocVault supports combining text queries with tags, collections,")
    print("and other filters for precise documentation searches.")
    print()

    # Basic Examples
    print("\n📝 Basic Search Examples")
    print("-" * 30)

    print("\n1. Text search only:")
    run_command('dv search "authentication"')

    print("\n2. Tag search only (no text query):")
    run_command("dv search --tags python security")

    print("\n3. Collection search only:")
    run_command('dv search --collection "My Project"')

    # Combined Examples
    print("\n\n🔗 Combined Search Examples")
    print("-" * 30)

    print("\n1. Text + Tags:")
    print("   Find 'authentication' in Python security documents")
    run_command('dv search "authentication" --tags python security')

    print("\n2. Text + Collection:")
    print("   Find 'database' in your project collection")
    run_command('dv search "database" --collection "My Project"')

    print("\n3. Text + Tags + Collection:")
    print("   Find 'async' in Python docs within your project")
    run_command('dv search "async" --tags python --collection "My Project"')

    print("\n4. Tags + Collection (no text):")
    print("   Find all Django ORM docs in your project")
    run_command('dv search --tags django orm --collection "Django Project"')

    # Advanced Combinations
    print("\n\n🚀 Advanced Search Combinations")
    print("-" * 30)

    print("\n1. Full combination with all filters:")
    run_command(
        'dv search "models" --tags django orm --collection "Web App" --limit 10'
    )

    print("\n2. Library docs with specific tags:")
    run_command('dv search "configuration" --tags python --library')

    print("\n3. Version-specific search with tags:")
    run_command('dv search "decorators" --tags python --version 3.10')

    print("\n4. Search within specific document:")
    run_command('dv search "function" --in-doc 123')

    # Tag Modes
    print("\n\n🏷️  Tag Combination Modes")
    print("-" * 30)

    print("\n1. ANY mode (default - match any tag):")
    run_command('dv search "api" --tags rest graphql --tag-mode any')

    print("\n2. ALL mode (must have all tags):")
    run_command('dv search "api" --tags python rest --tag-mode all')

    # Special Features
    print("\n\n✨ Special Search Features")
    print("-" * 30)

    print("\n1. Search with summaries:")
    run_command('dv search "authentication" --tags security --summarize')

    print("\n2. Search with suggestions:")
    run_command('dv search "database" --tags python --suggestions')

    print("\n3. Text-only search (no embeddings):")
    run_command('dv search "django models" --tags django --text-only')

    # Output Formats
    print("\n\n📊 Output Formats")
    print("-" * 30)

    print("\n1. JSON output for automation:")
    run_command('dv search "api" --tags python --format json --limit 2')

    # Search Patterns
    print("\n\n💡 Common Search Patterns")
    print("-" * 30)

    print(
        """
1. Project-specific searches:
   dv search "error handling" --collection "My SaaS" --tags python

2. Learning path searches:
   dv search --collection "Learn Django" --tags beginner tutorial

3. Security audit searches:
   dv search --tags security vulnerability --collection "Production Apps"

4. API documentation searches:
   dv search "endpoints" --tags api rest --library

5. Cross-project searches:
   dv search "authentication" --tags security oauth2
   (searches across all documents with those tags)

6. Debugging searches:
   dv search "traceback" --tags python debugging --limit 20
"""
    )

    # Tips
    print("\n🎯 Pro Tips")
    print("-" * 30)
    print(
        """
• Combine text queries with tags for precision
• Use collections to scope searches to projects
• Use --tag-mode all when you need specific combinations
• Add --summarize for quick overviews
• Use --format json for scripting and automation
• Text queries search content, tags filter documents
"""
    )


if __name__ == "__main__":
    main()
