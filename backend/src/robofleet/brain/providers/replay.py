"""Replay Provider (Phase 5 - CA-6).
Replays recorded decision sequences from an .ndjson file for bit-for-bit determinism in CI/CD.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from robofleet.brain.providers.base import LLMProviderResult
from robofleet.brain.providers.heuristic import HeuristicProvider
from robofleet.contracts.brain import DecisionProposal, SituationBrief


class ReplayProvider:
    name: str = "replay"

    def __init__(self, replay_file: Path | str | None = None) -> None:
        self.replay_file = Path(replay_file) if replay_file else None
        self.records: list[dict[str, Any]] = []
        self.cursor: int = 0
        self.fallback = HeuristicProvider()
        if self.replay_file and self.replay_file.exists():
            self.load_records(self.replay_file)

    def load_records(self, path: Path) -> int:
        self.records = []
        self.cursor = 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.records.append(json.loads(line))
        return len(self.records)

    async def decide(
        self,
        brief: SituationBrief,
        specialists: list[Any] | None = None,
    ) -> LLMProviderResult:
        if self.cursor < len(self.records):
            rec = self.records[self.cursor]
            self.cursor += 1
            proposals = [
                DecisionProposal.model_validate(p) for p in rec.get("proposals", [])
            ]
            return LLMProviderResult(
                proposals=proposals,
                commands=rec.get("final_commands", []),
                rationale=rec.get("rationale", "Replayed decision"),
                token_usage=rec.get("token_usage", {}),
                cost_usd=rec.get("cost_usd", 0.0),
                latency_ms=rec.get("latency_ms", 1.0),
                provider_name="replay",
            )
        # Fall back to heuristic if replay file exhausted
        return await self.fallback.decide(brief, specialists)
