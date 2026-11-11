"""Bin generation and static slotting engine.
Slots SKUs into rack shelf bins according to placement rules as hard constraints
and popularity-times-proximity score. Top popular SKUs get replica bins.
"""

from __future__ import annotations

import numpy as np

from robofleet.contracts.catalogue import Bin, Sku, TemperatureClass
from robofleet.contracts.common import Coordinate
from robofleet.contracts.layout import CellType, Layout
from robofleet.rules.engine import RuleEngine


class InventoryStore:
    def __init__(self, bins: list[Bin], skus: list[Sku]) -> None:
        self.bins: dict[str, Bin] = {b.bin_id: b for b in bins}
        self.skus: dict[str, Sku] = {s.sku_id: s for s in skus}
        self._sku_to_bins: dict[str, list[str]] = {}
        for b in bins:
            if b.sku_id:
                self._sku_to_bins.setdefault(b.sku_id, []).append(b.bin_id)

    def locate(self, sku_id: str) -> list[Bin]:
        bin_ids = self._sku_to_bins.get(sku_id, [])
        return [self.bins[bid] for bid in bin_ids]

    def get_bin(self, bin_id: str) -> Bin | None:
        return self.bins.get(bin_id)

    def decrement_stock(self, bin_id: str, quantity: int = 1) -> bool:
        b = self.bins.get(bin_id)
        if b and b.quantity >= quantity:
            b.quantity -= quantity
            return True
        return False


def slot_inventory(
    layout: Layout,
    skus: list[Sku],
    rule_engine: RuleEngine | None = None,
    empty_bin_pct: float = 5.0,
    top_k_popular_replicas: int = 50,
    seed: int = 42,
) -> tuple[list[Bin], InventoryStore]:
    rng = np.random.default_rng(seed)

    # 1. Identify all SHELF cells and generate multi-level bins
    bins: list[Bin] = []
    shelf_cells = [c for c in layout.cells if c.cell_type == CellType.SHELF]

    # Reference station for proximity calculation (average station coordinate)
    station_positions = [st.pos for st in layout.stations]
    ref_x = (
        int(np.mean([p.x for p in station_positions])) if station_positions else layout.width // 2
    )
    ref_y = (
        int(np.mean([p.y for p in station_positions])) if station_positions else layout.height - 2
    )
    ref_pos = Coordinate(x=ref_x, y=ref_y)

    for sc in shelf_cells:
        levels = sc.level_count
        temp_zone = sc.metadata.get("temperature_zone", "ambient")
        for lvl in range(1, levels + 1):
            bin_id = f"BIN-{sc.pos.x:02d}-{sc.pos.y:02d}-L{lvl}"
            b = Bin(
                bin_id=bin_id,
                cell=sc.pos,
                level=lvl,
                capacity=50,
                max_weight_g=25000,
            )
            b.ext["temperature_zone"] = temp_zone
            bins.append(b)

    # Sort bins by proximity to picking stations (closer first)
    bins.sort(key=lambda b: (b.cell.manhattan_distance(ref_pos), b.level))

    # Partition SKUs by temperature class, sorted by popularity rank
    ambient_skus = [
        s
        for s in sorted(skus, key=lambda s: s.popularity_rank)
        if s.temperature_class == TemperatureClass.AMBIENT
    ]
    chilled_skus = [
        s
        for s in sorted(skus, key=lambda s: s.popularity_rank)
        if s.temperature_class == TemperatureClass.CHILLED
    ]
    frozen_skus = [
        s
        for s in sorted(skus, key=lambda s: s.popularity_rank)
        if s.temperature_class == TemperatureClass.FROZEN
    ]

    sku_indices = {"ambient": 0, "chilled": 0, "frozen": 0}
    sku_pools = {"ambient": ambient_skus, "chilled": chilled_skus, "frozen": frozen_skus}

    assigned_count = 0

    # Slotting loop
    for b in bins:
        # Honor empty bin target
        if rng.uniform(0.0, 100.0) < empty_bin_pct:
            continue

        b_zone = str(b.ext.get("temperature_zone", "ambient"))
        pool = sku_pools.get(b_zone, ambient_skus)
        curr_idx = sku_indices.get(b_zone, 0)

        chosen_sku: Sku | None = None
        if curr_idx < len(pool):
            candidate = pool[curr_idx]
            # Check heavy item rule: if unit_weight_g > 5000 and level >= 4, find next lighter item
            if candidate.unit_weight_g > 5000 and b.level >= 4:
                # Find next candidate in pool that is <= 5000g
                for sub_idx in range(curr_idx + 1, len(pool)):
                    if pool[sub_idx].unit_weight_g <= 5000:
                        chosen_sku = pool.pop(sub_idx)
                        break
                if not chosen_sku:
                    chosen_sku = candidate
                    sku_indices[b_zone] = curr_idx + 1
            else:
                chosen_sku = candidate
                sku_indices[b_zone] = curr_idx + 1
        elif top_k_popular_replicas > 0 and pool:
            # Replica of popular SKU in this pool
            chosen_sku = pool[rng.integers(0, min(top_k_popular_replicas, len(pool)))]

        if chosen_sku:
            b.sku_id = chosen_sku.sku_id
            b.quantity = int(rng.integers(15, b.capacity))
            assigned_count += 1

    store = InventoryStore(bins=bins, skus=skus)
    return bins, store
