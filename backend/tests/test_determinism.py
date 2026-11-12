"""Tests for determinism, canonical state hashes, and seed sensitivity (P1-A6)."""

from __future__ import annotations

from robofleet.catalogue.generator import generate_catalogue
from robofleet.catalogue.slotting import slot_inventory
from robofleet.config.loader import load_config
from robofleet.layout.generator import generate_parametric_layout
from robofleet.sim.engine import SimEngine
from robofleet.sim.state_hash import compute_state_hash


def run_and_collect_hashes(seed: int, sample_ticks: list[int]) -> dict[int, str]:
    cfg, _ = load_config(scenario_name="standard")
    cfg.seed = seed
    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=300, seed=seed)
    bins, _ = slot_inventory(layout=layout, skus=skus, seed=seed)
    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)

    hashes: dict[int, str] = {}
    max_tick = max(sample_ticks)
    for tick in range(1, max_tick + 1):
        engine.step()
        if tick in sample_ticks:
            hashes[tick] = compute_state_hash(engine.get_dynamic_state())
    return hashes


def test_bit_for_bit_determinism_across_runs() -> None:
    sample_ticks = [100, 300, 500]

    run1_hashes = run_and_collect_hashes(seed=42, sample_ticks=sample_ticks)
    run2_hashes = run_and_collect_hashes(seed=42, sample_ticks=sample_ticks)

    # Identical seed MUST produce identical state hashes at every sampled tick
    for t in sample_ticks:
        assert run1_hashes[t] == run2_hashes[t], (
            f"Determinism break at tick {t}! Hash 1: {run1_hashes[t]}, Hash 2: {run2_hashes[t]}"
        )


def test_different_seeds_produce_different_hashes() -> None:
    sample_ticks = [100, 300]
    hashes_seed_42 = run_and_collect_hashes(seed=42, sample_ticks=sample_ticks)
    hashes_seed_99 = run_and_collect_hashes(seed=99, sample_ticks=sample_ticks)

    assert hashes_seed_42[100] != hashes_seed_99[100], (
        "Different seeds unexpectedly produced identical state hash!"
    )
