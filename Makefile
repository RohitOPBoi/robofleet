.PHONY: setup lint format typecheck test run schemas types drills demo start soak preflight sbom verify evidence calibrate clean

setup:
	uv pip install -e ".[dev]"
	cd frontend && npm install

lint:
	uv run ruff check backend/src backend/tests
	uv run python backend/src/robofleet/tools/magic_numbers.py
	uv run python tools/scan_secrets.py

format:
	uv run ruff format backend/src backend/tests

typecheck:
	uv run mypy backend/src
	cd frontend && npm run build

test:
	uv run pytest --cov=robofleet --cov-report=term-missing backend/tests

run:
	uv run python -m robofleet.cli run --scenario standard --duration 3600

schemas:
	uv run python -m robofleet.cli export-schemas

types:
	uv run python -m robofleet.cli export-schemas
	uv run python tools/export_types.py

drills:
	uv run python -m robofleet.cli drills

start:
	uv run python tools/run_demo.py

demo:
	uv run python tools/run_demo.py

preflight:
	uv run python tools/preflight.py

sbom:
	uv run python tools/generate_sbom.py

soak:
	uv run python tools/soak_test.py

evidence:
	uv run python -m robofleet.cli evidence --scenarios standard,rush,match_night,chaos --strategies fcfs_nearest,edf_deadline,batch_greedy,heuristic --seeds 42..51 --duration 300

calibrate:
	uv run python -m robofleet.cli calibrate --file examples/customer_orders_sample.csv

verify:
	uv run python tools/verify_all.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage reports/evidence-*
