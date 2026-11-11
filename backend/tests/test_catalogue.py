"""Tests for Indian quick-commerce realism pack catalogue, slotting, and zero-placeholder rule."""

from __future__ import annotations

import numpy as np
from robofleet.catalogue.generator import build_co_purchase_affinity_matrix, generate_catalogue
from robofleet.catalogue.slotting import slot_inventory
from robofleet.config.loader import load_config
from robofleet.layout.generator import generate_parametric_layout
from robofleet.rules.engine import RuleEngine

FORBIDDEN_PLACEHOLDER_WORDS = [
    "lorem",
    "sample",
    "dummy",
    "test",
    "foo",
    "bar",
    "todo",
    "placeholder",
]


def test_catalogue_sku_count_and_zero_placeholders() -> None:
    skus = generate_catalogue(sku_count=1500, seed=42)
    assert len(skus) == 1500

    for sku in skus:
        name_lower = sku.name.lower()
        id_lower = sku.sku_id.lower()
        for bad_word in FORBIDDEN_PLACEHOLDER_WORDS:
            assert bad_word not in name_lower, (
                f"SKU {sku.sku_id} name contains placeholder '{bad_word}': {sku.name}"
            )
            assert bad_word not in id_lower, (
                f"SKU id contains placeholder '{bad_word}': {sku.sku_id}"
            )
        assert sku.mrp_inr > 0.0
        assert sku.unit_weight_g > 0
        assert sku.popularity_rank >= 1


def test_co_purchase_affinity_matrix() -> None:
    skus = generate_catalogue(sku_count=500, seed=42)
    affinities = build_co_purchase_affinity_matrix(skus, top_n=50)
    assert len(affinities) > 0
    # Check that dairy has affinities with bakery etc.
    dairy_skus = [s for s in skus if s.category == "dairy"]
    if dairy_skus:
        assert dairy_skus[0].sku_id in affinities


def test_slotting_popularity_proximity_and_rules() -> None:
    cfg, _ = load_config(scenario_name="standard")
    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=1000, seed=42)
    engine = RuleEngine("rules")

    bins, store = slot_inventory(
        layout=layout,
        skus=skus,
        rule_engine=engine,
        empty_bin_pct=5.0,
        top_k_popular_replicas=30,
        seed=42,
    )

    # 1. High proportion of top SKUs are accessible via locate()
    located_count = 0
    for s in skus[:200]:
        matching_bins = store.locate(s.sku_id)
        if matching_bins:
            located_count += 1
    assert located_count >= 120

    # 2. Check popularity proximity:
    # Popular SKUs (rank 1-50) must be closer on average to pick stations than unpopular (rank 400-500)
    station_pos = layout.stations[0].pos
    popular_distances: list[int] = []
    unpopular_distances: list[int] = []

    for s in skus[:50]:
        for b in store.locate(s.sku_id):
            popular_distances.append(b.cell.manhattan_distance(station_pos))

    for s in skus[400:500]:
        for b in store.locate(s.sku_id):
            unpopular_distances.append(b.cell.manhattan_distance(station_pos))

    assert len(popular_distances) > 0
    assert len(unpopular_distances) > 0
    mean_popular_dist = float(np.mean(popular_distances))
    mean_unpopular_dist = float(np.mean(unpopular_distances))
    print(
        f"Mean popular distance: {mean_popular_dist:.2f}, Mean unpopular distance: {mean_unpopular_dist:.2f}"
    )
    assert mean_popular_dist < mean_unpopular_dist, (
        f"Expected popular SKUs to be closer to stations than unpopular SKUs: {mean_popular_dist} vs {mean_unpopular_dist}"
    )
