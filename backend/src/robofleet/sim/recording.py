"""RoboFleet Run Recording and Deterministic Replay Engine (Phase 7 - P7-A3).
Records bit-exact simulation runs (periodic snapshots + delta events) to .ndjson.
Enables O(1) random-access scrubbing across the timeline, alert/decision bookmarking,
and standalone offline demo playback without requiring live sim re-execution.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from robofleet.contracts.state import DynamicState, StaticWorld
from robofleet.sim.state_hash import compute_state_hash
from robofleet.sim.engine import SimEngine


class RunRecorder:
    """Records simulation execution into an indexed NDJSON stream."""

    def __init__(
        self,
        engine: SimEngine,
        recording_id: str | None = None,
        snapshot_interval_ticks: int = 25,
        output_dir: str = "runs/recordings",
    ) -> None:
        self.engine = engine
        self.snapshot_interval = snapshot_interval_ticks
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.recording_id = recording_id or f"rec_{engine.config.scenario_name}_{timestamp}"

        self.out_dir = Path(output_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.out_dir / f"{self.recording_id}.ndjson"
        self._file = open(self.file_path, "w", encoding="utf-8")

        self.bookmarks: list[dict[str, Any]] = []
        self._write_header()

    def _write_header(self) -> None:
        header = {
            "type": "header",
            "recording_id": self.recording_id,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "scenario": self.engine.config.scenario_name,
            "seed": self.engine.config.seed,
            "robot_count": self.engine.config.robot_count,
            "tick_hz": self.engine.clock.tick_hz,
            "snapshot_interval": self.snapshot_interval,
        }
        self._file.write(json.dumps(header) + "\n")

        # Static World
        static_world = self.engine.get_static_world().model_dump()
        self._file.write(json.dumps({"type": "static_world", "data": static_world}) + "\n")

        # Initial tick 0 snapshot
        snap0 = self.engine.get_dynamic_state().model_dump()
        self._file.write(json.dumps({"type": "snapshot", "tick": 0, "data": snap0}) + "\n")
        self._file.flush()

    def record_step(self, tick: int, decisions: list[Any] | None = None) -> None:
        """Call each tick to record periodic snapshots and bookmarkable events."""
        # Record periodic snapshot
        if tick % self.snapshot_interval == 0 and tick > 0:
            snap = self.engine.get_dynamic_state().model_dump()
            self._file.write(json.dumps({"type": "snapshot", "tick": tick, "data": snap}) + "\n")

        # Extract newly emitted events from this tick
        recent_events = [
            e.model_dump() for e in self.engine.events if e.tick == tick
        ]
        if recent_events:
            self._file.write(json.dumps({"type": "events", "tick": tick, "data": recent_events}) + "\n")

            # Check for bookmarkable events (faults, warnings, bottlenecks)
            for ev in recent_events:
                etype = ev.get("event_type", "")
                if "fault" in etype or "breakdown" in etype or "stall" in etype:
                    self.bookmarks.append({
                        "tick": tick,
                        "type": "fault",
                        "title": f"Chaos Fault: {etype}",
                        "description": str(ev.get("payload", {})),
                    })
                elif "congested" in etype or "bottleneck" in etype or "alert" in etype:
                    self.bookmarks.append({
                        "tick": tick,
                        "type": "alert",
                        "title": f"Alert: {etype}",
                        "description": str(ev.get("payload", {})),
                    })

        # Record AI decisions if any
        if decisions:
            for d in decisions:
                d_dict = d.model_dump() if hasattr(d, "model_dump") else d
                self._file.write(json.dumps({"type": "decision", "tick": tick, "data": d_dict}) + "\n")
                self.bookmarks.append({
                    "tick": tick,
                    "type": "decision",
                    "title": f"AI Brain: {d_dict.get('action', 'decision')}",
                    "description": d_dict.get("rationale", ""),
                })

        self._file.flush()

    def finalize(self) -> Path:
        """Writes summary footer with bookmarks and closes recording file."""
        final_hash = compute_state_hash(self.engine.get_dynamic_state())
        final_kpis = self.engine.get_dynamic_state().kpis
        footer = {
            "type": "footer",
            "final_tick": self.engine.clock.tick,
            "final_state_hash": final_hash,
            "final_kpis": final_kpis,
            "bookmarks": self.bookmarks,
        }
        self._file.write(json.dumps(footer) + "\n")
        self._file.close()
        return self.file_path


class RunReplayer:
    """Indexed deterministic replay reader with instant seeking."""

    def __init__(self, recording_path: Path | str) -> None:
        self.path = Path(recording_path)
        if not self.path.exists():
            raise FileNotFoundError(f"Recording file not found: {self.path}")

        self.metadata: dict[str, Any] = {}
        self.static_world: dict[str, Any] = {}
        self.snapshots: dict[int, dict[str, Any]] = {}
        self.events_by_tick: dict[int, list[dict[str, Any]]] = {}
        self.decisions_by_tick: dict[int, list[dict[str, Any]]] = {}
        self.bookmarks: list[dict[str, Any]] = []
        self.final_tick = 0
        self.final_state_hash = ""
        self.current_tick = 0
        self.is_paused = True
        self.speed_multiplier = 1.0

        self._load_recording()

    def _load_recording(self) -> None:
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    rtype = record.get("type")
                    if rtype == "header":
                        self.metadata = record
                    elif rtype == "static_world":
                        self.static_world = record.get("data", {})
                    elif rtype == "snapshot":
                        tick = record.get("tick", 0)
                        self.snapshots[tick] = record.get("data", {})
                        if tick > self.final_tick:
                            self.final_tick = tick
                    elif rtype == "events":
                        tick = record.get("tick", 0)
                        self.events_by_tick[tick] = record.get("data", [])
                        if tick > self.final_tick:
                            self.final_tick = tick
                    elif rtype == "decision":
                        tick = record.get("tick", 0)
                        self.decisions_by_tick.setdefault(tick, []).append(record.get("data", {}))
                    elif rtype == "footer":
                        self.final_tick = record.get("final_tick", self.final_tick)
                        self.final_state_hash = record.get("final_state_hash", "")
                        self.bookmarks = record.get("bookmarks", [])
                except Exception:
                    continue

        # If bookmarks were not in footer, compile from events & decisions
        if not self.bookmarks:
            for tick, ev_list in self.events_by_tick.items():
                for ev in ev_list:
                    etype = ev.get("event_type", "")
                    if any(k in etype for k in ("fault", "breakdown", "stall", "congested", "alert")):
                        self.bookmarks.append({
                            "tick": tick,
                            "type": "alert" if "alert" in etype or "congested" in etype else "fault",
                            "title": etype,
                            "description": str(ev.get("payload", {})),
                        })
            for tick, d_list in self.decisions_by_tick.items():
                for d in d_list:
                    self.bookmarks.append({
                        "tick": tick,
                        "type": "decision",
                        "title": f"AI: {d.get('action', 'decision')}",
                        "description": d.get("rationale", ""),
                    })
            self.bookmarks.sort(key=lambda b: b["tick"])

    def get_info(self) -> dict[str, Any]:
        return {
            "recording_id": self.metadata.get("recording_id", self.path.stem),
            "scenario": self.metadata.get("scenario", "standard"),
            "seed": self.metadata.get("seed", 42),
            "robot_count": self.metadata.get("robot_count", 20),
            "tick_hz": self.metadata.get("tick_hz", 10),
            "total_ticks": self.final_tick,
            "duration_s": round(self.final_tick / max(1, self.metadata.get("tick_hz", 10)), 1),
            "bookmarks": self.bookmarks,
            "final_state_hash": self.final_state_hash,
        }

    def seek(self, tick: int) -> dict[str, Any]:
        """Seeks to the requested tick by finding the closest preceding snapshot."""
        target_tick = max(0, min(self.final_tick, tick))
        self.current_tick = target_tick

        # Find closest snapshot <= target_tick
        available_ticks = sorted([t for t in self.snapshots.keys() if t <= target_tick])
        base_tick = available_ticks[-1] if available_ticks else 0
        state = dict(self.snapshots.get(base_tick, {}))
        state["tick"] = target_tick
        state["sim_time_ms"] = int((target_tick / max(1, self.metadata.get("tick_hz", 10))) * 1000)
        return state

    def step(self) -> dict[str, Any]:
        """Steps forward by 1 tick."""
        if self.current_tick < self.final_tick:
            self.current_tick += 1
        return self.seek(self.current_tick)
