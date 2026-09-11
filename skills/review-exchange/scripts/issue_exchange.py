#!/usr/bin/env python3
"""Prepare and verify bounded issue-plan review exchanges."""

from __future__ import annotations

import copy
import importlib.util
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import review_exchange

if TYPE_CHECKING or __package__ not in {None, ""}:
    from skills._cli import argument_parser
else:
    _cli_path = Path(__file__).resolve().parents[2] / "_cli.py"
    _cli_spec = importlib.util.spec_from_file_location(
        "athena_installed_cli", _cli_path
    )
    if _cli_spec is None or _cli_spec.loader is None:
        raise RuntimeError(
            f"The installed Athena CLI helper is unavailable: '{_cli_path}'."
        )
    _cli = importlib.util.module_from_spec(_cli_spec)
    _cli_spec.loader.exec_module(_cli)
    argument_parser = _cli.argument_parser

SNAPSHOT_SCHEMA_ID = "athena.issue-exchange.snapshot"
INSPECT_SCHEMA_ID = "athena.issue-exchange.inspect-result"
PREPARE_SCHEMA_ID = "athena.issue-exchange.prepare-result"
PUBLICATION_SCHEMA_ID = "athena.issue-exchange.publication-result"
FINALIZE_SCHEMA_ID = "athena.issue-exchange.finalize-result"
SCHEMA_VERSION = 1

PLAN_MARKER = "<!-- HomericIntelligence:plan-issue -->"
REVIEW_MARKER = "<!-- HomericIntelligence:issue-review -->"
PLAN_MARKERS = (
    PLAN_MARKER,
    "<!-- hephaestus-plan:canonical -->",
    "<!-- athena:plan-issue -->",
)
REVIEW_MARKERS = (
    REVIEW_MARKER,
    "<!-- hephaestus-plan-review:canonical -->",
    "<!-- athena:issue-review -->",
)
FINALIZE_NAMESPACE_PATTERN = re.compile(
    r"<!-- (?:HomericIntelligence|athena):finalize-plan(?=\s|-->)"
)
FINALIZE_PATTERN = re.compile(
    r"<!-- (?:HomericIntelligence|athena):finalize-plan "
    r"R=([0-9a-f]{64}) P=([0-9a-f]{64}) V=([0-9a-f]{64}) "
    r"F=([0-9a-f]{64}) -->"
)
REVIEWED_PLAN_PREFIX = "<!-- HomericIntelligence:reviewed-plan:v1 "
REVIEWED_PLAN_PATTERN = re.compile(
    r"<!-- HomericIntelligence:reviewed-plan:v1 "
    r"token=([0-9a-f]{64}) -->"
)
HEX_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
TARGET_KINDS = frozenset(
    {"path", "module", "interface", "workflow", "dependency", "migration", "command"}
)

ProtocolError = review_exchange.ProtocolError
OperationalError = review_exchange.OperationalError


