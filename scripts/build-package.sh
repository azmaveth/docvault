#!/bin/bash
# Script to build and package DocVault for PyPI

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/

# Build the package using hatch (as specified in pyproject.toml)
echo "Building package..."
python -m build

# Alternative using UV
# echo "Building package with UV..."
# uv pip build .

# Show the built files
echo -e "\nBuilt packages:"
ls -l dist/

echo -e "\nTo publish to TestPyPI (recommended for testing):"
echo "uv publish --repository testpypi"

echo -e "\nTo publish to PyPI:"
echo "uv publish"

echo -e "\nBuild complete!"
