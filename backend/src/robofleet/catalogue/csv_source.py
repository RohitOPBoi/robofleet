"""CSV Catalogue Source adapter (CA-2).
Loads SKU definitions from external CSV files.
"""

from __future__ import annotations

import csv
from pathlib import Path

from robofleet.contracts.catalogue import HazardClass, Sku, TemperatureClass


def load_catalogue_from_csv(csv_path: Path | str) -> list[Sku]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Catalogue CSV not found: {csv_path}")

    skus: list[Sku] = []
    with path.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            temp_cls = TemperatureClass(row.get("temperature_class", "ambient"))
            hazard_cls = HazardClass(row.get("hazard_class", "none"))
            sku = Sku(
                sku_id=row["sku_id"],
                name=row["name"],
                category=row.get("category", "general"),
                pack_size=row.get("pack_size", "1 pc"),
                mrp_inr=float(row.get("mrp_inr", 100.0)),
                popularity_rank=int(row.get("popularity_rank", 1)),
                size_class=row.get("size_class", "medium"),
                fragile=row.get("fragile", "false").lower() in ("true", "1"),
                handling_difficulty=float(row.get("handling_difficulty", 1.0)),
                unit_weight_g=int(row.get("unit_weight_g", 500)),
                dimensions_mm=[100, 100, 100],
                temperature_class=temp_cls,
                shelf_life_days=int(row.get("shelf_life_days", 90)),
                hazard_class=hazard_cls,
            )
            skus.append(sku)
    return skus
