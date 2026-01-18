.PHONY: install format lint clean test pytest mypy docs docs-serve

install:
	uv sync
	pre-commit install

lint:
	uv run ruff check --fix ./gakido/
	uv run ruff format ./gakido/
	uv run ty ./gakido/

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
