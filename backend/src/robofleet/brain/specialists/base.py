"""Specialist Agent Base Interface (Phase 5 - CD-6).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable
from robofleet.contracts.brain import DecisionProposal, SituationBrief


@runtime_checkable
class Specialist(Protocol):
    name: str
    prompt_file: Path

    def propose(self, brief: SituationBrief) -> list[DecisionProposal]:
        ...
