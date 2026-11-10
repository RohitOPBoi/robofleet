.PHONY: setup lint typecheck test run schemas drills clean

setup:
	uv pip install -e ".[dev]"

lint:
	uv run ruff check backend/src backend/tests
	uv run python backend/src/robofleet/tools/magic_numbers.py

format:
	uv run ruff format backend/src backend/tests

typecheck:
	uv run mypy backend/src

test:
	uv run pytest --cov=robofleet --cov-report=term-missing backend/tests

run:
	uv run python -m robofleet.cli run --scenario standard --duration 3600

schemas:
	uv run python -m robofleet.cli export-schemas

drills:
	uv run python -m robofleet.cli drills

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
