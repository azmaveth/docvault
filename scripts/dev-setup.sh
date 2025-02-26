#!/bin/bash
# Script to set up development environment using UV

# Create development directory if it doesn't exist
mkdir -p .docvault/

# Create venv using UV (faster than traditional venv)
uv venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install package in development mode with UV
uv pip install -e .

# Check if sqlite-vec extension is installed
echo "Checking for sqlite-vec extension..."
python -c "import sqlite3; conn = sqlite3.connect(':memory:'); try: conn.enable_load_extension(True); conn.load_extension('sqlite_vec'); print('✅ sqlite-vec extension found!'); except Exception as e: print('❌ sqlite-vec extension not found.'); print('Please install from https://github.com/asg017/sqlite-vec');"

echo "Development environment setup complete!"
