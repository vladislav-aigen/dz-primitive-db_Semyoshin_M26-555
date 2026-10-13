.PHONY: install run lint test build
install:
	uv sync --locked
run:
	uv run database
lint:
	uv run ruff check .
test:
	uv run pytest
build:
	uv build