def _object(value: object, name: str, fields: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtocolError(f"{name} must be an object.")
    actual = frozenset(value)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if unknown:
            details.append(f"unknown {', '.join(unknown)}")
        raise ProtocolError(f"{name} has invalid fields: {'; '.join(details)}.")
    return cast(dict[str, Any], value)


def _string(value: object, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ProtocolError(f"{name} must be text.")
    return value


def _integer(value: object, name: str) -> int:
    if type(value) is not int or value < 1:
        raise ProtocolError(f"{name} must be a positive integer.")
    return value


def _boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ProtocolError(f"{name} must be a Boolean.")
    return value


def _nullable_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _string(value, name)


def _digest(value: object, name: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or HEX_DIGEST.fullmatch(value) is None:
        raise ProtocolError(f"{name} must be a lowercase SHA-256 digest.")
    return value


def _actor(value: object, name: str) -> dict[str, str]:
    actor = _object(value, name, frozenset({"id", "login"}))
    return {
        "id": _string(actor["id"], f"{name}.id"),
        "login": _string(actor["login"], f"{name}.login", allow_empty=True),
    }


def _comment_author(value: object, name: str) -> dict[str, Any]:
    author = _object(value, name, frozenset({"id", "login", "is_authority"}))
    return {
        "id": _string(author["id"], f"{name}.id"),
        "login": _string(author["login"], f"{name}.login", allow_empty=True),
        "is_authority": _boolean(author["is_authority"], f"{name}.is_authority"),
    }


def _snapshot(value: object) -> dict[str, Any]:
    snapshot = _object(
        value,
        "issue snapshot",
        frozenset(
            {
                "schema_id",
                "schema_version",
                "target",
                "actor",
                "issue",
                "comments",
                "comments_complete",
            }
        ),
    )
    if snapshot["schema_id"] != SNAPSHOT_SCHEMA_ID:
        raise ProtocolError("The issue snapshot schema identifier is not supported.")
    if (
        snapshot["schema_version"] != SCHEMA_VERSION
        or type(snapshot["schema_version"]) is not int
    ):
        raise ProtocolError("The issue snapshot schema version is not supported.")
    target_value = _object(
        snapshot["target"],
        "issue target",
        frozenset({"provider", "host", "repository", "issue_id", "number", "url"}),
    )
    provider = _string(target_value["provider"], "issue target.provider")
    if provider not in review_exchange.PROVIDER_BODY_LIMITS:
        raise ProtocolError("The issue target provider is not supported.")
    target = {
        "provider": provider,
        "host": _string(target_value["host"], "issue target.host"),
        "repository": _string(target_value["repository"], "issue target.repository"),
        "issue_id": _string(target_value["issue_id"], "issue target.issue_id"),
        "number": _integer(target_value["number"], "issue target.number"),
        "url": _string(target_value["url"], "issue target.url"),
    }
    issue_value = _object(
        snapshot["issue"],
        "issue",
        frozenset({"state", "title", "body", "acceptance_criteria"}),
    )
    state = _string(issue_value["state"], "issue.state")
    if state not in {"open", "closed"}:
        raise ProtocolError("The issue state is not supported.")
    criteria_value = issue_value["acceptance_criteria"]
    if not isinstance(criteria_value, list):
        raise ProtocolError("Issue acceptance criteria must be a list.")
    criteria: list[dict[str, str]] = []
    for index, raw in enumerate(criteria_value):
        criterion = _object(
            raw,
            f"acceptance criteria[{index}]",
            frozenset({"id", "text", "source"}),
        )
        criteria.append(
            {
                "id": _string(criterion["id"], f"acceptance criteria[{index}].id"),
                "text": _string(
                    criterion["text"], f"acceptance criteria[{index}].text"
                ),
                "source": _string(
                    criterion["source"], f"acceptance criteria[{index}].source"
                ),
            }
        )
    criterion_ids = [criterion["id"] for criterion in criteria]
    if len(criterion_ids) != len(set(criterion_ids)):
        raise ProtocolError("Issue acceptance criteria contain a duplicate ID.")
    comments_value = snapshot["comments"]
    if not isinstance(comments_value, list):
        raise ProtocolError("Issue comments must be a list.")
    comments: list[dict[str, Any]] = []
    for index, raw in enumerate(comments_value):
        comment = _object(
            raw,
            f"issue comments[{index}]",
            frozenset({"id", "url", "author", "body"}),
        )
        comments.append(
            {
                "id": _string(comment["id"], f"issue comments[{index}].id"),
                "url": _string(comment["url"], f"issue comments[{index}].url"),
                "author": _comment_author(
                    comment["author"], f"issue comments[{index}].author"
                ),
                "body": _string(
                    comment["body"], f"issue comments[{index}].body", allow_empty=True
                ),
            }
        )
    comment_ids = [comment["id"] for comment in comments]
    if len(comment_ids) != len(set(comment_ids)):
        raise ProtocolError("Issue comments contain a duplicate ID.")
    if not _boolean(snapshot["comments_complete"], "issue comments completeness"):
        raise ProtocolError("The issue comment collection is not complete.")
    return {
        "schema_id": SNAPSHOT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "target": target,
        "actor": _actor(snapshot["actor"], "issue actor"),
        "issue": {
            "state": state,
            "title": _string(issue_value["title"], "issue.title", allow_empty=True),
            "body": _string(issue_value["body"], "issue.body", allow_empty=True),
            "acceptance_criteria": criteria,
        },
        "comments": comments,
        "comments_complete": True,
    }


def _core_target(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    target = snapshot["target"]
    return {
        "provider": target["provider"],
        "repository": target["repository"],
        "number": target["number"],
        "url": target["url"],
    }


def _requirements_sha256(snapshot: Mapping[str, Any]) -> str:
    return review_exchange.sha256_json(
        {
            "schema_id": "athena.issue-exchange.requirements",
            "schema_version": SCHEMA_VERSION,
            "target": snapshot["target"],
            "title": snapshot["issue"]["title"],
            "body": snapshot["issue"]["body"],
            "acceptance_criteria": snapshot["issue"]["acceptance_criteria"],
        }
    )


def _body_sha256(body: str) -> str:
    return review_exchange.sha256_text(body)


def _diagnostic(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _starts_finalize_namespace(line: str) -> bool:
    indentation = len(line) - len(line.lstrip(" "))
    return bool(
        indentation <= 3
        and FINALIZE_NAMESPACE_PATTERN.match(line[indentation:]) is not None
    )


def _finalized_marker(body: str) -> tuple[str, dict[str, str] | None]:
    """Classify and parse one finalized marker."""
    matches: list[tuple[int, int, re.Match[str]]] = []
    malformed = False
    for start, end, line in review_exchange.top_level_markdown_lines(body):
        if not _starts_finalize_namespace(line):
            continue
        match = FINALIZE_PATTERN.fullmatch(line)
        if match is None:
            malformed = True
        else:
            matches.append((start, end, match))
    if malformed or len(matches) > 1:
        return "invalid", None
    if not matches:
        return "absent", None
    start, end, match = matches[0]
    marker = match.group(0)
    expected = match.group(4)
    template_marker = marker[: marker.rfind("F=")] + "F=<F> -->"
    template = body[:start] + template_marker + body[end:]
    if review_exchange.sha256_text(template) != expected:
        return "invalid", None
    return (
        "valid",
        {
            "R": match.group(1),
            "P": match.group(2),
            "V": match.group(3),
            "F": match.group(4),
        },
    )


def _finalized_status(body: str) -> str:
    """Classify a finalized marker as absent, valid, or invalid."""
    return _finalized_marker(body)[0]


def _role_comments(
    snapshot: Mapping[str, Any], markers: Sequence[str]
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    marker_set = frozenset(markers)
    for comment in snapshot["comments"]:
        for _start, _end, line in review_exchange.top_level_markdown_lines(
            comment["body"]
        ):
            if line in marker_set:
                matches.append(comment)
    return matches


def _reviewed_plan_token(body: str) -> str:
    """Return the one exact plan-source token in a review artifact."""
    matches: list[str] = []
    malformed = False
    for _start, _end, line in review_exchange.top_level_markdown_lines(body):
        if not line.startswith(REVIEWED_PLAN_PREFIX):
            continue
        match = REVIEWED_PLAN_PATTERN.fullmatch(line)
        if match is None:
            malformed = True
        else:
            matches.append(match.group(1))
    if malformed or len(matches) != 1:
        raise ProtocolError(
            "The review must contain one exact reviewed-plan source marker."
        )
    return matches[0]


def _source_token_from_summary(summary: Mapping[str, Any]) -> str:
    return review_exchange.sha256_json(
        {"comment_id": summary["id"], "body_sha256": summary["body_sha256"]}
    )


def _review_visible(content: object, plan: Mapping[str, Any]) -> str:
    visible = _visible(REVIEW_MARKER, content)
    return (
        f"{visible}\n\n{REVIEWED_PLAN_PREFIX}token={_source_token(plan)['token']} -->"
    )


def _artifact_summary(comment: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if comment is None:
        return None
    return {
        "id": comment["id"],
        "author_id": comment["author"]["id"],
        "body_sha256": _body_sha256(comment["body"]),
    }


def _precondition_sha256(
    *,
    target: Mapping[str, Any],
    actor_id: str,
    requirements_sha256: str,
    plan: Mapping[str, Any] | None,
    review: Mapping[str, Any] | None,
    authority_receipt: Mapping[str, str] | None,
) -> str:
    return review_exchange.sha256_json(
        {
            "schema_id": "athena.issue-exchange.precondition",
            "schema_version": SCHEMA_VERSION,
            "target": target,
            "actor_id": actor_id,
            "requirements_sha256": requirements_sha256,
            "plan": plan,
            "review": review,
            "authority_receipt": authority_receipt,
        }
    )


def _precondition(
    snapshot: Mapping[str, Any],
    requirements_sha256: str,
    plan: Mapping[str, Any] | None,
    review: Mapping[str, Any] | None,
    authority_receipt: Mapping[str, str] | None = None,
) -> str:
    return _precondition_sha256(
        target=snapshot["target"],
        actor_id=snapshot["actor"]["id"],
        requirements_sha256=requirements_sha256,
        plan=_artifact_summary(plan),
        review=_artifact_summary(review),
        authority_receipt=authority_receipt,
    )


def _strip_author_event(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(event[key])
        for key in (
            "event_type",
            "exchange_id",
            "prior_state_sha256",
            "artifact_binding",
            "scope",
            "scope_change_reason",
            "responses",
        )
    }


def _is_initial_plan_event(plan: Mapping[str, Any], event: Mapping[str, Any]) -> bool:
    artifact = event["artifact_binding"]
    visible_sha256 = artifact["visible_content_sha256"]
    return bool(
        event["prior_state_sha256"] is None
        and event["responses"] == []
        and event["scope_change_reason"] is None
        and artifact["sha256"] == visible_sha256
        and artifact["revision"] in {plan["id"], f"pending:{visible_sha256}"}
    )


def _initial_exchange_id(snapshot: Mapping[str, Any], requirements_sha256: str) -> str:
    return (
        "issue-"
        + review_exchange.sha256_json(
            {
                "target": snapshot["target"],
                "requirements_sha256": requirements_sha256,
            }
        )[:24]
    )


def _artifact_matches(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    return bool(
        first["revision"] == second["revision"] and first["sha256"] == second["sha256"]
    )


def _withheld_inspection(
    snapshot: Mapping[str, Any],
    requirements_sha256: str,
    code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "schema_id": INSPECT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "withheld",
        "requirements_sha256": requirements_sha256,
        "precondition_sha256": _precondition(snapshot, requirements_sha256, None, None),
        "plan": None,
        "review": None,
        "envelope": None,
        "state": None,
        "state_sha256": None,
        "next_action": "human_decision",
        "diagnostics": [_diagnostic(code, message)],
    }


def _pending_reframe(
    snapshot: Mapping[str, Any],
    requirements_sha256: str,
    plan: Mapping[str, Any],
    plan_envelope: Mapping[str, Any],
    review: Mapping[str, Any],
    review_envelope: Mapping[str, Any],
) -> bool:
    plan_state = plan_envelope["state"]
    review_state = review_envelope["state"]
    if not (
        plan_state["prior_state_sha256"] == review_envelope["state_sha256"]
        and plan_state["exchange_id"] != review_state["exchange_id"]
    ):
        return False
    if (
        review_state["surface"] != "issue"
        or review_state["target"] != _core_target(snapshot)
        or review_state["requirements_sha256"] == requirements_sha256
        or review_state["artifact_binding"]["revision"] != plan["id"]
        or plan_state["target"] != review_state["target"]
        or plan_state["requirements_sha256"] != requirements_sha256
        or plan_state["exchange_id"]
        != _reframe_exchange_id(snapshot, review_envelope["state_sha256"])
        or plan_state["artifact_binding"]["revision"] != plan["id"]
        or plan_state["responses"]
        or plan_state["scope_change_reason"] is not None
    ):
        raise ProtocolError(
            "The pending reframe does not bind the retained review state exactly."
        )
    expected_authority = _authority_context(
        action="reframe",
        target=plan_state["target"],
        exchange_id=plan_state["exchange_id"],
        requirements_sha256=plan_state["requirements_sha256"],
        prior_state_sha256=None,
        supersedes_state_sha256=review_envelope["state_sha256"],
        decisions=[],
    )
    authority_body = review_exchange.canonical_json(expected_authority)
    authority_comments = [
        comment
        for comment in snapshot["comments"]
        if comment["body"] == authority_body and comment["author"]["is_authority"]
    ]
    if len(authority_comments) != 1:
        raise ProtocolError(
            "The pending reframe needs one exact live authority record."
        )
    authority = authority_comments[0]
    receipt = {
        "reference": authority["url"],
        "sha256": review_exchange.sha256_text(authority_body),
    }
    review_exchange.verify_authority_record(authority_body, receipt, expected_authority)
    _reviewed_plan_token(review["body"])
    _verify_state_authorities(snapshot, review_state)
    return True


def inspect_snapshot(value: object) -> dict[str, Any]:
    """Normalize one issue snapshot and select the next protocol action."""
    snapshot = _snapshot(value)
    requirements_sha256 = _requirements_sha256(snapshot)
    finalized = _finalized_status(snapshot["issue"]["body"])
    if finalized == "invalid":
        return _withheld_inspection(
            snapshot,
            requirements_sha256,
            "malformed_finalize_marker",
            "The issue body contains an invalid finalized planning marker.",
        )
    if finalized == "valid":
        return {
            "schema_id": INSPECT_SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "status": "finalized",
            "requirements_sha256": requirements_sha256,
            "precondition_sha256": _precondition(
                snapshot, requirements_sha256, None, None
            ),
            "plan": None,
            "review": None,
            "envelope": None,
            "state": None,
            "state_sha256": None,
            "next_action": "none",
            "diagnostics": [],
        }
    plan_comments = _role_comments(snapshot, PLAN_MARKERS)
    review_comments = _role_comments(snapshot, REVIEW_MARKERS)
    actor_id = snapshot["actor"]["id"]
    if (
        len(plan_comments) > 1
        or len(review_comments) > 1
        or (
            plan_comments
            and review_comments
            and plan_comments[0]["id"] == review_comments[0]["id"]
        )
    ):
        return _withheld_inspection(
            snapshot,
            requirements_sha256,
            "marker_conflict",
            "The issue contains multiple canonical planning markers.",
        )
    if any(
        comment["author"]["id"] != actor_id
        for comment in (*plan_comments, *review_comments)
    ):
        return _withheld_inspection(
            snapshot,
            requirements_sha256,
            "foreign_marker",
            "A canonical planning marker is not owned by the authenticated actor.",
        )
    plan = plan_comments[0] if plan_comments else None
    review = review_comments[0] if review_comments else None
    plan_envelope: dict[str, Any] | None = None
    review_envelope: dict[str, Any] | None = None
    try:
        if plan is not None and review_exchange.CARRIER_PREFIX in plan["body"]:
            plan_envelope = review_exchange.extract_carrier(plan["body"])
            if plan_envelope["schema_id"] != review_exchange.AUTHOR_EVENT_SCHEMA_ID:
                raise ProtocolError(
                    "The plan comment does not contain an author event."
                )
        if review is not None and review_exchange.CARRIER_PREFIX in review["body"]:
            review_envelope = review_exchange.extract_carrier(review["body"])
            if review_envelope["schema_id"] != review_exchange.STATE_SCHEMA_ID:
                raise ProtocolError("The review comment does not contain review state.")
    except ProtocolError as error:
        return _withheld_inspection(
            snapshot, requirements_sha256, "malformed_carrier", str(error)
        )
    if plan_envelope is not None:
        plan_state = plan_envelope["state"]
        assert plan is not None
        if (
            plan_state["requirements_sha256"] != requirements_sha256
            and review is None
            and plan_state["target"] == _core_target(snapshot)
            and _is_initial_plan_event(plan, plan_state)
            and plan_state["exchange_id"]
            == _initial_exchange_id(snapshot, plan_state["requirements_sha256"])
        ):
            return {
                "schema_id": INSPECT_SCHEMA_ID,
                "schema_version": SCHEMA_VERSION,
                "status": "ready",
                "requirements_sha256": requirements_sha256,
                "precondition_sha256": _precondition(
                    snapshot, requirements_sha256, plan, None
                ),
                "plan": _artifact_summary(plan),
                "review": None,
                "envelope": None,
                "state": None,
                "state_sha256": None,
                "next_action": "prepare_plan",
                "diagnostics": [],
            }
        if plan_state["requirements_sha256"] != requirements_sha256:
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "requirements_drift",
                "The plan carrier does not bind the current issue requirements.",
            )
        if plan_state["target"] != _core_target(snapshot):
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "target_drift",
                "The plan carrier does not bind the current issue target.",
            )
        if (
            plan_state["artifact_binding"]["sha256"]
            != plan_state["artifact_binding"]["visible_content_sha256"]
        ):
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "plan_binding_mismatch",
                "The plan carrier does not bind its visible plan content.",
            )
        if (
            review is None
            and plan_state["prior_state_sha256"] is None
            and not _is_initial_plan_event(plan, plan_state)
        ):
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "plan_identity_drift",
                "The initial plan carrier does not bind its comment identity.",
            )
    if (
        plan is not None
        and plan_envelope is not None
        and review is not None
        and review_envelope is not None
    ):
        try:
            pending_reframe = _pending_reframe(
                snapshot,
                requirements_sha256,
                plan,
                plan_envelope,
                review,
                review_envelope,
            )
        except ProtocolError as error:
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "pending_reframe_invalid",
                str(error),
            )
        if pending_reframe:
            return {
                "schema_id": INSPECT_SCHEMA_ID,
                "schema_version": SCHEMA_VERSION,
                "status": "ready",
                "requirements_sha256": requirements_sha256,
                "precondition_sha256": _precondition(
                    snapshot, requirements_sha256, plan, review
                ),
                "plan": _artifact_summary(plan),
                "review": _artifact_summary(review),
                "envelope": copy.deepcopy(review_envelope),
                "state": copy.deepcopy(review_envelope["state"]),
                "state_sha256": review_envelope["state_sha256"],
                "next_action": "prepare_review",
                "diagnostics": [
                    _diagnostic(
                        "pending_reframe",
                        "The reframed plan requires an explicit reframe review event.",
                    )
                ],
            }
    pending_author = bool(
        plan_envelope is not None
        and review_envelope is not None
        and plan_envelope["state"]["prior_state_sha256"]
        == review_envelope["state_sha256"]
    )
    if review_envelope is not None:
        assert review is not None
        state = review_envelope["state"]
        if (
            state["surface"] != "issue"
            or state["requirements_sha256"] != requirements_sha256
            or state["target"] != _core_target(snapshot)
        ):
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "review_drift",
                "The review carrier does not bind the current issue state.",
            )
        if plan is None:
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "reviewed_plan_missing",
                "The review state has no retained canonical plan.",
            )
        expected_artifact_sha256 = (
            plan_envelope["state"]["artifact_binding"]["sha256"]
            if plan_envelope is not None
            else _body_sha256(plan["body"])
        )
        if state["artifact_binding"]["revision"] != plan["id"] or (
            not pending_author
            and state["artifact_binding"]["sha256"] != expected_artifact_sha256
        ):
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "plan_identity_drift",
                "The review does not bind the current plan artifact.",
            )
        try:
            reviewed_plan = _reviewed_plan_token(review["body"])
        except ProtocolError as error:
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "malformed_reviewed_plan",
                str(error),
            )
        if not pending_author and reviewed_plan != _source_token(plan)["token"]:
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "reviewed_plan_drift",
                "The review does not bind the exact current plan carrier.",
            )
        try:
            _verify_state_authorities(snapshot, state)
        except ProtocolError as error:
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "authority_receipt_invalid",
                str(error),
            )
    current = review_envelope
    if plan_envelope is not None and review_envelope is not None:
        assert plan is not None
        author_event = plan_envelope["state"]
        review_state = review_envelope["state"]
        if author_event["exchange_id"] != review_state["exchange_id"]:
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "artifact_chain_conflict",
                "The current plan and review name different exchanges.",
            )
        if author_event["prior_state_sha256"] == review_envelope["state_sha256"]:
            if author_event["artifact_binding"]["revision"] != plan["id"]:
                return _withheld_inspection(
                    snapshot,
                    requirements_sha256,
                    "plan_identity_drift",
                    "The author event does not bind the current plan comment identity.",
                )
            try:
                current = review_exchange.reduce_request(
                    {
                        "previous": review_envelope,
                        "event": _strip_author_event(author_event),
                    }
                )["envelope"]
            except ProtocolError as error:
                return _withheld_inspection(
                    snapshot, requirements_sha256, "author_event_rejected", str(error)
                )
        elif plan_envelope not in _expected_retained_plan_envelopes(
            review_state, plan
        ) and not (
            review_state["phase"] == "complete" and review_state["verdict"] == "GO"
        ):
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "artifact_chain_conflict",
                "The current plan and review do not form one exchange chain.",
            )
    elif plan_envelope is not None:
        author_event = plan_envelope["state"]
        if (
            author_event["prior_state_sha256"] is not None
            or author_event["responses"]
            or author_event["scope_change_reason"] is not None
        ):
            return _withheld_inspection(
                snapshot,
                requirements_sha256,
                "orphan_author_event",
                "A continued author event has no prior review state.",
            )
    if current is not None:
        if (
            current["state"]["phase"] == "complete"
            and current["state"]["verdict"] == "GO"
            and plan is not None
            and review is not None
        ):
            try:
                _verify_issue_source_chain(
                    snapshot,
                    current["state"],
                    current["state_sha256"],
                    plan,
                    review,
                    requirements_sha256,
                )
            except ProtocolError as error:
                return _withheld_inspection(
                    snapshot,
                    requirements_sha256,
                    "terminal_source_chain_invalid",
                    str(error),
                )
        next_action = {
            "author_response": "prepare_plan",
            "review_assessment": "prepare_review",
            "finalize": "finalize",
            "human_decision": "human_decision",
        }[current["state"]["next_action"]]
        state_value = current["state"]
        state_sha256 = current["state_sha256"]
    else:
        next_action = "prepare_review" if plan is not None else "prepare_plan"
        state_value = None
        state_sha256 = None
    return {
        "schema_id": INSPECT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "ready",
        "requirements_sha256": requirements_sha256,
        "precondition_sha256": _precondition(
            snapshot, requirements_sha256, plan, review
        ),
        "plan": _artifact_summary(plan),
        "review": _artifact_summary(review),
        "envelope": current,
        "state": state_value,
        "state_sha256": state_sha256,
        "next_action": next_action,
        "diagnostics": [],
    }


