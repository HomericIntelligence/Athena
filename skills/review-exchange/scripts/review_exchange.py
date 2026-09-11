#!/usr/bin/env python3
"""Validate and reduce one bounded two-sided review exchange."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, cast

sys.dont_write_bytecode = True

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

STATE_SCHEMA_ID = "athena.review-exchange.state"
AUTHOR_EVENT_SCHEMA_ID = "athena.review-exchange.author-event"
RESULT_SCHEMA_ID = "athena.review-exchange.reduce-result"
AUTHORITY_SCHEMA_ID = "athena.review-exchange.authority"
SCHEMA_VERSION = 1
ROUND_LIMIT = 5
MAX_FINDINGS = 100
MAX_ACCEPTED_EVENTS = MAX_FINDINGS * ROUND_LIMIT + (2 * ROUND_LIMIT - 1)
MAX_INPUT_BYTES = 1024 * 1024
PROVIDER_BODY_LIMITS = {"github": 65_536, "gitlab": 1_000_000}

HEX_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
FINDING_ID = re.compile(r"F-(?:00[1-9]|0[1-9][0-9]|100)\Z")
NATIVE_FINDING_ID = re.compile(r"native:[A-Za-z0-9._~:/+=-]{1,256}\Z")
CARRIER_PREFIX = "<!-- HomericIntelligence:review-exchange:"
CARRIER_PATTERN = re.compile(
    r"^<!-- HomericIntelligence:review-exchange:v1 "
    r"kind=(state|author-event) sha256=([0-9a-f]{64}) -->$",
    re.MULTILINE,
)

SEVERITIES = frozenset({"critical", "major", "minor", "nit", "FYI"})
DISPOSITIONS = frozenset({"required", "suggestion", "nit", "FYI"})
CATEGORIES = frozenset({"simplification"})
FINDING_STATES = frozenset(
    {
        "open",
        "answered_fix",
        "answered_tradeoff",
        "contested",
        "partial",
        "still_present",
        "countered",
        "resolved",
        "withdrawn",
        "accepted_risk",
        "escalated",
        "nonblocking",
    }
)
ACTIVE_REQUIRED_STATES = frozenset(
    {
        "open",
        "answered_fix",
        "answered_tradeoff",
        "contested",
        "partial",
        "still_present",
        "countered",
        "escalated",
    }
)
ARTIFACT_TERMINAL_STATES = frozenset({"resolved", "withdrawn", "accepted_risk"})
AUTHOR_ACTIONS = frozenset({"fix", "fix_with_tradeoff", "contest", "risk_acceptance"})
REVIEWER_ACTIONS = frozenset(
    {
        "resolve",
        "partial",
        "still_present",
        "withdraw",
        "accept",
        "counter",
        "refute",
        "escalate",
    }
)
INTRODUCTIONS = frozenset(
    {
        "initial",
        "introduced_by_correction",
        "new_evidence",
        "missed_high_risk",
        "missed_security",
        "missed_correctness",
        "nonblocking_follow_up",
    }
)
STOP_REASONS = frozenset(
    {
        "closure_conflict",
        "replacement_blocker",
        "scope_growth_without_progress",
        "no_consensus",
        "requirements_reframe",
    }
)


class ProtocolError(ValueError):
    """A supplied record violates the review-exchange protocol."""


class OperationalError(RuntimeError):
    """The helper could not read or write its requested local stream."""


def canonical_json(value: object) -> str:
    """Return the canonical JSON representation used for all digests."""
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        encoded.encode("utf-8")
        return encoded
    except (TypeError, UnicodeEncodeError, ValueError) as error:
        raise ProtocolError("The value cannot be encoded as canonical JSON.") from error


def sha256_json(value: object) -> str:
    """Hash one canonical JSON value."""
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    """Hash one exact UTF-8 text value."""
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProtocolError("The text is not valid UTF-8.") from error
    return sha256(encoded).hexdigest()


def _reject_constant(value: str) -> NoReturn:
    raise ProtocolError(f"JSON contains a non-finite number: {value}.")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(f"JSON contains the duplicate key '{key}'.")
        result[key] = value
    return result


def parse_json_bytes(content: bytes) -> Any:
    """Parse bounded UTF-8 JSON and reject ambiguous JSON features."""
    if len(content) > MAX_INPUT_BYTES:
        raise ProtocolError("The input is larger than 1 MiB.")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProtocolError("The input is not valid UTF-8.") from error
    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        canonical_json(value)
        return value
    except ProtocolError:
        raise
    except (ValueError, RecursionError) as error:
        raise ProtocolError("The input is not valid bounded JSON.") from error


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


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"{name} must be a nonempty string.")
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


def _integer(
    value: object, name: str, *, minimum: int = 0, maximum: int | None = None
) -> int:
    if type(value) is not int or value < minimum:
        raise ProtocolError(f"{name} must be an integer of at least {minimum}.")
    if maximum is not None and value > maximum:
        raise ProtocolError(f"{name} must not be more than {maximum}.")
    return value


def _boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ProtocolError(f"{name} must be a Boolean.")
    return value


def _enum(value: object, name: str, allowed: frozenset[str]) -> str:
    text = _string(value, name)
    if text not in allowed:
        raise ProtocolError(f"{name} has the unsupported value '{text}'.")
    return text


def _strings(value: object, name: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ProtocolError(f"{name} must be a list.")
    result = [_string(item, f"{name} item") for item in value]
    if not allow_empty and not result:
        raise ProtocolError(f"{name} must not be empty.")
    if len(result) != len(set(result)):
        raise ProtocolError(f"{name} contains a duplicate value.")
    return result


def _scope(value: object, name: str) -> list[str]:
    return sorted(_strings(value, name))


def _target(value: object, name: str = "target") -> dict[str, Any]:
    target = _object(
        value,
        name,
        frozenset({"provider", "repository", "number", "url"}),
    )
    provider = _enum(
        target["provider"], f"{name}.provider", frozenset(PROVIDER_BODY_LIMITS)
    )
    return {
        "provider": provider,
        "repository": _string(target["repository"], f"{name}.repository"),
        "number": _integer(target["number"], f"{name}.number", minimum=1),
        "url": _string(target["url"], f"{name}.url"),
    }


def _artifact(value: object, name: str = "artifact_binding") -> dict[str, str]:
    artifact = _object(
        value,
        name,
        frozenset({"revision", "sha256", "visible_content_sha256"}),
    )
    digest = _digest(artifact["sha256"], f"{name}.sha256")
    visible = _digest(
        artifact["visible_content_sha256"], f"{name}.visible_content_sha256"
    )
    assert digest is not None and visible is not None
    return {
        "revision": _string(artifact["revision"], f"{name}.revision"),
        "sha256": digest,
        "visible_content_sha256": visible,
    }


def _authority(value: object, name: str) -> dict[str, str]:
    authority = _object(value, name, frozenset({"reference", "sha256"}))
    digest = _digest(authority["sha256"], f"{name}.sha256")
    assert digest is not None
    return {
        "reference": _string(authority["reference"], f"{name}.reference"),
        "sha256": digest,
    }


def _finding_input(value: object, name: str) -> dict[str, Any]:
    finding = _object(
        value,
        name,
        frozenset(
            {
                "id",
                "severity",
                "disposition",
                "category",
                "material_architecture",
                "location",
                "impact",
                "evidence",
                "closure_condition",
                "introduction",
            }
        ),
    )
    finding_id = _string(finding["id"], f"{name}.id")
    is_native = NATIVE_FINDING_ID.fullmatch(finding_id) is not None
    if FINDING_ID.fullmatch(finding_id) is None and not is_native:
        raise ProtocolError(
            f"{name}.id is not a stable F-001 through F-100 or native value."
        )
    severity = _enum(finding["severity"], f"{name}.severity", SEVERITIES)
    disposition = _enum(finding["disposition"], f"{name}.disposition", DISPOSITIONS)
    category = _nullable_string(finding["category"], f"{name}.category")
    if category is not None and category not in CATEGORIES:
        raise ProtocolError(f"{name}.category has the unsupported value '{category}'.")
    architecture = _boolean(
        finding["material_architecture"], f"{name}.material_architecture"
    )
    if (
        severity in {"critical", "major"} or architecture
    ) and disposition != "required":
        raise ProtocolError(f"{name} must have the required disposition.")
    if severity == "minor" and disposition not in {"required", "suggestion"}:
        raise ProtocolError(f"{name} must have the required or suggestion disposition.")
    if severity in {"nit", "FYI"} and disposition != severity:
        raise ProtocolError(f"{name} must use its matching nonblocking disposition.")
    if is_native and disposition != "required":
        raise ProtocolError(f"{name} is a legacy native finding and must be required.")
    closure = _nullable_string(
        finding["closure_condition"], f"{name}.closure_condition"
    )
    if disposition == "required" and closure is None:
        raise ProtocolError(f"{name} requires an observable closure condition.")
    if disposition != "required" and closure is not None:
        raise ProtocolError(f"{name} cannot make a nonblocking closure condition.")
    return {
        "id": finding_id,
        "severity": severity,
        "disposition": disposition,
        "category": category,
        "material_architecture": architecture,
        "location": _string(finding["location"], f"{name}.location"),
        "impact": _string(finding["impact"], f"{name}.impact"),
        "evidence": _strings(finding["evidence"], f"{name}.evidence"),
        "closure_condition": closure,
        "introduction": _enum(
            finding["introduction"], f"{name}.introduction", INTRODUCTIONS
        ),
    }


def _author_response(value: object, name: str) -> dict[str, Any]:
    response = _object(
        value,
        name,
        frozenset({"finding_id", "kind", "evidence", "tradeoff"}),
    )
    kind = _enum(response["kind"], f"{name}.kind", AUTHOR_ACTIONS)
    tradeoff = _nullable_string(response["tradeoff"], f"{name}.tradeoff")
    if kind in {"fix_with_tradeoff", "risk_acceptance"} and tradeoff is None:
        raise ProtocolError(f"{name} requires a trade-off or residual-risk statement.")
    if kind not in {"fix_with_tradeoff", "risk_acceptance"} and tradeoff is not None:
        raise ProtocolError(f"{name} has an inapplicable trade-off statement.")
    return {
        "finding_id": _string(response["finding_id"], f"{name}.finding_id"),
        "kind": kind,
        "evidence": _strings(response["evidence"], f"{name}.evidence"),
        "tradeoff": tradeoff,
    }


def _reviewer_response(value: object, name: str) -> dict[str, Any]:
    response = _object(
        value,
        name,
        frozenset({"finding_id", "kind", "evidence", "closure_condition"}),
    )
    kind = _enum(response["kind"], f"{name}.kind", REVIEWER_ACTIONS)
    closure = _nullable_string(
        response["closure_condition"], f"{name}.closure_condition"
    )
    if kind == "counter" and closure is None:
        raise ProtocolError(f"{name} must supply a revised closure condition.")
    if kind != "counter" and closure is not None:
        raise ProtocolError(f"{name} has an inapplicable closure condition.")
    return {
        "finding_id": _string(response["finding_id"], f"{name}.finding_id"),
        "kind": kind,
        "evidence": _strings(response["evidence"], f"{name}.evidence"),
        "closure_condition": closure,
    }


def _unique_responses(
    value: object,
    name: str,
    parser: Callable[[object, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ProtocolError(f"{name} must be a list.")
    responses = [parser(item, f"{name}[{index}]") for index, item in enumerate(value)]
    ids = [response["finding_id"] for response in responses]
    if len(ids) != len(set(ids)):
        raise ProtocolError(f"{name} contains a duplicate finding response.")
    return responses


def _human_decisions(
    value: object, name: str, *, allow_empty: bool = False
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or (not allow_empty and not value):
        requirement = (
            "must be a list" if not isinstance(value, list) else "must not be empty"
        )
        raise ProtocolError(f"{name} {requirement}.")
    decisions: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        decision = _object(
            raw,
            f"{name}[{index}]",
            frozenset({"finding_id", "kind", "closure_condition"}),
        )
        kind = _enum(
            decision["kind"],
            f"{name}[{index}].kind",
            frozenset({"accept_risk", "select_closure"}),
        )
        closure = _nullable_string(
            decision["closure_condition"],
            f"{name}[{index}].closure_condition",
        )
        if kind == "select_closure" and closure is None:
            raise ProtocolError("A selected closure must contain a condition.")
        if kind == "accept_risk" and closure is not None:
            raise ProtocolError("Risk acceptance cannot replace the closure condition.")
        decisions.append(
            {
                "finding_id": _string(
                    decision["finding_id"], f"{name}[{index}].finding_id"
                ),
                "kind": kind,
                "closure_condition": closure,
            }
        )
    ids = [decision["finding_id"] for decision in decisions]
    if len(ids) != len(set(ids)):
        raise ProtocolError(f"{name} contains a duplicate finding.")
    return decisions


def _validate_introduction_policy(
    finding: Mapping[str, Any], introduced_round: int
) -> None:
    introduction = finding["introduction"]
    disposition = finding["disposition"]
    if introduced_round == 1:
        if introduction != "initial":
            raise ProtocolError("Round 1 findings must use the initial basis.")
        return
    if introduction == "initial":
        raise ProtocolError("A later finding must identify its new evidence basis.")
    if introduction == "nonblocking_follow_up" and disposition == "required":
        raise ProtocolError("A low-risk follow-up cannot be required.")
    if (
        introduction == "missed_high_risk"
        and finding["severity"] not in {"critical", "major"}
        and not finding["material_architecture"]
    ):
        raise ProtocolError("A missed late finding must be high risk.")
    if (
        introduction in {"missed_security", "missed_correctness"}
        and disposition != "required"
    ):
        raise ProtocolError("A late security or correctness finding must be required.")
    if disposition != "required" and introduction != "nonblocking_follow_up":
        raise ProtocolError(
            "A later nonblocking finding must be a nonblocking follow-up."
        )


def _new_findings(
    value: object,
    name: str,
    *,
    existing_count: int,
    round_number: int,
    existing_ids: Sequence[str] = (),
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ProtocolError(f"{name} must be a list.")
    if existing_count + len(value) > MAX_FINDINGS:
        raise ProtocolError("One exchange cannot contain more than 100 findings.")
    findings = [
        _finding_input(item, f"{name}[{index}]") for index, item in enumerate(value)
    ]
    seen = set(existing_ids)
    next_number = (
        sum(FINDING_ID.fullmatch(item) is not None for item in existing_ids) + 1
    )
    if not existing_ids:
        next_number = existing_count + 1
    for finding in findings:
        finding_id = finding["id"]
        if finding_id in seen:
            raise ProtocolError(
                "A finding identifier cannot be reused in one exchange."
            )
        seen.add(finding_id)
        if FINDING_ID.fullmatch(finding_id) is not None:
            expected = f"F-{next_number:03d}"
            if finding_id != expected:
                raise ProtocolError(
                    f"Finding identifiers must be consecutive; expected '{expected}'."
                )
            next_number += 1
        elif round_number != 1:
            raise ProtocolError(
                "A legacy native finding can be adopted only in round 1."
            )
        _validate_introduction_policy(finding, round_number)
    return findings


def _state_finding(value: object, name: str) -> dict[str, Any]:
    finding = _object(
        value,
        name,
        frozenset(
            {
                "id",
                "severity",
                "disposition",
                "category",
                "material_architecture",
                "location",
                "impact",
                "evidence",
                "closure_condition",
                "closure_revision",
                "introduction",
                "introduced_round",
                "state",
                "author_response",
                "reviewer_response",
                "authority_receipt",
            }
        ),
    )
    basic = _finding_input(
        {
            key: finding[key]
            for key in (
                "id",
                "severity",
                "disposition",
                "category",
                "material_architecture",
                "location",
                "impact",
                "evidence",
                "closure_condition",
                "introduction",
            )
        },
        name,
    )
    state = _enum(finding["state"], f"{name}.state", FINDING_STATES)
    if basic["disposition"] != "required" and state != "nonblocking":
        raise ProtocolError(f"{name} is nonblocking but has a blocking state.")
    author = finding["author_response"]
    if author is not None:
        author_record = _object(
            author,
            f"{name}.author_response",
            frozenset({"kind", "evidence", "tradeoff", "artifact_revision"}),
        )
        parsed_author = _author_response(
            {
                "finding_id": basic["id"],
                "kind": author_record["kind"],
                "evidence": author_record["evidence"],
                "tradeoff": author_record["tradeoff"],
            },
            f"{name}.author_response",
        )
        author = {
            "kind": parsed_author["kind"],
            "evidence": parsed_author["evidence"],
            "tradeoff": parsed_author["tradeoff"],
            "artifact_revision": _string(
                author_record["artifact_revision"],
                f"{name}.author_response.artifact_revision",
            ),
        }
    reviewer = finding["reviewer_response"]
    if reviewer is not None:
        reviewer_record = _object(
            reviewer,
            f"{name}.reviewer_response",
            frozenset({"kind", "evidence", "closure_condition", "round"}),
        )
        parsed_reviewer = _reviewer_response(
            {
                "finding_id": basic["id"],
                "kind": reviewer_record["kind"],
                "evidence": reviewer_record["evidence"],
                "closure_condition": reviewer_record["closure_condition"],
            },
            f"{name}.reviewer_response",
        )
        reviewer = {
            "kind": parsed_reviewer["kind"],
            "evidence": parsed_reviewer["evidence"],
            "closure_condition": parsed_reviewer["closure_condition"],
            "round": _integer(
                reviewer_record["round"],
                f"{name}.reviewer_response.round",
                minimum=1,
                maximum=ROUND_LIMIT,
            ),
        }
    authority = finding["authority_receipt"]
    if authority is not None:
        authority = _authority(authority, f"{name}.authority_receipt")
    if state == "accepted_risk" and authority is None:
        raise ProtocolError(f"{name} accepted risk without an authority receipt.")
    return {
        **basic,
        "closure_revision": _integer(
            finding["closure_revision"], f"{name}.closure_revision", minimum=0
        ),
        "introduced_round": _integer(
            finding["introduced_round"],
            f"{name}.introduced_round",
            minimum=1,
            maximum=ROUND_LIMIT,
        ),
        "state": state,
        "author_response": author,
        "reviewer_response": reviewer,
        "authority_receipt": authority,
    }


def _progress(value: object, name: str) -> dict[str, Any]:
    progress = _object(
        value,
        name,
        frozenset(
            {
                "round",
                "artifact_revision",
                "scope",
                "scope_size",
                "required_remaining",
                "accepted_event_sha256",
            }
        ),
    )
    digest = _digest(progress["accepted_event_sha256"], f"{name}.accepted_event_sha256")
    assert digest is not None
    scope = _scope(progress["scope"], f"{name}.scope")
    scope_size = _integer(progress["scope_size"], f"{name}.scope_size")
    if scope_size != len(scope):
        raise ProtocolError(f"{name}.scope_size does not match its scope set.")
    return {
        "round": _integer(
            progress["round"], f"{name}.round", minimum=1, maximum=ROUND_LIMIT
        ),
        "artifact_revision": _string(
            progress["artifact_revision"], f"{name}.artifact_revision"
        ),
        "scope": scope,
        "scope_size": scope_size,
        "required_remaining": _integer(
            progress["required_remaining"],
            f"{name}.required_remaining",
            maximum=MAX_FINDINGS,
        ),
        "accepted_event_sha256": digest,
    }


def _active_required(findings: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        finding
        for finding in findings
        if finding["disposition"] == "required"
        and finding["state"] in ACTIVE_REQUIRED_STATES
    ]


def _merge_unique_evidence(target: list[str], additions: Sequence[str]) -> None:
    known = set(target)
    for evidence in additions:
        if evidence not in known:
            target.append(evidence)
            known.add(evidence)


def _validate_finding_state(finding: Mapping[str, Any], round_number: int) -> None:
    """Reject a stored finding that no legal transition can produce."""
    state = finding["state"]
    required = finding["disposition"] == "required"
    author = finding["author_response"]
    reviewer = finding["reviewer_response"]
    authority = finding["authority_receipt"]
    introduced_round = finding["introduced_round"]
    closure_revision = finding["closure_revision"]

    if introduced_round > round_number:
        raise ProtocolError("A finding cannot be introduced in a future round.")
    _validate_introduction_policy(finding, introduced_round)
    if not required:
        if (
            state != "nonblocking"
            or closure_revision != 0
            or author is not None
            or reviewer is not None
            or authority is not None
        ):
            raise ProtocolError("A nonblocking finding has blocking transition state.")
        return
    if state == "nonblocking" or closure_revision < 1:
        raise ProtocolError("A required finding cannot have nonblocking state.")
    if reviewer is not None and not (
        introduced_round < reviewer["round"] <= round_number
    ):
        raise ProtocolError("A reviewer response has an invalid reviewer round.")
    if authority is not None and state != "accepted_risk" and closure_revision < 2:
        raise ProtocolError(
            "An authority receipt does not follow an authoritative closure selection."
        )

    author_kind = None if author is None else author["kind"]
    reviewer_kind = None if reviewer is None else reviewer["kind"]
    evidence_ledger = set(finding["evidence"])
    if author is not None and not set(author["evidence"]).issubset(evidence_ledger):
        raise ProtocolError("Stored author evidence is absent from the finding ledger.")
    if reviewer is not None and not set(reviewer["evidence"]).issubset(evidence_ledger):
        raise ProtocolError(
            "Stored reviewer evidence is absent from the finding ledger."
        )
    if (
        reviewer_kind == "counter"
        and reviewer["closure_condition"] != finding["closure_condition"]
    ):
        raise ProtocolError("A stored counter does not match the revised closure.")
    legal = False
    if state == "open":
        legal = author is None and reviewer is None and authority is None
    elif state == "answered_fix":
        legal = author_kind == "fix" and reviewer is None
    elif state == "answered_tradeoff":
        legal = (
            author_kind in {"fix_with_tradeoff", "risk_acceptance"} and reviewer is None
        )
    elif state == "contested":
        legal = author_kind == "contest" and reviewer is None
    elif state == "partial":
        legal = (
            author_kind in {"fix", "fix_with_tradeoff"} and reviewer_kind == "partial"
        )
    elif state == "still_present":
        legal = (
            author_kind in {"fix", "fix_with_tradeoff", "risk_acceptance"}
            and reviewer_kind == "still_present"
        ) or (author_kind == "contest" and reviewer_kind == "refute")
        legal = legal or (
            author is None
            and reviewer is None
            and authority is not None
            and closure_revision >= 2
        )
    elif state == "countered":
        legal = (
            author_kind == "contest"
            and reviewer_kind == "counter"
            and closure_revision >= 2
        )
    elif state == "resolved":
        legal = (
            author_kind in {"fix", "fix_with_tradeoff"} and reviewer_kind == "resolve"
        )
    elif state == "withdrawn":
        legal = (author_kind == "contest" and reviewer_kind == "accept") or (
            author_kind != "contest"
            and author is not None
            and reviewer_kind == "withdraw"
        )
    elif state == "accepted_risk":
        legal = (
            author_kind == "risk_acceptance"
            and authority is not None
            and reviewer_kind in {None, "still_present", "escalate"}
        )
    elif state == "escalated":
        legal = author is not None and reviewer_kind == "escalate"
    if not legal:
        raise ProtocolError(
            "The stored finding state has no legal response transition."
        )


def _validate_state(value: object) -> dict[str, Any]:
    state = _object(
        value,
        "state",
        frozenset(
            {
                "exchange_id",
                "surface",
                "target",
                "requirements_sha256",
                "round",
                "round_limit",
                "phase",
                "artifact_binding",
                "scope",
                "prior_state_sha256",
                "accepted_event_sha256",
                "accepted_events",
                "supersedes_state_sha256",
                "supersession_authority_receipt",
                "coverage_complete",
                "go_eligible",
                "progress",
                "findings",
                "verdict",
                "next_action",
            }
        ),
    )
    surface = _enum(
        state["surface"],
        "state.surface",
        frozenset({"issue", "pull_request"}),
    )
    artifact = _artifact(state["artifact_binding"], "state.artifact_binding")
    scope = _scope(state["scope"], "state.scope")
    findings_value = state["findings"]
    if not isinstance(findings_value, list):
        raise ProtocolError("state.findings must be a list.")
    if len(findings_value) > MAX_FINDINGS:
        raise ProtocolError("One exchange cannot contain more than 100 findings.")
    findings = [
        _state_finding(item, f"state.findings[{index}]")
        for index, item in enumerate(findings_value)
    ]
    identifiers = [finding["id"] for finding in findings]
    if len(identifiers) != len(set(identifiers)):
        raise ProtocolError("State finding identifiers are not unique.")
    next_number = 1
    for finding in findings:
        finding_id = finding["id"]
        if FINDING_ID.fullmatch(finding_id) is not None:
            if finding_id != f"F-{next_number:03d}":
                raise ProtocolError(
                    "State finding identifiers are not stable and consecutive."
                )
            next_number += 1
        elif (
            surface != "pull_request"
            or finding["introduced_round"] != 1
            or finding["introduction"] != "initial"
        ):
            raise ProtocolError(
                "A legacy native finding must be an initial pull-request finding."
            )
    progress_value = state["progress"]
    if not isinstance(progress_value, list):
        raise ProtocolError("state.progress must be a list.")
    progress = [
        _progress(item, f"state.progress[{index}]")
        for index, item in enumerate(progress_value)
    ]
    round_number = _integer(
        state["round"], "state.round", minimum=1, maximum=ROUND_LIMIT
    )
    for finding in findings:
        _validate_finding_state(finding, round_number)
    if len(progress) != round_number or [item["round"] for item in progress] != list(
        range(1, round_number + 1)
    ):
        raise ProtocolError(
            "State progress must contain each reviewer round exactly once."
        )
    phase = _enum(
        state["phase"],
        "state.phase",
        frozenset(
            {
                "awaiting_author",
                "awaiting_reviewer",
                "awaiting_evidence",
                "complete",
                "decision_required",
            }
        ),
    )
    go_eligible = _boolean(state["go_eligible"], "state.go_eligible")
    verdict = _enum(
        state["verdict"],
        "state.verdict",
        frozenset({"GO", "NO-GO", "CONDITIONAL GO"}),
    )
    next_action = _enum(
        state["next_action"],
        "state.next_action",
        frozenset(
            {
                "author_response",
                "review_assessment",
                "finalize",
                "human_decision",
                "none",
            }
        ),
    )
    expected = {
        "awaiting_author": ("NO-GO", "author_response"),
        "awaiting_reviewer": ("NO-GO", "review_assessment"),
        "awaiting_evidence": ("NO-GO", "review_assessment"),
        "complete": (("GO", "finalize") if go_eligible else ("CONDITIONAL GO", "none")),
        "decision_required": ("NO-GO", "human_decision"),
    }[phase]
    if (verdict, next_action) != expected:
        raise ProtocolError("State phase, verdict, and next action do not agree.")
    coverage = _boolean(state["coverage_complete"], "state.coverage_complete")
    active = _active_required(findings)
    if surface == "issue" and not go_eligible:
        raise ProtocolError("An issue review state must be eligible for GO.")
    if phase == "complete" and (active or not coverage):
        raise ProtocolError("A complete state has an active finding or coverage gap.")
    if phase == "awaiting_author" and not active:
        raise ProtocolError(
            "An author response was requested without a required finding."
        )
    if phase == "awaiting_evidence" and (active or coverage):
        raise ProtocolError("The evidence-wait state does not match current coverage.")
    active_states = {finding["state"] for finding in active}
    if phase == "awaiting_author" and not active_states.issubset(
        {"open", "partial", "still_present", "countered"}
    ):
        raise ProtocolError(
            "The author-wait state contains an unanswered reviewer transition."
        )
    if phase == "awaiting_reviewer" and (
        not active_states
        or not active_states.issubset(
            {"answered_fix", "answered_tradeoff", "contested"}
        )
    ):
        raise ProtocolError(
            "The reviewer-wait state contains a finding without an author answer."
        )
    if phase != "decision_required" and "escalated" in active_states:
        raise ProtocolError("An escalated finding requires a human decision.")
    if round_number == ROUND_LIMIT and phase not in {"complete", "decision_required"}:
        raise ProtocolError("Round 5 cannot request another automated exchange step.")
    prior = _digest(
        state["prior_state_sha256"], "state.prior_state_sha256", nullable=True
    )
    accepted = _digest(state["accepted_event_sha256"], "state.accepted_event_sha256")
    accepted_events_value = state["accepted_events"]
    if not isinstance(accepted_events_value, list) or not accepted_events_value:
        raise ProtocolError("State accepted events must be a nonempty list.")
    if len(accepted_events_value) > MAX_ACCEPTED_EVENTS:
        raise ProtocolError(
            f"State cannot contain more than {MAX_ACCEPTED_EVENTS} accepted events."
        )
    accepted_events = copy.deepcopy(accepted_events_value)
    supersedes = _digest(
        state["supersedes_state_sha256"],
        "state.supersedes_state_sha256",
        nullable=True,
    )
    supersession_authority = (
        None
        if state["supersession_authority_receipt"] is None
        else _authority(
            state["supersession_authority_receipt"],
            "state.supersession_authority_receipt",
        )
    )
    if (supersedes is None) != (supersession_authority is None):
        raise ProtocolError(
            "A superseding exchange must include its authority receipt."
        )
    requirements = _digest(state["requirements_sha256"], "state.requirements_sha256")
    assert accepted is not None and requirements is not None
    if (
        _integer(state["round_limit"], "state.round_limit", minimum=ROUND_LIMIT)
        != ROUND_LIMIT
    ):
        raise ProtocolError("The review round limit must be five.")
    latest_progress = progress[-1]
    if accepted == latest_progress["accepted_event_sha256"]:
        if scope != latest_progress["scope"]:
            raise ProtocolError(
                "The current scope does not match the latest reviewer progress."
            )
        if artifact["revision"] != latest_progress["artifact_revision"]:
            raise ProtocolError(
                "The current artifact does not match the latest reviewer progress."
            )
        if len(active) != latest_progress["required_remaining"]:
            raise ProtocolError(
                "The current findings do not match the latest reviewer progress."
            )
    result = {
        "exchange_id": _string(state["exchange_id"], "state.exchange_id"),
        "surface": surface,
        "target": _target(state["target"], "state.target"),
        "requirements_sha256": requirements,
        "round": round_number,
        "round_limit": ROUND_LIMIT,
        "phase": phase,
        "artifact_binding": artifact,
        "scope": scope,
        "prior_state_sha256": prior,
        "accepted_event_sha256": accepted,
        "accepted_events": accepted_events,
        "supersedes_state_sha256": supersedes,
        "supersession_authority_receipt": supersession_authority,
        "coverage_complete": coverage,
        "go_eligible": go_eligible,
        "progress": progress,
        "findings": findings,
        "verdict": verdict,
        "next_action": next_action,
    }
    _verify_state_history(result)
    return result


def _validate_author_event_record(value: object) -> dict[str, Any]:
    event = _object(
        value,
        "author event",
        frozenset(
            {
                "event_type",
                "exchange_id",
                "prior_state_sha256",
                "target",
                "requirements_sha256",
                "artifact_binding",
                "scope",
                "scope_change_reason",
                "responses",
            }
        ),
    )
    if event["event_type"] != "author_response":
        raise ProtocolError("The author-event envelope has the wrong event type.")
    prior = _digest(
        event["prior_state_sha256"], "author event prior state", nullable=True
    )
    requirements = _digest(
        event["requirements_sha256"], "author event requirements digest"
    )
    assert requirements is not None
    return {
        "event_type": "author_response",
        "exchange_id": _string(event["exchange_id"], "author event exchange ID"),
        "prior_state_sha256": prior,
        "target": _target(event["target"], "author event target"),
        "requirements_sha256": requirements,
        "artifact_binding": _artifact(
            event["artifact_binding"], "author event artifact binding"
        ),
        "scope": _scope(event["scope"], "author event scope"),
        "scope_change_reason": _nullable_string(
            event["scope_change_reason"], "author event scope change reason"
        ),
        "responses": _unique_responses(
            event["responses"], "author event responses", _author_response
        ),
    }


def make_envelope(state: object, schema_id: str = STATE_SCHEMA_ID) -> dict[str, Any]:
    """Build one canonical envelope after full semantic validation."""
    if type(state) is not dict:
        raise ProtocolError("The envelope state must be an object.")
    state_object = cast(dict[str, Any], state)
    if schema_id == STATE_SCHEMA_ID:
        validated = _validate_state(dict(state_object))
    elif schema_id == AUTHOR_EVENT_SCHEMA_ID:
        validated = _validate_author_event_record(dict(state_object))
    else:
        raise ProtocolError("The envelope schema identifier is not supported.")
    return {
        "schema_id": schema_id,
        "schema_version": SCHEMA_VERSION,
        "state": validated,
        "state_sha256": sha256_json(validated),
    }


def verify_envelope(value: object) -> dict[str, Any]:
    """Validate one state or author-event envelope and its digest."""
    envelope = _object(
        value,
        "envelope",
        frozenset({"schema_id", "schema_version", "state", "state_sha256"}),
    )
    schema_id = _enum(
        envelope["schema_id"],
        "envelope.schema_id",
        frozenset({STATE_SCHEMA_ID, AUTHOR_EVENT_SCHEMA_ID}),
    )
    if (
        _integer(envelope["schema_version"], "envelope.schema_version", minimum=1)
        != SCHEMA_VERSION
    ):
        raise ProtocolError("The envelope schema version is not supported.")
    canonical = make_envelope(envelope["state"], schema_id)
    supplied = _digest(envelope["state_sha256"], "envelope.state_sha256")
    if supplied != canonical["state_sha256"]:
        raise ProtocolError("The envelope state digest does not match its state.")
    return canonical


def _initial_review_event(value: object) -> dict[str, Any]:
    event = _object(
        value,
        "initial reviewer assessment",
        frozenset(
            {
                "event_type",
                "exchange_id",
                "prior_state_sha256",
                "round",
                "surface",
                "target",
                "requirements_sha256",
                "supersedes_state_sha256",
                "artifact_binding",
                "scope",
                "coverage_complete",
                "go_eligible",
                "responses",
                "new_findings",
                "stop_reason",
            }
        ),
    )
    if event["event_type"] != "reviewer_assessment":
        raise ProtocolError("An exchange must start with a reviewer assessment.")
    if event["prior_state_sha256"] is not None:
        raise ProtocolError("An initial assessment cannot name a prior state.")
    if event["responses"] != []:
        raise ProtocolError("An initial assessment cannot reconcile prior findings.")
    requirements = _digest(event["requirements_sha256"], "initial requirements digest")
    supersedes = _digest(
        event["supersedes_state_sha256"],
        "initial superseded state digest",
        nullable=True,
    )
    if supersedes is not None:
        raise ProtocolError("A fresh exchange cannot claim an unverified supersession.")
    assert requirements is not None
    surface = _enum(
        event["surface"],
        "initial surface",
        frozenset({"issue", "pull_request"}),
    )
    new_findings = _new_findings(
        event["new_findings"],
        "initial findings",
        existing_count=0,
        round_number=1,
    )
    if surface != "pull_request" and any(
        NATIVE_FINDING_ID.fullmatch(finding["id"]) is not None
        for finding in new_findings
    ):
        raise ProtocolError("A legacy native finding is valid only for a pull request.")
    return {
        "event_type": "reviewer_assessment",
        "exchange_id": _string(event["exchange_id"], "initial exchange ID"),
        "prior_state_sha256": None,
        "round": _integer(
            event["round"], "initial round", minimum=1, maximum=ROUND_LIMIT
        ),
        "surface": surface,
        "target": _target(event["target"]),
        "requirements_sha256": requirements,
        "supersedes_state_sha256": None,
        "artifact_binding": _artifact(event["artifact_binding"]),
        "scope": _scope(event["scope"], "initial scope"),
        "coverage_complete": _boolean(
            event["coverage_complete"], "initial coverage completeness"
        ),
        "go_eligible": _boolean(event["go_eligible"], "initial GO eligibility"),
        "responses": [],
        "new_findings": new_findings,
        "stop_reason": (
            None
            if event["stop_reason"] is None
            else _enum(event["stop_reason"], "initial stop reason", STOP_REASONS)
        ),
    }


def _reframe_event(value: object) -> dict[str, Any]:
    event = _object(
        value,
        "requirements reframe",
        frozenset(
            {
                "event_type",
                "exchange_id",
                "prior_state_sha256",
                "round",
                "surface",
                "target",
                "requirements_sha256",
                "supersedes_state_sha256",
                "superseded_exchange_ids",
                "authority_receipt",
                "artifact_binding",
                "scope",
                "coverage_complete",
                "go_eligible",
                "responses",
                "new_findings",
                "stop_reason",
            }
        ),
    )
    if event["event_type"] != "reframe":
        raise ProtocolError("The event is not a requirements reframe.")
    prior = _digest(event["prior_state_sha256"], "reframe prior state digest")
    supersedes = _digest(
        event["supersedes_state_sha256"], "reframe superseded state digest"
    )
    assert prior is not None and supersedes is not None
    superseded_exchange_ids = _strings(
        event["superseded_exchange_ids"],
        "reframe superseded exchange IDs",
    )
    exchange_id = _string(event["exchange_id"], "reframe exchange ID")
    if exchange_id in superseded_exchange_ids:
        raise ProtocolError("A reframe cannot reuse a superseded exchange identity.")
    authority = _authority(event["authority_receipt"], "reframe authority receipt")
    initial_event = dict(event)
    del initial_event["authority_receipt"]
    del initial_event["superseded_exchange_ids"]
    initial = _initial_review_event(
        {
            **initial_event,
            "event_type": "reviewer_assessment",
            "prior_state_sha256": None,
            "supersedes_state_sha256": None,
        }
    )
    return {
        **initial,
        "event_type": "reframe",
        "prior_state_sha256": prior,
        "supersedes_state_sha256": supersedes,
        "superseded_exchange_ids": superseded_exchange_ids,
        "authority_receipt": authority,
    }


def _continued_author_event(value: object) -> dict[str, Any]:
    event = _object(
        value,
        "author response",
        frozenset(
            {
                "event_type",
                "exchange_id",
                "prior_state_sha256",
                "artifact_binding",
                "scope",
                "scope_change_reason",
                "responses",
            }
        ),
    )
    if event["event_type"] != "author_response":
        raise ProtocolError("The event is not an author response.")
    prior = _digest(event["prior_state_sha256"], "author prior state digest")
    assert prior is not None
    return {
        "event_type": "author_response",
        "exchange_id": _string(event["exchange_id"], "author exchange ID"),
        "prior_state_sha256": prior,
        "artifact_binding": _artifact(event["artifact_binding"]),
        "scope": _scope(event["scope"], "author scope"),
        "scope_change_reason": _nullable_string(
            event["scope_change_reason"], "author scope change reason"
        ),
        "responses": _unique_responses(
            event["responses"], "author responses", _author_response
        ),
    }


def _continued_review_event(
    value: object, existing_findings: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    event = _object(
        value,
        "corrective reviewer assessment",
        frozenset(
            {
                "event_type",
                "exchange_id",
                "prior_state_sha256",
                "round",
                "artifact_binding",
                "scope",
                "coverage_complete",
                "go_eligible",
                "responses",
                "new_findings",
                "stop_reason",
            }
        ),
    )
    if event["event_type"] != "reviewer_assessment":
        raise ProtocolError("The event is not a reviewer assessment.")
    prior = _digest(event["prior_state_sha256"], "reviewer prior state digest")
    assert prior is not None
    round_number = _integer(
        event["round"], "reviewer round", minimum=1, maximum=ROUND_LIMIT
    )
    return {
        "event_type": "reviewer_assessment",
        "exchange_id": _string(event["exchange_id"], "reviewer exchange ID"),
        "prior_state_sha256": prior,
        "round": round_number,
        "artifact_binding": _artifact(event["artifact_binding"]),
        "scope": _scope(event["scope"], "reviewer scope"),
        "coverage_complete": _boolean(
            event["coverage_complete"], "reviewer coverage completeness"
        ),
        "go_eligible": _boolean(event["go_eligible"], "reviewer GO eligibility"),
        "responses": _unique_responses(
            event["responses"], "reviewer responses", _reviewer_response
        ),
        "new_findings": _new_findings(
            event["new_findings"],
            "new findings",
            existing_count=len(existing_findings),
            round_number=round_number,
            existing_ids=[finding["id"] for finding in existing_findings],
        ),
        "stop_reason": (
            None
            if event["stop_reason"] is None
            else _enum(event["stop_reason"], "reviewer stop reason", STOP_REASONS)
        ),
    }


def _human_event(value: object) -> dict[str, Any]:
    event = _object(
        value,
        "human decision",
        frozenset(
            {
                "event_type",
                "exchange_id",
                "prior_state_sha256",
                "artifact_binding",
                "authority_receipt",
                "decisions",
            }
        ),
    )
    if event["event_type"] != "human_decision":
        raise ProtocolError("The event is not a human decision.")
    prior = _digest(event["prior_state_sha256"], "human prior state digest")
    assert prior is not None
    decisions = _human_decisions(event["decisions"], "human decisions")
    return {
        "event_type": "human_decision",
        "exchange_id": _string(event["exchange_id"], "human exchange ID"),
        "prior_state_sha256": prior,
        "artifact_binding": _artifact(event["artifact_binding"]),
        "authority_receipt": _authority(
            event["authority_receipt"], "human authority receipt"
        ),
        "decisions": decisions,
    }


def _event_digest(event: Mapping[str, Any]) -> str:
    return sha256_json(
        {
            "schema_id": "athena.review-exchange.event",
            "schema_version": SCHEMA_VERSION,
            "event": event,
        }
    )


def _authority_record(value: object, name: str) -> dict[str, Any]:
    record = _object(
        value,
        name,
        frozenset(
            {
                "schema_id",
                "schema_version",
                "action",
                "target",
                "exchange_id",
                "requirements_sha256",
                "prior_state_sha256",
                "supersedes_state_sha256",
                "decisions",
            }
        ),
    )
    if record["schema_id"] != AUTHORITY_SCHEMA_ID:
        raise ProtocolError(f"{name}.schema_id is not supported.")
    if (
        _integer(record["schema_version"], f"{name}.schema_version", minimum=1)
        != SCHEMA_VERSION
    ):
        raise ProtocolError(f"{name}.schema_version is not supported.")
    action = _enum(
        record["action"],
        f"{name}.action",
        frozenset({"human_decision", "reframe"}),
    )
    prior = _digest(
        record["prior_state_sha256"],
        f"{name}.prior_state_sha256",
        nullable=True,
    )
    supersedes = _digest(
        record["supersedes_state_sha256"],
        f"{name}.supersedes_state_sha256",
        nullable=True,
    )
    decisions = _human_decisions(
        record["decisions"],
        f"{name}.decisions",
        allow_empty=action == "reframe",
    )
    if action == "human_decision" and (prior is None or supersedes is not None):
        raise ProtocolError(
            "A human authority record must name its prior state and cannot "
            "supersede an exchange."
        )
    if action == "reframe" and (prior is not None or supersedes is None or decisions):
        raise ProtocolError(
            "A reframe authority record must name one superseded state, no prior "
            "current-exchange state, and no decisions."
        )
    requirements = _digest(record["requirements_sha256"], f"{name}.requirements_sha256")
    assert requirements is not None
    return {
        "schema_id": AUTHORITY_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "action": action,
        "target": _target(record["target"], f"{name}.target"),
        "exchange_id": _string(record["exchange_id"], f"{name}.exchange_id"),
        "requirements_sha256": requirements,
        "prior_state_sha256": prior,
        "supersedes_state_sha256": supersedes,
        "decisions": decisions,
    }


def parse_authority_record(body: str) -> dict[str, Any]:
    """Parse one exact canonical authority-comment body."""
    if not isinstance(body, str):
        raise ProtocolError("The authority record body must be text.")
    try:
        encoded = body.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProtocolError("The authority record body is not valid UTF-8.") from error
    record = _authority_record(parse_json_bytes(encoded), "authority record")
    if canonical_json(record) != body:
        raise ProtocolError("The authority record body is not canonical JSON.")
    provider = record["target"]["provider"]
    if len(encoded) > PROVIDER_BODY_LIMITS[provider]:
        raise ProtocolError(f"The authority record exceeds the {provider} body limit.")
    return record


def _decision_identity(decision: Mapping[str, Any]) -> str:
    return canonical_json(decision)


def verify_authority_record(
    body: str,
    receipt: object,
    expected: object,
    *,
    allow_extra_decisions: bool = False,
) -> dict[str, Any]:
    """Verify one authority body, receipt digest, and expected action context."""
    if type(allow_extra_decisions) is not bool:
        raise ProtocolError("The extra-decision policy must be a Boolean.")
    authority = _authority(receipt, "authority receipt")
    actual = parse_authority_record(body)
    if sha256_text(body) != authority["sha256"]:
        raise ProtocolError("The authority receipt digest does not match its body.")
    normalized_expected = _authority_record(expected, "expected authority context")
    actual_context = {key: value for key, value in actual.items() if key != "decisions"}
    expected_context = {
        key: value for key, value in normalized_expected.items() if key != "decisions"
    }
    if actual_context != expected_context:
        raise ProtocolError("The authority record does not match its action context.")
    if allow_extra_decisions:
        actual_decisions = {
            _decision_identity(decision) for decision in actual["decisions"]
        }
        expected_decisions = {
            _decision_identity(decision)
            for decision in normalized_expected["decisions"]
        }
        decisions_match = expected_decisions.issubset(actual_decisions)
    else:
        decisions_match = actual["decisions"] == normalized_expected["decisions"]
    if not decisions_match:
        raise ProtocolError("The authority record does not match its decisions.")
    return actual


def verify_authority_record_for_event(
    body: str,
    receipt: object,
    event: Mapping[str, Any],
    result_envelope: object,
) -> dict[str, Any]:
    """Verify authority for one accepted human-decision or reframe event."""
    if not isinstance(event, Mapping):
        raise ProtocolError("The authority event must be an object.")
    event_type = event.get("event_type")
    if event_type == "human_decision":
        parsed_event = _human_event(event)
    elif event_type == "reframe":
        parsed_event = _reframe_event(event)
    else:
        raise ProtocolError("The authority event type is not supported.")
    authority = _authority(receipt, "authority receipt")
    if parsed_event["authority_receipt"] != authority:
        raise ProtocolError("The authority receipt does not match the event.")
    envelope = verify_envelope(result_envelope)
    if envelope["schema_id"] != STATE_SCHEMA_ID:
        raise ProtocolError("The authority event result is not review state.")
    state = envelope["state"]
    event_digest = _event_digest(parsed_event)
    if state["accepted_event_sha256"] != event_digest:
        raise ProtocolError("The authority event result does not accept this event.")
    if event_type == "reframe":
        expected_state, _ = _initial_reduce(parsed_event, event_digest)
        expected_state["supersession_authority_receipt"] = authority
        if make_envelope(expected_state) != envelope:
            raise ProtocolError(
                "The reframe result does not match its authority event."
            )
        expected = {
            "schema_id": AUTHORITY_SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "action": "reframe",
            "target": state["target"],
            "exchange_id": state["exchange_id"],
            "requirements_sha256": state["requirements_sha256"],
            "prior_state_sha256": None,
            "supersedes_state_sha256": parsed_event["supersedes_state_sha256"],
            "decisions": [],
        }
    else:
        if (
            state["exchange_id"] != parsed_event["exchange_id"]
            or state["prior_state_sha256"] != parsed_event["prior_state_sha256"]
            or state["artifact_binding"] != parsed_event["artifact_binding"]
        ):
            raise ProtocolError("The human-decision result does not match its event.")
        by_id = {finding["id"]: finding for finding in state["findings"]}
        for decision in parsed_event["decisions"]:
            finding = by_id.get(decision["finding_id"])
            if finding is None or finding["authority_receipt"] != authority:
                raise ProtocolError(
                    "The human-decision result does not retain its authority."
                )
            if decision["kind"] == "accept_risk":
                matches = finding["state"] == "accepted_risk"
            else:
                matches = (
                    finding["state"] == "still_present"
                    and finding["author_response"] is None
                    and finding["reviewer_response"] is None
                    and finding["closure_condition"] == decision["closure_condition"]
                )
            if not matches:
                raise ProtocolError(
                    "The human-decision result does not apply its decision."
                )
        expected = {
            "schema_id": AUTHORITY_SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "action": "human_decision",
            "target": state["target"],
            "exchange_id": state["exchange_id"],
            "requirements_sha256": state["requirements_sha256"],
            "prior_state_sha256": parsed_event["prior_state_sha256"],
            "supersedes_state_sha256": None,
            "decisions": parsed_event["decisions"],
        }
    return verify_authority_record(body, authority, expected)


def _authority_decision_for_finding(finding: Mapping[str, Any]) -> dict[str, Any]:
    if finding["state"] == "accepted_risk":
        return {
            "finding_id": finding["id"],
            "kind": "accept_risk",
            "closure_condition": None,
        }
    return {
        "finding_id": finding["id"],
        "kind": "select_closure",
        "closure_condition": finding["closure_condition"],
    }


def verify_authority_record_for_state(
    body: str, receipt: object, envelope: object
) -> dict[str, Any]:
    """Verify one retained authority receipt against current review state."""
    authority = _authority(receipt, "authority receipt")
    verified = verify_envelope(envelope)
    if verified["schema_id"] != STATE_SCHEMA_ID:
        raise ProtocolError("The authority receipt is not attached to review state.")
    state = verified["state"]
    supersession_matches = state["supersession_authority_receipt"] == authority
    matching_findings = [
        finding
        for finding in state["findings"]
        if finding["authority_receipt"] == authority
    ]
    if supersession_matches and matching_findings:
        raise ProtocolError("One authority receipt has ambiguous retained actions.")
    if supersession_matches:
        expected = {
            "schema_id": AUTHORITY_SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "action": "reframe",
            "target": state["target"],
            "exchange_id": state["exchange_id"],
            "requirements_sha256": state["requirements_sha256"],
            "prior_state_sha256": None,
            "supersedes_state_sha256": state["supersedes_state_sha256"],
            "decisions": [],
        }
        return verify_authority_record(body, authority, expected)
    if not matching_findings:
        raise ProtocolError("The authority receipt is not retained in review state.")
    matching_events = [
        event
        for event in state["accepted_events"]
        if event.get("event_type") == "human_decision"
        and event.get("authority_receipt") == authority
    ]
    if len(matching_events) != 1:
        raise ProtocolError(
            "One human authority receipt must identify exactly one accepted event."
        )
    authority_event = _human_event(matching_events[0])
    decisions = [
        _authority_decision_for_finding(finding) for finding in matching_findings
    ]
    expected = {
        "schema_id": AUTHORITY_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "action": "human_decision",
        "target": state["target"],
        "exchange_id": state["exchange_id"],
        "requirements_sha256": state["requirements_sha256"],
        "prior_state_sha256": authority_event["prior_state_sha256"],
        "supersedes_state_sha256": None,
        "decisions": decisions,
    }
    return verify_authority_record(
        body,
        authority,
        expected,
        allow_extra_decisions=True,
    )


def _state_phase(
    findings: Sequence[Mapping[str, Any]],
    coverage_complete: bool,
    go_eligible: bool,
    *,
    stop_reason: str | None,
    round_number: int,
) -> tuple[str, str, str, str]:
    active = _active_required(findings)
    if stop_reason not in {None, "requirements_reframe"} and not active:
        raise ProtocolError(
            "A finding-dependent stop reason requires an active required finding."
        )
    if stop_reason is not None or any(
        finding["state"] == "escalated" for finding in active
    ):
        return (
            "decision_required",
            "NO-GO",
            "human_decision",
            (stop_reason or "reviewer_escalation"),
        )
    if not active and coverage_complete:
        if go_eligible:
            return "complete", "GO", "finalize", "complete"
        if round_number == ROUND_LIMIT:
            return "decision_required", "NO-GO", "human_decision", "review_limit"
        return "complete", "CONDITIONAL GO", "none", "conditional_complete"
    if round_number == ROUND_LIMIT:
        return "decision_required", "NO-GO", "human_decision", "review_limit"
    if active:
        return "awaiting_author", "NO-GO", "author_response", "required_findings"
    return "awaiting_evidence", "NO-GO", "review_assessment", "evidence_gap"


def _stored_finding(finding: Mapping[str, Any], round_number: int) -> dict[str, Any]:
    required = finding["disposition"] == "required"
    return {
        **finding,
        "closure_revision": 1 if required else 0,
        "introduced_round": round_number,
        "state": "open" if required else "nonblocking",
        "author_response": None,
        "reviewer_response": None,
        "authority_receipt": None,
    }


def _decision(state: Mapping[str, Any], reason: str) -> dict[str, Any]:
    next_role: str | None
    if state["next_action"] == "author_response":
        next_role = "author"
    elif state["next_action"] == "review_assessment":
        next_role = "reviewer"
    elif state["next_action"] == "human_decision":
        next_role = "human"
    else:
        next_role = None
    return {
        "phase": state["phase"],
        "reason": reason,
        "next_role": next_role,
        "review_round": state["round"],
        "rounds_remaining": ROUND_LIMIT - cast(int, state["round"]),
        "required_remaining": len(
            _active_required(cast(list[dict[str, Any]], state["findings"]))
        ),
    }


def _initial_reduce(
    event: dict[str, Any], event_digest: str
) -> tuple[dict[str, Any], str]:
    if event["round"] != 1:
        raise ProtocolError("The first reviewer assessment must be round 1.")
    findings = [_stored_finding(item, 1) for item in event["new_findings"]]
    phase, verdict, next_action, reason = _state_phase(
        findings,
        event["coverage_complete"],
        event["go_eligible"],
        stop_reason=event["stop_reason"],
        round_number=1,
    )
    state = {
        "exchange_id": event["exchange_id"],
        "surface": event["surface"],
        "target": event["target"],
        "requirements_sha256": event["requirements_sha256"],
        "round": 1,
        "round_limit": ROUND_LIMIT,
        "phase": phase,
        "artifact_binding": event["artifact_binding"],
        "scope": event["scope"],
        "prior_state_sha256": None,
        "accepted_event_sha256": event_digest,
        "accepted_events": [copy.deepcopy(event)],
        "supersedes_state_sha256": event["supersedes_state_sha256"],
        "supersession_authority_receipt": None,
        "coverage_complete": event["coverage_complete"],
        "go_eligible": event["go_eligible"],
        "progress": [
            {
                "round": 1,
                "artifact_revision": event["artifact_binding"]["revision"],
                "scope": event["scope"],
                "scope_size": len(event["scope"]),
                "required_remaining": len(_active_required(findings)),
                "accepted_event_sha256": event_digest,
            }
        ],
        "findings": findings,
        "verdict": verdict,
        "next_action": next_action,
    }
    return state, reason


def _reframe_reduce(
    previous: Mapping[str, Any],
    previous_sha256: str,
    event: dict[str, Any],
    event_digest: str,
) -> tuple[dict[str, Any], str]:
    if event["prior_state_sha256"] != previous_sha256:
        raise ProtocolError("The reframe is not bound to the prior review state.")
    if event["supersedes_state_sha256"] != previous_sha256:
        raise ProtocolError("The reframe does not supersede the prior review state.")
    genesis = previous["accepted_events"][0]
    previous_ancestry = (
        genesis["superseded_exchange_ids"] if genesis["event_type"] == "reframe" else []
    )
    expected_ancestry = [*previous_ancestry, previous["exchange_id"]]
    if event["superseded_exchange_ids"] != expected_ancestry:
        raise ProtocolError(
            "A reframe must retain the exact ordered exchange ancestry."
        )
    if event["exchange_id"] in expected_ancestry:
        raise ProtocolError("A reframe cannot reuse a superseded exchange identity.")
    if event["requirements_sha256"] == previous["requirements_sha256"]:
        raise ProtocolError("A reframe must bind a new requirements identity.")
    if event["surface"] != previous["surface"] or event["target"] != previous["target"]:
        raise ProtocolError("A reframe must keep the same review target.")
    state, reason = _initial_reduce(event, event_digest)
    state["supersession_authority_receipt"] = event["authority_receipt"]
    return state, reason


def _author_reduce(
    previous: dict[str, Any], event: dict[str, Any], event_digest: str
) -> tuple[dict[str, Any], dict[str, Any], str]:
    changed_revision = (
        event["artifact_binding"]["revision"]
        != previous["artifact_binding"]["revision"]
    )
    changed_artifact = changed_revision or (
        event["artifact_binding"]["sha256"] != previous["artifact_binding"]["sha256"]
    )
    conditional_complete = (
        previous["surface"] == "pull_request"
        and previous["phase"] == "complete"
        and previous["verdict"] == "CONDITIONAL GO"
        and previous["next_action"] == "none"
        and not previous["go_eligible"]
        and previous["round"] < ROUND_LIMIT
    )
    artifact_refresh = (
        previous["surface"] == "pull_request"
        and changed_revision
        and (
            previous["phase"] in {"awaiting_reviewer", "awaiting_evidence"}
            or conditional_complete
        )
    )
    if previous["phase"] != "awaiting_author" and not artifact_refresh:
        raise ProtocolError("The exchange is not awaiting an author response.")
    active = _active_required(previous["findings"])
    revalidation = [
        finding
        for finding in previous["findings"]
        if changed_artifact
        and finding["disposition"] == "required"
        and finding["state"] in ARTIFACT_TERMINAL_STATES
    ]
    revalidation_ids = {finding["id"] for finding in revalidation}
    expected = {finding["id"] for finding in active} | revalidation_ids
    actual = {response["finding_id"] for response in event["responses"]}
    if actual != expected:
        raise ProtocolError(
            "The author response must cover every required finding that needs "
            "an answer or artifact revalidation."
        )
    by_id = {response["finding_id"]: response for response in event["responses"]}
    has_correction = any(
        response["kind"] in {"fix", "fix_with_tradeoff"}
        for response in event["responses"]
    )
    if (
        has_correction
        and previous["surface"] == "pull_request"
        and not changed_revision
    ):
        raise ProtocolError("A pull-request fix must bind a new head revision.")
    if has_correction and previous["surface"] == "issue" and not changed_artifact:
        raise ProtocolError("An issue-plan fix must bind a changed artifact.")
    scope_changed = event["scope"] != previous["scope"]
    if scope_changed != (event["scope_change_reason"] is not None):
        raise ProtocolError("A scope change must have exactly one scope-change reason.")
    findings = copy.deepcopy(previous["findings"])
    for finding in findings:
        response = by_id.get(finding["id"])
        if response is None:
            continue
        if finding["id"] in revalidation_ids and finding["state"] == "accepted_risk":
            finding["authority_receipt"] = None
        _merge_unique_evidence(finding["evidence"], response["evidence"])
        finding["author_response"] = {
            "kind": response["kind"],
            "evidence": response["evidence"],
            "tradeoff": response["tradeoff"],
            "artifact_revision": event["artifact_binding"]["revision"],
        }
        finding["reviewer_response"] = None
        if response["kind"] == "fix":
            finding["state"] = "answered_fix"
        elif response["kind"] in {"fix_with_tradeoff", "risk_acceptance"}:
            finding["state"] = "answered_tradeoff"
        else:
            finding["state"] = "contested"
    invalidates_coverage = changed_artifact or scope_changed
    has_active_findings = bool(_active_required(findings))
    state = {
        **previous,
        "phase": "awaiting_reviewer" if has_active_findings else "awaiting_evidence",
        "artifact_binding": event["artifact_binding"],
        "scope": event["scope"],
        "prior_state_sha256": event["prior_state_sha256"],
        "accepted_event_sha256": event_digest,
        "accepted_events": [*previous["accepted_events"], copy.deepcopy(event)],
        "coverage_complete": previous["coverage_complete"] and not invalidates_coverage,
        "findings": findings,
        "verdict": "NO-GO",
        "next_action": "review_assessment",
    }
    author_record = {
        **event,
        "target": previous["target"],
        "requirements_sha256": previous["requirements_sha256"],
    }
    if artifact_refresh:
        reason = "author_reanswered" if has_active_findings else "artifact_refreshed"
    else:
        reason = "author_answered"
    return state, author_record, reason


def _apply_reviewer_response(
    finding: dict[str, Any], response: Mapping[str, Any], round_number: int
) -> None:
    state = finding["state"]
    action = response["kind"]
    author_kind = (
        finding["author_response"]["kind"]
        if finding["author_response"] is not None
        else None
    )
    if state in {"answered_fix", "answered_tradeoff"}:
        allowed = {"resolve", "partial", "still_present", "withdraw", "escalate"}
        if author_kind == "risk_acceptance":
            allowed = {"still_present", "withdraw", "escalate"}
        mapping = {
            "resolve": "resolved",
            "partial": "partial",
            "still_present": "still_present",
            "withdraw": "withdrawn",
            "escalate": "escalated",
        }
    elif state == "contested":
        allowed = {"accept", "counter", "refute", "escalate"}
        mapping = {
            "accept": "withdrawn",
            "counter": "countered",
            "refute": "still_present",
            "escalate": "escalated",
        }
    else:
        raise ProtocolError("A reviewer response does not match an author answer.")
    if action not in allowed:
        raise ProtocolError(
            "The reviewer response is not legal for this author answer."
        )
    if action in {"counter", "refute"} and set(response["evidence"]).issubset(
        set(finding["evidence"])
    ):
        raise ProtocolError(
            "A contest response must add evidence, not restate the finding."
        )
    if action == "counter":
        closure = cast(str, response["closure_condition"])
        if closure == finding["closure_condition"]:
            raise ProtocolError("A counter must revise the closure condition.")
        finding["closure_condition"] = closure
        finding["closure_revision"] += 1
        finding["authority_receipt"] = None
    finding["state"] = mapping[action]
    finding["reviewer_response"] = {
        "kind": action,
        "evidence": response["evidence"],
        "closure_condition": response["closure_condition"],
        "round": round_number,
    }
    _merge_unique_evidence(finding["evidence"], response["evidence"])


def _artifact_has_correction(previous: Mapping[str, Any]) -> bool:
    current_artifact = previous["artifact_binding"]
    return any(
        event["event_type"] == "author_response"
        and event["artifact_binding"]["revision"] == current_artifact["revision"]
        and event["artifact_binding"]["sha256"] == current_artifact["sha256"]
        and any(
            response["kind"] in {"fix", "fix_with_tradeoff"}
            for response in event["responses"]
        )
        for event in previous["accepted_events"]
    )


def _validate_late_findings(
    previous: Mapping[str, Any], new_findings: Sequence[Mapping[str, Any]]
) -> None:
    known_evidence = {
        evidence for finding in previous["findings"] for evidence in finding["evidence"]
    }
    known_identities = {
        (finding["location"], finding["impact"]) for finding in previous["findings"]
    }
    correction_precedes = _artifact_has_correction(previous)
    for finding in new_findings:
        evidence = set(finding["evidence"])
        identity = (finding["location"], finding["impact"])
        if identity in known_identities:
            raise ProtocolError("A prior finding cannot be relabeled with a new ID.")
        known_identities.add(identity)
        if finding["introduction"] == "new_evidence" and evidence.issubset(
            known_evidence
        ):
            raise ProtocolError("A new-evidence finding must supply new evidence.")
        if finding["introduction"] == "introduced_by_correction" and not (
            correction_precedes
        ):
            raise ProtocolError(
                "A correction-introduced finding must follow an author correction."
            )


def _revalidated_terminal_ids(previous: Mapping[str, Any]) -> set[str]:
    pending = {
        finding["id"]
        for finding in previous["findings"]
        if finding["state"] in {"answered_fix", "answered_tradeoff", "contested"}
    }
    terminal: set[str] = set()
    for event in reversed(previous["accepted_events"]):
        event_type = event["event_type"]
        if event_type == "human_decision":
            for decision in event["decisions"]:
                finding_id = decision["finding_id"]
                if finding_id not in pending:
                    continue
                if decision["kind"] == "accept_risk":
                    terminal.add(finding_id)
                pending.remove(finding_id)
        elif event_type in {"reviewer_assessment", "reframe"}:
            for response in event["responses"]:
                finding_id = response["finding_id"]
                if finding_id not in pending:
                    continue
                if response["kind"] in {"resolve", "withdraw", "accept"}:
                    terminal.add(finding_id)
                pending.remove(finding_id)
            for finding in event["new_findings"]:
                pending.discard(finding["id"])
        if not pending:
            break
    return terminal


def _review_reduce(
    previous: dict[str, Any], event: dict[str, Any], event_digest: str
) -> tuple[dict[str, Any], str]:
    conditional_complete = (
        previous["surface"] == "pull_request"
        and previous["phase"] == "complete"
        and previous["verdict"] == "CONDITIONAL GO"
        and previous["next_action"] == "none"
        and not previous["go_eligible"]
    )
    if previous["phase"] not in {"awaiting_reviewer", "awaiting_evidence"} and not (
        conditional_complete
    ):
        raise ProtocolError("The exchange is not awaiting a reviewer assessment.")
    if conditional_complete and not event["go_eligible"]:
        raise ProtocolError(
            "A conditional review can continue only with a GO-eligible assessment."
        )
    if conditional_complete and previous["round"] == ROUND_LIMIT:
        raise ProtocolError("A round-5 conditional review cannot add another round.")
    expected_round = previous["round"] + 1
    if event["round"] != expected_round:
        raise ProtocolError("Reviewer rounds must be consecutive.")
    if event["round"] > ROUND_LIMIT:
        raise ProtocolError("No automated sixth reviewer assessment is valid.")
    if (
        event["artifact_binding"]["revision"]
        != previous["artifact_binding"]["revision"]
        or event["artifact_binding"]["sha256"] != previous["artifact_binding"]["sha256"]
    ):
        raise ProtocolError(
            "The reviewer assessment does not bind the author artifact."
        )
    if event["scope"] != previous["scope"]:
        raise ProtocolError("The reviewer assessment changed the declared scope.")
    _validate_late_findings(previous, event["new_findings"])
    expected = {
        finding["id"]
        for finding in previous["findings"]
        if finding["state"] in {"answered_fix", "answered_tradeoff", "contested"}
    }
    revalidated_terminal_ids = _revalidated_terminal_ids(previous)
    actual = {response["finding_id"] for response in event["responses"]}
    if actual != expected:
        raise ProtocolError("The reviewer must reconcile every prior author answer.")
    findings = copy.deepcopy(previous["findings"])
    by_id = {finding["id"]: finding for finding in findings}
    for response in event["responses"]:
        finding = by_id.get(response["finding_id"])
        if finding is None:
            raise ProtocolError("The reviewer response names an unknown finding.")
        _apply_reviewer_response(finding, response, event["round"])
    for new_finding in event["new_findings"]:
        findings.append(_stored_finding(new_finding, event["round"]))
    required_remaining = len(_active_required(findings))
    prior_progress = previous["progress"][-1]
    reason_override = event["stop_reason"]
    if (
        reason_override is None
        and required_remaining > 0
        and required_remaining >= prior_progress["required_remaining"]
        and bool(set(event["scope"]) - set(prior_progress["scope"]))
    ):
        reason_override = "scope_growth_without_progress"
    if (
        reason_override is None
        and required_remaining >= prior_progress["required_remaining"]
        and (
            any(
                finding["introduction"] == "introduced_by_correction"
                and finding["disposition"] == "required"
                for finding in event["new_findings"]
            )
            or any(
                finding["id"] in revalidated_terminal_ids
                and finding["state"] in ACTIVE_REQUIRED_STATES
                for finding in findings
            )
        )
        and _artifact_has_correction(previous)
    ):
        reason_override = "replacement_blocker"
    if any(finding["state"] == "escalated" for finding in findings):
        reason_override = reason_override or "reviewer_escalation"
    phase, verdict, next_action, reason = _state_phase(
        findings,
        event["coverage_complete"],
        event["go_eligible"],
        stop_reason=reason_override,
        round_number=event["round"],
    )
    state = {
        **previous,
        "round": event["round"],
        "phase": phase,
        "artifact_binding": event["artifact_binding"],
        "scope": event["scope"],
        "prior_state_sha256": event["prior_state_sha256"],
        "accepted_event_sha256": event_digest,
        "accepted_events": [*previous["accepted_events"], copy.deepcopy(event)],
        "coverage_complete": event["coverage_complete"],
        "go_eligible": event["go_eligible"],
        "progress": [
            *previous["progress"],
            {
                "round": event["round"],
                "artifact_revision": event["artifact_binding"]["revision"],
                "scope": event["scope"],
                "scope_size": len(event["scope"]),
                "required_remaining": required_remaining,
                "accepted_event_sha256": event_digest,
            },
        ],
        "findings": findings,
        "verdict": verdict,
        "next_action": next_action,
    }
    return state, reason


def _human_reduce(
    previous: dict[str, Any], event: dict[str, Any], event_digest: str
) -> tuple[dict[str, Any], str]:
    if (
        event["artifact_binding"]["revision"]
        != previous["artifact_binding"]["revision"]
        or event["artifact_binding"]["sha256"] != previous["artifact_binding"]["sha256"]
    ):
        raise ProtocolError("The human decision changed the reviewed artifact.")
    if previous["round"] == ROUND_LIMIT and any(
        decision["kind"] == "select_closure" for decision in event["decisions"]
    ):
        raise ProtocolError("A round-5 closure selection cannot start another round.")
    findings = copy.deepcopy(previous["findings"])
    by_id = {finding["id"]: finding for finding in findings}
    for decision in event["decisions"]:
        finding = by_id.get(decision["finding_id"])
        if (
            finding is None
            or finding["disposition"] != "required"
            or finding["state"] not in ACTIVE_REQUIRED_STATES
        ):
            raise ProtocolError("The human decision names no active required finding.")
        if decision["kind"] == "accept_risk":
            author = finding["author_response"]
            if author is None or author["kind"] != "risk_acceptance":
                raise ProtocolError(
                    "Risk acceptance must answer an author risk request."
                )
            finding["state"] = "accepted_risk"
            finding["authority_receipt"] = event["authority_receipt"]
        else:
            if decision["closure_condition"] == finding["closure_condition"]:
                raise ProtocolError("The human decision did not select a new closure.")
            finding["closure_condition"] = decision["closure_condition"]
            finding["closure_revision"] += 1
            finding["state"] = "still_present"
            finding["author_response"] = None
            finding["reviewer_response"] = None
            finding["authority_receipt"] = event["authority_receipt"]
    active = _active_required(findings)
    if not active:
        phase, verdict, next_action, reason = _state_phase(
            findings,
            previous["coverage_complete"],
            previous["go_eligible"],
            stop_reason=None,
            round_number=previous["round"],
        )
    elif previous["round"] == ROUND_LIMIT or any(
        finding["state"] == "escalated" for finding in active
    ):
        phase, verdict, next_action, reason = (
            "decision_required",
            "NO-GO",
            "human_decision",
            "authority_partial",
        )
    elif all(
        finding["state"] in {"answered_fix", "answered_tradeoff", "contested"}
        for finding in active
    ):
        phase, verdict, next_action, reason = (
            "awaiting_reviewer",
            "NO-GO",
            "review_assessment",
            "authority_partial",
        )
    elif all(
        finding["state"] in {"open", "partial", "still_present", "countered"}
        for finding in active
    ):
        phase, verdict, next_action, reason = (
            "awaiting_author",
            "NO-GO",
            "author_response",
            "authority_selected_closure",
        )
    else:
        raise ProtocolError(
            "The human decision leaves incompatible author and reviewer responses."
        )
    state = {
        **previous,
        "phase": phase,
        "artifact_binding": event["artifact_binding"],
        "prior_state_sha256": event["prior_state_sha256"],
        "accepted_event_sha256": event_digest,
        "accepted_events": [*previous["accepted_events"], copy.deepcopy(event)],
        "findings": findings,
        "verdict": verdict,
        "next_action": next_action,
    }
    return state, reason


def _verify_state_history(expected: Mapping[str, Any]) -> None:
    """Replay the complete current-exchange ledger without envelope recursion."""
    raw_events = expected["accepted_events"]
    first_raw = raw_events[0]
    if not isinstance(first_raw, Mapping):
        raise ProtocolError("The first accepted event must be an object.")
    first_type = first_raw.get("event_type")
    if first_type == "reviewer_assessment":
        first = _initial_review_event(first_raw)
        current, _ = _initial_reduce(first, _event_digest(first))
    elif first_type == "reframe":
        first = _reframe_event(first_raw)
        if first["prior_state_sha256"] != first["supersedes_state_sha256"]:
            raise ProtocolError(
                "A reframe genesis must bind its superseded state exactly."
            )
        current, _ = _initial_reduce(first, _event_digest(first))
        current["supersession_authority_receipt"] = first["authority_receipt"]
    else:
        raise ProtocolError(
            "State history must start with an initial assessment or reframe."
        )

    for raw_event in raw_events[1:]:
        if not isinstance(raw_event, Mapping):
            raise ProtocolError("Each accepted event must be an object.")
        event_type = raw_event.get("event_type")
        if event_type == "author_response":
            event = _continued_author_event(raw_event)
        elif event_type == "reviewer_assessment":
            event = _continued_review_event(raw_event, current["findings"])
        elif event_type == "human_decision":
            event = _human_event(raw_event)
        else:
            raise ProtocolError(
                "A current-exchange history cannot contain this event type."
            )
        conditional_continuation = (
            current["surface"] == "pull_request"
            and current["phase"] == "complete"
            and current["verdict"] == "CONDITIONAL GO"
            and current["next_action"] == "none"
            and not current["go_eligible"]
            and current["round"] < ROUND_LIMIT
            and (
                event_type == "reviewer_assessment"
                or (
                    event_type == "author_response"
                    and event["artifact_binding"]["revision"]
                    != current["artifact_binding"]["revision"]
                )
            )
        )
        if current["phase"] == "complete" and not conditional_continuation:
            raise ProtocolError("State history continues after a terminal review.")
        if current["phase"] == "decision_required" and event_type not in {
            "human_decision",
        }:
            raise ProtocolError(
                "Decision-required history must continue with a human decision."
            )
        if event["prior_state_sha256"] != sha256_json(current):
            raise ProtocolError(
                "An accepted event does not bind its preceding review state."
            )
        if event["exchange_id"] != current["exchange_id"]:
            raise ProtocolError("An accepted event changes the review exchange.")
        if (
            current["phase"] == "complete"
            and event_type == "reviewer_assessment"
            and not event["go_eligible"]
        ):
            raise ProtocolError(
                "A conditional review can continue only with a GO-eligible assessment."
            )
        event_digest = _event_digest(event)
        if event_type == "author_response":
            current, _author_record, _ = _author_reduce(current, event, event_digest)
        elif event_type == "reviewer_assessment":
            current, _ = _review_reduce(current, event, event_digest)
        else:
            current, _ = _human_reduce(current, event, event_digest)

    if current["accepted_event_sha256"] != _event_digest(
        cast(Mapping[str, Any], raw_events[-1])
    ):
        raise ProtocolError("State does not name its final accepted event digest.")
    if current != expected:
        raise ProtocolError("State does not match its accepted-event replay.")


def _event_for_replay(
    value: Mapping[str, Any], current: Mapping[str, Any]
) -> dict[str, Any] | None:
    event_type = value.get("event_type")
    if event_type == "reviewer_assessment":
        if value.get("prior_state_sha256") is None:
            return _initial_review_event(value)
        round_number = _integer(
            value.get("round"), "reviewer round", minimum=1, maximum=ROUND_LIMIT
        )
        prior_findings = [
            finding
            for finding in current["findings"]
            if finding["introduced_round"] < round_number
        ]
        return _continued_review_event(value, prior_findings)
    if event_type == "author_response":
        return _continued_author_event(value)
    if event_type == "human_decision":
        return _human_event(value)
    if event_type == "reframe":
        return _reframe_event(value)
    return None


def reduce_request(value: object) -> dict[str, Any]:
    """Validate and apply one event to an optional prior state envelope."""
    request = _object(value, "reduction request", frozenset({"previous", "event"}))
    previous_envelope = (
        None if request["previous"] is None else verify_envelope(request["previous"])
    )
    if (
        previous_envelope is not None
        and previous_envelope["schema_id"] != STATE_SCHEMA_ID
    ):
        raise ProtocolError("The prior envelope is not a review state.")
    raw_event = request["event"]
    if not isinstance(raw_event, dict):
        raise ProtocolError("The event must be an object.")
    event_type = raw_event.get("event_type")
    if previous_envelope is not None:
        previous = cast(dict[str, Any], previous_envelope["state"])
        replay_event = _event_for_replay(raw_event, previous)
        if replay_event is not None and previous[
            "accepted_event_sha256"
        ] == _event_digest(replay_event):
            return {
                "schema_id": RESULT_SCHEMA_ID,
                "schema_version": SCHEMA_VERSION,
                "status": "replayed",
                "decision": _decision(previous, "idempotent_replay"),
                "author_event": None,
                "envelope": previous_envelope,
            }
    if previous_envelope is None:
        event = _initial_review_event(raw_event)
    elif event_type == "author_response":
        event = _continued_author_event(raw_event)
    elif event_type == "reviewer_assessment":
        event = _continued_review_event(
            raw_event, previous_envelope["state"]["findings"]
        )
    elif event_type == "human_decision":
        event = _human_event(raw_event)
    elif event_type == "reframe":
        event = _reframe_event(raw_event)
    else:
        raise ProtocolError("The event type is not supported in the current state.")
    event_digest = _event_digest(event)
    if previous_envelope is not None:
        previous = cast(dict[str, Any], previous_envelope["state"])
        conditional_continuation = (
            previous["surface"] == "pull_request"
            and previous["phase"] == "complete"
            and previous["verdict"] == "CONDITIONAL GO"
            and previous["next_action"] == "none"
            and not previous["go_eligible"]
            and previous["round"] < ROUND_LIMIT
            and (
                (event_type == "reviewer_assessment" and event["go_eligible"])
                or (
                    event_type == "author_response"
                    and event["artifact_binding"]["revision"]
                    != previous["artifact_binding"]["revision"]
                )
            )
        )
        if (
            previous["phase"] == "complete"
            and event_type != "reframe"
            and not (conditional_continuation)
        ):
            raise ProtocolError("A terminal review state cannot accept another event.")
        if previous["phase"] == "decision_required" and event_type not in {
            "human_decision",
            "reframe",
        }:
            raise ProtocolError(
                "A decision-required state accepts only an authoritative decision or reframe."
            )
        if event["prior_state_sha256"] != previous_envelope["state_sha256"]:
            raise ProtocolError("The event is not bound to the prior review state.")
        if event_type != "reframe" and event["exchange_id"] != previous["exchange_id"]:
            raise ProtocolError("The event names a different review exchange.")
    author_envelope: dict[str, Any] | None = None
    if previous_envelope is None:
        state, reason = _initial_reduce(event, event_digest)
    elif event_type == "author_response":
        state, author_record, reason = _author_reduce(
            cast(dict[str, Any], previous_envelope["state"]), event, event_digest
        )
        author_envelope = make_envelope(author_record, AUTHOR_EVENT_SCHEMA_ID)
    elif event_type == "reviewer_assessment":
        state, reason = _review_reduce(
            cast(dict[str, Any], previous_envelope["state"]), event, event_digest
        )
    elif event_type == "reframe":
        state, reason = _reframe_reduce(
            cast(dict[str, Any], previous_envelope["state"]),
            previous_envelope["state_sha256"],
            event,
            event_digest,
        )
    else:
        state, reason = _human_reduce(
            cast(dict[str, Any], previous_envelope["state"]), event, event_digest
        )
    envelope = make_envelope(state)
    return {
        "schema_id": RESULT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "accepted",
        "decision": _decision(envelope["state"], reason),
        "author_event": author_envelope,
        "envelope": envelope,
    }


def _carrier_kind(envelope: Mapping[str, Any]) -> str:
    if envelope["schema_id"] == STATE_SCHEMA_ID:
        return "state"
    if envelope["schema_id"] == AUTHOR_EVENT_SCHEMA_ID:
        return "author-event"
    raise ProtocolError("The envelope cannot be put in a review carrier.")


_HTML_BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "base",
        "basefont",
        "blockquote",
        "body",
        "caption",
        "center",
        "col",
        "colgroup",
        "dd",
        "details",
        "dialog",
        "dir",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "frame",
        "frameset",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "head",
        "header",
        "hr",
        "html",
        "iframe",
        "legend",
        "li",
        "link",
        "main",
        "menu",
        "menuitem",
        "nav",
        "noframes",
        "ol",
        "optgroup",
        "option",
        "p",
        "param",
        "search",
        "section",
        "summary",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "title",
        "tr",
        "track",
        "ul",
    }
)
_HTML_VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "basefont",
        "br",
        "col",
        "embed",
        "frame",
        "hr",
        "img",
        "input",
        "link",
        "menuitem",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
PersistentEnd = str | tuple[str, ...] | re.Pattern[str]


def _html_tag_prefix_at(text: str, start: int) -> tuple[int, str] | None:
    if text[start : start + 1] != "<":
        return None
    position = start + 1
    if text[position : position + 1] == "/":
        position += 1
    name_start = position
    if not text[position : position + 1].isalpha():
        return None
    position += 1
    while (
        text[position : position + 1].isalnum() or text[position : position + 1] == "-"
    ):
        position += 1
    tag_name = text[name_start:position].lower()
    if text[position : position + 1] not in {"", " ", "\t", "\r", "\n", "\f", "/", ">"}:
        return None
    return position, tag_name


def _html_tag_at(text: str, start: int) -> tuple[int, int, str] | None:
    prefix = _html_tag_prefix_at(text, start)
    if prefix is None:
        return None
    position, tag_name = prefix
    quote: str | None = None
    while position < len(text):
        character = text[position]
        if quote is not None:
            if character == quote:
                quote = None
        elif character in {"'", '"'}:
            quote = character
        elif character == "<":
            return None
        elif character == ">":
            return start, position + 1, tag_name
        position += 1
    return None


def _html_tag_ranges(text: str) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    position = 0
    while position < len(text):
        start = text.find("<", position)
        if start < 0:
            break
        tag = _html_tag_at(text, start)
        if tag is None:
            position = start + 1
        else:
            ranges.append(tag)
            position = tag[1]
    return ranges


def _persistent_end_match(
    text: str, terminator: PersistentEnd, position: int = 0
) -> tuple[int, int] | None:
    if isinstance(terminator, str):
        start = text.find(terminator, position)
        return None if start < 0 else (start, start + len(terminator))
    if isinstance(terminator, tuple):
        matches = [
            (start, start + len(value))
            for value in terminator
            if (start := text.find(value, position)) >= 0
        ]
        return min(matches) if matches else None
    match = terminator.search(text, position)
    return None if match is None else match.span()


def _persistent_html_opening(
    line: str, position: int, *, require_line_start: bool
) -> tuple[re.Match[str], PersistentEnd] | None:
    candidates: list[tuple[re.Match[str], PersistentEnd]] = []
    fixed = (
        (re.compile(r"<!--"), ("-->", "--!>")),
        (re.compile(r"<\?"), "?>"),
        (re.compile(r"<!\[CDATA\[", re.IGNORECASE), "]]>"),
        (re.compile(r"<![A-Z]"), ">"),
    )
    for start, end in fixed:
        match = start.search(line, position)
        if match is not None:
            candidates.append((match, end))
    raw_tag = re.compile(
        r"<(script|pre|style|textarea)(?=[\t />]|$)", re.IGNORECASE
    ).search(line, position)
    if raw_tag is not None:
        candidates.append(
            (
                raw_tag,
                re.compile(rf"</{re.escape(raw_tag.group(1))}>", re.IGNORECASE),
            )
        )
    if not candidates:
        return None
    opening = min(candidates, key=lambda item: item[0].start())
    if require_line_start and opening[0].start() != position:
        return None
    return opening


class _HTMLContainerParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []
        self._open_tag_counts: dict[str, int] = {}
        self._deferred_parts: list[str] = []
        self._deferred_quote: str | None = None
        self._deferred_honors_quotes = False

    @staticmethod
    def _tag_boundary(
        text: str, quote: str | None, honors_quotes: bool, position: int = 0
    ) -> tuple[bool, str | None]:
        while position < len(text):
            character = text[position]
            if quote is not None:
                if character == quote:
                    quote = None
            elif honors_quotes and character in {"'", '"'}:
                quote = character
            elif character == ">":
                return True, quote
            position += 1
        return False, quote

    def _defer_unfinished_input(self) -> None:
        if not self.rawdata:
            return
        honors_quotes = re.match(r"<[A-Za-z]", self.rawdata) is not None
        _boundary, quote = self._tag_boundary(
            self.rawdata, None, honors_quotes, 2 if honors_quotes else 0
        )
        self._deferred_parts = [self.rawdata]
        self._deferred_quote = quote
        self._deferred_honors_quotes = honors_quotes
        self.rawdata = ""

    @property
    def has_unfinished_input(self) -> bool:
        return bool(self._deferred_parts or self.rawdata)

    def feed(self, data: str) -> None:
        """Feed HTML without repeatedly reparsing unfinished input."""
        if self._deferred_parts:
            boundary, quote = self._tag_boundary(
                data,
                self._deferred_quote,
                self._deferred_honors_quotes,
            )
            self._deferred_parts.append(data)
            self._deferred_quote = quote
            if not boundary:
                return
            data = "".join(self._deferred_parts)
            self._deferred_parts = []
            self._deferred_quote = None
            self._deferred_honors_quotes = False
        super().feed(data)
        self._defer_unfinished_input()

    def close(self) -> None:
        if self._deferred_parts:
            self.rawdata += "".join(self._deferred_parts)
            self._deferred_parts = []
            self._deferred_quote = None
            self._deferred_honors_quotes = False
        super().close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag not in _HTML_VOID_TAGS:
            self.stack.append(tag)
            self._open_tag_counts[tag] = self._open_tag_counts.get(tag, 0) + 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        # HTML ignores the XML-style slash for non-void elements. Browsers
        # therefore keep `<details/>` open and can hide a later carrier.
        if tag not in _HTML_VOID_TAGS:
            self.stack.append(tag)
            self._open_tag_counts[tag] = self._open_tag_counts.get(tag, 0) + 1

    def handle_endtag(self, tag: str) -> None:
        count = self._open_tag_counts.get(tag, 0)
        if count == 0:
            return
        if self.stack[-1] != tag:
            raise ProtocolError("The Markdown body has a misnested HTML container.")
        self.stack.pop()
        if count == 1:
            del self._open_tag_counts[tag]
        else:
            self._open_tag_counts[tag] = count - 1


def _backtick_runs(
    text: str,
) -> tuple[list[re.Match[str]], list[int | None]]:
    runs = list(re.finditer(r"`+", text))
    next_same_length: list[int | None] = [None] * len(runs)
    latest_by_length: dict[int, int] = {}
    for index in range(len(runs) - 1, -1, -1):
        length = runs[index].end() - runs[index].start()
        next_same_length[index] = latest_by_length.get(length)
        latest_by_length[length] = index
    return runs, next_same_length


def _mask_markdown_code_spans(line: str) -> str:
    masked = list(line)
    html_ranges = _html_tag_ranges(line)
    runs, next_same_length = _backtick_runs(line)
    skip_through = -1
    html_index = 0
    for index, opening in enumerate(runs):
        if index <= skip_through:
            continue
        while (
            html_index < len(html_ranges)
            and html_ranges[html_index][1] <= opening.start()
        ):
            html_index += 1
        in_html = (
            html_index < len(html_ranges)
            and html_ranges[html_index][0]
            <= opening.start()
            < html_ranges[html_index][1]
        )
        backslashes = 0
        before = opening.start() - 1
        while before >= 0 and line[before] == "\\":
            backslashes += 1
            before -= 1
        if in_html or backslashes % 2:
            continue
        closing_index = next_same_length[index]
        if closing_index is None:
            continue
        closing = runs[closing_index]
        masked[opening.start() : closing.end()] = " " * (
            closing.end() - opening.start()
        )
        skip_through = closing_index
    return "".join(masked)


def _markdown_source_lines(body: str) -> list[tuple[int, int, int, str]]:
    """Split Markdown line endings and retain exact source offsets."""
    result: list[tuple[int, int, int, str]] = []
    offset = 0
    while offset < len(body):
        content_end = offset
        while content_end < len(body) and body[content_end] not in {"\r", "\n"}:
            content_end += 1
        raw_end = content_end
        if raw_end < len(body):
            raw_end += 1
            if body[content_end] == "\r" and body[raw_end : raw_end + 1] == "\n":
                raw_end += 1
        result.append((offset, content_end, raw_end, body[offset:content_end]))
        offset = raw_end
    return result


def _multiline_code_spans(body: str) -> tuple[list[tuple[int, int]], tuple[int, ...]]:
    searchable = list(body)
    fence_character: str | None = None
    fence_length = 0
    for offset, _content_end, raw_end, line in _markdown_source_lines(body):
        opening = re.fullmatch(r" {0,3}(`{3,}|~{3,})(.*)", line)
        in_fence = fence_character is not None
        if not in_fence and opening is not None:
            fence = opening.group(1)
            if fence[0] != "`" or "`" not in opening.group(2):
                fence_character = fence[0]
                fence_length = len(fence)
                in_fence = True
        if in_fence:
            for index in range(offset, raw_end):
                if searchable[index] not in {"\r", "\n"}:
                    searchable[index] = " "
            closing = re.fullmatch(r" {0,3}([`~]+)[ \t]*", line)
            if (
                closing is not None
                and closing.group(1)[0] == fence_character
                and len(closing.group(1)) >= fence_length
            ):
                fence_character = None
                fence_length = 0

    searchable_text = "".join(searchable)
    html_ranges = _html_tag_ranges(searchable_text)
    runs, next_same_length = _backtick_runs(searchable_text)

    spans: list[tuple[int, int]] = []
    unmatched: list[int] = []
    skip_through = -1
    html_index = 0
    for index, run in enumerate(runs):
        if index <= skip_through:
            continue
        while (
            html_index < len(html_ranges) and html_ranges[html_index][1] <= run.start()
        ):
            html_index += 1
        in_html = (
            html_index < len(html_ranges)
            and html_ranges[html_index][0] <= run.start() < html_ranges[html_index][1]
        )
        backslashes = 0
        before = run.start() - 1
        while before >= 0 and searchable_text[before] == "\\":
            backslashes += 1
            before -= 1
        if in_html or backslashes % 2:
            continue
        closing_index = next_same_length[index]
        if closing_index is None:
            unmatched.append(run.start())
            continue
        closing = runs[closing_index]
        if (
            "\n" in body[run.start() : closing.end()]
            or "\r" in body[run.start() : closing.end()]
        ):
            spans.append((run.start(), closing.end()))
        skip_through = closing_index
    return spans, tuple(unmatched)


def _mask_persistent_html(
    line: str,
    current_end: PersistentEnd | None,
    markdown_line: str,
) -> tuple[str, PersistentEnd | None]:
    masked = list(markdown_line)
    position = 0
    if current_end is not None:
        closing = _persistent_end_match(line, current_end)
        if closing is None:
            return " " * len(line), current_end
        for index in range(closing[1]):
            masked[index] = " "
        position = closing[1]
        current_end = None
    while True:
        opening = _persistent_html_opening(
            markdown_line, position, require_line_start=False
        )
        if opening is None:
            return "".join(masked), None
        match, current_end = opening
        opening_start = match.start()
        opening_end = match.end()
        closing = _persistent_end_match(line, current_end, opening_end)
        if closing is None:
            for index in range(opening_start, len(masked)):
                masked[index] = " "
            return "".join(masked), current_end
        for index in range(opening_start, closing[1]):
            masked[index] = " "
        position = closing[1]
        current_end = None


def _first_html_start(line: str) -> int | None:
    starts = [start for start, _end, _tag_name in _html_tag_ranges(line)]
    position = 0
    while position < len(line):
        start = line.find("<", position)
        if start < 0:
            break
        if _html_tag_prefix_at(line, start) is not None:
            starts.append(start)
        position = start + 1
    persistent = _persistent_html_opening(line, 0, require_line_start=False)
    if persistent is not None:
        starts.append(persistent[0].start())
    return min(starts) if starts else None


def _has_html_code_precedence_conflict(body: str) -> bool:
    fence_character: str | None = None
    fence_length = 0
    persistent_end: PersistentEnd | None = None
    html_block = False
    pending_type6_tag = False
    incomplete_type6_hazard = False
    html_parser = _HTMLContainerParser()
    for _offset, _content_end, _raw_end, line in _markdown_source_lines(body):
        if fence_character is not None:
            closing = re.fullmatch(r" {0,3}([`~]+)[ \t]*", line)
            if (
                closing is not None
                and closing.group(1)[0] == fence_character
                and len(closing.group(1)) >= fence_length
            ):
                fence_character = None
                fence_length = 0
            continue

        persistent_before = persistent_end is not None
        container_before = bool(html_parser.stack) or html_parser.has_unfinished_input
        block_before = html_block
        active_before = persistent_before or container_before or block_before
        opening_fence = re.fullmatch(r" {0,3}(`{3,}|~{3,})(.*)", line)
        if not active_before and opening_fence is not None:
            fence = opening_fence.group(1)
            if fence[0] != "`" or "`" not in opening_fence.group(2):
                fence_character = fence[0]
                fence_length = len(fence)
                continue

        indentation = len(line) - len(line.lstrip(" "))
        is_indented_code = indentation >= 4 or line.startswith("\t")
        first_tick = line.find("`")
        html_start = _first_html_start(line)
        if first_tick >= 0 and (
            active_before
            or (
                not is_indented_code
                and html_start is not None
                and html_start < first_tick
            )
        ):
            return True
        if is_indented_code and not active_before:
            continue

        markdown_line = line if active_before else _mask_markdown_code_spans(line)
        markdown_stripped = markdown_line.lstrip(" ")
        block_prefix = _html_tag_prefix_at(markdown_stripped, 0)
        starts_type6_block = (
            indentation <= 3
            and block_prefix is not None
            and block_prefix[1] in _HTML_BLOCK_TAGS
        )
        if starts_type6_block:
            pending_type6_tag = True
        scan_line, persistent_end = _mask_persistent_html(
            line, persistent_end, markdown_line
        )
        html_parser.feed(scan_line + "\n")
        if pending_type6_tag:
            if not html_parser.has_unfinished_input:
                pending_type6_tag = False
            elif not line.strip():
                incomplete_type6_hazard = True

        if starts_type6_block:
            html_block = True
        if html_block:
            if not line.strip():
                html_block = False
            continue
        block_opening = _persistent_html_opening(
            markdown_stripped, 0, require_line_start=True
        )
        if indentation <= 3 and block_opening is not None:
            continue
        first_tag = _html_tag_at(markdown_stripped, 0) if indentation <= 3 else None
        if first_tag is not None:
            _start, tag_end, tag_name = first_tag
            if tag_name in _HTML_BLOCK_TAGS or tag_end == len(markdown_stripped):
                html_block = True
    incomplete_type6_tag = incomplete_type6_hazard or pending_type6_tag
    html_parser.close()
    return incomplete_type6_tag


def top_level_markdown_lines(
    body: str, *, require_closed: bool = False
) -> list[tuple[int, int, str]]:
    """Return source spans for lines outside Markdown code and HTML blocks."""
    if not isinstance(body, str):
        raise ProtocolError("The Markdown body must be text.")
    if type(require_closed) is not bool:
        raise ProtocolError("The closed-block policy must be a Boolean.")
    if _has_html_code_precedence_conflict(body):
        raise ProtocolError(
            "The Markdown body has ambiguous HTML and code-delimiter precedence."
        )
    lines: list[tuple[int, int, str]] = []
    fence_character: str | None = None
    fence_length = 0
    persistent_end: PersistentEnd | None = None
    html_block = False
    html_parser = _HTMLContainerParser()
    multiline_code_spans, unmatched_code_runs = _multiline_code_spans(body)
    multiline_span_index = 0
    for offset, end_offset, _raw_end, line in _markdown_source_lines(body):
        if fence_character is not None:
            closing = re.fullmatch(r" {0,3}([`~]+)[ \t]*", line)
            if (
                closing is not None
                and closing.group(1)[0] == fence_character
                and len(closing.group(1)) >= fence_length
            ):
                fence_character = None
                fence_length = 0
            continue
        persistent_before = persistent_end is not None
        container_before = bool(html_parser.stack)
        if html_block:
            markdown_line = line
            scan_line, persistent_end = _mask_persistent_html(
                line, persistent_end, markdown_line
            )
            html_parser.feed(scan_line + "\n")
            if not line.strip():
                html_block = False
                if persistent_end is None and not html_parser.stack:
                    lines.append((offset, end_offset, line))
            continue
        opening_fence = re.fullmatch(r" {0,3}(`{3,}|~{3,})(.*)", line)
        if not persistent_before and not container_before and opening_fence is not None:
            fence = opening_fence.group(1)
            if fence[0] != "`" or "`" not in opening_fence.group(2):
                fence_character = fence[0]
                fence_length = len(fence)
                continue
        markdown_line = _mask_markdown_code_spans(line)
        fully_in_multiline_code = False
        while (
            multiline_span_index < len(multiline_code_spans)
            and multiline_code_spans[multiline_span_index][1] <= offset
        ):
            multiline_span_index += 1
        candidate_span_index = multiline_span_index
        while candidate_span_index < len(multiline_code_spans):
            span_start, span_end = multiline_code_spans[candidate_span_index]
            if span_start >= end_offset:
                break
            intersection_start = max(offset, span_start)
            intersection_end = min(end_offset, span_end)
            if intersection_start < intersection_end:
                relative_start = intersection_start - offset
                relative_end = intersection_end - offset
                markdown_line = (
                    markdown_line[:relative_start]
                    + " " * (relative_end - relative_start)
                    + markdown_line[relative_end:]
                )
                if span_start <= offset and span_end >= end_offset:
                    fully_in_multiline_code = True
            candidate_span_index += 1
        indentation = len(line) - len(line.lstrip(" "))
        stripped = line.lstrip(" ")
        markdown_stripped = markdown_line.lstrip(" ")
        if line and fully_in_multiline_code:
            continue
        if indentation >= 4 or line.startswith("\t"):
            continue
        block_opening = _persistent_html_opening(
            markdown_stripped, 0, require_line_start=True
        )
        scan_line, persistent_end = _mask_persistent_html(
            line, persistent_end, markdown_line
        )
        html_parser.feed(scan_line + "\n")
        if persistent_before or container_before:
            continue
        if indentation <= 3 and block_opening is not None:
            if (
                persistent_end is None
                and not html_parser.stack
                and re.fullmatch(
                    r"<!-- (?:HomericIntelligence:|athena:|hephaestus-)"
                    r"[^\r\n]*-->[ \t]*",
                    stripped,
                )
                is not None
            ):
                lines.append((offset, end_offset, line))
            continue
        block_prefix = _html_tag_prefix_at(markdown_stripped, 0)
        if (
            indentation <= 3
            and block_prefix is not None
            and block_prefix[1] in _HTML_BLOCK_TAGS
        ):
            html_block = True
            continue
        first_tag = _html_tag_at(markdown_stripped, 0) if indentation <= 3 else None
        if first_tag is not None:
            _start, tag_end, tag_name = first_tag
            if tag_name in _HTML_BLOCK_TAGS or tag_end == len(stripped):
                html_block = True
                continue
        lines.append((offset, end_offset, line))
    html_parser.close()
    if require_closed and fence_character is not None:
        raise ProtocolError("The Markdown body contains an open code fence.")
    last_line_end = max(body.rfind("\n"), body.rfind("\r"))
    if (
        require_closed
        and unmatched_code_runs
        and unmatched_code_runs[0] < last_line_end
    ):
        raise ProtocolError("The Markdown body contains an open multiline code span.")
    if require_closed and (persistent_end is not None or html_parser.stack):
        raise ProtocolError("The Markdown body contains an open HTML block.")
    return lines


def write_utf8_stdout(output: str) -> None:
    """Write exact UTF-8 output and normalize local stream failures."""
    try:
        encoded = output.encode("utf-8")
        binary = getattr(sys.stdout, "buffer", None)
        if binary is None:
            written = sys.stdout.write(output)
            sys.stdout.flush()
            expected = len(output)
        else:
            written = binary.write(encoded)
            binary.flush()
            expected = len(encoded)
        if written != expected:
            raise OSError("The output write was incomplete.")
    except (OSError, UnicodeError, ValueError) as error:
        raise OperationalError(f"The output cannot be written: {error}") from error


def _single_line_diagnostic(error: BaseException) -> str:
    return "".join(
        character if character.isprintable() else ascii(character)[1:-1]
        for character in str(error)
    )


def render_carrier(visible_content: str, value: object, kind: str) -> str:
    """Append one verified final carrier to exact visible content."""
    if not isinstance(visible_content, str):
        raise ProtocolError("The visible content must be text.")
    if CARRIER_PREFIX in visible_content:
        raise ProtocolError("The visible content contains a review-exchange marker.")
    top_level_markdown_lines(visible_content, require_closed=True)
    envelope = verify_envelope(value)
    expected_kind = _carrier_kind(envelope)
    if kind != expected_kind:
        raise ProtocolError("The carrier kind does not match the envelope.")
    expected_visible = envelope["state"]["artifact_binding"]["visible_content_sha256"]
    if sha256_text(visible_content) != expected_visible:
        raise ProtocolError("The carrier does not bind the visible content.")
    marker = (
        "<!-- HomericIntelligence:review-exchange:v1 "
        f"kind={kind} sha256={envelope['state_sha256']} -->"
    )
    separator = "\n\n" if visible_content else ""
    document = (
        f"{visible_content}{separator}{marker}\n```json\n"
        f"{canonical_json(envelope)}\n```\n"
    )
    marker_start = len(visible_content) + len(separator)
    if (
        marker_start,
        marker_start + len(marker),
        marker,
    ) not in top_level_markdown_lines(document, require_closed=True):
        raise ProtocolError("The review-exchange marker is not a top-level line.")
    provider = envelope["state"]["target"]["provider"]
    if len(document.encode("utf-8")) > PROVIDER_BODY_LIMITS[provider]:
        raise ProtocolError(f"The document exceeds the {provider} body limit.")
    return document


def extract_carrier(document: str) -> dict[str, Any]:
    """Extract and verify one unique final review-exchange carrier."""
    if not isinstance(document, str):
        raise ProtocolError("The carrier document must be text.")
    try:
        encoded_document = document.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProtocolError("The carrier document is not valid UTF-8.") from error
    if len(encoded_document) > MAX_INPUT_BYTES:
        raise ProtocolError("The carrier document is larger than 1 MiB.")
    matches = list(CARRIER_PATTERN.finditer(document))
    if len(matches) != 1:
        raise ProtocolError(
            "The document must contain exactly one review-exchange carrier."
        )
    match = matches[0]
    marker_start = match.start()
    if marker_start == 0:
        visible = ""
    elif document[:marker_start].endswith("\n\n"):
        visible = document[: marker_start - 2]
    else:
        raise ProtocolError("The review-exchange carrier is not a final section.")
    if CARRIER_PREFIX in visible:
        raise ProtocolError("The document contains a malformed or repeated carrier.")
    top_level_markdown_lines(visible, require_closed=True)
    suffix = document[match.end() :]
    if not suffix.startswith("\n```json\n") or not suffix.endswith("\n```\n"):
        raise ProtocolError("The review-exchange JSON fence is malformed or not final.")
    if (
        match.start(),
        match.end(),
        match.group(0),
    ) not in top_level_markdown_lines(document, require_closed=True):
        raise ProtocolError("The review-exchange marker is not a top-level line.")
    encoded = suffix[len("\n```json\n") : -len("\n```\n")]
    if "\n" in encoded:
        raise ProtocolError("The carrier JSON must use canonical one-line encoding.")
    envelope = verify_envelope(parse_json_bytes(encoded.encode("utf-8")))
    if canonical_json(envelope) != encoded:
        raise ProtocolError("The carrier JSON is not canonical.")
    if match.group(1) != _carrier_kind(envelope):
        raise ProtocolError("The carrier kind does not match the envelope.")
    if match.group(2) != envelope["state_sha256"]:
        raise ProtocolError("The carrier marker digest does not match the envelope.")
    expected_visible = envelope["state"]["artifact_binding"]["visible_content_sha256"]
    if sha256_text(visible) != expected_visible:
        raise ProtocolError("The carrier visible-content digest does not match.")
    provider = envelope["state"]["target"]["provider"]
    if len(encoded_document) > PROVIDER_BODY_LIMITS[provider]:
        raise ProtocolError(f"The document exceeds the {provider} body limit.")
    return envelope


def _read_input(path: str) -> bytes:
    try:
        if path == "-":
            content = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with Path(path).open("rb") as stream:
                content = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as error:
        raise OperationalError(f"The input cannot be read: {error}") from error
    if len(content) > MAX_INPUT_BYTES:
        raise ProtocolError("The input is larger than 1 MiB.")
    return content


def _parse_render_request(value: object) -> tuple[str, dict[str, Any], str]:
    request = _object(
        value,
        "render request",
        frozenset({"visible_content", "envelope", "kind"}),
    )
    visible = request["visible_content"]
    if not isinstance(visible, str):
        raise ProtocolError("The render visible content must be text.")
    kind = _enum(
        request["kind"], "render carrier kind", frozenset({"state", "author-event"})
    )
    return visible, verify_envelope(request["envelope"]), kind


def main(argv: Sequence[str] | None = None) -> int:
    """Run one pure review-exchange operation."""
    parser = argument_parser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("reduce", "verify", "extract", "render"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument(
            "input", help="A JSON or Markdown file, or '-' for stdin."
        )
    arguments = parser.parse_args(argv)
    try:
        content = _read_input(arguments.input)
        if arguments.command == "extract":
            try:
                document = content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ProtocolError("The carrier input is not valid UTF-8.") from error
            output = canonical_json(extract_carrier(document)) + "\n"
        else:
            value = parse_json_bytes(content)
            if arguments.command == "reduce":
                output = canonical_json(reduce_request(value)) + "\n"
            elif arguments.command == "verify":
                output = canonical_json(verify_envelope(value)) + "\n"
            else:
                visible, envelope, kind = _parse_render_request(value)
                output = render_carrier(visible, envelope, kind)
        write_utf8_stdout(output)
    except ProtocolError as error:
        print(_single_line_diagnostic(error), file=sys.stderr)
        return 1
    except OperationalError as error:
        print(_single_line_diagnostic(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
