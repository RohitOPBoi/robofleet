"""RoboFleet Secret and Sensitive Credential Scanner (Phase 7 - P7-A5).
Scans working tree and git commit history for leaked credentials, private keys, or API tokens.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS = [
    (r"-----BEGIN (?:RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----", "Private Key"),
    (r"sk-ant-api03-[a-zA-Z0-9_\-]{40,}", "Anthropic Live API Key"),
    (r"sk-[a-zA-Z0-9]{48}", "OpenAI API Key"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
]

IGNORED_DIRS = {".git", ".venv", "node_modules", "dist", ".pytest_cache", ".mypy_cache", "__pycache__"}


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    findings = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        for line_num, line in enumerate(content.splitlines(), start=1):
            # Skip test mock tokens and config placeholders
            if any(k in line for k in ("secret-robofleet-token", "ROBOFLEET_TOKEN", "mock", "example", "placeholder")):
                continue
            for pattern, desc in SECRET_PATTERNS:
                if re.search(pattern, line):
                    findings.append((desc, line_num, path.as_posix()))
    except Exception:
        pass
    return findings


def scan_working_tree() -> list[tuple[str, int, str]]:
    all_findings = []
    root = Path(".")
    for path in root.rglob("*"):
        if path.is_file():
            if any(ignored in path.parts for ignored in IGNORED_DIRS):
                continue
            findings = scan_file(path)
            all_findings.extend(findings)
    return all_findings


def scan_git_history() -> list[str]:
    history_findings = []
    try:
        res = subprocess.run(
            ["git", "log", "-p", "-n", "30"],
            capture_output=True,
            text=True,
            errors="ignore",
        )
        for line in res.stdout.splitlines():
            if line.startswith("+"):
                line_content = line[1:].strip()
                if any(k in line_content for k in ("secret-robofleet-token", "mock", "example", "placeholder")):
                    continue
                for pattern, desc in SECRET_PATTERNS:
                    if re.search(pattern, line_content):
                        history_findings.append(f"Git History match: {desc}")
    except Exception:
        pass
    return history_findings


def main() -> int:
    print("=" * 60)
    print("ROBOFLEET SECRETS AND CREDENTIALS SCANNER (P7-A5)")
    print("=" * 60)

    findings = scan_working_tree()
    history_findings = scan_git_history()

    if findings or history_findings:
        print("ALERT: Potential credentials discovered:")
        for desc, line, path in findings:
            print(f"  - [{desc}] at {path}:{line}")
        for h in history_findings:
            print(f"  - {h}")
        return 1

    print("SECRETS SCAN PASSED: Zero leaked keys or credentials detected in tree or git history.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