def _scope_targets(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ProtocolError("The declared target set must not be empty.")
    targets: list[str] = []
    for index, raw in enumerate(value):
        target = _object(raw, f"scope targets[{index}]", frozenset({"kind", "value"}))
        kind = _string(target["kind"], f"scope targets[{index}].kind")
        if kind not in TARGET_KINDS:
            raise ProtocolError(f"The scope target kind '{kind}' is not supported.")
        targets.append(
            f"{kind}:{_string(target['value'], f'scope targets[{index}].value')}"
        )
    if len(targets) != len(set(targets)):
        raise ProtocolError("The declared target set contains a duplicate.")
    return sorted(targets)


def _visible(marker: str, content: object) -> str:
    text = _string(content, "visible artifact content")
    if (
        any(role_marker in text for role_marker in (*PLAN_MARKERS, *REVIEW_MARKERS))
        or REVIEWED_PLAN_PREFIX in text
        or review_exchange.CARRIER_PREFIX in text
        or FINALIZE_NAMESPACE_PATTERN.search(text) is not None
    ):
        raise ProtocolError("Visible content cannot contain an Athena artifact marker.")
    return f"{marker}\n\n{text.rstrip()}"


def _find_comment(
    snapshot: Mapping[str, Any], summary: Mapping[str, Any] | None
) -> dict[str, Any] | None:
    if summary is None:
        return None
    matches = [
        comment for comment in snapshot["comments"] if comment["id"] == summary["id"]
    ]
    if len(matches) != 1:
        raise ProtocolError("The retained issue comment is unavailable.")
    return cast(dict[str, Any], matches[0])


def _operation(
    *,
    artifact: str,
    body: str,
    comment: Mapping[str, Any] | None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "action": "create" if comment is None else "update",
        "artifact": artifact,
        "comment_id": None if comment is None else comment["id"],
        "expected_body_sha256": (
            None if comment is None else _body_sha256(cast(str, comment["body"]))
        ),
        "body": body,
        "body_sha256": _body_sha256(body),
    }
    value["operation_sha256"] = review_exchange.sha256_json(value)
    return value


def _peer_binding(
    inspection: Mapping[str, Any], artifact: str
) -> dict[str, Any] | None:
    peer = inspection["review"] if artifact == "plan" else inspection["plan"]
    return cast(dict[str, Any] | None, copy.deepcopy(peer))


def _prepared_result(
    *,
    inspection: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    state_envelope: Mapping[str, Any] | None,
    operation: Mapping[str, Any] | None,
    diagnostics: list[dict[str, str]],
    authority_receipt: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    status = "ready" if operation is not None else "withheld"
    state = None if state_envelope is None else state_envelope["state"]
    state_sha256 = None if state_envelope is None else state_envelope["state_sha256"]
    next_action = inspection["next_action"]
    if state is not None:
        next_action = state["next_action"]
    artifact = None if operation is None else operation["artifact"]
    if state is None and artifact == "plan":
        next_action = "prepare_review"
    precondition = inspection["precondition_sha256"]
    if authority_receipt is not None:
        precondition = _precondition_sha256(
            target=snapshot["target"],
            actor_id=snapshot["actor"]["id"],
            requirements_sha256=inspection["requirements_sha256"],
            plan=inspection["plan"],
            review=inspection["review"],
            authority_receipt=authority_receipt,
        )
    return {
        "schema_id": PREPARE_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "requirements_sha256": inspection["requirements_sha256"],
        "precondition_sha256": precondition,
        "target": copy.deepcopy(snapshot["target"]),
        "actor_id": snapshot["actor"]["id"],
        "peer": None if artifact is None else _peer_binding(inspection, artifact),
        "state": state,
        "state_sha256": state_sha256,
        "authority_receipt": (
            None if authority_receipt is None else dict(authority_receipt)
        ),
        "next_action": next_action,
        "operation": None if operation is None else dict(operation),
        "diagnostics": diagnostics,
    }


def _inspection_has_diagnostic(inspection: Mapping[str, Any], code: str) -> bool:
    return any(
        isinstance(diagnostic, Mapping) and diagnostic.get("code") == code
        for diagnostic in inspection["diagnostics"]
    )


def _prepare_input(
    value: object, name: str
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    request = _object(value, name, frozenset({"snapshot", "content", "event"}))
    snapshot = _snapshot(request["snapshot"])
    content = _string(request["content"], f"{name}.content")
    if not isinstance(request["event"], dict):
        raise ProtocolError(f"{name}.event must be an object.")
    return snapshot, content, cast(dict[str, Any], request["event"])


def _verified_reframe_context(
    snapshot: Mapping[str, Any], value: object
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    previous = review_exchange.verify_envelope(value)
    if previous["schema_id"] != review_exchange.STATE_SCHEMA_ID:
        raise ProtocolError("The reframe prior record is not review state.")
    state = previous["state"]
    requirements = _requirements_sha256(snapshot)
    if (
        state["surface"] != "issue"
        or state["target"] != _core_target(snapshot)
        or state["requirements_sha256"] == requirements
    ):
        raise ProtocolError(
            "A reframe requires changed requirements and a prior review state."
        )
    if _finalized_status(snapshot["issue"]["body"]) != "absent":
        raise ProtocolError("A finalized or malformed issue cannot be reframed.")
    plan_comments = _role_comments(snapshot, PLAN_MARKERS)
    review_comments = _role_comments(snapshot, REVIEW_MARKERS)
    actor_id = snapshot["actor"]["id"]
    if (
        len(plan_comments) != 1
        or len(review_comments) != 1
        or plan_comments[0]["id"] == review_comments[0]["id"]
        or any(
            comment["author"]["id"] != actor_id
            for comment in (*plan_comments, *review_comments)
        )
    ):
        raise ProtocolError(
            "A reframe requires one actor-owned plan and review comment."
        )
    plan = plan_comments[0]
    review = review_comments[0]
    retained = review_exchange.extract_carrier(review["body"])
    if retained != previous:
        raise ProtocolError(
            "The supplied prior state is not the retained review state."
        )
    plan_envelope = review_exchange.extract_carrier(plan["body"])
    if plan_envelope["schema_id"] != review_exchange.AUTHOR_EVENT_SCHEMA_ID:
        raise ProtocolError("The retained plan does not contain an author event.")
    plan_state = plan_envelope["state"]
    if (
        state["artifact_binding"]["revision"] != plan["id"]
        or plan_state["exchange_id"] != state["exchange_id"]
        or plan_state["requirements_sha256"] != state["requirements_sha256"]
        or plan_state["target"] != state["target"]
        or plan_state["artifact_binding"]["revision"]
        not in {
            plan["id"],
            f"pending:{plan_state['artifact_binding']['visible_content_sha256']}",
        }
        or plan_state["artifact_binding"]["sha256"]
        != plan_state["artifact_binding"]["visible_content_sha256"]
    ):
        raise ProtocolError(
            "The retained plan and review do not form one exact exchange."
        )
    synchronized = _reviewed_plan_token(review["body"]) == _source_token(plan)["token"]
    if synchronized:
        if (
            state["artifact_binding"]["sha256"]
            != plan_state["artifact_binding"]["sha256"]
        ):
            raise ProtocolError(
                "The retained plan and review do not form one exact exchange."
            )
    else:
        if (
            plan_state["prior_state_sha256"] != previous["state_sha256"]
            or plan_state["artifact_binding"]["revision"] != plan["id"]
        ):
            raise ProtocolError(
                "The retained plan and review do not form one exact exchange."
            )
        review_exchange.reduce_request(
            {
                "previous": previous,
                "event": _strip_author_event(plan_state),
            }
        )
        raise ProtocolError(
            "A reframe must checkpoint the pending author event with a reviewer "
            "assessment before it supersedes the review state."
        )
    _verify_state_authorities(snapshot, state)
    return previous, plan, review


def _reframe_preparation_view(
    snapshot: Mapping[str, Any],
    previous: Mapping[str, Any],
    plan: Mapping[str, Any],
    review: Mapping[str, Any],
) -> dict[str, Any]:
    requirements = _requirements_sha256(snapshot)
    return {
        "status": "ready",
        "requirements_sha256": requirements,
        "precondition_sha256": _precondition(snapshot, requirements, plan, review),
        "plan": _artifact_summary(plan),
        "review": _artifact_summary(review),
        "envelope": previous,
        "next_action": "prepare_plan",
    }


def _reframe_exchange_id(snapshot: Mapping[str, Any], previous_sha256: str) -> str:
    return (
        "issue-"
        + review_exchange.sha256_json(
            {
                "target": snapshot["target"],
                "requirements_sha256": _requirements_sha256(snapshot),
                "supersedes_state_sha256": previous_sha256,
            }
        )[:24]
    )


def _superseded_exchange_ids(state: Mapping[str, Any]) -> list[str]:
    genesis = state["accepted_events"][0]
    inherited = (
        genesis["superseded_exchange_ids"] if genesis["event_type"] == "reframe" else []
    )
    return [*cast(list[str], inherited), cast(str, state["exchange_id"])]


def _authority_context(
    *,
    action: str,
    target: Mapping[str, Any],
    exchange_id: str,
    requirements_sha256: str,
    prior_state_sha256: str | None,
    supersedes_state_sha256: str | None,
    decisions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_id": review_exchange.AUTHORITY_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "action": action,
        "target": copy.deepcopy(dict(target)),
        "exchange_id": exchange_id,
        "requirements_sha256": requirements_sha256,
        "prior_state_sha256": prior_state_sha256,
        "supersedes_state_sha256": supersedes_state_sha256,
        "decisions": copy.deepcopy(list(decisions)),
    }


def _verified_replanned_context(
    snapshot: Mapping[str, Any], value: object
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    previous = review_exchange.verify_envelope(value)
    if previous["schema_id"] != review_exchange.STATE_SCHEMA_ID:
        raise ProtocolError("The reframe prior record is not review state.")
    state = previous["state"]
    requirements = _requirements_sha256(snapshot)
    if (
        state["surface"] != "issue"
        or state["target"] != _core_target(snapshot)
        or state["requirements_sha256"] == requirements
    ):
        raise ProtocolError(
            "A reframe requires changed requirements and a prior review state."
        )
    if _finalized_status(snapshot["issue"]["body"]) != "absent":
        raise ProtocolError("A finalized or malformed issue cannot be reframed.")
    plan_comments = _role_comments(snapshot, PLAN_MARKERS)
    review_comments = _role_comments(snapshot, REVIEW_MARKERS)
    actor_id = snapshot["actor"]["id"]
    if (
        len(plan_comments) != 1
        or len(review_comments) != 1
        or plan_comments[0]["id"] == review_comments[0]["id"]
        or any(
            comment["author"]["id"] != actor_id
            for comment in (*plan_comments, *review_comments)
        )
    ):
        raise ProtocolError(
            "A reframe requires one actor-owned plan and review comment."
        )
    plan = plan_comments[0]
    review = review_comments[0]
    retained = review_exchange.extract_carrier(review["body"])
    if retained != previous:
        raise ProtocolError(
            "The supplied prior state is not the retained review state."
        )
    plan_envelope = review_exchange.extract_carrier(plan["body"])
    if plan_envelope["schema_id"] != review_exchange.AUTHOR_EVENT_SCHEMA_ID:
        raise ProtocolError("The reframed plan does not contain an author event.")
    plan_state = plan_envelope["state"]
    expected_exchange_id = _reframe_exchange_id(snapshot, previous["state_sha256"])
    if (
        state["artifact_binding"]["revision"] != plan["id"]
        or plan_state["exchange_id"] != expected_exchange_id
        or plan_state["prior_state_sha256"] != previous["state_sha256"]
        or plan_state["requirements_sha256"] != requirements
        or plan_state["target"] != state["target"]
        or plan_state["artifact_binding"]["revision"] != plan["id"]
        or plan_state["artifact_binding"]["sha256"]
        != plan_state["artifact_binding"]["visible_content_sha256"]
        or plan_state["responses"]
        or plan_state["scope_change_reason"] is not None
    ):
        raise ProtocolError(
            "The reframed plan is not bound to the old exchange exactly."
        )
    _verify_state_authorities(snapshot, state)
    return previous, plan, review, plan_envelope


def prepare_plan(value: object) -> dict[str, Any]:
    """Prepare one create or update for the canonical actor-owned plan."""
    snapshot, content, raw_event = _prepare_input(value, "prepare-plan request")
    if raw_event.get("event_type") == "reframe":
        reframe = _object(
            raw_event,
            "plan reframe event",
            frozenset({"event_type", "previous", "authority_receipt", "scope"}),
        )
        previous, plan_comment, review_comment = _verified_reframe_context(
            snapshot, reframe["previous"]
        )
        authority, authority_body = _authority_comment(
            snapshot, reframe["authority_receipt"]
        )
        scope = _scope_targets(reframe["scope"])
        visible = _visible(PLAN_MARKER, content)
        visible_sha256 = review_exchange.sha256_text(visible)
        artifact = {
            "revision": plan_comment["id"],
            "sha256": visible_sha256,
            "visible_content_sha256": visible_sha256,
        }
        author_record = {
            "event_type": "author_response",
            "exchange_id": _reframe_exchange_id(snapshot, previous["state_sha256"]),
            "prior_state_sha256": previous["state_sha256"],
            "target": _core_target(snapshot),
            "requirements_sha256": _requirements_sha256(snapshot),
            "artifact_binding": artifact,
            "scope": scope,
            "scope_change_reason": None,
            "responses": [],
        }
        review_exchange.verify_authority_record(
            authority_body,
            authority,
            _authority_context(
                action="reframe",
                target=author_record["target"],
                exchange_id=author_record["exchange_id"],
                requirements_sha256=author_record["requirements_sha256"],
                prior_state_sha256=None,
                supersedes_state_sha256=previous["state_sha256"],
                decisions=[],
            ),
        )
        author_envelope = review_exchange.make_envelope(
            author_record, review_exchange.AUTHOR_EVENT_SCHEMA_ID
        )
        body = review_exchange.render_carrier(visible, author_envelope, "author-event")
        inspection = _reframe_preparation_view(
            snapshot, previous, plan_comment, review_comment
        )
        return _prepared_result(
            inspection=inspection,
            snapshot=snapshot,
            state_envelope=None,
            operation=_operation(artifact="plan", body=body, comment=plan_comment),
            diagnostics=[],
            authority_receipt=authority,
        )
    event = _object(
        raw_event,
        "plan event",
        frozenset({"scope", "scope_change_reason", "responses"}),
    )
    inspection = inspect_snapshot(snapshot)
    if inspection["status"] != "ready" or inspection["next_action"] != "prepare_plan":
        code = (
            "state_not_awaiting_author"
            if inspection["status"] == "ready"
            else "inspection_withheld"
        )
        return _prepared_result(
            inspection=inspection,
            snapshot=snapshot,
            state_envelope=inspection["envelope"],
            operation=None,
            diagnostics=[_diagnostic(code, "The exchange is not awaiting a plan.")],
        )
    scope = _scope_targets(event["scope"])
    visible = _visible(PLAN_MARKER, content)
    visible_sha256 = review_exchange.sha256_text(visible)
    current_plan_comment = _find_comment(snapshot, inspection["plan"])
    artifact = {
        "revision": (
            f"pending:{visible_sha256}"
            if current_plan_comment is None
            else current_plan_comment["id"]
        ),
        "sha256": visible_sha256,
        "visible_content_sha256": visible_sha256,
    }
    previous = inspection["envelope"]
    if previous is None:
        responses = event["responses"]
        if responses != []:
            raise ProtocolError("An initial plan cannot answer a prior finding.")
        if event["scope_change_reason"] is not None:
            raise ProtocolError("An initial plan cannot contain a scope-change reason.")
        exchange_id = _initial_exchange_id(snapshot, inspection["requirements_sha256"])
        author_record = {
            "event_type": "author_response",
            "exchange_id": exchange_id,
            "prior_state_sha256": None,
            "target": _core_target(snapshot),
            "requirements_sha256": inspection["requirements_sha256"],
            "artifact_binding": artifact,
            "scope": scope,
            "scope_change_reason": None,
            "responses": [],
        }
        author_envelope = review_exchange.make_envelope(
            author_record, review_exchange.AUTHOR_EVENT_SCHEMA_ID
        )
        state_envelope = None
    else:
        raw_author_event = {
            "event_type": "author_response",
            "exchange_id": previous["state"]["exchange_id"],
            "prior_state_sha256": previous["state_sha256"],
            "artifact_binding": artifact,
            "scope": scope,
            "scope_change_reason": _nullable_string(
                event["scope_change_reason"], "plan scope-change reason"
            ),
            "responses": event["responses"],
        }
        reduced = review_exchange.reduce_request(
            {"previous": previous, "event": raw_author_event}
        )
        author_envelope = reduced["author_event"]
        state_envelope = reduced["envelope"]
        assert author_envelope is not None
    body = review_exchange.render_carrier(visible, author_envelope, "author-event")
    operation = _operation(artifact="plan", body=body, comment=current_plan_comment)
    return _prepared_result(
        inspection=inspection,
        snapshot=snapshot,
        state_envelope=state_envelope,
        operation=operation,
        diagnostics=[],
    )


def prepare_review(value: object) -> dict[str, Any]:
    """Prepare one create or update for the canonical actor-owned review."""
    snapshot, content, raw_event = _prepare_input(value, "prepare-review request")
    event_type = raw_event.get("event_type")
    if event_type == "reframe":
        event = _object(
            raw_event,
            "review reframe event",
            frozenset(
                {
                    "event_type",
                    "previous",
                    "authority_receipt",
                    "coverage_complete",
                    "responses",
                    "new_findings",
                    "stop_reason",
                    "legacy_import",
                    "scope",
                }
            ),
        )
        if _boolean(event["legacy_import"], "reframe legacy-import flag"):
            raise ProtocolError(
                "A versioned reframe cannot import legacy review state."
            )
        if event["responses"] != []:
            raise ProtocolError(
                "A reframe cannot reconcile findings from the old exchange."
            )
        previous, plan_comment, review_comment, plan_envelope = (
            _verified_replanned_context(snapshot, event["previous"])
        )
        authority, authority_body = _authority_comment(
            snapshot, event["authority_receipt"]
        )
        scope = _scope_targets(event["scope"])
        if scope != plan_envelope["state"]["scope"]:
            raise ProtocolError(
                "The reframe review scope differs from the new plan targets."
            )
        visible = _review_visible(content, plan_comment)
        artifact = {
            **copy.deepcopy(plan_envelope["state"]["artifact_binding"]),
            "visible_content_sha256": review_exchange.sha256_text(visible),
        }
        reviewer_event = {
            "event_type": "reframe",
            "exchange_id": plan_envelope["state"]["exchange_id"],
            "prior_state_sha256": previous["state_sha256"],
            "round": 1,
            "surface": "issue",
            "target": _core_target(snapshot),
            "requirements_sha256": _requirements_sha256(snapshot),
            "supersedes_state_sha256": previous["state_sha256"],
            "superseded_exchange_ids": _superseded_exchange_ids(previous["state"]),
            "authority_receipt": authority,
            "artifact_binding": artifact,
            "scope": scope,
            "coverage_complete": _boolean(
                event["coverage_complete"], "reframe coverage completeness"
            ),
            "go_eligible": True,
            "responses": [],
            "new_findings": event["new_findings"],
            "stop_reason": event["stop_reason"],
        }
        reduced = review_exchange.reduce_request(
            {"previous": previous, "event": reviewer_event}
        )
        state_envelope = reduced["envelope"]
        review_exchange.verify_authority_record_for_event(
            authority_body, authority, reviewer_event, state_envelope
        )
        body = review_exchange.render_carrier(visible, state_envelope, "state")
        inspection = _reframe_preparation_view(
            snapshot, previous, plan_comment, review_comment
        )
        return _prepared_result(
            inspection=inspection,
            snapshot=snapshot,
            state_envelope=state_envelope,
            operation=_operation(artifact="review", body=body, comment=review_comment),
            diagnostics=[],
        )
    if event_type == "human_decision":
        event = _object(
            raw_event,
            "human review event",
            frozenset({"event_type", "authority_receipt", "decisions"}),
        )
        inspection = inspect_snapshot(snapshot)
        if inspection["status"] == "ready" and _inspection_has_diagnostic(
            inspection, "pending_reframe"
        ):
            return _prepared_result(
                inspection=inspection,
                snapshot=snapshot,
                state_envelope=inspection["envelope"],
                operation=None,
                diagnostics=[
                    _diagnostic(
                        "pending_reframe_event_required",
                        "The reframed plan requires an explicit reframe review event.",
                    )
                ],
            )
        if (
            inspection["status"] != "ready"
            or inspection["next_action"]
            not in {"prepare_plan", "prepare_review", "human_decision"}
            or inspection["envelope"] is None
            or inspection["plan"] is None
            or inspection["review"] is None
        ):
            return _prepared_result(
                inspection=inspection,
                snapshot=snapshot,
                state_envelope=inspection["envelope"],
                operation=None,
                diagnostics=[
                    _diagnostic(
                        "state_not_awaiting_human",
                        "The exchange cannot accept a human decision.",
                    )
                ],
            )
        previous = inspection["envelope"]
        human_plan_comment = _find_comment(snapshot, inspection["plan"])
        human_review_comment = _find_comment(snapshot, inspection["review"])
        assert human_plan_comment is not None and human_review_comment is not None
        authority, authority_body = _authority_comment(
            snapshot, event["authority_receipt"]
        )
        visible = _review_visible(content, human_plan_comment)
        artifact = {
            **copy.deepcopy(previous["state"]["artifact_binding"]),
            "visible_content_sha256": review_exchange.sha256_text(visible),
        }
        reduced = review_exchange.reduce_request(
            {
                "previous": previous,
                "event": {
                    "event_type": "human_decision",
                    "exchange_id": previous["state"]["exchange_id"],
                    "prior_state_sha256": previous["state_sha256"],
                    "artifact_binding": artifact,
                    "authority_receipt": authority,
                    "decisions": event["decisions"],
                },
            }
        )
        state_envelope = reduced["envelope"]
        review_exchange.verify_authority_record_for_event(
            authority_body,
            authority,
            {
                "event_type": "human_decision",
                "exchange_id": previous["state"]["exchange_id"],
                "prior_state_sha256": previous["state_sha256"],
                "artifact_binding": artifact,
                "authority_receipt": authority,
                "decisions": event["decisions"],
            },
            state_envelope,
        )
        body = review_exchange.render_carrier(visible, state_envelope, "state")
        return _prepared_result(
            inspection=inspection,
            snapshot=snapshot,
            state_envelope=state_envelope,
            operation=_operation(
                artifact="review", body=body, comment=human_review_comment
            ),
            diagnostics=[],
        )
    event = _object(
        raw_event,
        "review event",
        frozenset(
            {
                "event_type",
                "coverage_complete",
                "responses",
                "new_findings",
                "stop_reason",
                "legacy_import",
                "scope",
            }
        ),
    )
    if event["event_type"] != "reviewer_assessment":
        raise ProtocolError("The prepare-review event type is not supported.")
    inspection = inspect_snapshot(snapshot)
    if inspection["status"] != "ready":
        return _prepared_result(
            inspection=inspection,
            snapshot=snapshot,
            state_envelope=inspection["envelope"],
            operation=None,
            diagnostics=[
                _diagnostic("inspection_withheld", "Issue identity validation failed.")
            ],
        )
    if _inspection_has_diagnostic(inspection, "pending_reframe"):
        return _prepared_result(
            inspection=inspection,
            snapshot=snapshot,
            state_envelope=inspection["envelope"],
            operation=None,
            diagnostics=[
                _diagnostic(
                    "pending_reframe_event_required",
                    "The reframed plan requires an explicit reframe review event.",
                )
            ],
        )
    if inspection["plan"] is None:
        return _prepared_result(
            inspection=inspection,
            snapshot=snapshot,
            state_envelope=inspection["envelope"],
            operation=None,
            diagnostics=[
                _diagnostic("plan_absent", "The canonical issue plan is absent.")
            ],
        )
    if inspection["next_action"] != "prepare_review":
        return _prepared_result(
            inspection=inspection,
            snapshot=snapshot,
            state_envelope=inspection["envelope"],
            operation=None,
            diagnostics=[
                _diagnostic(
                    "state_not_awaiting_reviewer",
                    "The exchange is not awaiting a reviewer assessment.",
                )
            ],
        )
    current_plan_comment = _find_comment(snapshot, inspection["plan"])
    assert current_plan_comment is not None
    legacy_plan = review_exchange.CARRIER_PREFIX not in current_plan_comment["body"]
    current_review_comment = _find_comment(snapshot, inspection["review"])
    legacy_review = (
        current_review_comment is not None
        and review_exchange.CARRIER_PREFIX not in current_review_comment["body"]
    )
    legacy_import = _boolean(event["legacy_import"], "review legacy-import flag")
    if (legacy_plan or legacy_review) and not legacy_import:
        return _prepared_result(
            inspection=inspection,
            snapshot=snapshot,
            state_envelope=inspection["envelope"],
            operation=None,
            diagnostics=[
                _diagnostic(
                    "legacy_import_required",
                    "An active unversioned review needs an explicit round-one import.",
                )
            ],
        )
    visible = _review_visible(content, current_plan_comment)
    visible_sha256 = review_exchange.sha256_text(visible)
    previous = inspection["envelope"]
    if previous is None:
        if review_exchange.CARRIER_PREFIX in current_plan_comment["body"]:
            plan_envelope = review_exchange.extract_carrier(
                current_plan_comment["body"]
            )
            plan_state = plan_envelope["state"]
            exchange_id = plan_state["exchange_id"]
            artifact = {
                **copy.deepcopy(plan_state["artifact_binding"]),
                "revision": current_plan_comment["id"],
            }
            scope = plan_state["scope"]
            if event["scope"] != [] and _scope_targets(event["scope"]) != scope:
                raise ProtocolError(
                    "The review event scope differs from the plan targets."
                )
        else:
            exchange_id = (
                "issue-"
                + review_exchange.sha256_json(
                    {
                        "target": snapshot["target"],
                        "requirements_sha256": inspection["requirements_sha256"],
                        "legacy_plan_sha256": _body_sha256(
                            current_plan_comment["body"]
                        ),
                    }
                )[:24]
            )
            plan_digest = _body_sha256(current_plan_comment["body"])
            artifact = {
                "revision": current_plan_comment["id"],
                "sha256": plan_digest,
                "visible_content_sha256": visible_sha256,
            }
            scope = _scope_targets(event["scope"])
        artifact = {**artifact, "visible_content_sha256": visible_sha256}
        reviewer_event = {
            "event_type": "reviewer_assessment",
            "exchange_id": exchange_id,
            "prior_state_sha256": None,
            "round": 1,
            "surface": "issue",
            "target": _core_target(snapshot),
            "requirements_sha256": inspection["requirements_sha256"],
            "supersedes_state_sha256": None,
            "artifact_binding": artifact,
            "scope": scope,
            "coverage_complete": _boolean(
                event["coverage_complete"], "review coverage completeness"
            ),
            "go_eligible": True,
            "responses": [],
            "new_findings": event["new_findings"],
            "stop_reason": event["stop_reason"],
        }
    else:
        if (
            event["scope"] != []
            and _scope_targets(event["scope"]) != previous["state"]["scope"]
        ):
            raise ProtocolError("The review event scope differs from the plan targets.")
        artifact = {
            **previous["state"]["artifact_binding"],
            "visible_content_sha256": visible_sha256,
        }
        reviewer_event = {
            "event_type": "reviewer_assessment",
            "exchange_id": previous["state"]["exchange_id"],
            "prior_state_sha256": previous["state_sha256"],
            "round": previous["state"]["round"] + 1,
            "artifact_binding": artifact,
            "scope": previous["state"]["scope"],
            "coverage_complete": _boolean(
                event["coverage_complete"], "review coverage completeness"
            ),
            "go_eligible": True,
            "responses": event["responses"],
            "new_findings": event["new_findings"],
            "stop_reason": event["stop_reason"],
        }
    reduced = review_exchange.reduce_request(
        {"previous": previous, "event": reviewer_event}
    )
    state_envelope = reduced["envelope"]
    body = review_exchange.render_carrier(visible, state_envelope, "state")
    operation = _operation(artifact="review", body=body, comment=current_review_comment)
    return _prepared_result(
        inspection=inspection,
        snapshot=snapshot,
        state_envelope=state_envelope,
        operation=operation,
        diagnostics=[],
    )


def _snapshot_peer_matches(
    snapshot: Mapping[str, Any], peer: Mapping[str, Any] | None
) -> bool:
    if peer is None:
        return True
    matches = [
        comment for comment in snapshot["comments"] if comment["id"] == peer["id"]
    ]
    return (
        len(matches) == 1
        and matches[0]["author"]["id"] == peer["author_id"]
        and _body_sha256(matches[0]["body"]) == peer["body_sha256"]
    )


def _artifact_summary_record(value: object, name: str) -> dict[str, str] | None:
    if value is None:
        return None
    summary = _object(value, name, frozenset({"id", "author_id", "body_sha256"}))
    digest = _digest(summary["body_sha256"], f"{name}.body_sha256")
    assert digest is not None
    return {
        "id": _string(summary["id"], f"{name}.id"),
        "author_id": _string(summary["author_id"], f"{name}.author_id"),
        "body_sha256": digest,
    }


def _authority_record(
    value: object, name: str, *, nullable: bool = False
) -> dict[str, str] | None:
    if value is None and nullable:
        return None
    receipt = _object(value, name, frozenset({"reference", "sha256"}))
    digest = _digest(receipt["sha256"], f"{name}.sha256")
    assert digest is not None
    return {
        "reference": _string(receipt["reference"], f"{name}.reference"),
        "sha256": digest,
    }


def _prepared_target(value: object) -> dict[str, Any]:
    target = _object(
        value,
        "prepared target",
        frozenset({"provider", "host", "repository", "issue_id", "number", "url"}),
    )
    provider = _string(target["provider"], "prepared target.provider")
    if provider not in review_exchange.PROVIDER_BODY_LIMITS:
        raise ProtocolError("The prepared target provider is not supported.")
    return {
        "provider": provider,
        "host": _string(target["host"], "prepared target.host"),
        "repository": _string(target["repository"], "prepared target.repository"),
        "issue_id": _string(target["issue_id"], "prepared target.issue_id"),
        "number": _integer(target["number"], "prepared target.number"),
        "url": _string(target["url"], "prepared target.url"),
    }


def _prepared_state(
    state_value: object, digest_value: object
) -> tuple[dict[str, Any] | None, str | None]:
    if state_value is None:
        if digest_value is not None:
            raise ProtocolError("A missing prepared state cannot have a digest.")
        return None, None
    if not isinstance(state_value, dict):
        raise ProtocolError("The prepared state must be an object.")
    envelope = review_exchange.make_envelope(state_value)
    digest = _digest(digest_value, "prepared state digest")
    if digest != envelope["state_sha256"]:
        raise ProtocolError("The prepared state digest does not match its state.")
    return envelope["state"], envelope["state_sha256"]


def _prepared_comment_operation(value: object) -> dict[str, Any]:
    operation = _object(
        value,
        "prepared comment operation",
        frozenset(
            {
                "action",
                "artifact",
                "comment_id",
                "expected_body_sha256",
                "body",
                "body_sha256",
                "operation_sha256",
            }
        ),
    )
    action = _string(operation["action"], "prepared comment operation.action")
    artifact = _string(operation["artifact"], "prepared comment operation.artifact")
    if action not in {"create", "update"} or artifact not in {"plan", "review"}:
        raise ProtocolError("The prepared comment operation is not supported.")
    comment_id = _nullable_string(
        operation["comment_id"], "prepared comment operation.comment_id"
    )
    expected = _digest(
        operation["expected_body_sha256"],
        "prepared comment operation.expected_body_sha256",
        nullable=True,
    )
    if action == "create" and (comment_id is not None or expected is not None):
        raise ProtocolError("The prepared comment action and identity do not agree.")
    if action == "update" and (comment_id is None or expected is None):
        raise ProtocolError("The prepared comment action and identity do not agree.")
    body = _string(
        operation["body"], "prepared comment operation.body", allow_empty=True
    )
    body_digest = _digest(
        operation["body_sha256"], "prepared comment operation.body_sha256"
    )
    if body_digest != _body_sha256(body):
        raise ProtocolError("The prepared comment body digest does not match.")
    canonical = {
        "action": action,
        "artifact": artifact,
        "comment_id": comment_id,
        "expected_body_sha256": expected,
        "body": body,
        "body_sha256": body_digest,
    }
    operation_digest = _digest(
        operation["operation_sha256"], "prepared comment operation.operation_sha256"
    )
    if operation_digest != review_exchange.sha256_json(canonical):
        raise ProtocolError("The prepared comment operation digest does not match.")
    return {**canonical, "operation_sha256": operation_digest}


def _validate_prepared_publication(value: object) -> dict[str, Any]:
    prepared = _object(
        value,
        "prepared publication",
        frozenset(
            {
                "schema_id",
                "schema_version",
                "status",
                "requirements_sha256",
                "precondition_sha256",
                "target",
                "actor_id",
                "peer",
                "state",
                "state_sha256",
                "authority_receipt",
                "next_action",
                "operation",
                "diagnostics",
            }
        ),
    )
    if (
        prepared["schema_id"] != PREPARE_SCHEMA_ID
        or type(prepared["schema_version"]) is not int
        or prepared["schema_version"] != SCHEMA_VERSION
    ):
        raise ProtocolError("The prepared issue operation is invalid.")
    if prepared["status"] != "ready" or prepared["diagnostics"] != []:
        raise ProtocolError("Only a ready prepared issue operation can be verified.")
    requirements = _digest(
        prepared["requirements_sha256"], "prepared requirements digest"
    )
    precondition = _digest(
        prepared["precondition_sha256"], "prepared precondition digest"
    )
    assert requirements is not None and precondition is not None
    target = _prepared_target(prepared["target"])
    peer = _artifact_summary_record(prepared["peer"], "prepared peer")
    actor_id = _string(prepared["actor_id"], "prepared actor ID")
    state, state_sha256 = _prepared_state(prepared["state"], prepared["state_sha256"])
    authority = _authority_record(
        prepared["authority_receipt"],
        "prepared authority receipt",
        nullable=True,
    )
    operation = _prepared_comment_operation(prepared["operation"])
    changed_summary = (
        None
        if operation["action"] == "create"
        else {
            "id": operation["comment_id"],
            "author_id": actor_id,
            "body_sha256": operation["expected_body_sha256"],
        }
    )
    prepared_plan = changed_summary if operation["artifact"] == "plan" else peer
    prepared_review = peer if operation["artifact"] == "plan" else changed_summary
    expected_precondition = _precondition_sha256(
        target=target,
        actor_id=actor_id,
        requirements_sha256=requirements,
        plan=prepared_plan,
        review=prepared_review,
        authority_receipt=authority,
    )
    if precondition != expected_precondition:
        raise ProtocolError("The prepared publication precondition does not match.")
    envelope = review_exchange.extract_carrier(operation["body"])
    expected_schema = (
        review_exchange.AUTHOR_EVENT_SCHEMA_ID
        if operation["artifact"] == "plan"
        else review_exchange.STATE_SCHEMA_ID
    )
    if envelope["schema_id"] != expected_schema:
        raise ProtocolError("The prepared comment carrier has the wrong role.")
    carrier_state = envelope["state"]
    if (
        carrier_state["target"]
        != {
            "provider": target["provider"],
            "repository": target["repository"],
            "number": target["number"],
            "url": target["url"],
        }
        or carrier_state["requirements_sha256"] != requirements
    ):
        raise ProtocolError(
            "The prepared carrier does not bind its target and requirements."
        )
    if state is not None and (
        state["target"] != carrier_state["target"]
        or state["requirements_sha256"] != requirements
    ):
        raise ProtocolError("The prepared result state does not bind its request.")
    if operation["artifact"] == "review" and (
        state is None
        or envelope["state_sha256"] != state_sha256
        or envelope["state"] != state
    ):
        raise ProtocolError(
            "The prepared review body does not contain its result state."
        )
    if operation["artifact"] == "review":
        assert state is not None
        if peer is None or state["artifact_binding"]["revision"] != peer["id"]:
            raise ProtocolError("The prepared review does not bind its plan identity.")
        if _reviewed_plan_token(operation["body"]) != _source_token_from_summary(peer):
            raise ProtocolError(
                "The prepared review does not bind its exact plan source."
            )
    else:
        artifact = carrier_state["artifact_binding"]
        expected_revision = (
            f"pending:{artifact['visible_content_sha256']}"
            if operation["action"] == "create"
            else operation["comment_id"]
        )
        if (
            artifact["revision"] != expected_revision
            or artifact["sha256"] != artifact["visible_content_sha256"]
        ):
            raise ProtocolError(
                "The prepared plan does not bind its comment operation."
            )
    reframe_plan = bool(
        operation["artifact"] == "plan"
        and state is None
        and carrier_state["prior_state_sha256"] is not None
    )
    if (
        operation["artifact"] == "plan"
        and state is None
        and not reframe_plan
        and not _is_initial_plan_event({"id": operation["comment_id"]}, carrier_state)
    ):
        raise ProtocolError(
            "The prepared initial plan does not contain a legal initial author event."
        )
    if reframe_plan != (authority is not None):
        raise ProtocolError(
            "Only a reframed plan can contain a prepared authority receipt."
        )
    if reframe_plan and (operation["action"] != "update" or peer is None):
        raise ProtocolError(
            "A reframed plan must update one retained plan beside one review."
        )
    next_action = _string(prepared["next_action"], "prepared next action")
    expected_next_action = "prepare_review" if state is None else state["next_action"]
    if next_action != expected_next_action:
        raise ProtocolError("The prepared next action does not match its state.")
    return {
        "schema_id": PREPARE_SCHEMA_ID,
        "schema_version": 1,
        "status": "ready",
        "requirements_sha256": requirements,
        "precondition_sha256": precondition,
        "target": target,
        "actor_id": actor_id,
        "peer": peer,
        "state": state,
        "state_sha256": state_sha256,
        "authority_receipt": authority,
        "next_action": next_action,
        "operation": operation,
        "diagnostics": [],
    }


def _publication_identity_matches(
    snapshot: Mapping[str, Any], prepared: Mapping[str, Any]
) -> tuple[bool, list[dict[str, Any]]]:
    operation = prepared["operation"]
    target_markers = PLAN_MARKERS if operation["artifact"] == "plan" else REVIEW_MARKERS
    peer_markers = REVIEW_MARKERS if operation["artifact"] == "plan" else PLAN_MARKERS
    target_comments = _role_comments(snapshot, target_markers)
    peer_comments = _role_comments(snapshot, peer_markers)
    if len(target_comments) != 1:
        return False, []
    target = target_comments[0]
    if target["author"]["id"] != prepared["actor_id"]:
        return False, []
    if operation["action"] == "create":
        if target["body"] != operation["body"]:
            return False, []
    elif target["id"] != operation["comment_id"] or target["body"] != operation["body"]:
        return False, []
    peer = prepared["peer"]
    if peer is None:
        if peer_comments:
            return False, []
    elif len(peer_comments) != 1 or not _snapshot_peer_matches(snapshot, peer):
        return False, []
    if (
        target_comments
        and peer_comments
        and target_comments[0]["id"] == peer_comments[0]["id"]
    ):
        return False, []
    return True, [target]


def verify_publication(value: object) -> dict[str, Any]:
    """Verify the exact result of one prepared issue-comment mutation."""
    request = _object(
        value, "publication verification", frozenset({"prepared", "snapshot"})
    )
    prepared = _validate_prepared_publication(request["prepared"])
    snapshot = _snapshot(request["snapshot"])
    operation = prepared["operation"]
    verified = (
        snapshot["target"] == prepared["target"]
        and snapshot["actor"]["id"] == prepared["actor_id"]
        and _requirements_sha256(snapshot) == prepared["requirements_sha256"]
    )
    matches: list[dict[str, Any]] = []
    authority_error: str | None = None
    if verified:
        verified, matches = _publication_identity_matches(snapshot, prepared)
    if verified and (
        prepared["state"] is not None or prepared["authority_receipt"] is not None
    ):
        try:
            if prepared["state"] is not None:
                _verify_state_authorities(snapshot, prepared["state"])
                live = inspect_snapshot(snapshot)
                if live["status"] != "ready" or live[
                    "envelope"
                ] != review_exchange.make_envelope(prepared["state"]):
                    raise ProtocolError(
                        "The published exchange state is not the exact live reduction."
                    )
            if prepared["authority_receipt"] is not None:
                author_envelope = review_exchange.extract_carrier(operation["body"])
                _verify_reframe_plan_authority(
                    snapshot,
                    prepared["authority_receipt"],
                    author_envelope["state"],
                )
                live = inspect_snapshot(snapshot)
                if (
                    live["status"] != "ready"
                    or live["next_action"] != "prepare_review"
                    or live["review"] != prepared["peer"]
                    or live["envelope"] is None
                    or live["envelope"]["state_sha256"]
                    != author_envelope["state"]["prior_state_sha256"]
                ):
                    raise ProtocolError(
                        "The reframe plan does not supersede the exact live review state."
                    )
        except ProtocolError as error:
            verified = False
            authority_error = str(error)
    receipt: dict[str, Any] | None = None
    diagnostics: list[dict[str, str]] = []
    if verified:
        assert isinstance(operation, dict)
        receipt = {
            "operation_sha256": operation["operation_sha256"],
            "action": operation["action"],
            "artifact": operation["artifact"],
            "comment_id": matches[0]["id"],
            "url": matches[0]["url"],
            "body_sha256": operation["body_sha256"],
            "verified_precondition_sha256": prepared["precondition_sha256"],
        }
    else:
        code = "publication_not_proven"
        message = "The prepared issue-comment outcome was not verified exactly."
        if authority_error is not None:
            code = "publication_authority_drift"
            message = authority_error
        elif snapshot["target"] == prepared["target"]:
            code = "publication_identity_conflict"
        diagnostics.append(
            _diagnostic(
                code,
                message,
            )
        )
    return {
        "schema_id": PUBLICATION_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "verified" if verified else "unknown_outcome",
        "state": prepared.get("state"),
        "state_sha256": prepared.get("state_sha256"),
        "receipt": receipt,
        "diagnostics": diagnostics,
    }


def _source_token(comment: Mapping[str, Any]) -> dict[str, str]:
    body_sha256 = _body_sha256(comment["body"])
    return {
        "token": review_exchange.sha256_json(
            {"comment_id": comment["id"], "body_sha256": body_sha256}
        ),
        "comment_id": comment["id"],
        "body_sha256": body_sha256,
    }


def _authority_comment(
    snapshot: Mapping[str, Any], value: object
) -> tuple[dict[str, str], str]:
    receipt = _authority_record(value, "authority receipt")
    assert receipt is not None
    reference = receipt["reference"]
    digest = receipt["sha256"]
    matches = [
        comment
        for comment in snapshot["comments"]
        if reference in {comment["id"], comment["url"]}
        and _body_sha256(comment["body"]) == digest
    ]
    if len(matches) != 1:
        raise ProtocolError(
            "The authority receipt does not match one exact live issue comment."
        )
    if not matches[0]["author"]["is_authority"]:
        raise ProtocolError(
            "The authority receipt comment has no verified repository authority."
        )
    body = matches[0]["body"]
    if any(marker in body for marker in (*PLAN_MARKERS, *REVIEW_MARKERS)) or (
        FINALIZE_NAMESPACE_PATTERN.search(body) is not None
    ):
        raise ProtocolError(
            "A canonical workflow artifact cannot also be an authority receipt."
        )
    return {"reference": reference, "sha256": digest}, body


def _verify_reframe_plan_authority(
    snapshot: Mapping[str, Any], receipt: object, author_event: Mapping[str, Any]
) -> None:
    authority, body = _authority_comment(snapshot, receipt)
    review_exchange.verify_authority_record(
        body,
        authority,
        _authority_context(
            action="reframe",
            target=author_event["target"],
            exchange_id=author_event["exchange_id"],
            requirements_sha256=author_event["requirements_sha256"],
            prior_state_sha256=None,
            supersedes_state_sha256=author_event["prior_state_sha256"],
            decisions=[],
        ),
    )


def _verify_state_authorities(
    snapshot: Mapping[str, Any], state: Mapping[str, Any]
) -> None:
    envelope = review_exchange.make_envelope(state)
    receipts: set[tuple[str, str]] = set()
    supersession = state["supersession_authority_receipt"]
    if supersession is not None:
        authority, body = _authority_comment(snapshot, supersession)
        review_exchange.verify_authority_record_for_state(body, authority, envelope)
        receipts.add((supersession["reference"], supersession["sha256"]))
    for finding in state["findings"]:
        receipt = finding["authority_receipt"]
        if receipt is None:
            continue
        key = (receipt["reference"], receipt["sha256"])
        if key not in receipts:
            authority, body = _authority_comment(snapshot, receipt)
            review_exchange.verify_authority_record_for_state(body, authority, envelope)
            receipts.add(key)


def _expected_retained_plan_envelopes(
    state: Mapping[str, Any], plan: Mapping[str, Any]
) -> list[dict[str, Any]]:
    accepted_events = state["accepted_events"]
    author_events = [
        event for event in accepted_events if event["event_type"] == "author_response"
    ]
    if author_events:
        records = [
            {
                **copy.deepcopy(author_events[-1]),
                "target": copy.deepcopy(state["target"]),
                "requirements_sha256": state["requirements_sha256"],
            }
        ]
    else:
        initial = accepted_events[0]
        if initial["event_type"] not in {"reviewer_assessment", "reframe"}:
            raise ProtocolError("The review history has no initial plan source.")
        prior_state_sha256 = (
            initial["supersedes_state_sha256"]
            if initial["event_type"] == "reframe"
            else None
        )
        artifact_sha256 = initial["artifact_binding"]["sha256"]
        revisions = [plan["id"]]
        if initial["event_type"] == "reviewer_assessment":
            revisions.append(f"pending:{artifact_sha256}")
        records = [
            {
                "event_type": "author_response",
                "exchange_id": state["exchange_id"],
                "prior_state_sha256": prior_state_sha256,
                "target": copy.deepcopy(state["target"]),
                "requirements_sha256": state["requirements_sha256"],
                "artifact_binding": {
                    "revision": revision,
                    "sha256": artifact_sha256,
                    "visible_content_sha256": artifact_sha256,
                },
                "scope": copy.deepcopy(initial["scope"]),
                "scope_change_reason": None,
                "responses": [],
            }
            for revision in revisions
        ]
    return [
        review_exchange.make_envelope(record, review_exchange.AUTHOR_EVENT_SCHEMA_ID)
        for record in records
    ]


def _verify_issue_source_chain(
    snapshot: Mapping[str, Any],
    state: Mapping[str, Any],
    state_sha256: str,
    plan: Mapping[str, Any],
    review: Mapping[str, Any],
    requirements_sha256: str,
) -> None:
    review_envelope = review_exchange.extract_carrier(review["body"])
    expected_envelope = review_exchange.make_envelope(state)
    if (
        review_envelope != expected_envelope
        or expected_envelope["state_sha256"] != state_sha256
        or state["surface"] != "issue"
        or state["target"] != _core_target(snapshot)
        or state["requirements_sha256"] != requirements_sha256
        or state["phase"] != "complete"
        or state["verdict"] != "GO"
        or state["artifact_binding"]["revision"] != plan["id"]
        or _reviewed_plan_token(review["body"]) != _source_token(plan)["token"]
    ):
        raise ProtocolError(
            "The terminal review does not bind exact R, P, and V sources."
        )
    if review_exchange.CARRIER_PREFIX in plan["body"]:
        plan_envelope = review_exchange.extract_carrier(plan["body"])
        if plan_envelope not in _expected_retained_plan_envelopes(state, plan):
            raise ProtocolError(
                "The terminal plan carrier is outside the review chain."
            )
    elif state["artifact_binding"]["sha256"] != _body_sha256(plan["body"]):
        raise ProtocolError("The legacy terminal plan body does not match the review.")
    _verify_state_authorities(snapshot, state)


def _requirements_context_sha256(snapshot: Mapping[str, Any]) -> str:
    return review_exchange.sha256_json(
        {
            "target": snapshot["target"],
            "state": snapshot["issue"]["state"],
            "title": snapshot["issue"]["title"],
            "acceptance_criteria": snapshot["issue"]["acceptance_criteria"],
        }
    )


def _withheld_finalize(
    requirements_sha256: str | None, code: str, message: str
) -> dict[str, Any]:
    return {
        "schema_id": FINALIZE_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "withheld",
        "requirements_sha256": requirements_sha256,
        "state": None,
        "state_sha256": None,
        "sources": None,
        "operation": None,
        "deletion_allowlist": [],
        "remaining_comment_ids": [],
        "diagnostics": [_diagnostic(code, message)],
    }


def _unknown_finalize(
    prepared: Mapping[str, Any], code: str, message: str
) -> dict[str, Any]:
    return {
        "schema_id": FINALIZE_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "unknown_outcome",
        "requirements_sha256": prepared["requirements_sha256"],
        "state": prepared["state"],
        "state_sha256": prepared["state_sha256"],
        "sources": prepared["sources"],
        "operation": None,
        "deletion_allowlist": [],
        "remaining_comment_ids": [],
        "diagnostics": [_diagnostic(code, message)],
    }


def _prepared_source(value: object, name: str) -> dict[str, str]:
    source = _object(value, name, frozenset({"token", "comment_id", "body_sha256"}))
    token = _digest(source["token"], f"{name}.token")
    body = _digest(source["body_sha256"], f"{name}.body_sha256")
    assert token is not None and body is not None
    comment_id = _string(source["comment_id"], f"{name}.comment_id")
    if token != review_exchange.sha256_json(
        {"comment_id": comment_id, "body_sha256": body}
    ):
        raise ProtocolError(f"{name} token does not match its source.")
    return {"token": token, "comment_id": comment_id, "body_sha256": body}


def _prepared_finalize_operation(
    value: object, sources: Mapping[str, Any]
) -> dict[str, Any]:
    operation = _object(
        value,
        "prepared finalization operation",
        frozenset(
            {
                "action",
                "expected_issue_body_sha256",
                "body",
                "body_sha256",
                "F",
                "operation_sha256",
            }
        ),
    )
    if operation["action"] != "replace_body":
        raise ProtocolError("The prepared finalization action is not supported.")
    expected = _digest(
        operation["expected_issue_body_sha256"],
        "prepared finalization expected body digest",
    )
    body = _string(operation["body"], "prepared finalization body")
    body_digest = _digest(operation["body_sha256"], "prepared finalization body digest")
    final_digest = _digest(operation["F"], "prepared finalization F digest")
    assert expected is not None and body_digest is not None and final_digest is not None
    if body_digest != _body_sha256(body):
        raise ProtocolError("The prepared finalization body digest does not match.")
    status, marker = _finalized_marker(body)
    if status != "valid" or marker is None:
        raise ProtocolError("The prepared finalization marker is invalid.")
    if marker != {
        "R": sources["R"],
        "P": sources["P"]["token"],
        "V": sources["V"]["token"],
        "F": final_digest,
    }:
        raise ProtocolError(
            "The prepared finalization marker does not match its sources."
        )
    canonical = {
        "action": "replace_body",
        "expected_issue_body_sha256": expected,
        "body": body,
        "body_sha256": body_digest,
        "F": final_digest,
    }
    operation_digest = _digest(
        operation["operation_sha256"], "prepared finalization operation digest"
    )
    if operation_digest != review_exchange.sha256_json(canonical):
        raise ProtocolError(
            "The prepared finalization operation digest does not match."
        )
    return {**canonical, "operation_sha256": operation_digest}


def _finalize_precondition_sha256(
    *,
    target: Mapping[str, Any],
    actor_id: str,
    requirements_sha256: str,
    requirements_context_sha256: str,
    state_sha256: str,
    plan: Mapping[str, Any],
    review: Mapping[str, Any],
    expected_issue_body_sha256: str,
) -> str:
    return review_exchange.sha256_json(
        {
            "schema_id": "athena.issue-exchange.finalize-precondition",
            "schema_version": SCHEMA_VERSION,
            "target": target,
            "actor_id": actor_id,
            "requirements_sha256": requirements_sha256,
            "requirements_context_sha256": requirements_context_sha256,
            "state_sha256": state_sha256,
            "plan": plan,
            "review": review,
            "expected_issue_body_sha256": expected_issue_body_sha256,
        }
    )


def _validate_prepared_finalize(value: object) -> dict[str, Any]:
    prepared = _object(
        value,
        "prepared finalization",
        frozenset(
            {
                "schema_id",
                "schema_version",
                "status",
                "requirements_sha256",
                "requirements_context_sha256",
                "target",
                "actor_id",
                "precondition_sha256",
                "state",
                "state_sha256",
                "sources",
                "operation",
                "deletion_allowlist",
                "remaining_comment_ids",
                "diagnostics",
            }
        ),
    )
    if (
        prepared["schema_id"] != FINALIZE_SCHEMA_ID
        or type(prepared["schema_version"]) is not int
        or prepared["schema_version"] != SCHEMA_VERSION
        or prepared["status"] != "ready"
        or prepared["diagnostics"] != []
        or prepared["remaining_comment_ids"] != []
    ):
        raise ProtocolError("The prepared finalization record is invalid.")
    requirements = _digest(
        prepared["requirements_sha256"], "prepared finalization requirements digest"
    )
    context = _digest(
        prepared["requirements_context_sha256"],
        "prepared finalization requirements context digest",
    )
    precondition = _digest(
        prepared["precondition_sha256"], "prepared finalization precondition digest"
    )
    assert requirements is not None and context is not None and precondition is not None
    state, state_sha256 = _prepared_state(prepared["state"], prepared["state_sha256"])
    if (
        state is None
        or state_sha256 is None
        or state["surface"] != "issue"
        or state["verdict"] != "GO"
        or state["phase"] != "complete"
        or state["requirements_sha256"] != requirements
    ):
        raise ProtocolError(
            "The prepared finalization state is not an issue GO ledger."
        )
    sources_value = _object(
        prepared["sources"], "prepared finalization sources", frozenset({"R", "P", "V"})
    )
    source_r = _digest(sources_value["R"], "prepared finalization R")
    if source_r != requirements:
        raise ProtocolError("The prepared finalization R does not match requirements.")
    sources: dict[str, Any] = {
        "R": source_r,
        "P": _prepared_source(sources_value["P"], "prepared finalization P"),
        "V": _prepared_source(sources_value["V"], "prepared finalization V"),
    }
    if sources["P"]["comment_id"] == sources["V"]["comment_id"]:
        raise ProtocolError("The prepared plan and review sources are not distinct.")
    operation = _prepared_finalize_operation(prepared["operation"], sources)
    target = _prepared_target(prepared["target"])
    actor_id = _string(prepared["actor_id"], "prepared finalization actor ID")
    if (
        state["target"]
        != {
            "provider": target["provider"],
            "repository": target["repository"],
            "number": target["number"],
            "url": target["url"],
        }
        or state["artifact_binding"]["revision"] != sources["P"]["comment_id"]
    ):
        raise ProtocolError(
            "The prepared GO ledger does not bind its exact plan source."
        )
    expected_precondition = _finalize_precondition_sha256(
        target=target,
        actor_id=actor_id,
        requirements_sha256=requirements,
        requirements_context_sha256=context,
        state_sha256=state_sha256,
        plan={
            "id": sources["P"]["comment_id"],
            "author_id": actor_id,
            "body_sha256": sources["P"]["body_sha256"],
        },
        review={
            "id": sources["V"]["comment_id"],
            "author_id": actor_id,
            "body_sha256": sources["V"]["body_sha256"],
        },
        expected_issue_body_sha256=operation["expected_issue_body_sha256"],
    )
    if precondition != expected_precondition:
        raise ProtocolError("The prepared finalization precondition does not match.")
    allowlist = prepared["deletion_allowlist"]
    expected_allowlist = [sources["P"]["comment_id"], sources["V"]["comment_id"]]
    if allowlist != expected_allowlist:
        raise ProtocolError("The prepared deletion allowlist does not match P and V.")
    return {
        "schema_id": FINALIZE_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "ready",
        "requirements_sha256": requirements,
        "requirements_context_sha256": context,
        "target": target,
        "actor_id": actor_id,
        "precondition_sha256": precondition,
        "state": state,
        "state_sha256": state_sha256,
        "sources": sources,
        "operation": operation,
        "deletion_allowlist": expected_allowlist,
        "remaining_comment_ids": [],
        "diagnostics": [],
    }


def _verify_finalize_readback(
    snapshot: dict[str, Any], prepared: Mapping[str, Any]
) -> dict[str, Any]:
    operation = prepared.get("operation")
    sources = prepared.get("sources")
    if not isinstance(operation, dict) or not isinstance(sources, dict):
        raise ProtocolError("The prepared finalization record is invalid.")
    if snapshot["target"] != prepared.get("target") or snapshot["actor"][
        "id"
    ] != prepared.get("actor_id"):
        return _unknown_finalize(
            prepared,
            "finalize_identity_drift",
            "The issue target or actor changed during finalization.",
        )
    if snapshot["issue"]["body"] != operation.get("body"):
        return _unknown_finalize(
            prepared,
            "finalize_readback_mismatch",
            "The finalized issue body was not read back exactly.",
        )
    if (
        _requirements_context_sha256(snapshot)
        != prepared["requirements_context_sha256"]
    ):
        return _unknown_finalize(
            prepared,
            "finalize_requirements_drift",
            "The issue requirements changed during finalization.",
        )
    plan_comments = _role_comments(snapshot, PLAN_MARKERS)
    review_comments = _role_comments(snapshot, REVIEW_MARKERS)
    if len(plan_comments) != 1 or len(review_comments) != 1:
        return _unknown_finalize(
            prepared,
            "finalize_marker_conflict",
            "The canonical plan or review identity changed during finalization.",
        )
    selected = {"P": plan_comments[0], "V": review_comments[0]}
    for role, comment in selected.items():
        source = sources[role]
        if (
            comment["id"] != source["comment_id"]
            or comment["author"]["id"] != prepared["actor_id"]
            or _body_sha256(comment["body"]) != source["body_sha256"]
        ):
            return _unknown_finalize(
                prepared,
                "finalize_source_drift",
                "A sealed plan or review source changed before cleanup.",
            )
    try:
        _verify_issue_source_chain(
            snapshot,
            prepared["state"],
            prepared["state_sha256"],
            selected["P"],
            selected["V"],
            prepared["requirements_sha256"],
        )
    except ProtocolError as error:
        return _unknown_finalize(
            prepared,
            "finalize_source_chain_invalid",
            str(error),
        )
    result = copy.deepcopy(dict(prepared))
    result["status"] = "verified"
    result["deletion_allowlist"] = [
        sources["P"]["comment_id"],
        sources["V"]["comment_id"],
    ]
    result["diagnostics"] = []
    return result


def verify_finalize(value: object) -> dict[str, Any]:
    """Prepare or verify one terminal issue-plan materialization."""
    if not isinstance(value, dict):
        raise ProtocolError("The finalization request must be an object.")
    if frozenset(value) == frozenset({"snapshot", "prepared"}):
        snapshot = _snapshot(value["snapshot"])
        prepared = _validate_prepared_finalize(value["prepared"])
        return _verify_finalize_readback(snapshot, prepared)
    request = _object(
        value,
        "finalization request",
        frozenset({"snapshot", "candidate_body"}),
    )
    snapshot = _snapshot(request["snapshot"])
    candidate = _string(request["candidate_body"], "finalized candidate body")
    if FINALIZE_NAMESPACE_PATTERN.search(candidate) is not None:
        return _withheld_finalize(
            _requirements_sha256(snapshot),
            "candidate_marker",
            "The candidate body already contains a finalization marker.",
        )
    inspection = inspect_snapshot(snapshot)
    if inspection["status"] == "finalized":
        marker_status, marker = _finalized_marker(snapshot["issue"]["body"])
        assert marker_status == "valid" and marker is not None
        plan_comments = _role_comments(snapshot, PLAN_MARKERS)
        review_comments = _role_comments(snapshot, REVIEW_MARKERS)
        remaining: list[str] = []
        for role, comments in (("P", plan_comments), ("V", review_comments)):
            if not comments:
                continue
            matches = [
                comment
                for comment in comments
                if comment["author"]["id"] == snapshot["actor"]["id"]
                and _source_token(comment)["token"] == marker[role]
            ]
            if len(comments) != 1 or len(matches) != 1:
                return _withheld_finalize(
                    marker["R"],
                    "finalized_source_mismatch",
                    "A retained finalized source does not match its sealed identity.",
                )
            remaining.append(matches[0]["id"])
        try:
            if plan_comments and review_comments:
                retained_review = review_exchange.extract_carrier(
                    review_comments[0]["body"]
                )
                _verify_issue_source_chain(
                    snapshot,
                    retained_review["state"],
                    retained_review["state_sha256"],
                    plan_comments[0],
                    review_comments[0],
                    marker["R"],
                )
            elif review_comments:
                retained_review = review_exchange.extract_carrier(
                    review_comments[0]["body"]
                )
                state = retained_review["state"]
                if (
                    state["surface"] != "issue"
                    or state["target"] != _core_target(snapshot)
                    or state["requirements_sha256"] != marker["R"]
                    or state["phase"] != "complete"
                    or state["verdict"] != "GO"
                    or _reviewed_plan_token(review_comments[0]["body"]) != marker["P"]
                ):
                    raise ProtocolError(
                        "The retained review does not match the finalized epoch."
                    )
                _verify_state_authorities(snapshot, state)
        except ProtocolError as error:
            return _withheld_finalize(
                marker["R"], "finalized_source_mismatch", str(error)
            )
        if remaining:
            return {
                **_withheld_finalize(
                    marker["R"],
                    "partial_cleanup",
                    "A sealed intermediate comment remains after finalization.",
                ),
                "status": "partial_cleanup",
                "remaining_comment_ids": remaining,
            }
        return {
            **_withheld_finalize(
                marker["R"],
                "already_finalized",
                "The issue already contains a finalized planning epoch.",
            ),
            "status": "no_change",
        }
    if (
        inspection["status"] != "ready"
        or inspection["next_action"] != "finalize"
        or inspection["state"] is None
        or inspection["state"]["verdict"] != "GO"
        or inspection["state"]["phase"] != "complete"
    ):
        return _withheld_finalize(
            inspection["requirements_sha256"],
            "terminal_ledger_required",
            "Finalization requires one current exact GO terminal ledger.",
        )
    plan = _find_comment(snapshot, inspection["plan"])
    review = _find_comment(snapshot, inspection["review"])
    if plan is None or review is None or plan["id"] == review["id"]:
        return _withheld_finalize(
            inspection["requirements_sha256"],
            "finalize_sources",
            "Finalization requires distinct current plan and review comments.",
        )
    p_source = _source_token(plan)
    v_source = _source_token(review)
    requirements = inspection["requirements_sha256"]
    marker_template = (
        "<!-- HomericIntelligence:finalize-plan "
        f"R={requirements} P={p_source['token']} V={v_source['token']} F=<F> -->\n"
    )
    template = f"{candidate.rstrip()}\n\n{marker_template}"
    final_digest = review_exchange.sha256_text(template)
    rendered_marker = marker_template.replace("F=<F>", f"F={final_digest}", 1)
    body = f"{candidate.rstrip()}\n\n{rendered_marker}"
    marker_status, marker_fields = _finalized_marker(body)
    if marker_status != "valid" or marker_fields != {
        "R": requirements,
        "P": p_source["token"],
        "V": v_source["token"],
        "F": final_digest,
    }:
        return _withheld_finalize(
            requirements,
            "candidate_finalization_invalid",
            "The candidate body cannot contain one exact top-level finalization marker.",
        )
    provider_limit = review_exchange.PROVIDER_BODY_LIMITS[
        snapshot["target"]["provider"]
    ]
    if len(body.encode("utf-8")) > provider_limit:
        raise ProtocolError(
            f"The finalized body exceeds the {snapshot['target']['provider']} body limit."
        )
    operation: dict[str, Any] = {
        "action": "replace_body",
        "expected_issue_body_sha256": _body_sha256(snapshot["issue"]["body"]),
        "body": body,
        "body_sha256": _body_sha256(body),
        "F": final_digest,
    }
    operation["operation_sha256"] = review_exchange.sha256_json(operation)
    requirements_context = _requirements_context_sha256(snapshot)
    state_sha256 = inspection["state_sha256"]
    assert isinstance(state_sha256, str)
    plan_summary = _artifact_summary(plan)
    review_summary = _artifact_summary(review)
    assert plan_summary is not None and review_summary is not None
    return {
        "schema_id": FINALIZE_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "ready",
        "requirements_sha256": requirements,
        "requirements_context_sha256": requirements_context,
        "target": copy.deepcopy(snapshot["target"]),
        "actor_id": snapshot["actor"]["id"],
        "precondition_sha256": _finalize_precondition_sha256(
            target=snapshot["target"],
            actor_id=snapshot["actor"]["id"],
            requirements_sha256=requirements,
            requirements_context_sha256=requirements_context,
            state_sha256=state_sha256,
            plan=plan_summary,
            review=review_summary,
            expected_issue_body_sha256=operation["expected_issue_body_sha256"],
        ),
        "state": inspection["state"],
        "state_sha256": inspection["state_sha256"],
        "sources": {"R": requirements, "P": p_source, "V": v_source},
        "operation": operation,
        "deletion_allowlist": [plan["id"], review["id"]],
        "remaining_comment_ids": [],
        "diagnostics": [],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run one read-only issue-exchange projection."""
    parser = argument_parser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        "inspect",
        "prepare-plan",
        "prepare-review",
        "verify-publication",
        "verify-finalize",
    ):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("input", help="A JSON file, or '-' for standard input.")
    arguments = parser.parse_args(argv)
    try:
        value = review_exchange.parse_json_bytes(
            review_exchange._read_input(arguments.input)
        )
        operations = {
            "inspect": inspect_snapshot,
            "prepare-plan": prepare_plan,
            "prepare-review": prepare_review,
            "verify-publication": verify_publication,
            "verify-finalize": verify_finalize,
        }
        result = operations[arguments.command](value)
        review_exchange.write_utf8_stdout(review_exchange.canonical_json(result) + "\n")
    except ProtocolError as error:
        print(review_exchange._single_line_diagnostic(error), file=sys.stderr)
        return 1
    except OperationalError as error:
        print(review_exchange._single_line_diagnostic(error), file=sys.stderr)
        return 2
    except OSError as error:
        print(review_exchange._single_line_diagnostic(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
