#!/bin/bash
# Script to set up development environment using UV

# Ensure we're in the project root
SCRIPT_DIR=$(dirname "$(realpath "$0")")
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
cd "$PROJECT_ROOT"

# Create development directory if it doesn't exist
mkdir -p .docvault/

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "UV not found. Installing UV..."
    pip install uv
fi

# Create venv using UV (faster than traditional venv)
echo "Creating virtual environment..."
uv venv .venv

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install package in development mode with UV
echo "Installing DocVault in development mode..."
uv pip install -e .

# Make the dv script executable and link it for development
echo "Setting up dv command..."
chmod +x "$PROJECT_ROOT/scripts/dv"

# Create a symlink in .venv/bin if it doesn't exist
if [ ! -f ".venv/bin/dv" ]; then
    ln -sf "$PROJECT_ROOT/scripts/dv" .venv/bin/dv
    echo "✅ Linked dv script to .venv/bin/dv"
fi

# Check if sqlite-vec extension is installed
echo "Checking for sqlite-vec extension..."
python -c "import sqlite3; conn = sqlite3.connect(':memory:'); try: conn.enable_load_extension(True); conn.load_extension('sqlite_vec'); print('✅ sqlite-vec extension found!'); except Exception as e: print('❌ sqlite-vec extension not found:'); print(e); try: import sqlite_vec; print('✅ sqlite-vec Python package is installed'); except ImportError: print('Please install with: pip install sqlite-vec');"

echo "Development environment setup complete!"
