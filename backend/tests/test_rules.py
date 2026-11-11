"""Tests for declarative YAML rule engine, linting, hot reload, and test cases."""

from __future__ import annotations

from pathlib import Path

from robofleet.rules.engine import RuleEngine, evaluate_condition


def test_evaluate_condition_primitives() -> None:
    ctx = {"user": {"role": "admin", "score": 85}, "items": ["a", "b"]}

    assert evaluate_condition({"field": "user.role", "op": "==", "value": "admin"}, ctx) is True
    assert evaluate_condition({"field": "user.score", "op": ">=", "value": 80}, ctx) is True
    assert evaluate_condition({"field": "user.score", "op": "<", "value": 50}, ctx) is False
    assert evaluate_condition({"field": "items", "op": "contains", "value": "a"}, ctx) is True
    assert (
        evaluate_condition({"field": "user.role", "op": "in", "value": ["admin", "super"]}, ctx)
        is True
    )


def test_shipped_rules_lint_and_pass_tests() -> None:
    engine = RuleEngine("rules")
    assert len(engine.rules) >= 7

    ok, lint_errors = engine.lint()
    assert ok, f"Rule lint failed: {lint_errors}"

    passed, failed, failures = engine.test_all()
    assert failed == 0, f"Rule embedded test failures: {failures}"
    assert passed >= 14


def test_invalid_rule_rejected_without_disturbing_active_set(tmp_path: Path) -> None:
    # 1. Create a valid rule file
    r1 = tmp_path / "rule1.yaml"
    r1.write_text(
        """
id: valid_rule_1
description: A valid rule
scope: placement
effect: deny
when:
  field: x
  op: "=="
  value: 1
""",
        encoding="utf-8",
    )

    engine = RuleEngine(tmp_path)
    assert len(engine.rules) == 1
    assert "valid_rule_1" in engine.rules

    # 2. Add an invalid rule file with bad YAML syntax
    r2 = tmp_path / "rule2_bad.yaml"
    r2.write_text("id: bad: [unclosed yaml", encoding="utf-8")

    count, errors = engine.load_rules()
    assert len(errors) > 0
    # The active rule set still retains valid_rule_1!
    assert len(engine.rules) == 1
    assert "valid_rule_1" in engine.rules
