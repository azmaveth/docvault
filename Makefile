.PHONY: help test test-unit test-cli test-all test-coverage lint format clean install dev-install

# Default target
help:
	@echo "DocVault Development Commands"
	@echo "============================"
	@echo ""
	@echo "Testing:"
	@echo "  make test          - Run all tests"
	@echo "  make test-unit     - Run unit tests only"
	@echo "  make test-cli      - Run CLI tests only"
	@echo "  make test-coverage - Run tests with coverage report"
	@echo "  make test-quick    - Run quick smoke tests"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint          - Run linting checks"
	@echo "  make format        - Format code with ruff"
	@echo ""
	@echo "Setup:"
	@echo "  make install       - Install DocVault"
	@echo "  make dev-install   - Install for development"
	@echo "  make clean         - Clean build artifacts"
	@echo ""

# Testing targets
test:
	@./scripts/run-tests.sh all

test-unit:
	@./scripts/run-tests.sh unit

test-cli:
	@./scripts/run-tests.sh cli

test-coverage:
	@./scripts/run-tests.sh -c all

test-quick:
	@./scripts/run-tests.sh quick

# Code quality targets
lint:
	@echo "Running linting checks..."
	@uv run ruff check .
	@echo "✅ Linting passed!"

format:
	@echo "Formatting code..."
	@uv run ruff format .
	@echo "✅ Code formatted!"

# Installation targets
install:
	@echo "Installing DocVault..."
	@uv pip install -e ".[dev]"
	@./scripts/install-dv.sh
	@echo "✅ Installation complete!"

dev-install:
	@echo "Setting up development environment..."
	@./scripts/dev-setup.sh
	@echo "✅ Development setup complete!"

# Cleanup
clean:
	@echo "Cleaning build artifacts..."
	@rm -rf build/ dist/ *.egg-info/ .coverage htmlcov/ .pytest_cache/
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "✅ Clean complete!"