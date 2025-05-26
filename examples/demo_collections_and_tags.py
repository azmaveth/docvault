#!/usr/bin/env python3
"""
Demonstration of using Collections and Tags together in DocVault.

This script shows the power of combining tags (descriptive attributes)
with collections (project groupings) for effective documentation management.
"""

import subprocess


def run_command(command, check=True):
    """Run a shell command and return the output."""
    print(f"\n$ {command}")
    print("-" * 60)

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, check=False
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
    """Demonstrate collections and tags working together."""

    print("DocVault Collections + Tags Demo")
    print("================================")
    print()
    print("This demo shows how Collections (project groupings) and Tags")
    print("(descriptive attributes) work together for powerful organization.")
    print()

    # Scenario 1: Starting a New Project
    print("\n🚀 Scenario 1: Starting a New Full-Stack Project")
    print("=" * 50)

    print("\n1. Create a project collection with suggested tags:")
    run_command(
        'dv collection create "Full-Stack SaaS" --description "My SaaS startup docs" --tags python django react postgresql'
    )

    print("\n2. Search for relevant Django documentation:")
    run_command("dv search django --limit 3")

    print("\n3. Add Django docs to our collection (example IDs):")
    print("   # In real usage, use actual document IDs from search results")
    print('   $ dv collection add "Full-Stack SaaS" 123 124 125')

    print("\n4. Tag these documents with our project tags:")
    print("   $ dv tag add 123 124 125 python django backend saas-project")

    # Scenario 2: Cross-Project Documentation
    print("\n\n🔄 Scenario 2: Sharing Docs Across Projects")
    print("=" * 50)

    print("\n1. A security document can belong to multiple collections:")
    print('   $ dv collection add "Full-Stack SaaS" 789')
    print('   $ dv collection add "Mobile App" 789')
    print('   $ dv collection add "Security Best Practices" 789')

    print("\n2. Tag it appropriately:")
    print("   $ dv tag add 789 security authentication oauth2 best-practices")

    # Scenario 3: Power Search Combinations
    print("\n\n🔍 Scenario 3: Powerful Search Combinations")
    print("=" * 50)

    print("\n1. Find all Python security docs in your project:")
    run_command('dv search --collection "Full-Stack SaaS" --tags python security')

    print("\n2. Search for authentication within your project collection:")
    run_command('dv search authentication --collection "Full-Stack SaaS"')

    print("\n3. Find all Django docs tagged as 'tutorial':")
    run_command("dv search --tags django tutorial")

    # Scenario 4: Building a Learning Path
    print("\n\n📚 Scenario 4: Creating a Learning Path")
    print("=" * 50)

    print("\n1. Create a learning collection:")
    run_command(
        'dv collection create "Learn React" --description "React from basics to advanced"'
    )

    print("\n2. Add documents in learning order:")
    print('   $ dv collection add "Learn React" 201  # React basics')
    print('   $ dv collection add "Learn React" 202  # Components')
    print('   $ dv collection add "Learn React" 203  # State management')
    print('   $ dv collection add "Learn React" 204  # Advanced patterns')

    print("\n3. Tag by difficulty level:")
    print("   $ dv tag add 201 202 react javascript beginner")
    print("   $ dv tag add 203 react javascript intermediate")
    print("   $ dv tag add 204 react javascript advanced patterns")

    # Scenario 5: Project Organization
    print("\n\n📁 Scenario 5: Organizing Multiple Projects")
    print("=" * 50)

    print("\n1. List all your collections:")
    run_command("dv collection list")

    print("\n2. View a specific collection:")
    run_command('dv collection show "Full-Stack SaaS"')

    print("\n3. Find which collections contain a document:")
    print("   $ dv collection find 789")

    # Best Practices
    print("\n\n💡 Best Practices")
    print("=" * 50)

    print("\n1. Tags describe WHAT:")
    print("   - Languages: python, javascript, rust")
    print("   - Topics: authentication, caching, testing")
    print("   - Types: tutorial, reference, api-docs")
    print("   - Status: deprecated, experimental, stable")

    print("\n2. Collections organize FOR:")
    print('   - Projects: "My SaaS App", "Client Website"')
    print('   - Learning: "Learn Django", "Master React"')
    print('   - Reference: "Security Best Practices", "Performance Tips"')

    print("\n3. Power Combinations:")
    print("   - Use collection default tags for consistency")
    print("   - Search within collections using tags")
    print("   - Share documents across collections")
    print("   - Build ordered learning paths")

    # Example Workflow
    print("\n\n🔧 Complete Workflow Example")
    print("=" * 50)

    print(
        """
# 1. Start a new project
dv collection create "E-commerce Platform" \\
    --description "Next.js + Stripe + PostgreSQL" \\
    --tags nextjs react stripe postgresql e-commerce

# 2. Find and add relevant documentation
dv search "nextjs server components" --limit 5
dv collection add "E-commerce Platform" 301 302 303

dv search "stripe payment integration"
dv collection add "E-commerce Platform" 401 402

# 3. Apply consistent tagging
dv tag add 301 302 303 nextjs react frontend e-commerce
dv tag add 401 402 stripe payments backend e-commerce

# 4. Search within your project
dv search "payment" --collection "E-commerce Platform"
dv search --collection "E-commerce Platform" --tags frontend

# 5. Check project status
dv collection show "E-commerce Platform"
    """
    )

    print("\n✨ Collections + Tags = Powerful Documentation Management!")


if __name__ == "__main__":
    main()
