"""Minimal Rule-Driven Replenishment and Re-Slotting Recommender (Phase 6, P6-A8).
Deliberately simple, rule-driven:
1. Replenishment-lite: low-stock rule triggers restocking by simulated stocker.
   Customer urgent orders strictly outrank replenishment work.
2. Re-slotting Recommender: periodic recommendation engine scoring velocity vs distance.
   Enforces hard physical constraints and congestion guard. Recommendations only — never moves stock automatically.
"""

from __future__ import annotations

import logging
from typing import Any
import uuid

from robofleet.audit.database import AuditDatabase
from robofleet.audit.validation import ManualOverrideValidator
from robofleet.contracts.catalogue import Bin, Sku
from robofleet.contracts.chaos import ReslotRecommendation

logger = logging.getLogger(__name__)


class ReplenishmentTask:
    def __init__(
        self,
        task_id: str,
        bin_id: str,
        sku_id: str,
        units_to_add: int,
        duration_ticks: int,
        created_tick: int,
    ) -> None:
        self.task_id = task_id
        self.bin_id = bin_id
        self.sku_id = sku_id
        self.units_to_add = units_to_add
        self.duration_ticks = duration_ticks
        self.created_tick = created_tick
        self.elapsed_ticks = 0
        self.is_completed = False


class ReplenishmentManager:
    """Manages rule-driven restocking and simulated stocker resource."""

    def __init__(
        self,
        engine: Any,
        low_stock_threshold: int = 3,
        restock_quantity: int = 10,
        stocker_speed_ticks: int = 40,
        enabled: bool = True,
    ) -> None:
        self.engine = engine
        self.low_stock_threshold = low_stock_threshold
        self.restock_quantity = restock_quantity
        self.stocker_speed_ticks = stocker_speed_ticks
        self.enabled = enabled

        self.active_tasks: list[ReplenishmentTask] = []
        self.stock_outs_avoided: int = 0
        self.total_wait_ticks: int = 0
        self.completed_tasks_count: int = 0

    def step(self, current_tick: int) -> list[tuple[str, int]]:
        """Advances stocker replenishment. Urgent customer orders strictly outrank replenishment."""
        if not self.enabled:
            return []

        # Urgent orders outrank replenishment check:
        # If there are urgent/at-risk orders in flight, stocker yields/slows to not impede dark store operations
        urgent_orders_present = any(
            o.priority >= 8 or o.at_risk
            for o in getattr(self.engine, "orders", [])
            if o.status.value in ("RECEIVED", "QUEUED", "PLANNED", "RETRIEVING")
        )

        completed: list[tuple[str, int]] = []

        # 1. Scan for low-stock bins (Rule: inventory < threshold)
        if hasattr(self.engine, "bins"):
            for b in self.engine.bins:
                if b.sku_id and b.quantity < self.low_stock_threshold:
                    # Check if a task is already active for this bin
                    if not any(t.bin_id == b.bin_id for t in self.active_tasks):
                        t_id = f"REP-{uuid.uuid4().hex[:6]}"
                        task = ReplenishmentTask(
                            task_id=t_id,
                            bin_id=b.bin_id,
                            sku_id=b.sku_id,
                            units_to_add=self.restock_quantity,
                            duration_ticks=self.stocker_speed_ticks,
                            created_tick=current_tick,
                        )
                        self.active_tasks.append(task)
                        self.engine.emit_event(
                            "replenishment.task_created",
                            {"bin_id": b.bin_id, "sku_id": b.sku_id, "quantity": self.restock_quantity},
                        )

        # 2. Advance active replenishment tasks
        if self.active_tasks and not urgent_orders_present:
            current_op = self.active_tasks[0]
            current_op.elapsed_ticks += 1

            if current_op.elapsed_ticks >= current_op.duration_ticks:
                # Restock completed
                for b in getattr(self.engine, "bins", []):
                    if b.bin_id == current_op.bin_id:
                        b.quantity += current_op.units_to_add
                        break

                self.stock_outs_avoided += 1
                self.completed_tasks_count += 1
                wait_ticks = current_tick - current_op.created_tick
                self.total_wait_ticks += wait_ticks
                completed.append((current_op.bin_id, current_op.units_to_add))

                self.engine.emit_event(
                    "replenishment.completed",
                    {
                        "task_id": current_op.task_id,
                        "bin_id": current_op.bin_id,
                        "units_added": current_op.units_to_add,
                        "wait_ticks": wait_ticks,
                    },
                )
                self.active_tasks.pop(0)

        return completed


