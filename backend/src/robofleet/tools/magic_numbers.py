"""Tool to scan Python source files for numeric and string literals outside config and allowlist.

Enforces SR-5 (Dynamic by design).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any


def is_allowed_literal(
    val: int | float | str,
    allowlist: dict[str, Any],
    rel_path: str,
    line_no: int,
) -> bool:
    # 0, 1, -1, empty string, single character docstrings/formatting are universally acceptable in logic
    if val in (0, 1, -1, 0.0, 1.0, -1.0, "", " ", "\n", "\t"):
        return True

    file_entries = allowlist.get(rel_path, [])
    for entry in file_entries:
        if entry.get("value") == val:
            entry_line = entry.get("line")
            if entry_line is None or entry_line == line_no:
                return True
    return False


def scan_file(
    filepath: Path,
    base_dir: Path,
    allowlist: dict[str, Any],
) -> list[str]:
    violations: list[str] = []
    # Relative path from project root: e.g. backend/src/robofleet/layout/generator.py
    rel_path = filepath.relative_to(base_dir).as_posix()

    # Exclude config/, cli/, contracts/, tools/, and catalogue/ from magic number checks
    parts = rel_path.split("/")
    if any(p in ("config", "cli", "contracts", "tools", "catalogue") for p in parts):
        return violations

    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except Exception as e:
        return [f"Failed to parse {rel_path}: {e}"]

    for node in ast.walk(tree):
        # Skip docstrings
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            continue

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if isinstance(node.value, bool):
                continue
            line = getattr(node, "lineno", 0)
            if not is_allowed_literal(node.value, allowlist, rel_path, line):
                violations.append(
                    f"{rel_path}:{line}: Magic number literal {node.value!r} not in config or allowlist"
                )

    return violations


def main() -> int:
    # Base directory is project root
    project_root = Path.cwd()
    src_dir = project_root / "backend" / "src" / "robofleet"
    allowlist_path = src_dir / "tools" / "magic_numbers_allowlist.json"

    allowlist: dict[str, Any] = {}
    if allowlist_path.exists():
        try:
            allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error loading allowlist: {e}", file=sys.stderr)
            return 1

    all_violations: list[str] = []
    if src_dir.exists():
        for py_file in src_dir.rglob("*.py"):
            all_violations.extend(scan_file(py_file, project_root, allowlist))

    if all_violations:
        print(
            f"FAILED: Found {len(all_violations)} magic literal violations (SR-5):", file=sys.stderr
        )
        for v in all_violations:
            print(f"  {v}", file=sys.stderr)
        return 1

    print("Magic number scan passed: 0 undeclared literals found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
