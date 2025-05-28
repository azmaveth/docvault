#!/usr/bin/env bash
#
# Run DocVault end-to-end tests
#
# Usage:
#   ./run-e2e-tests.sh                    # Run all tests
#   ./run-e2e-tests.sh -v                 # Verbose output
#   ./run-e2e-tests.sh -f "search"        # Filter tests by pattern
#   ./run-e2e-tests.sh -l                 # List available tests
#   ./run-e2e-tests.sh -r report.json     # Save report to file
#

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Default options
VERBOSE=""
FILTER=""
LIST_ONLY=""
REPORT=""
PARALLEL=""
NO_MOCK=""

# Print usage
usage() {
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  -v, --verbose      Verbose output"
    echo "  -f, --filter PAT   Filter tests by pattern"
    echo "  -l, --list         List tests without running"
    echo "  -r, --report FILE  Save report to file"
    echo "  -p, --parallel     Run tests in parallel"
    echo "  -n, --no-mock      Disable mock server"
    echo "  -h, --help         Show this help message"
    echo
    echo "Examples:"
    echo "  $0                           # Run all tests"
    echo "  $0 -v                        # Verbose output"
    echo "  $0 -f search                 # Run only search tests"
    echo "  $0 -r results.json           # Save report"
    echo "  $0 -l                        # List available tests"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="--verbose"
            shift
            ;;
        -f|--filter)
            FILTER="--filter $2"
            shift 2
            ;;
        -l|--list)
            LIST_ONLY="--list"
            shift
            ;;
        -r|--report)
            REPORT="--report $2"
            shift 2
            ;;
        -p|--parallel)
            PARALLEL="--parallel"
            shift
            ;;
        -n|--no-mock)
            NO_MOCK="--no-mock"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Change to project root
cd "$PROJECT_ROOT"

# Check if virtual environment is active
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}Warning: No virtual environment detected${NC}"
    echo "Consider activating your virtual environment first"
    echo
fi

# Print header
if [[ -z "$LIST_ONLY" ]]; then
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}     DocVault End-to-End Test Suite${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo
    echo "Test Environment:"
    echo "  Python: $(python --version 2>&1)"
    echo "  DocVault: $(python -m docvault.main --version 2>&1 || echo 'Not installed')"
    echo "  Working Dir: $PWD"
    echo
fi

# Ensure DocVault is installed
if ! python -c "import docvault" 2>/dev/null; then
    echo -e "${RED}Error: DocVault is not installed${NC}"
    echo "Please install DocVault first:"
    echo "  pip install -e ."
    exit 1
fi

# Create reports directory if needed
if [[ -n "$REPORT" ]]; then
    mkdir -p "$(dirname "$REPORT")"
fi

# Run the tests
echo -e "${GREEN}Starting test runner...${NC}"
echo

# Build command
CMD="python -m tests.e2e.test_runner"
[[ -n "$VERBOSE" ]] && CMD="$CMD $VERBOSE"
[[ -n "$FILTER" ]] && CMD="$CMD $FILTER"
[[ -n "$LIST_ONLY" ]] && CMD="$CMD $LIST_ONLY"
[[ -n "$REPORT" ]] && CMD="$CMD $REPORT"
[[ -n "$PARALLEL" ]] && CMD="$CMD $PARALLEL"
[[ -n "$NO_MOCK" ]] && CMD="$CMD $NO_MOCK"

# Execute
if $CMD; then
    EXIT_CODE=0
    if [[ -z "$LIST_ONLY" ]]; then
        echo
        echo -e "${GREEN}✅ All tests passed!${NC}"
    fi
else
    EXIT_CODE=$?
    if [[ -z "$LIST_ONLY" ]]; then
        echo
        echo -e "${RED}❌ Some tests failed${NC}"
        echo "Exit code: $EXIT_CODE"
    fi
fi

# Show report location if saved
if [[ -n "$REPORT" ]] && [[ -f "$REPORT" ]]; then
    echo
    echo -e "${BLUE}Test report saved to: $REPORT${NC}"
    
    # Show summary from report
    if command -v jq &> /dev/null; then
        echo
        echo "Summary:"
        jq -r '.summary | "  Total: \(.total)\n  Passed: \(.passed)\n  Failed: \(.failed)\n  Errors: \(.errors)\n  Success Rate: \(.success_rate)%"' "$REPORT"
    fi
fi

exit $EXIT_CODE