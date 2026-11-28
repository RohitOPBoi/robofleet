"""Structured JSON Extraction and Schema Validation for LLM Decisions.

Validates both cloud AI Mode and Local LLM Mode responses against RoboFleet's
typed command contracts, rejecting unknown actions, fabricated entities, and
malformed payloads without crashing simulation execution.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from robofleet.contracts.brain import (
    COMMAND_TYPE_MODELS,
    DecisionProposal,
    SituationBrief,
    validate_brain_command,
)
from robofleet.contracts.common import Coordinate

_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_CODE_INJECTION_PATTERNS = (
    "__import__",
    "eval(",
    "exec(",
    "subprocess",
    "os.system",
    "drop table",
    "select * from",
    "<script",
)

# Normalized alias mapping from conceptual action verbs to canonical RoboFleet command types
_ACTION_ALIAS_MAP: dict[str, str] = {
    "yield": "yield_robot",
    "yield_robot": "yield_robot",
    "reroute": "reroute_robot",
    "reroute_robot": "reroute_robot",
    "charge": "send_to_charge",
    "send_to_charge": "send_to_charge",
    "assign": "assign_task",
    "assign_task": "assign_task",
    "reprioritise": "reprioritise_order",
    "reprioritise_order": "reprioritise_order",
    "reprioritize_order": "reprioritise_order",
    "batch_orders": "batch_orders",
    "hold_zone": "hold_zone",
    "release_zone": "release_zone",
    "set_station_policy": "set_station_policy",
    "set_strategy_params": "set_strategy_params",
    "reassign": "reassign_task",
    "reassign_task": "reassign_task",
    "substitute_item": "substitute_item",
    "reroute_station": "reroute_station",
    "clear_fault": "clear_fault",
    "escalate": "escalate_to_human",
    "escalate_to_human": "escalate_to_human",
    "no_action": "no_action",
    "none": "no_action",
    "wait": "no_action",
}


@dataclass
class ValidatedLLMOutput:
    """Result of strict LLM payload parsing and command validation."""

    ok: bool
    commands: list[dict[str, Any]] = field(default_factory=list)
    rejected_commands: list[dict[str, Any]] = field(default_factory=list)
    proposals: list[DecisionProposal] = field(default_factory=list)
    situation_summary: str = ""
    rationale: str = ""
    traffic_plan: dict[str, Any] = field(default_factory=dict)
    unresolved_risks: list[str] = field(default_factory=list)
    requires_human_approval: bool = False
    confidence: float = 1.0
    error: str = ""


def extract_json_object(raw_text: str) -> dict[str, Any] | None:
    """Safely extract a JSON object from model text (handling think tags and markdown fences)."""
    if not raw_text or not isinstance(raw_text, str):
        return None
    cleaned = _THINK_TAG_RE.sub("", raw_text).strip()
    if not cleaned:
        return None

    # 1. Direct JSON parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 2. Markdown code block extraction
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence_match:
        try:
            parsed = json.loads(fence_match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 3. Balanced outermost brace extraction
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx > start_idx:
        candidate = cleaned[start_idx : end_idx + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def _contains_suspicious_code(value: Any) -> bool:
    serialized = json.dumps(value, default=str).lower()
    return any(pat in serialized for pat in _CODE_INJECTION_PATTERNS)


def _normalize_action_dict(raw_item: dict[str, Any], tick: int) -> dict[str, Any]:
    """Normalize shorthand 'actions' items or canonical 'commands' items into RoboFleet schema."""
    cmd = dict(raw_item)
    if "command_type" not in cmd and "action" in cmd:
        raw_action = str(cmd.get("action", "")).strip().lower()
        canonical = _ACTION_ALIAS_MAP.get(raw_action, raw_action)
        cmd["command_type"] = canonical
    elif isinstance(cmd.get("command_type"), str):
        raw_ct = cmd["command_type"].strip().lower()
        cmd["command_type"] = _ACTION_ALIAS_MAP.get(raw_ct, raw_ct)

    ctype = cmd.get("command_type", "")
    # Map generic 'target' field if provided by prompt shorthand
    if "target" in cmd and cmd["target"] is not None:
        tgt = cmd.pop("target")
        if ctype == "yield_robot" and "yield_cell" not in cmd:
            if isinstance(tgt, dict) and "x" in tgt and "y" in tgt:
                cmd["yield_cell"] = tgt
        elif ctype == "send_to_charge" and "charger_id" not in cmd and isinstance(tgt, str):
            cmd["charger_id"] = tgt
        elif ctype in ("hold_zone", "release_zone") and "zone_id" not in cmd and isinstance(tgt, str):
            cmd["zone_id"] = tgt
        elif ctype in ("set_station_policy", "reroute_station") and "station_id" not in cmd and isinstance(tgt, str):
            cmd["station_id"] = tgt
        elif ctype == "reprioritise_order" and "order_id" not in cmd and isinstance(tgt, str):
            cmd["order_id"] = tgt
        elif ctype == "assign_task":
            if isinstance(tgt, dict) and "x" in tgt and "y" in tgt and "destination" not in cmd:
                cmd["destination"] = tgt
            elif isinstance(tgt, str) and "order_id" not in cmd:
                cmd["order_id"] = tgt

    if "issued_tick" not in cmd:
        cmd["issued_tick"] = tick
    return cmd


def _collect_valid_entities(brief: SituationBrief) -> tuple[set[str], set[str], set[str], set[str], set[str]]:
    valid_robots = {r.robot_id for r in brief.critical_robots} | {
        r.robot_id for r in brief.robots_overview
    }
    for dl in brief.deadlocks_detected:
        valid_robots.update(dl.robots_involved)
    valid_orders = {o.order_id for o in brief.at_risk_orders}
    valid_stations = {s.station_id for s in brief.station_queues}
    valid_zones = set(brief.available_zones) | set(brief.held_zone_ids)
    valid_chargers = set(brief.available_chargers)
    return valid_robots, valid_orders, valid_stations, valid_zones, valid_chargers


def _validate_entity_references(
    cmd_dict: dict[str, Any],
    brief: SituationBrief,
) -> str | None:
    """Return error reason if a command references non-existent entities present in brief sets."""
    valid_robots, valid_orders, valid_stations, valid_zones, valid_chargers = _collect_valid_entities(
        brief
    )

    rid = cmd_dict.get("robot_id")
    if rid and valid_robots and rid not in valid_robots:
        return f"Unknown robot_id '{rid}' not present in current fleet state"

    target_rid = cmd_dict.get("target_robot_id")
    if target_rid and valid_robots and target_rid not in valid_robots:
        return f"Unknown target_robot_id '{target_rid}' not present in current fleet state"

    prio_rid = cmd_dict.get("priority_robot_id")
    if prio_rid and valid_robots and prio_rid not in valid_robots:
        return f"Unknown priority_robot_id '{prio_rid}' not present in current fleet state"

    oid = cmd_dict.get("order_id")
    if (
        oid
        and valid_orders
        and oid not in valid_orders
        and str(oid).upper().startswith("ORD-")
        and len(brief.at_risk_orders) > 0
        and brief.kpis.at_risk_count <= len(brief.at_risk_orders)
    ):
        return f"Unknown order_id '{oid}' not in active SituationBrief"

    sid = cmd_dict.get("station_id")
    if sid and valid_stations and sid not in valid_stations:
        return f"Unknown station_id '{sid}' not present in warehouse layout"

    cid = cmd_dict.get("charger_id")
    if cid and valid_chargers and cid not in valid_chargers:
        return f"Unknown charger_id '{cid}' not present in warehouse layout"

    zid = cmd_dict.get("zone_id")
    if zid and valid_zones and zid not in valid_zones:
        return f"Unknown zone_id '{zid}' not present in warehouse layout"

    # Reject malformed negative coordinates
    for coord_key in ("yield_cell", "destination"):
        coord_val = cmd_dict.get(coord_key)
        if isinstance(coord_val, dict):
            try:
                c = Coordinate.model_validate(coord_val)
                if c.x < 0 or c.y < 0:
                    return f"Invalid negative coordinate for {coord_key}"
            except ValidationError as exc:
                return f"Invalid coordinate for {coord_key}: {exc}"

    return None


def parse_and_validate_llm_response(
    raw_text: str,
    brief: SituationBrief,
) -> ValidatedLLMOutput:
    """Strictly parse and validate structured JSON output from Cloud AI or Local Ollama."""
    data = extract_json_object(raw_text)
    if data is None:
        return ValidatedLLMOutput(ok=False, error="Malformed or missing JSON object in model output")

    if _contains_suspicious_code(data):
        return ValidatedLLMOutput(
            ok=False,
            error="Rejected output containing disallowed code/script patterns",
        )

    raw_actions = data.get("commands")
    if raw_actions is None:
        raw_actions = data.get("actions")

    if raw_actions is None:
        return ValidatedLLMOutput(
            ok=False,
            error="Structured response missing 'actions' or 'commands' array",
        )
    if not isinstance(raw_actions, list):
        return ValidatedLLMOutput(
            ok=False,
            error="Field 'actions'/'commands' must be a JSON array",
        )

    valid_commands: list[dict[str, Any]] = []
    rejected_commands: list[dict[str, Any]] = []
    seen_fingerprints: set[str] = set()

    for item in raw_actions:
        if not isinstance(item, dict):
            rejected_commands.append({"raw": item, "rejection_reason": "Command item is not a JSON object"})
            continue

        normalized = _normalize_action_dict(item, brief.tick)
        ctype = normalized.get("command_type")
        if not isinstance(ctype, str) or ctype not in COMMAND_TYPE_MODELS:
            rejected_commands.append(
                {
                    "raw": item,
                    "rejection_reason": f"Unsupported command_type '{ctype}'",
                }
            )
            continue

        try:
            validated_model = validate_brain_command(normalized)
            cmd_dump = validated_model.model_dump()
        except (ValidationError, ValueError) as exc:
            rejected_commands.append(
                {
                    "raw": item,
                    "rejection_reason": f"Schema validation error: {exc}",
                }
            )
            continue

        entity_err = _validate_entity_references(cmd_dump, brief)
        if entity_err:
            rejected_commands.append(
                {
                    "raw": cmd_dump,
                    "rejection_reason": entity_err,
                }
            )
            continue

        # Duplicate command guard within same decision
        fp_copy = {k: v for k, v in cmd_dump.items() if k not in ("command_id", "issued_tick", "reason", "expected_effect")}
        fp = json.dumps(fp_copy, sort_keys=True)
        if fp in seen_fingerprints:
            rejected_commands.append(
                {
                    "raw": cmd_dump,
                    "rejection_reason": "Duplicate command within single decision response",
                }
            )
            continue
        seen_fingerprints.add(fp)
        valid_commands.append(cmd_dump)

    # Empty array is only acceptable if invalid commands didn't wipe everything
    if not valid_commands and rejected_commands:
        return ValidatedLLMOutput(
            ok=False,
            rejected_commands=rejected_commands,
            error="All proposed actions failed schema or entity validation",
        )

    if not valid_commands and len(raw_actions) == 0:
        # Explicitly convert empty list with valid situation summary into safe no_action if desired, or flag empty
        valid_commands.append(
            {
                "command_type": "no_action",
                "issued_tick": brief.tick,
                "reason": str(data.get("situation_summary") or "Nominal operation"),
                "expected_effect": "Maintain current trajectories",
            }
        )

    # Parse optional proposals metadata safely
    validated_proposals: list[DecisionProposal] = []
    raw_proposals = data.get("proposals", [])
    if isinstance(raw_proposals, list):
        for p in raw_proposals:
            if isinstance(p, dict):
                try:
                    spec = str(p.get("specialist", "orchestrator")).lower()
                    if spec not in ("planner", "traffic", "exceptions", "explainer", "human", "orchestrator"):
                        spec = "orchestrator"
                    validated_proposals.append(
                        DecisionProposal(
                            specialist=spec,  # type: ignore[arg-type]
                            action=str(p.get("action", "coordinate")),
                            command=p.get("command", {}) if isinstance(p.get("command"), dict) else {},
                            confidence=float(max(0.0, min(1.0, float(p.get("confidence", 0.9))))),
                            rationale=str(p.get("rationale", ""))[:240],
                        )
                    )
                except Exception:
                    continue

    # Synthesize proposals from valid commands if model returned compact actions list only
    if not validated_proposals:
        for cmd in valid_commands:
            validated_proposals.append(
                DecisionProposal(
                    specialist="orchestrator",
                    action=str(cmd.get("command_type", "no_action")),
                    command=cmd,
                    confidence=float(max(0.0, min(1.0, float(data.get("confidence", 0.9))))),
                    rationale=str(cmd.get("reason") or data.get("situation_summary") or "")[:240],
                )
            )

    traffic_plan = data.get("traffic_plan", {})
    if not isinstance(traffic_plan, dict):
        traffic_plan = {}

    unresolved_risks = data.get("unresolved_risks", [])
    if not isinstance(unresolved_risks, list):
        unresolved_risks = []
    unresolved_risks = [str(r) for r in unresolved_risks[:8]]

    summary = str(data.get("situation_summary") or data.get("expected_result") or "").strip()
    rationale = str(data.get("rationale") or summary or "Coordinated fleet decision").strip()
    try:
        conf_val = float(data.get("confidence", 0.9))
    except (TypeError, ValueError):
        conf_val = 0.9
    conf_val = max(0.0, min(1.0, conf_val))

    return ValidatedLLMOutput(
        ok=True,
        commands=valid_commands,
        rejected_commands=rejected_commands,
        proposals=validated_proposals,
        situation_summary=summary,
        rationale=rationale,
        traffic_plan=traffic_plan,
        unresolved_risks=unresolved_risks,
        requires_human_approval=bool(data.get("requires_human_approval", False)),
        confidence=conf_val,
    )
