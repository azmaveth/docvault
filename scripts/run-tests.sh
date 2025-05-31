#!/bin/bash
# DocVault Test Runner Script

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 DocVault Test Runner${NC}"
echo -e "${BLUE}=====================${NC}\n"

# Check if we're in the project root
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ Error: Must run from project root directory${NC}"
    exit 1
fi

# Parse command line arguments
TEST_SUITE="all"
VERBOSE=""
COVERAGE=""
FAILFAST=""
MARKERS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            echo "Usage: $0 [options] [test_suite]"
            echo ""
            echo "Test suites:"
            echo "  all       - Run all tests (default)"
            echo "  unit      - Run unit tests only"
            echo "  cli       - Run CLI tests only"
            echo "  mcp       - Run MCP server tests only"
            echo "  db        - Run database tests only"
            echo "  quick     - Run quick smoke tests"
            echo ""
            echo "Options:"
            echo "  -v, --verbose     Show detailed test output"
            echo "  -c, --coverage    Generate coverage report"
            echo "  -f, --failfast    Stop on first failure"
            echo "  -m, --markers     Additional pytest markers"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run all tests"
            echo "  $0 cli                # Run CLI tests only"
            echo "  $0 -v -c unit         # Run unit tests with verbose output and coverage"
            echo "  $0 -f quick           # Run quick tests, stop on first failure"
            exit 0
            ;;
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -c|--coverage)
            COVERAGE="--cov=docvault --cov-report=term-missing --cov-report=html"
            shift
            ;;
        -f|--failfast)
            FAILFAST="-x"
            shift
            ;;
        -m|--markers)
            MARKERS="$2"
            shift 2
            ;;
        *)
            TEST_SUITE="$1"
            shift
            ;;
    esac
done

# Ensure dev dependencies are installed
echo -e "${BLUE}Checking test dependencies...${NC}"
if ! uv run python -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}Installing dev dependencies...${NC}"
    uv pip install -e ".[dev]"
fi

# Define test patterns for different suites
case $TEST_SUITE in
    all)
        echo -e "${YELLOW}Running all tests...${NC}\n"
        TEST_PATTERN="tests/"
        ;;
    unit)
        echo -e "${YELLOW}Running unit tests...${NC}\n"
        TEST_PATTERN="tests/test_basic.py tests/test_embeddings.py tests/test_library_manager.py tests/test_scraper.py tests/test_sections.py tests/test_schema.py tests/test_db_operations.py tests/test_diagnostics.py tests/test_project_import.py"
        ;;
    cli)
        echo -e "${YELLOW}Running CLI tests...${NC}\n"
        TEST_PATTERN="tests/test_cli*.py"
        ;;
    mcp)
        echo -e "${YELLOW}Running MCP server tests...${NC}\n"
        TEST_PATTERN="tests/test_mcp_server.py"
        ;;
    db)
        echo -e "${YELLOW}Running database tests...${NC}\n"
        TEST_PATTERN="tests/test_db_operations.py tests/test_schema.py"
        ;;
    quick)
        echo -e "${YELLOW}Running quick smoke tests...${NC}\n"
        TEST_PATTERN="tests/test_basic.py tests/test_cli.py::test_placeholder"
        if [ -n "$MARKERS" ]; then
            MARKERS="${MARKERS} and not slow"
        else
            MARKERS="not slow"
        fi
        ;;
    *)
        echo -e "${RED}❌ Unknown test suite: $TEST_SUITE${NC}"
        echo "Use -h or --help to see available options"
        exit 1
        ;;
esac

# Build pytest command
PYTEST_CMD="uv run pytest $TEST_PATTERN $VERBOSE $COVERAGE $FAILFAST"

# Add markers if specified
if [ -n "$MARKERS" ]; then
    PYTEST_CMD="$PYTEST_CMD -m '$MARKERS'"
fi

# Show command being run
echo -e "${BLUE}Running: $PYTEST_CMD${NC}\n"

# Run tests
if eval $PYTEST_CMD; then
    echo -e "\n${GREEN}✅ Tests passed!${NC}"
    
    # Show coverage report location if coverage was enabled
    if [ -n "$COVERAGE" ]; then
        echo -e "${BLUE}📊 Coverage report generated at: htmlcov/index.html${NC}"
    fi
    
    exit 0
else
    echo -e "\n${RED}❌ Tests failed!${NC}"
    exit 1
fi