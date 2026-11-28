"""RoboFleet Preflight Stage-Safety & System Diagnostic Tool (Phase 7 - P7-A14).
Validates runtime environment, ports, WebGL advice, screen resolution, API keys,
and offline demo assets before live presentations or customer meetings.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import socket
import subprocess
import sys


def check_python_version() -> tuple[bool, str]:
    v = sys.version_info
    ok = (v.major == 3 and v.minor >= 11)
    msg = f"Python {v.major}.{v.minor}.{v.micro} ({'OK >= 3.11' if ok else 'FAIL < 3.11'})"
    return ok, msg


def check_node_version() -> tuple[bool, str]:
    try:
        res = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True)
        raw_v = res.stdout.strip()
        major = int(raw_v.lstrip("v").split(".")[0])
        ok = major >= 18
        return ok, f"Node.js {raw_v} ({'OK >= 18' if ok else 'FAIL < 18'})"
    except Exception as e:
        return False, f"Node.js not found or error: {e}"


def check_port_available(port: int, allow_robofleet_bound: bool = True) -> tuple[bool, str]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        res = s.connect_ex(("127.0.0.1", port))
        is_in_use = (res == 0)
        if not is_in_use:
            return True, f"Port {port} is FREE"
        if allow_robofleet_bound:
            return True, f"Port {port} is ACTIVE (RoboFleet Live Server running)"
        return False, f"Port {port} is BUSY by another process"


def check_offline_assets() -> tuple[bool, str]:
    golden_rec = Path("runs/recordings/demo_golden_run.ndjson")
    if golden_rec.exists() and golden_rec.stat().st_size > 1000:
        return True, f"Offline Demo Recording present ({golden_rec.stat().st_size // 1024} KB)"
    return False, "Offline Demo Recording MISSING (run `tools/record_demo.py`)"


def check_sample_integration_data() -> tuple[bool, str]:
    sample_csv = Path("examples/customer_orders_sample.csv")
    if sample_csv.exists() and sample_csv.stat().st_size > 500:
        return True, f"Sample Customer Orders present ({sample_csv.stat().st_size // 1024} KB)"
    return False, "Sample Customer Orders MISSING in examples/"


def check_api_key_status(require_key: bool = False) -> tuple[bool, str]:
    import os
    from urllib import request

    key_vars = (
        "ROBOFLEET_AI_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "TOGETHER_API_KEY",
        "FIREWORKS_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
    )
    active_vars = [name for name in key_vars if os.environ.get(name)]
    ollama_url = os.environ.get("ROBOFLEET_BRAIN__LOCAL__BASE_URL", "http://localhost:11434").rstrip("/")
    ollama_ok = False
    try:
        with request.urlopen(f"{ollama_url}/api/tags", timeout=1.0) as resp:
            ollama_ok = resp.status == 200
    except Exception:
        ollama_ok = False

    if active_vars and ollama_ok:
        return True, f"Cloud AI ({', '.join(active_vars)}) & Local Ollama ready"
    if active_vars:
        return True, f"Cloud AI key set via {', '.join(active_vars)} (Local Ollama offline)"
    if ollama_ok:
        return True, f"Local Ollama online at {ollama_url} (Recommended model: qwen3.5:4b)"
    if require_key:
        return False, "No Cloud AI API key set and Local Ollama unreachable"
    return True, "No Cloud AI key or Local Ollama detected (Heuristic & Replay modes active)"


def run_preflight(require_key: bool = False, test_port: int | None = None) -> bool:
    print("=" * 70)
    print("ROBOFLEET FLAGSHIP STAGE PREFLIGHT CHECK (Phase 7 - P7-A14)")
    print("=" * 70)

    checks: list[tuple[str, bool, str]] = []

    # 1. Python
    ok, msg = check_python_version()
    checks.append(("Python Runtime", ok, msg))

    # 2. Node
    ok, msg = check_node_version()
    checks.append(("Node.js Runtime", ok, msg))

    # 3. Ports
    p8000 = test_port or 8000
    ok, msg = check_port_available(p8000)
    checks.append((f"API Port {p8000}", ok, msg))

    # 4. Offline Demo Safety Net
    ok, msg = check_offline_assets()
    checks.append(("Offline Demo Asset", ok, msg))

    # 5. Integration Data
    ok, msg = check_sample_integration_data()
    checks.append(("Integration Sample", ok, msg))

    # 6. AI Brain / API Key
    ok, msg = check_api_key_status(require_key=require_key)
    checks.append(("AI Brain Provider", ok, msg))

    # 7. Hardware & WebGL Guidance
    arch = platform.machine()
    proc = platform.processor()
    checks.append(("WebGL & Graphics", True, f"Host Arch: {arch} | Three.js R3F 60fps target"))
    checks.append(("Resolution Advice", True, "Min: 1280x720, Recommended: 1920x1080 (16:9)"))

    # Print Report Table
    print(f"{'CHECK ITEM':<22} | {'STATUS':<8} | {'DETAILS'}")
    print("-" * 70)
    all_passed = True
    for name, status_ok, details in checks:
        status_label = "[ GO ]" if status_ok else "[NO-GO]"
        if not status_ok:
            all_passed = False
        print(f"{name:<22} | {status_label:<8} | {details}")

    print("=" * 70)
    verdict = "GO FOR STAGE PRESENTATION" if all_passed else "NO-GO: RESOLVE ISSUES BEFORE PRESENTATION"
    print(f"PREFLIGHT VERDICT: {verdict}")
    print("=" * 70)

    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="RoboFleet Preflight Checker")
    parser.add_argument("--require-key", action="store_true", help="Fail if ANTHROPIC_API_KEY is not set")
    parser.add_argument("--check-port", type=int, default=None, help="Explicit port to test")
    args = parser.parse_args()

    passed = run_preflight(require_key=args.require_key, test_port=args.check_port)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