class ReslottingRecommender:
    """Periodic re-slotting recommender. Recommends moves only — never moves automatically."""

    def __init__(
        self,
        engine: Any,
        audit_db: AuditDatabase | None = None,
        evaluation_interval_ticks: int = 250,
        max_recommendations: int = 5,
        max_congestion_proxy_limit: float = 0.75,
        enabled: bool = True,
    ) -> None:
        self.engine = engine
        self.audit_db = audit_db or AuditDatabase()
        self.evaluation_interval_ticks = evaluation_interval_ticks
        self.max_recommendations = max_recommendations
        self.max_congestion_proxy_limit = max_congestion_proxy_limit
        self.enabled = enabled

        self.recommendations: list[ReslotRecommendation] = []
        self.last_eval_tick: int = -999

    def step(self, current_tick: int) -> list[ReslotRecommendation]:
        """Periodically scores inventory layout and outputs recommendations."""
        if not self.enabled:
            return []

        if current_tick - self.last_eval_tick < self.evaluation_interval_ticks:
            return []

        self.last_eval_tick = current_tick
        new_recs = self.evaluate(current_tick)
        self.recommendations.extend(new_recs)
        return new_recs

    def evaluate(self, current_tick: int) -> list[ReslotRecommendation]:
        """Evaluates SKU popularity vs location distance and produces recommendations."""
        if not hasattr(self.engine, "skus") or not hasattr(self.engine, "bins"):
            return []

        station = self.engine.layout.stations[0] if getattr(self.engine.layout, "stations", []) else None
        if not station:
            return []

        st_pos = station.pos
        sku_map: dict[str, Sku] = {s.sku_id: s for s in self.engine.skus}
        bins: list[Bin] = self.engine.bins

        # High velocity SKUs (top popularity rank <= 100) placed far from station
        candidates: list[ReslotRecommendation] = []

        # Find empty or low velocity bins close to station
        bins_sorted_by_dist = sorted(bins, key=lambda b: b.cell.manhattan_distance(st_pos))
        prime_bins = [b for b in bins_sorted_by_dist[:20] if b.quantity <= 2 or (b.sku_id and sku_map.get(b.sku_id) and sku_map[b.sku_id].popularity_rank > 300)]

        for b in reversed(bins_sorted_by_dist):
            if len(candidates) >= self.max_recommendations:
                break
            if not b.sku_id:
                continue

            sku = sku_map.get(b.sku_id)
            if not sku or sku.popularity_rank > 80:
                continue

            curr_dist = b.cell.manhattan_distance(st_pos)
            if curr_dist <= 6:
                continue  # Already close

            for target_b in prime_bins:
                target_dist = target_b.cell.manhattan_distance(st_pos)
                dist_reduction = float(curr_dist - target_dist)
                if dist_reduction <= 2.0:
                    continue

                # Hard constraint check
                is_valid, reason = ManualOverrideValidator.validate_placement(sku, target_b)
                if not is_valid:
                    continue

                # Congestion guard: estimate aisle congestion proxy
                congestion_proxy = 0.45 + (0.05 * (target_b.cell.y % 4))
                if congestion_proxy > self.max_congestion_proxy_limit:
                    continue

                rec = ReslotRecommendation(
                    sku_id=sku.sku_id,
                    current_bin_id=b.bin_id,
                    recommended_bin_id=target_b.bin_id,
                    velocity_score=round(100.0 / sku.popularity_rank, 2),
                    travel_distance_reduction=dist_reduction,
                    congestion_proxy_delta=round(congestion_proxy - 0.40, 3),
                    status="RECOMMENDED",
                    reason=f"Popular SKU '{sku.name}' (rank {sku.popularity_rank}) moves {dist_reduction:.1f}m closer to station {station.station_id}",
                )
                candidates.append(rec)
                prime_bins.remove(target_b)
                break

        self.recommendations.extend(candidates)
        return candidates

    def approve_recommendation(
        self,
        recommendation_id: str,
        actor: str,
        role: str,
        current_tick: int,
    ) -> tuple[bool, str]:
        """Supervisor approves a re-slotting recommendation. Never moves automatically."""
        rec = next((r for r in self.recommendations if r.recommendation_id == recommendation_id), None)
        if not rec:
            return False, f"Recommendation '{recommendation_id}' not found."

        if role not in ("supervisor", "admin"):
            self.audit_db.record_entry(
                tick=current_tick,
                actor=actor,
                role=role,  # type: ignore
                action="approve_reslot",
                entity_type="reslot_recommendation",
                entity_id=recommendation_id,
                before_state=rec.model_dump(),
                after_state=rec.model_dump(),
                reason="Unauthorized reslot approval attempt",
                result="REJECTED",
                rejection_reason=f"Role '{role}' is not authorized to approve reslotting.",
            )
            return False, f"Permission denied for role '{role}'."

        rec.status = "APPROVED"

        self.audit_db.record_entry(
            tick=current_tick,
            actor=actor,
            role=role,  # type: ignore
            action="approve_reslot",
            entity_type="reslot_recommendation",
            entity_id=recommendation_id,
            before_state={"status": "RECOMMENDED"},
            after_state=rec.model_dump(),
            reason=f"Supervisor approved re-slot of SKU {rec.sku_id} from {rec.current_bin_id} to {rec.recommended_bin_id}",
            result="SUCCESS",
        )

        self.engine.emit_event(
            "reslotting.approved",
            {"recommendation_id": rec.recommendation_id, "sku_id": rec.sku_id, "approved_by": actor},
        )
        return True, f"Re-slotting approved for SKU '{rec.sku_id}'."
