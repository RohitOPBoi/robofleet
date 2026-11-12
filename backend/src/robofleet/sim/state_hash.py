"""Bit-for-bit deterministic state hashing using canonical SHA-256 JSON serialization.
Enforces P1-A6 determinism across runs and platforms.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from robofleet.contracts.state import DynamicState


def canonical_json_dump(obj: Any) -> str:
    """Produces canonical JSON with sorted keys and stable float formatting."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_state_hash(state: DynamicState) -> str:
    """Computes SHA-256 hash of authoritative dynamic simulation state."""
    raw = state.model_dump(mode="json")
    # Strip non-authoritative ephemeral metadata if any
    raw.pop("ext", None)
    canonical_str = canonical_json_dump(raw)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
