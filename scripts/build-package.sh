#!/bin/bash
# Script to build and package DocVault for PyPI

# Ensure we're in the project root
SCRIPT_DIR=$(dirname "$(realpath "$0")")
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
cd "$PROJECT_ROOT"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/

# Ensure build is installed
if ! python -c "import build" &> /dev/null; then
    echo "Installing build package..."
    pip install build
fi

# Build the package
echo "Building package..."
python -m build

# Show the built files
echo -e "\nBuilt packages:"
ls -l dist/

# Copy the dv script to the dist directory for inclusion in docs
cp scripts/dv dist/ 2>/dev/null || true
echo "Copied dv script to dist/ directory"

# Help for publishing
echo -e "\nTo publish to TestPyPI first (recommended):"
echo "pip install twine  # if not already installed"
echo "twine upload --repository testpypi dist/*"

echo -e "\nTo publish to PyPI:"
echo "twine upload dist/*"

echo -e "\nBuild complete!"
