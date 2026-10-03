"""This module defines the tracked main-ruleset policy."""

from __future__ import annotations

from collections.abc import Mapping

REQUIRED_CHECK_CONTEXT = "required-checks-gate"
REQUIRED_STATUS_CHECKS = [{"context": REQUIRED_CHECK_CONTEXT, "integration_id": 15368}]
REQUIRED_MERGE_METHOD = "SQUASH"


def _merge_queue_rules(rules: list[object]) -> list[dict[str, object]]:
    return [
        rule
        for rule in rules
        if isinstance(rule, dict) and rule.get("type") == "merge_queue"
    ]


def evaluate_ruleset(document: object) -> list[str]:
    """Return tracked main-ruleset violations."""
    if not isinstance(document, Mapping):
        return ["The ruleset must be a JSON object."]
    rules = document.get("rules")
    if not isinstance(rules, list):
        return ["The ruleset must contain a rules list."]
    status_check_rules = [
        rule
        for rule in rules
        if isinstance(rule, dict) and rule.get("type") == "required_status_checks"
    ]
    errors: list[str] = []
    if len(status_check_rules) != 1:
        return ["The ruleset must contain exactly one status-check policy."]
    status_checks = status_check_rules[0]
    parameters = status_checks.get("parameters")
    if not isinstance(parameters, dict):
        return ["The required status-check policy is invalid."]
    if parameters.get("strict_required_status_checks_policy") is not False:
        errors.append(
            "The ruleset must not require up-to-date branches. The merge queue manages freshness."
        )
    if parameters.get("required_status_checks") != REQUIRED_STATUS_CHECKS:
        errors.append(
            "The ruleset must require only 'required-checks-gate' from the GitHub Actions integration."
        )
    pull_request = next(
        (
            rule
            for rule in rules
            if isinstance(rule, dict) and rule.get("type") == "pull_request"
        ),
        None,
    )
    if not isinstance(pull_request, dict) or not isinstance(
        pull_request.get("parameters"), dict
    ):
        errors.append("The pull-request policy is missing.")
    elif pull_request["parameters"].get("allowed_merge_methods") != ["squash"]:
        errors.append("Pull requests must merge by squash only.")
    merge_queues = _merge_queue_rules(rules)
    if not merge_queues:
        errors.append("The merge queue policy is missing.")
        return errors
    if len(merge_queues) != 1:
        errors.append("The merge queue policy must appear exactly once.")
        return errors
    merge_queue = merge_queues[0]
    queue_parameters = merge_queue.get("parameters")
    if not isinstance(queue_parameters, dict):
        errors.append("The merge queue policy must include a parameters object.")
        return errors
    if queue_parameters.get("merge_method") != REQUIRED_MERGE_METHOD:
        errors.append("The merge queue merge method must be SQUASH.")
    return errors
