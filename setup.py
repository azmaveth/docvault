#!/usr/bin/env python3
"""
DocVault setup script.
"""
from setuptools import find_packages, setup

setup(
    name="docvault",
    version="0.1.0",
    description="Document management system with vector search and MCP integration for LLMs",
    author="DocVault Contributors",
    author_email="your.email@example.com",
    url="https://github.com/azmaveth/docvault",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.1.3",
        "rich>=13.3.1",
        "python-dotenv>=1.0.0",
        "requests>=2.28.1",
        "beautifulsoup4>=4.11.1",
        "html2text>=2020.1.16",
        "aiohttp>=3.8.4",
        "numpy>=1.24.0",
        "markdown-it-py>=2.2.0",
        "httpx>=0.23.3",
        "httpx-sse>=0.3.0",
        "mcp[cli]>=1.3.0",
        "sqlite-vec>=0.1.0",
        "uvicorn>=0.17.6",
    ],
    scripts=["scripts/dv"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.12",
        "Topic :: Documentation",
        "Topic :: Text Processing",
        "Topic :: Utilities",
    ],
    python_requires=">=3.12",
)
