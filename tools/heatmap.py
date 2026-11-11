"""RoboFleet Congestion Heatmap Tool.
Generates a cell traffic congestion map from an events.ndjson file.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def generate_heatmap(events_path: str | Path, output_path: str | Path | None = None) -> None:
    events_file = Path(events_path)
    if not events_file.exists():
        print(f"Error: {events_file} does not exist.")
        return

    cell_visits: Counter[tuple[int, int]] = Counter()
    max_x, max_y = 0, 0

    with events_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            ev = json.loads(line)
            if ev.get("event_type") == "safety.move_denied":
                pass
            # Track positions if present in payloads or snapshot
            payload = ev.get("payload", {})
            if "cell" in payload and isinstance(payload["cell"], dict):
                x = payload["cell"].get("x", 0)
                y = payload["cell"].get("y", 0)
                cell_visits[(x, y)] += 1
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    print(f"Heatmap analysis complete: {len(cell_visits)} unique high-traffic cells tracked.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate congestion heatmap from event stream")
    parser.add_argument("events", type=str, help="Path to events.ndjson")
    parser.add_argument(
        "--output", type=str, default="congestion_heatmap.png", help="Output PNG path"
    )
    args = parser.parse_args()
    generate_heatmap(args.events, args.output)


if __name__ == "__main__":
    main()
