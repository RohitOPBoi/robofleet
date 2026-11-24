"""Declarative YAML Rule Engine for RoboFleet (CA-3).
Evaluates placement constraints, movement restrictions, alert rules, and command governance.
Zero eval: safe structured conditions evaluated against typed context.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

OPERATORS: dict[str, Callable[[Any, Any], Any]] = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "contains": lambda a, b: b in a,
}


def _resolve_field(context: dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    curr: Any = context
    for p in parts:
        if isinstance(curr, dict):
            curr = curr.get(p)
        elif hasattr(curr, p):
            curr = getattr(curr, p)
        else:
            return None
        if curr is None:
            return None
    return curr


def evaluate_condition(cond: dict[str, Any], context: dict[str, Any]) -> bool:
    """Safe evaluation of structured condition tree (all, any, not, field-op-value)."""
    if "all" in cond:
        return all(evaluate_condition(sub, context) for sub in cond["all"])
    if "any" in cond:
        return any(evaluate_condition(sub, context) for sub in cond["any"])
    if "not" in cond:
        return not evaluate_condition(cond["not"], context)

    field_path = cond.get("field")
    op_str = cond.get("op", "==")
    target_val = cond.get("value")

    if field_path is None or op_str not in OPERATORS:
        return False

    actual_val = _resolve_field(context, field_path)
    if actual_val is None and target_val is not None and op_str not in ("!=", "not_in"):
        return False

    try:
        return bool(OPERATORS[op_str](actual_val, target_val))
    except Exception:
        return False


class RuleTestCase(BaseModel):
    name: str
    context: dict[str, Any]
    expected_match: bool


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id: str
    description: str
    scope: Literal["placement", "movement", "alert", "command"]
    when: dict[str, Any]
    effect: Literal["deny", "warn", "require_human", "alert", "score_penalty"]
    severity: Literal["INFO", "WARN", "CRITICAL"] = "WARN"
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    version: str = "1.0.0"
    tests: list[RuleTestCase] = Field(
        default_factory=list, validation_alias=AliasChoices("tests", "test_cases")
    )

    def matches(self, context: dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        return evaluate_condition(self.when, context)


class RuleEngine:
    def __init__(self, rules_dir: Path | str = "rules") -> None:
        self.rules_dir = Path(rules_dir)
        self.rules: dict[str, Rule] = {}
        self.load_rules()

    def load_rules(self) -> tuple[int, list[str]]:
        errors: list[str] = []
        if not self.rules_dir.exists():
            return 0, [f"Rules directory '{self.rules_dir}' does not exist."]

        new_rules: dict[str, Rule] = {}
        for yml_file in self.rules_dir.glob("*.yaml"):
            try:
                content = yaml.safe_load(yml_file.read_text(encoding="utf-8"))
                if not content:
                    continue
                # Support single rule or list of rules per file
                items = content if isinstance(content, list) else [content]
                for item in items:
                    rule = Rule.model_validate(item)
                    new_rules[rule.id] = rule
            except Exception as e:
                errors.append(f"Error in {yml_file.name}: {e}")

        # Atomic reload: only replace active rules if no fatal read failure
        if not errors or not self.rules:
            self.rules = new_rules

        return len(self.rules), errors

    def list_rules(self) -> list[Rule]:
        return list(self.rules.values())

    def evaluate(self, scope: str, context: dict[str, Any]) -> list[Rule]:
        matched: list[Rule] = []
        for rule in self.rules.values():
            if rule.scope == scope and rule.matches(context):
                matched.append(rule)
        return matched

    def lint(self) -> tuple[bool, list[str]]:
        reports: list[str] = []
        is_ok = True
        for rule in self.rules.values():
            # Check condition syntax
            if not rule.when:
                reports.append(f"Rule {rule.id}: Empty condition 'when'.")
                is_ok = False
        return is_ok, reports

    def test_all(self) -> tuple[int, int, list[str]]:
        passed = 0
        failed = 0
        failures: list[str] = []
        for rule in self.rules.values():
            for tc in rule.tests:
                res = rule.matches(tc.context)
                if res == tc.expected_match:
                    passed += 1
                else:
                    failed += 1
                    failures.append(
                        f"Rule '{rule.id}' test '{tc.name}' FAILED: expected {tc.expected_match}, got {res}"
                    )
        return passed, failed, failures
