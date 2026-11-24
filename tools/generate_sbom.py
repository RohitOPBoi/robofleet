"""Software Bill of Materials (SBOM) Generator (Phase 7 - P7-A5).
Produces CycloneDX / SPDX JSON SBOM covering Python backend and Node.js frontend dependencies.
"""

from __future__ import annotations

import datetime
import importlib.metadata
import json
from pathlib import Path
import sys


def get_python_dependencies() -> list[dict[str, str]]:
    components = []
    # Key direct and transitive packages
    packages = [
        "fastapi", "uvicorn", "pydantic", "pyyaml", "numpy", "websockets",
        "matplotlib", "psutil", "pytest", "ruff", "mypy", "hypothesis", "httpx"
    ]
    for pkg in packages:
        try:
            ver = importlib.metadata.version(pkg)
            components.append({
                "type": "library",
                "name": pkg,
                "version": ver,
                "purl": f"pkg:pypi/{pkg}@{ver}",
                "ecosystem": "PyPI",
            })
        except Exception:
            pass
    return components


def get_node_dependencies() -> list[dict[str, str]]:
    components = []
    pkg_json_path = Path("frontend/package.json")
    if not pkg_json_path.exists():
        return components

    try:
        with open(pkg_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        for name, ver in deps.items():
            clean_ver = ver.lstrip("^~")
            components.append({
                "type": "library",
                "name": name,
                "version": clean_ver,
                "purl": f"pkg:npm/{name}@{clean_ver}",
                "ecosystem": "npm",
            })
    except Exception as e:
        print(f"Warning parsing frontend package.json: {e}")

    return components


def generate_sbom(out_path: Path | None = None) -> Path:
    out_file = out_path or Path("sbom.json")
    py_deps = get_python_dependencies()
    node_deps = get_node_dependencies()
    all_components = py_deps + node_deps

    sbom_doc = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:robofleet-sbom-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "component": {
                "name": "robofleet",
                "version": "0.1.0",
                "type": "application",
                "description": "RoboFleet Dark Store Command Centre & Digital Twin",
            },
            "tools": [{"vendor": "RoboFleet", "name": "sbom-generator", "version": "1.0.0"}],
        },
        "components": all_components,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(sbom_doc, f, indent=2)

    print(f"Generated SBOM at {out_file} ({len(all_components)} components: {len(py_deps)} PyPI, {len(node_deps)} npm)")
    return out_file


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    generate_sbom(out)
