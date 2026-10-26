"""Unit tests for scripts/policies/ruleset.py."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any, cast

from scripts.policies import ruleset

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "docs" / "policies" / "required-checks.md"
RULESET_PATH = ROOT / ".github" / "rulesets" / "homeric-main-baseline.json"


def _policy_text() -> str:
    return POLICY_PATH.read_text(encoding="utf-8")


def _approved() -> dict[str, Any]:
    return ruleset.approved_ruleset_policy(_policy_text())


def _tracked() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(RULESET_PATH.read_text(encoding="utf-8")))


def _merge_queue(document: dict[str, Any]) -> dict[str, Any]:
    rules = cast(list[dict[str, Any]], document["rules"])
    return next(r for r in rules if r["type"] == "merge_queue")


class ApprovedMergeQueueParameterTests(unittest.TestCase):
    """Exercise the tracked merge-queue policy source."""

    def test_tracked_ruleset_matches_the_approved_policy(self) -> None:
        self.assertEqual(
            _merge_queue(_tracked())["parameters"],
            _merge_queue(_approved())["parameters"],
        )

    def test_approved_policy_uses_the_merge_queue_parameters(self) -> None:
        approved = _merge_queue(_approved())["parameters"]
        self.assertEqual(
            approved,
            ruleset.approved_merge_queue_parameters(_policy_text()),
        )
        self.assertEqual(approved["merge_method"], "SQUASH")

    def test_tuning_the_policy_block_changes_the_approved_parameters(self) -> None:
        tuned = _policy_text().replace(
            '"max_entries_to_build": 10', '"max_entries_to_build": 7'
        )
        self.assertEqual(
            ruleset.approved_merge_queue_parameters(tuned)["max_entries_to_build"], 7
        )

    def test_policy_block_failure_paths(self) -> None:
        cases: tuple[tuple[str, str, str], ...] = (
            ("missing block", _policy_text().replace("```json", "```text"), "missing"),
            ("not json", "```json\n{oops}\n```", "not valid JSON"),
            ("not an object", "```json\n[1]\n```", "one JSON object"),
        )
        for name, text, literal in cases:
            with self.subTest(name=name):
                with self.assertRaises((ValueError, TypeError)) as caught:
                    ruleset.approved_merge_queue_parameters(text)
                self.assertIn(literal, str(caught.exception))


class EvaluateRulesetTests(unittest.TestCase):
    """Exercise exact comparison between the tracked and approved rulesets."""

    def test_matching_document_has_no_violation(self) -> None:
        self.assertEqual(
            ruleset.evaluate_ruleset(_tracked(), _approved(), "ruleset"), []
        )

    def test_drift_cases(self) -> None:
        approved = _approved()
        cases: tuple[tuple[str, Any, str], ...] = (
            ("wrong type", [], "Expected dict"),
            (
                "missing key",
                {k: v for k, v in approved.items() if k != "target"},
                "target",
            ),
            ("extra key", {**approved, "unexpected": True}, "unexpected keys"),
            (
                "value drift",
                {**copy.deepcopy(approved), "enforcement": "evaluate"},
                "enforcement",
            ),
        )
        for name, document, literal in cases:
            with self.subTest(name=name):
                errors = ruleset.evaluate_ruleset(document, approved, "ruleset")
                self.assertEqual(1, len(errors), errors)
                self.assertIn(literal, errors[0])

    def test_list_and_nested_paths_are_reported(self) -> None:
        approved = _approved()
        missing_key = copy.deepcopy(approved)
        rules = cast(list[dict[str, Any]], missing_key["rules"])
        rules[3]["parameters"].pop("allowed_merge_methods")
        self.assertIn(
            "ruleset.rules[3].parameters",
            ruleset.evaluate_ruleset(missing_key, approved, "ruleset")[0],
        )

        wrong_size = copy.deepcopy(approved)
        cast(list[dict[str, Any]], wrong_size["rules"])[3]["parameters"][
            "required_reviewers"
        ] = [1]
        self.assertIn(
            "Expected 0 entries",
            ruleset.evaluate_ruleset(wrong_size, approved, "ruleset")[0],
        )

    def test_messages_name_the_path_and_no_ticket(self) -> None:
        approved = _approved()
        document = copy.deepcopy(approved)
        cast(list[dict[str, Any]], document["rules"])[4]["parameters"][
            "max_entries_to_build"
        ] = 7
        errors = ruleset.evaluate_ruleset(document, approved, "ruleset")
        self.assertEqual(1, len(errors), errors)
        self.assertIn("ruleset.rules[4].parameters.max_entries_to_build", errors[0])
        self.assertIn("max_entries_to_build", errors[0])
        self.assertNotIn("issue #", errors[0])
