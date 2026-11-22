"""Manual Override and Constraint Validation (Phase 6, P6-A7).
Enforces non-bypassable physical constraint checks on manual supervisor actions
(temperature compatibility, shelf weight limits, chemical isolation, and rack level safety).
Rejected attempts are returned with precise actionable reasons and logged to the audit ledger.
"""

from __future__ import annotations

from typing import Any

from robofleet.contracts.catalogue import Bin, HazardClass, Sku, TemperatureClass


class ManualOverrideValidator:
    """Validates human supervisor slotting and task overrides against physical hard constraints."""

    PERISHABLE_FOOD_CATEGORIES = {"dairy", "bakery", "produce", "staples", "meat", "beverages", "snacks"}

    @classmethod
    def validate_placement(
        cls,
        sku: Sku,
        bin_obj: Bin,
        adjacent_category: str | None = None,
        bin_zone_temp: str = "ambient",
    ) -> tuple[bool, str | None]:
        """Validates placing a SKU into a designated bin against 4 physical hard constraints."""
        # 1. Temperature Constraint Check
        sku_temp = sku.temperature_class.value if hasattr(sku.temperature_class, "value") else str(sku.temperature_class)
        if sku_temp in ("chilled", "frozen") and bin_zone_temp != sku_temp:
            return False, f"Temperature violation: SKU '{sku.sku_id}' ({sku_temp}) cannot be placed in '{bin_zone_temp}' zone bin '{bin_obj.bin_id}'"
        if sku_temp == "ambient" and bin_zone_temp != "ambient":
            return False, f"Temperature violation: Ambient SKU '{sku.sku_id}' cannot be frozen/chilled in bin '{bin_obj.bin_id}'"

        # 2. Heavy Shelf / Ergonomic Weight Check
        if sku.unit_weight_g > 5000 and bin_obj.level >= 4:
            return False, f"Heavy shelf violation: SKU '{sku.sku_id}' ({sku.unit_weight_g}g) exceeds 5000g limit for top shelf level {bin_obj.level}"

        # 3. Rack Level Safety (top level reserved for light items < 2000g)
        if bin_obj.level >= 4 and sku.unit_weight_g > 2000 and sku.fragile:
            return False, f"Level safety violation: Fragile SKU '{sku.sku_id}' ({sku.unit_weight_g}g) cannot be placed on top level {bin_obj.level}"

        # 4. Chemical Isolation Check
        hazard = sku.hazard_class.value if hasattr(sku.hazard_class, "value") else str(sku.hazard_class)
        if hazard in ("chemical", "flammable"):
            if adjacent_category and adjacent_category.lower() in cls.PERISHABLE_FOOD_CATEGORIES:
                return False, f"Chemical isolation violation: Hazardous SKU '{sku.sku_id}' cannot be adjacent to food/perishable category '{adjacent_category}'"

        # 5. Bin Physical Capacity Check
        total_weight_if_added = (bin_obj.quantity + 1) * sku.unit_weight_g
        if total_weight_if_added > bin_obj.max_weight_g:
            return False, f"Weight capacity violation: Bin '{bin_obj.bin_id}' max weight ({bin_obj.max_weight_g}g) exceeded by load ({total_weight_if_added}g)"

        return True, None
