"""Tests for CSV Catalogue Source adapter."""

from __future__ import annotations

from pathlib import Path

import pytest
from robofleet.catalogue.csv_source import load_catalogue_from_csv
from robofleet.contracts.catalogue import TemperatureClass


def test_load_catalogue_from_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "test_catalogue.csv"
    csv_file.write_text(
        """sku_id,name,category,pack_size,mrp_inr,popularity_rank,size_class,fragile,handling_difficulty,unit_weight_g,temperature_class,shelf_life_days,hazard_class
SKU-DAI-0001,Organic Cow Milk,dairy,500 ml,40.0,1,medium,false,1.0,520,chilled,3,none
SKU-BAK-0002,Brown Bread Loaf,bakery,400 g,50.0,2,medium,false,1.0,410,ambient,5,none
""",
        encoding="utf-8",
    )

    skus = load_catalogue_from_csv(csv_file)
    assert len(skus) == 2
    assert skus[0].sku_id == "SKU-DAI-0001"
    assert skus[0].temperature_class == TemperatureClass.CHILLED
    assert skus[1].name == "Brown Bread Loaf"
    assert skus[1].mrp_inr == 50.0


def test_load_catalogue_from_missing_csv_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_catalogue_from_csv("non_existent_file.csv")
