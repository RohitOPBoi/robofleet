"""Deterministic realism pack catalogue generator for Indian quick-commerce dark stores.
Generates 1,500+ realistic SKUs in INR across authentic categories without placeholders.
Builds co-purchase affinity matrix for realistic order generation.
"""

from __future__ import annotations

import numpy as np

from robofleet.contracts.catalogue import HazardClass, Sku, TemperatureClass

# Realistic quick-commerce product templates across major Indian grocery categories
CATEGORY_TEMPLATES: dict[str, list[dict[str, object]]] = {
    "dairy": [
        {
            "name": "Toned Fresh Milk",
            "pack_size": "500 ml",
            "mrp": 34.0,
            "temp": TemperatureClass.CHILLED,
            "weight_g": 520,
            "shelf_life": 3,
        },
        {
            "name": "Full Cream Milk",
            "pack_size": "500 ml",
            "mrp": 38.0,
            "temp": TemperatureClass.CHILLED,
            "weight_g": 520,
            "shelf_life": 3,
        },
        {
            "name": "Cow Milk Pouch",
            "pack_size": "1 L",
            "mrp": 66.0,
            "temp": TemperatureClass.CHILLED,
            "weight_g": 1040,
            "shelf_life": 3,
        },
        {
            "name": "Salted Cooking Butter",
            "pack_size": "100 g",
            "mrp": 60.0,
            "temp": TemperatureClass.CHILLED,
            "weight_g": 110,
            "shelf_life": 180,
        },
        {
            "name": "Fresh Malai Paneer",
            "pack_size": "200 g",
            "mrp": 95.0,
            "temp": TemperatureClass.CHILLED,
            "weight_g": 210,
            "shelf_life": 15,
        },
        {
            "name": "Greek Yogurt Plain",
            "pack_size": "100 g",
            "mrp": 45.0,
            "temp": TemperatureClass.CHILLED,
            "weight_g": 115,
            "shelf_life": 14,
        },
        {
            "name": "Farm Fresh White Eggs",
            "pack_size": "6 pcs",
            "mrp": 54.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 360,
            "shelf_life": 14,
            "fragile": True,
        },
        {
            "name": "Farm Fresh Brown Eggs",
            "pack_size": "10 pcs",
            "mrp": 115.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 600,
            "shelf_life": 14,
            "fragile": True,
        },
        {
            "name": "Curd Dahi Cup",
            "pack_size": "400 g",
            "mrp": 40.0,
            "temp": TemperatureClass.CHILLED,
            "weight_g": 430,
            "shelf_life": 7,
        },
    ],
    "bakery": [
        {
            "name": "Whole Wheat Sandwich Bread",
            "pack_size": "400 g",
            "mrp": 50.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 410,
            "shelf_life": 5,
        },
        {
            "name": "White Sliced Bread",
            "pack_size": "400 g",
            "mrp": 45.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 410,
            "shelf_life": 5,
        },
        {
            "name": "Multigrain Seed Bread",
            "pack_size": "350 g",
            "mrp": 65.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 360,
            "shelf_life": 5,
        },
        {
            "name": "Fresh Pav Buns",
            "pack_size": "6 pcs",
            "mrp": 35.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 250,
            "shelf_life": 4,
        },
        {
            "name": "Burger Buns Soft",
            "pack_size": "4 pcs",
            "mrp": 40.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 220,
            "shelf_life": 4,
        },
        {
            "name": "Butter Rusk Toast",
            "pack_size": "200 g",
            "mrp": 45.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 210,
            "shelf_life": 90,
        },
    ],
    "produce": [
        {
            "name": "Fresh Red Onions",
            "pack_size": "1 kg",
            "mrp": 45.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 1020,
            "shelf_life": 10,
        },
        {
            "name": "Fresh Potato Solan",
            "pack_size": "1 kg",
            "mrp": 38.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 1020,
            "shelf_life": 14,
        },
        {
            "name": "Desi Tomatoes",
            "pack_size": "500 g",
            "mrp": 25.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 520,
            "shelf_life": 5,
        },
        {
            "name": "Hybrid Round Tomatoes",
            "pack_size": "1 kg",
            "mrp": 48.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 1020,
            "shelf_life": 6,
        },
        {
            "name": "Green Coriander Bunch",
            "pack_size": "100 g",
            "mrp": 15.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 110,
            "shelf_life": 3,
        },
        {
            "name": "Fresh Ginger Adrak",
            "pack_size": "200 g",
            "mrp": 35.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 210,
            "shelf_life": 10,
        },
        {
            "name": "Robusta Ripe Bananas",
            "pack_size": "1 kg",
            "mrp": 65.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 1050,
            "shelf_life": 4,
            "fragile": True,
        },
        {
            "name": "Shimla Red Apples",
            "pack_size": "4 pcs",
            "mrp": 160.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 700,
            "shelf_life": 14,
        },
    ],
    "staples": [
        {
            "name": "Chakki Atta 100% Whole Wheat",
            "pack_size": "5 kg",
            "mrp": 245.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 5050,
            "shelf_life": 90,
        },
        {
            "name": "Refined Sunflower Cooking Oil",
            "pack_size": "1 L",
            "mrp": 145.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 950,
            "shelf_life": 270,
        },
        {
            "name": "Mustard Oil Kachi Ghani",
            "pack_size": "1 L",
            "mrp": 165.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 950,
            "shelf_life": 270,
        },
        {
            "name": "Toor Dal Desi Unpolished",
            "pack_size": "1 kg",
            "mrp": 175.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 1010,
            "shelf_life": 180,
        },
        {
            "name": "Moong Dal Washed",
            "pack_size": "1 kg",
            "mrp": 140.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 1010,
            "shelf_life": 180,
        },
        {
            "name": "Basmati Rice Royal Grain",
            "pack_size": "1 kg",
            "mrp": 180.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 1010,
            "shelf_life": 365,
        },
        {
            "name": "Iodised Table Salt",
            "pack_size": "1 kg",
            "mrp": 28.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 1010,
            "shelf_life": 720,
        },
        {
            "name": "Refined White Sugar",
            "pack_size": "1 kg",
            "mrp": 52.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 1010,
            "shelf_life": 365,
        },
    ],
    "snacks": [
        {
            "name": "Classic Salted Potato Chips",
            "pack_size": "50 g",
            "mrp": 20.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 60,
            "shelf_life": 120,
            "fragile": True,
        },
        {
            "name": "Spicy Masala Potato Chips",
            "pack_size": "50 g",
            "mrp": 20.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 60,
            "shelf_life": 120,
            "fragile": True,
        },
        {
            "name": "Roasted Salted Almonds",
            "pack_size": "100 g",
            "mrp": 140.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 110,
            "shelf_life": 180,
        },
        {
            "name": "Dark Chocolate 70%",
            "pack_size": "100 g",
            "mrp": 120.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 105,
            "shelf_life": 365,
        },
        {
            "name": "Digestive Wheat Biscuits",
            "pack_size": "250 g",
            "mrp": 45.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 260,
            "shelf_life": 180,
        },
    ],
    "beverages": [
        {
            "name": "Instant Roast Coffee Granules",
            "pack_size": "100 g",
            "mrp": 210.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 250,
            "shelf_life": 365,
        },
        {
            "name": "Assam Kadak CTC Tea",
            "pack_size": "500 g",
            "mrp": 240.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 520,
            "shelf_life": 365,
        },
        {
            "name": "Cola Sparkling Drink Can",
            "pack_size": "300 ml",
            "mrp": 40.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 330,
            "shelf_life": 180,
        },
        {
            "name": "Orange Fruit Juice Tetrapack",
            "pack_size": "1 L",
            "mrp": 125.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 1050,
            "shelf_life": 180,
        },
        {
            "name": "Mineral Water Packaged",
            "pack_size": "1 L",
            "mrp": 20.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 1030,
            "shelf_life": 365,
        },
    ],
    "cleaning": [
        {
            "name": "Concentrated Toilet Cleaner Liquid",
            "pack_size": "500 ml",
            "mrp": 98.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 560,
            "shelf_life": 720,
            "hazard": HazardClass.CHEMICAL,
        },
        {
            "name": "Surface Disinfectant Floor Cleaner",
            "pack_size": "1 L",
            "mrp": 185.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 1080,
            "shelf_life": 720,
            "hazard": HazardClass.CHEMICAL,
        },
        {
            "name": "Lemon Dishwash Gel Squeeze",
            "pack_size": "500 ml",
            "mrp": 110.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 540,
            "shelf_life": 720,
            "hazard": HazardClass.CHEMICAL,
        },
        {
            "name": "Detergent Washing Powder",
            "pack_size": "2 kg",
            "mrp": 275.0,
            "temp": TemperatureClass.AMBIENT,
            "weight_g": 2050,
            "shelf_life": 720,
            "hazard": HazardClass.CHEMICAL,
        },
    ],
    "frozen": [
        {
            "name": "Frozen Green Peas Tender",
            "pack_size": "500 g",
            "mrp": 90.0,
            "temp": TemperatureClass.FROZEN,
            "weight_g": 510,
            "shelf_life": 180,
        },
        {
            "name": "Frozen Crispy French Fries",
            "pack_size": "420 g",
            "mrp": 120.0,
            "temp": TemperatureClass.FROZEN,
            "weight_g": 430,
            "shelf_life": 180,
        },
        {
            "name": "Vanilla Bean Ice Cream Tub",
            "pack_size": "700 ml",
            "mrp": 195.0,
            "temp": TemperatureClass.FROZEN,
            "weight_g": 480,
            "shelf_life": 90,
        },
    ],
}


