#!/usr/bin/env python3
"""
Generate test fixtures for end-to-end tests.

This script creates various test documents and data for comprehensive testing.
"""

import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timedelta


def create_html_fixture(title: str, content: str, filename: str):
    """Create an HTML test fixture."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>{title}</h1>
    {content}
</body>
</html>"""
    
    fixture_path = Path(__file__).parent / filename
    with open(fixture_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Created: {filename}")


def create_markdown_fixture(title: str, content: str, filename: str):
    """Create a Markdown test fixture."""
    md = f"""# {title}

{content}
"""
    
    fixture_path = Path(__file__).parent / filename
    with open(fixture_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"Created: {filename}")


def create_json_fixture(data: dict, filename: str):
    """Create a JSON test fixture."""
    fixture_path = Path(__file__).parent / filename
    with open(fixture_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"Created: {filename}")


def create_llms_txt_fixture(content: str, filename: str):
    """Create an llms.txt test fixture."""
    fixture_path = Path(__file__).parent / filename
    with open(fixture_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Created: {filename}")


def create_project_files():
    """Create mock project dependency files."""
    # Python requirements.txt
    with open(Path(__file__).parent / "requirements.txt", 'w') as f:
        f.write("""requests==2.31.0
django>=4.2,<5.0
pytest==7.4.0
numpy
pandas>=2.0.0
""")
    
    # package.json
    package_json = {
        "name": "test-project",
        "version": "1.0.0",
        "dependencies": {
            "express": "^4.18.0",
            "react": "^18.2.0",
            "axios": "^1.4.0"
        },
        "devDependencies": {
            "jest": "^29.0.0",
            "eslint": "^8.0.0"
        }
    }
    create_json_fixture(package_json, "package.json")
    
    # Gemfile
    with open(Path(__file__).parent / "Gemfile", 'w') as f:
        f.write("""source 'https://rubygems.org'

gem 'rails', '~> 7.0'
gem 'puma'
gem 'sqlite3'
""")
    
    # mix.exs (Elixir)
    with open(Path(__file__).parent / "mix.exs", 'w') as f:
        f.write("""defmodule TestProject.MixProject do
  use Mix.Project

  def project do
    [
      app: :test_project,
      deps: deps()
    ]
  end

  defp deps do
    [
      {:phoenix, "~> 1.7"},
      {:ecto, "~> 3.10"}
    ]
  end
end
""")
    
    # go.mod
    with open(Path(__file__).parent / "go.mod", 'w') as f:
        f.write("""module example.com/test

go 1.21

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/stretchr/testify v1.8.4
)
""")
    
    # Cargo.toml (Rust)
    with open(Path(__file__).parent / "Cargo.toml", 'w') as f:
        f.write("""[package]
name = "test-project"
version = "0.1.0"

[dependencies]
tokio = { version = "1.0", features = ["full"] }
serde = "1.0"
""")
    
    print("Created project dependency files")


def generate_all_fixtures():
    """Generate all test fixtures."""
    
    # HTML fixtures
    create_html_fixture(
        "Python Documentation",
        """
        <h2>Getting Started</h2>
        <p>Python is a high-level programming language.</p>
        <h3>Installation</h3>
        <pre><code>pip install python</code></pre>
        <h3>Functions</h3>
        <p>Here are some common functions:</p>
        <ul>
            <li><code>print()</code> - Output to console</li>
            <li><code>len()</code> - Get length</li>
            <li><code>range()</code> - Generate sequence</li>
        </ul>
        """,
        "python_docs.html"
    )
    
    create_html_fixture(
        "API Reference",
        """
        <h2>REST API</h2>
        <h3>Endpoints</h3>
        <h4>GET /users</h4>
        <p>Retrieve all users</p>
        <pre><code>curl https://api.example.com/users</code></pre>
        <h4>POST /users</h4>
        <p>Create a new user</p>
        <pre><code>curl -X POST https://api.example.com/users -d '{"name": "John"}'</code></pre>
        """,
        "api_reference.html"
    )
    
    # Markdown fixtures
    create_markdown_fixture(
        "Tutorial: Web Scraping",
        """## Introduction

Web scraping is the process of extracting data from websites.

### Prerequisites

- Python 3.8+
- requests library
- BeautifulSoup4

### Basic Example

```python
import requests
from bs4 import BeautifulSoup

response = requests.get('https://example.com')
soup = BeautifulSoup(response.text, 'html.parser')
```

### Best Practices

1. Respect robots.txt
2. Add delays between requests
3. Handle errors gracefully
""",
        "web_scraping_tutorial.md"
    )
    
    # JSON fixtures
    api_response = {
        "status": "success",
        "data": {
            "users": [
                {"id": 1, "name": "Alice", "email": "alice@example.com"},
                {"id": 2, "name": "Bob", "email": "bob@example.com"}
            ],
            "total": 2
        },
        "timestamp": datetime.now().isoformat()
    }
    create_json_fixture(api_response, "api_response.json")
    
    # llms.txt fixture
    create_llms_txt_fixture(
        """# Python Documentation Summary

## Overview
Python is a high-level, interpreted programming language known for its simplicity and readability.

## Key Features
- Dynamic typing
- Automatic memory management
- Extensive standard library
- Cross-platform compatibility

## Common Use Cases
- Web development (Django, Flask)
- Data science (NumPy, Pandas)
- Machine learning (TensorFlow, PyTorch)
- Automation and scripting

## Tags
#python #programming #documentation #tutorial
""",
        "python_llms.txt"
    )
    
    # Create project files
    create_project_files()
    
    # Create a complex nested HTML document
    create_html_fixture(
        "Complex Documentation",
        """
        <div class="toc">
            <h2>Table of Contents</h2>
            <ul>
                <li><a href="#intro">Introduction</a></li>
                <li><a href="#setup">Setup</a>
                    <ul>
                        <li><a href="#requirements">Requirements</a></li>
                        <li><a href="#installation">Installation</a></li>
                    </ul>
                </li>
                <li><a href="#usage">Usage</a></li>
            </ul>
        </div>
        
        <section id="intro">
            <h2>Introduction</h2>
            <p>This is a complex documentation example with nested sections.</p>
        </section>
        
        <section id="setup">
            <h2>Setup</h2>
            <section id="requirements">
                <h3>Requirements</h3>
                <ul>
                    <li>Python 3.8+</li>
                    <li>pip</li>
                </ul>
            </section>
            <section id="installation">
                <h3>Installation</h3>
                <pre><code>pip install complex-lib</code></pre>
            </section>
        </section>
        
        <section id="usage">
            <h2>Usage</h2>
            <pre><code>from complex_lib import ComplexClass
            
obj = ComplexClass()
obj.do_something()</code></pre>
        </section>
        """,
        "complex_docs.html"
    )
    
    print("\nAll fixtures generated successfully!")


if __name__ == "__main__":
    # Ensure fixtures directory exists
    fixtures_dir = Path(__file__).parent
    fixtures_dir.mkdir(exist_ok=True)
    
    # Generate all fixtures
    generate_all_fixtures()