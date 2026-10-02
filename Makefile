.PHONY: install format lint clean test pytest mypy docs docs-serve native native-test

install:
	uv sync
	pre-commit install

# Build the native TLS backend (Go + uTLS) shared library into gakido/_native/.
# Requires a Go toolchain; optional — the library is loaded when present.
native:
	$(MAKE) -C native build

native-test:
	$(MAKE) -C native test

lint:
	uv run ruff check --fix ./gakido/
	uv run ruff format ./gakido/
	uv run ty check ./gakido/

ruff:
	uv run ruff check --fix ./gakido/


ty:
	uv run ty check ./gakido/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf site/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

test:
	uv run pytest

docs:
	uv run mkdocs build

docs-serve:
	uv run mkdocs serve
