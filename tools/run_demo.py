"""RoboFleet Demo Launcher (make demo / P2-A1).
Builds frontend if needed and launches the integrated streaming command centre server.
"""

from __future__ import annotations

import subprocess
import sys
import webbrowser
from pathlib import Path


def main() -> int:
    dist_dir = Path("frontend/dist")
    if not dist_dir.exists() or not (dist_dir / "index.html").exists():
        print("[Demo] Compiling React operations frontend...")
        cmd = ["npm", "run", "build"]
        res = subprocess.run(cmd, cwd="frontend", shell=True)
        if res.returncode != 0:
            print("[Demo] Error compiling frontend", file=sys.stderr)
            return res.returncode

    print("=" * 70)
    print("  ROBOFLEET AUTONOMOUS ROBOT COMMAND CENTRE & DIGITAL TWIN")
    print("=" * 70)
    print("  - Command Centre UI:     http://localhost:8000")
    print("  - OpenAPI Documentation: http://localhost:8000/docs")
    print("  - WebSocket Streaming:   ws://localhost:8000/ws")
    print("  - Environment Status:    http://localhost:8000/api/environment")
    print("=" * 70)
    print("Starting simulation server with standard scenario (20 AMRs, demand engine)...")
    print("Press Ctrl+C to stop.\n")

    # Run CLI serve command
    try:
        from robofleet.cli.main import main as cli_main

        sys.argv = [
            "robofleet",
            "serve",
            "--scenario",
            "standard",
            "--port",
            "8000",
            "--set",
            "dispatcher.type=robot_supervisor",
        ]
        return cli_main()
    except KeyboardInterrupt:
        print("\n[Demo] Server stopped cleanly.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
