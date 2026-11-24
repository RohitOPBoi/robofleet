"""Independent named random streams using numpy SeedSequence.
Adding a new stream never alters or shifts existing named streams (P1-R3 determinism).
"""

from __future__ import annotations

import numpy as np


class RandomStreamManager:
    def __init__(self, root_seed: int = 42) -> None:
        self.root_seed = root_seed
        self._seed_seq = np.random.SeedSequence(root_seed)
        self._streams: dict[str, np.random.Generator] = {}
        # Predefined stream names to assign stable sub-seeds
        self._stream_keys = [
            "sim",
            "demand",
            "picker",
            "faults",
            "planner",
            "dispatcher",
            "catalogue",
            "battery",
        ]
        sub_seeds = self._seed_seq.spawn(len(self._stream_keys))
        for key, s in zip(self._stream_keys, sub_seeds, strict=False):
            self._streams[key] = np.random.default_rng(s)

    def get_stream(self, name: str) -> np.random.Generator:
        if name not in self._streams:
            # Deterministically hash name with root seed for newly requested stream
            extra_seed = np.random.SeedSequence([self.root_seed, abs(hash(name))])
            self._streams[name] = np.random.default_rng(extra_seed)
        return self._streams[name]
