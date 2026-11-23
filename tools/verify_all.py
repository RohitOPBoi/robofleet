"""RoboFleet Strict Flagship Verification Orchestrator (Phase 7 - P7-A8).
Executes complete offline verification suite:
- Preflight environment check
- Secrets & credential scan
- Magic numbers scanner
- Code style & linting (Ruff)
- Strict type-checking (Mypy)
- Full automated test suite (Pytest 104+ tests)
- Change Drills (CD-1 to CD-9)
- SBOM generation
- Documentation & contract schema validation
Prints a unified PASS / FAIL audit table and returns exit code 0 or 1.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


def run_step(name: str, cmd: list[str]) -> tuple[bool, float, str]:
    t0 = time.perf_counter()
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
        )
        elapsed = time.perf_counter() - t0
        ok = (res.returncode == 0)
        output = (res.stdout + "\n" + res.stderr).strip()
        return ok, elapsed, output
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return False, elapsed, str(e)


def main() -> int:
    print("=" * 75)
    print("ROBOFLEET FLAGSHIP VERIFICATION SUITE (make verify / P7-A8)")
    print("=" * 75)

    steps: list[tuple[str, list[str]]] = [
        ("Preflight Check", [sys.executable, "tools/preflight.py"]),
        ("Secrets Scan", [sys.executable, "tools/scan_secrets.py"]),
        ("Magic Numbers Scan", [sys.executable, "backend/src/robofleet/tools/magic_numbers.py"]),
        ("Python Linting (Ruff)", ["uv", "run", "ruff", "check", "backend/src", "backend/tests"]),
        ("Type Checking (Mypy)", ["uv", "run", "mypy", "backend/src"]),
        ("Unit & Property Tests (Pytest)", ["uv", "run", "pytest", "backend/tests"]),
        ("Change Drills (CD-1 to CD-9)", ["uv", "run", "python", "-m", "robofleet.cli.main", "drills"]),
        ("SBOM Generation", [sys.executable, "tools/generate_sbom.py"]),
        ("Schema Consistency Check", ["uv", "run", "python", "-m", "robofleet.cli.main", "export-schemas"]),
    ]

    results: list[tuple[str, bool, float, str]] = []
    all_passed = True

    for name, cmd in steps:
        print(f"Running: {name}...")
        ok, elapsed, out = run_step(name, cmd)
        results.append((name, ok, elapsed, out))
        status_str = "PASS" if ok else "FAIL"
        print(f"  [{status_str}] in {elapsed:.2f}s")
        if not ok:
            print(f"--- FAILURE DETAILS for {name} ---\n{out}\n------------------------")
            all_passed = False

    print("\n" + "=" * 75)
    print(f"{'VERIFICATION STAGE':<34} | {'RESULT':<8} | {'TIME'}")
    print("-" * 75)
    for name, ok, elapsed, _ in results:
        status_label = "PASS" if ok else "FAIL"
        print(f"{name:<34} | [{status_label:<4}] | {elapsed:.2f}s")

    print("=" * 75)
    if all_passed:
        print("ALL VERIFICATION CHECKS PASSED. SYSTEM IS FLAGSHIP READY.")
        print("=" * 75)
        return 0
    else:
        print("VERIFICATION FAILED: Review the failures listed above.")
        print("=" * 75)
        return 1


if __name__ == "__main__":
    sys.exit(main())
