"""Faithful author and reviewer replays for terminal GO delivery."""

from __future__ import annotations

from typing import Any, cast

from tests.unit.test_pr_review_go_delivery import load_module
from tests.unit.test_review_exchange_requirement_evidence import (
    HEX_A,
    HEX_B,
    HEX_C,
    finding,
    record,
    rows,
    target,
)


def _delivery() -> Any:
    return load_module()


def _binding(delivery: Any) -> Any:
    return delivery.ReviewBinding(
        repository="owner/repository",
        number=7,
        url="https://github.com/owner/repository/pull/7",
        base_oid="a" * 40,
        head_oid="b" * 40,
    )


def _initial_envelope(
    delivery: Any, requirement_evidence: dict[str, Any] | None = None
) -> dict[str, Any]:
    exchange = delivery.review_exchange
    event: dict[str, Any] = {
        "event_type": "reviewer_assessment",
        "exchange_id": "exchange-7",
        "prior_state_sha256": None,
        "round": 1,
        "surface": "pull_request",
        "target": target(),
        "requirements_sha256": HEX_C,
        "supersedes_state_sha256": None,
        "artifact_binding": {
            "revision": "revision-1",
            "sha256": HEX_B,
            "visible_content_sha256": HEX_A,
        },
        "scope": ["path:a.py", "path:b.py"],
        "coverage_complete": False,
        "responses": [],
        "new_findings": [finding()],
        "stop_reason": None,
    }
    if requirement_evidence is not None:
        event["requirement_evidence"] = requirement_evidence
    return cast(
        dict[str, Any],
        exchange.reduce_request({"previous": None, "event": event})["envelope"],
    )


def _author_event(
    previous: dict[str, Any],
    coverage_changes: bool,
    visible_sha256: str = HEX_B,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_type": "author_response",
        "exchange_id": "exchange-7",
        "prior_state_sha256": previous["state_sha256"],
        "artifact_binding": {
            "revision": "revision-2",
            "sha256": HEX_A,
            "visible_content_sha256": visible_sha256,
        },
        "scope": ["path:a.py", "path:b.py"],
        "scope_change_reason": None,
        "responses": [
            {
                "finding_id": "F-001",
                "kind": "fix",
                "evidence": ["The correction is in revision-2."],
                "tradeoff": None,
            }
        ],
    }
    if coverage_changes:
        event["coverage_changes"] = {
            "inventory_sha256": HEX_A,
            "retained_sections": ["S2"],
            "repeated_sections": ["S1"],
            "changed_dependencies": [],
            "causes": ["S1:finding_corrected:F-001"],
        }
    return event


def test_author_event_input_preserves_coverage_changes() -> None:
    delivery = _delivery()
    exchange = delivery.review_exchange
    initial = _initial_envelope(delivery)
    visible = "The author corrected F-001 and repeated S1."
    reduced = exchange.reduce_request(
        {
            "previous": initial,
            "event": _author_event(initial, True, exchange.sha256_text(visible)),
        }
    )
    author_record = cast(dict[str, Any], reduced["author_event"])
    assert "coverage_changes" in author_record["state"]

    carrier = exchange.render_carrier(visible, author_record, "author-event")
    persisted = exchange.extract_carrier(carrier)

    replay = exchange.reduce_request(
        {"previous": initial, "event": delivery._author_event_input(persisted)}
    )

    assert replay["author_event"] == author_record


def test_corrective_assessment_replays_replaced_requirement_evidence() -> None:
    delivery = _delivery()
    exchange = delivery.review_exchange
    first_evidence = record(
        first=rows(result="missing_coverage", finding_ids=["F-001"])
    )
    initial = _initial_envelope(delivery, first_evidence)
    answered = cast(
        dict[str, Any],
        exchange.reduce_request(
            {"previous": initial, "event": _author_event(initial, False)}
        )["envelope"],
    )
    replacement = record(
        first=rows(result="covered"),
        second=rows(section="S2", result="covered"),
    )
    corrective: dict[str, Any] = {
        "event_type": "reviewer_assessment",
        "exchange_id": "exchange-7",
        "prior_state_sha256": answered["state_sha256"],
        "round": 2,
        "artifact_binding": answered["state"]["artifact_binding"],
        "scope": answered["state"]["scope"],
        "coverage_complete": True,
        "responses": [
            {
                "finding_id": "F-001",
                "kind": "resolve",
                "evidence": ["The revision-2 guard covers the failing case."],
                "closure_condition": None,
            }
        ],
        "new_findings": [],
        "stop_reason": None,
        "requirement_evidence": replacement,
    }
    current = cast(
        dict[str, Any],
        exchange.reduce_request({"previous": answered, "event": corrective})[
            "envelope"
        ],
    )

    inferred = delivery._infer_reviewer_event(answered, current, None)
    replay = exchange.reduce_request({"previous": answered, "event": inferred})

    assert replay["envelope"] == current


def test_publish_round_batch_returns_the_graphql_review_id(monkeypatch: Any) -> None:
    delivery = _delivery()
    forge = delivery.GitHubForge(_binding(delivery))
    monkeypatch.setattr(
        delivery,
        "_gh",
        lambda *arguments, **options: (
            '{"id":5824368425,"node_id":"PRR_kwDOTfsgBs8AAAABWyjPKQ"}'
        ),
    )

    review_id = forge.publish_round_batch("Round carrier.", "b" * 40, ())

    assert review_id == "PRR_kwDOTfsgBs8AAAABWyjPKQ"


def test_publish_round_batch_normalizes_an_integer_rest_id(
    monkeypatch: Any,
) -> None:
    delivery = _delivery()
    forge = delivery.GitHubForge(_binding(delivery))
    monkeypatch.setattr(
        delivery, "_gh", lambda *arguments, **options: '{"id":5824368425}'
    )

    review_id = forge.publish_round_batch("Round carrier.", "b" * 40, ())

    assert review_id == "5824368425"
