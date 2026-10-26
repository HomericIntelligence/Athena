"""This module defines the approved tracked branch ruleset policy."""

from __future__ import annotations

import json
import re
from typing import Any, cast

APPROVED_RULESET_NAME = "homeric-main-baseline"
APPROVED_RULESET_TARGET = "branch"
APPROVED_RULESET_ENFORCEMENT = "active"
APPROVED_RULESET_BYPASS_ACTORS: list[object] = []
APPROVED_RULESET_CONDITIONS: dict[str, object] = {
    "ref_name": {
        "include": ["~DEFAULT_BRANCH"],
        "exclude": [],
    }
}
APPROVED_PULL_REQUEST_PARAMETERS: dict[str, object] = {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews_on_push": False,
    "required_reviewers": [],
    "dismissal_restriction": {"enabled": False, "allowed_actors": []},
    "require_code_owner_review": False,
    "require_last_push_approval": False,
    "required_review_thread_resolution": True,
    "allowed_merge_methods": ["squash"],
    "require_extra_approval_for_unattributed_changes": True,
}
REQUIRED_CHECK_CONTEXT = "required-checks-gate"
APPROVED_REQUIRED_STATUS_CHECKS_PARAMETERS: dict[str, object] = {
    "strict_required_status_checks_policy": False,
    "do_not_enforce_on_create": False,
    "required_status_checks": [
        {
            "context": REQUIRED_CHECK_CONTEXT,
            "integration_id": 15368,
        }
    ],
}
MERGE_QUEUE_PARAMETER_BLOCK = re.compile(
    r"^```json\n(?P<parameters>.+?)\n```$", re.MULTILINE | re.DOTALL
)


def approved_merge_queue_parameters(policy_text: str) -> dict[str, Any]:
    """Read the approved merge-queue parameters from the tracked policy document.

    The merge-queue parameters are a tuning decision that a maintainer records in
    `docs/policies/required-checks.md`. That document is the only approved source
    for these values, so a ruleset change and its policy text stay in one place.
    """
    match = MERGE_QUEUE_PARAMETER_BLOCK.search(policy_text)
    if match is None:
        raise ValueError(
            "The merge-queue policy is missing. The tracked policy document must "
            "contain one JSON object in a fenced json block."
        )
    try:
        parameters = json.loads(match.group("parameters"))
    except ValueError as error:
        raise ValueError(
            "The merge-queue policy is not valid JSON.\n"
            f"The operation returned this diagnostic.\n{error}"
        ) from error
    if not isinstance(parameters, dict):
        raise TypeError(
            "The merge-queue policy must be one JSON object of parameter names "
            "and values."
        )
    return cast(dict[str, Any], parameters)


def approved_ruleset_policy(policy_text: str) -> dict[str, Any]:
    """Return the approved tracked branch ruleset, including the queue parameters."""
    return {
        "name": APPROVED_RULESET_NAME,
        "target": APPROVED_RULESET_TARGET,
        "enforcement": APPROVED_RULESET_ENFORCEMENT,
        "bypass_actors": APPROVED_RULESET_BYPASS_ACTORS,
        "conditions": APPROVED_RULESET_CONDITIONS,
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "required_linear_history"},
            {
                "type": "pull_request",
                "parameters": APPROVED_PULL_REQUEST_PARAMETERS,
            },
            {
                "type": "merge_queue",
                "parameters": approved_merge_queue_parameters(policy_text),
            },
            {
                "type": "required_status_checks",
                "parameters": APPROVED_REQUIRED_STATUS_CHECKS_PARAMETERS,
            },
            {"type": "required_signatures"},
        ],
    }


def _json_type_name(value: object) -> str:
    """Return a stable JSON type name for validator diagnostics."""
    return "null" if value is None else type(value).__name__


def evaluate_ruleset(document: object, expected: object, path: str) -> list[str]:
    """Require one exact JSON value at the given path."""
    if type(document) is not type(expected):
        return [
            (
                f"The ruleset must match the approved policy at {path}. Expected "
                f"{_json_type_name(expected)} but found {_json_type_name(document)}."
            )
        ]

    if isinstance(expected, dict):
        actual_dict = cast(dict[str, object], document)
        expected_dict = cast(dict[str, object], expected)
        actual_keys = set(actual_dict)
        expected_keys = set(expected_dict)
        if actual_keys != expected_keys:
            missing = sorted(expected_keys - actual_keys)
            extra = sorted(actual_keys - expected_keys)
            parts: list[str] = []
            if missing:
                parts.append("missing keys: " + ", ".join(missing))
            if extra:
                parts.append("unexpected keys: " + ", ".join(extra))
            return [
                f"The ruleset must match the approved policy at {path}. "
                + "; ".join(parts)
                + "."
            ]

        for key in expected_dict:
            nested = evaluate_ruleset(
                actual_dict[key], expected_dict[key], f"{path}.{key}"
            )
            if nested:
                return nested
        return []

    if isinstance(expected, list):
        actual_list = cast(list[object], document)
        expected_list = cast(list[object], expected)
        if len(actual_list) != len(expected_list):
            return [
                (
                    f"The ruleset must match the approved policy at {path}. Expected "
                    f"{len(expected_list)} entries but found {len(actual_list)}."
                )
            ]
        for index, (actual_item, expected_item) in enumerate(
            zip(actual_list, expected_list)
        ):
            nested = evaluate_ruleset(actual_item, expected_item, f"{path}[{index}]")
            if nested:
                return nested
        return []

    if document != expected:
        return [
            (
                f"The ruleset must match the approved policy at {path}. Expected "
                f"{expected!r} but found {document!r}."
            )
        ]
    return []
