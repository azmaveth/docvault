#!/usr/bin/env bash
#
# Run DocVault end-to-end tests
#

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"

# Check if virtual environment is active
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "Warning: No virtual environment detected"
    echo "Consider activating your virtual environment first"
fi

# Run the tests
echo "Running DocVault End-to-End Tests..."
echo "=================================="
echo

python -m tests.e2e.test_runner "$@"