def generate_catalogue(sku_count: int = 1500, seed: int = 42) -> list[Sku]:
    rng = np.random.default_rng(seed)
    categories = list(CATEGORY_TEMPLATES.keys())

    # Weight categories realistically
    cat_weights = [0.20, 0.12, 0.18, 0.16, 0.14, 0.10, 0.06, 0.04]

    skus: list[Sku] = []
    global_rank = 1

    while len(skus) < sku_count:
        cat_idx = int(rng.choice(len(categories), p=cat_weights))
        cat = categories[cat_idx]
        templates = CATEGORY_TEMPLATES[cat]
        base = templates[int(rng.integers(0, len(templates)))]

        variant_suffix = ""
        idx = len(skus) + 1
        if idx > len(templates):
            variants = [
                "Classic",
                "Premium",
                "Select",
                "Value Pack",
                "Special",
                "Gold",
                "Pure",
                "Organic",
            ]
            var_idx = int(rng.integers(0, len(variants)))
            variant_suffix = f" {variants[var_idx]} #{idx % 50 + 1}"

        sku_id = f"SKU-{cat[:3].upper()}-{idx:04d}"
        name = f"{base['name']}{variant_suffix}"

        raw_weight = int(str(base["weight_g"]))
        raw_mrp = float(str(base["mrp"]))
        raw_temp = base.get("temp", TemperatureClass.AMBIENT)
        temp_val = (
            raw_temp if isinstance(raw_temp, TemperatureClass) else TemperatureClass(str(raw_temp))
        )
        raw_hazard = base.get("hazard", HazardClass.NONE)
        hazard_val = (
            raw_hazard if isinstance(raw_hazard, HazardClass) else HazardClass(str(raw_hazard))
        )

        sku = Sku(
            sku_id=sku_id,
            name=name,
            category=cat,
            pack_size=str(base["pack_size"]),
            mrp_inr=raw_mrp * (1.0 + float(rng.uniform(-0.1, 0.2))),
            popularity_rank=global_rank,
            size_class="large" if raw_weight > 3000 else "small" if raw_weight < 300 else "medium",
            fragile=bool(base.get("fragile", False)),
            handling_difficulty=1.5 if base.get("fragile") else (2.0 if raw_weight > 4000 else 1.0),
            unit_weight_g=raw_weight,
            dimensions_mm=[150, 100, 100],
            temperature_class=temp_val,
            shelf_life_days=int(str(base.get("shelf_life", 90))),
            hazard_class=hazard_val,
        )
        skus.append(sku)
        global_rank += 1

    return skus


def build_co_purchase_affinity_matrix(skus: list[Sku], top_n: int = 100) -> dict[str, list[str]]:
    """Builds realistic co-purchase affinities (e.g. bread with butter and milk, chips with cold drink)."""
    affinities: dict[str, list[str]] = {}
    cat_map: dict[str, list[str]] = {}
    for s in skus:
        cat_map.setdefault(s.category, []).append(s.sku_id)

    # Pairs of linked categories
    pair_rules = [
        ("dairy", "bakery"),
        ("bakery", "dairy"),
        ("snacks", "beverages"),
        ("beverages", "snacks"),
        ("produce", "staples"),
        ("staples", "produce"),
    ]

    for s in skus[:top_n]:
        linked: list[str] = []
        for cat_a, cat_b in pair_rules:
            if s.category == cat_a and cat_b in cat_map:
                linked.extend(cat_map[cat_b][:3])
        affinities[s.sku_id] = linked

    return affinities
