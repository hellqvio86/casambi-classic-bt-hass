.PHONY: help setup lint format clean hooks package secrets trivy test renovate renovate-summary

help:
	@echo "Available commands:"
	@echo "  make setup     - Set up development environment using uv"
	@echo "  make hooks     - Install git commit hook (runs secrets and lint before commit)"
	@echo "  make secrets   - Run TruffleHog secret scanning"
	@echo "  make trivy     - Run Trivy vulnerability scanning"
	@echo "  make lint      - Run ruff lint and format check"
	@echo "  make test      - Run pytest unit test suite"
	@echo "  make format    - Format code with ruff"
	@echo "  make package   - Build HACS zip archive (casambi_classic_bt.zip)"
	@echo "  make clean     - Clean temporary files"

hooks:
	@chmod +x .githooks/pre-commit
	@git config core.hooksPath .githooks
	@echo "Git pre-commit hook installed and core.hooksPath set to .githooks."

secrets:
	@echo "Running TruffleHog secret scan..."
	@which trufflehog >/dev/null 2>&1 || (echo "ERROR: trufflehog is required but not installed in PATH!" >&2 && exit 1)
	@trufflehog git file://$$(pwd) --fail

trivy:
	@echo "Running Trivy vulnerability scan..."
	@docker run --rm -v $$(pwd):/src -w /src aquasec/trivy:latest fs --severity HIGH,CRITICAL --exit-code 1 .

setup: hooks
	@echo "Setting up development environment with uv..."
	uv sync
	@echo "Environment setup complete!"

lint:
	@echo "Running linting..."
	uv run ruff check custom_components/ tests/
	uv run ruff format --check custom_components/ tests/

test:
	@echo "Running tests..."
	uv run pytest tests/ -v --cov=custom_components.casambi_classic_bt --cov-fail-under=80 --cov-report=term-missing --cov-report=json
	uv run python .github/scripts/generate_coverage_badge.py

format:
	@echo "Formatting code..."
	uv run ruff format custom_components/ tests/
	uv run ruff check --fix custom_components/ tests/

clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .ruff_cache/ casambi_classic_bt.zip
	@echo "Cleanup complete!"

package:
	@echo "Packaging custom component..."
	cd custom_components && zip -r ../casambi_classic_bt.zip casambi_classic_bt
	@echo "Packaged casambi_classic_bt.zip successfully!"

renovate:
	@./bin/renovate/run.sh

renovate-summary:
	@./bin/renovate/run.sh --summary
