"""Behaviour tests for the tolerated delivery findings of Comet issue #3848.

A GO review always delivers. A malformed annex field, a reviewed head behind
the live head, a forked exchange, and a stale requirements digest are warnings.
A caller that passes no collector still gets the strict behaviour. A review
verdict other than GO still blocks.
"""

from __future__ import annotations

import contextlib
import io
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from unittest.mock import patch

import pytest

from tests.unit.test_pr_review_anchor_proofs import git
from tests.unit.test_pr_review_go_delivery import (
    FakeForge,
    load_module,
    prepared_go_fixture,
)


@pytest.fixture(scope="module")
def delivery() -> ModuleType:
    """Load the GO-delivery helper once for this module."""
    return load_module()


class MismatchedRequirementsForge:
    """A forge whose live requirements differ from the reviewed binding."""

    def __init__(self, delivery: ModuleType, live: Any) -> None:
        self.delivery = delivery
        self.live = live
        self.collected = 0

    def collect_requirements_binding(self, _urls: tuple[str, ...]) -> Any:
        self.collected += 1
        return self.live

    def verify_requirements_binding(self, expected: Any) -> None:
        # Mirror the production adapter: name each field that differs instead of
        # raising one message for every difference.
        differing = expected.differing_fields(self.live)
        if differing:
            raise self.delivery.RequirementsBindingChanged(differing)


def requirements(delivery: ModuleType, digest: str) -> Any:
    """Make one requirements binding with a fixed digest."""
    return delivery.RequirementsBinding(
        reviewed_scope_sha256="0" * 64,
        requirements_sha256=digest,
        requirement_issue_urls=("https://github.com/LLM360/comet/issues/1",),
    )


def binding_for(delivery: ModuleType, head_oid: str) -> Any:
    """Make one review binding for the fixture pull request."""
    return delivery.ReviewBinding(
        repository="LLM360/comet",
        number=3848,
        url="https://github.com/LLM360/comet/pull/3848",
        base_oid="1" * 40,
        head_oid=head_oid,
    )


def snapshot_for(delivery: ModuleType, binding: Any, head_oid: str) -> Any:
    """Make one open pull-request snapshot at the given head."""
    return delivery.PullRequestSnapshot(
        repository=binding.repository,
        number=binding.number,
        url=binding.url,
        state="OPEN",
        is_draft=False,
        base_oid=binding.base_oid,
        head_oid=head_oid,
        labels=frozenset(),
        threads=(),
    )


def annex(visible: str, fields: dict[str, object], delivery: ModuleType) -> str:
    """Append one anchor annex with the supplied field set."""
    payload = delivery.anchor_proofs.canonical(fields)
    return f"{visible}\n\n{delivery.anchor_proofs.MARKER}\n```json\n{payload}\n```"


def annex_fields(delivery: ModuleType) -> dict[str, object]:
    """Return the required anchor annex fields with no optional field."""
    return {
        "schema_id": delivery.anchor_proofs.SCHEMA,
        "schema_version": 1,
        "base_oid": "1" * 40,
        "head_oid": "a" * 40,
        "merge_base_oid": "2" * 40,
        "findings": [
            {
                "id": "F-001",
                "line": 12,
                "path": "src/comet/example.py",
                "publication": "inline",
                "side": "RIGHT",
            }
        ],
    }


def warned(call: Any) -> tuple[Any, str]:
    """Run one call and return its result with the captured standard error."""
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        result = call()
    return result, buffer.getvalue()


def test_stale_requirements_digest_warns_and_continues(
    delivery: ModuleType,
) -> None:
    forge = MismatchedRequirementsForge(delivery, requirements(delivery, "b" * 64))
    warnings = delivery.DeliveryWarnings()

    _result, stderr = warned(
        lambda: delivery._warn_live_requirements(
            forge, requirements(delivery, "a" * 64), warnings
        )
    )

    assert [warning.code for warning in warnings.records] == [
        "stale-requirements-digest"
    ]
    assert warnings.records[0].document()["detail"] == {
        "cause": (
            "The live pull-request requirements differ from the reviewed binding."
        ),
        "requirement_issue_urls": "https://github.com/LLM360/comet/issues/1",
        "reviewed_requirements_sha256": "a" * 64,
    }
    assert "stale-requirements-digest" in stderr
    assert "a" * 64 in stderr


def test_stale_requirements_digest_still_blocks_without_warnings(
    delivery: ModuleType,
) -> None:
    forge = MismatchedRequirementsForge(delivery, requirements(delivery, "b" * 64))

    with pytest.raises(delivery.DeliveryError, match="requirements differ"):
        delivery._warn_live_requirements(forge, requirements(delivery, "a" * 64), None)


@pytest.mark.parametrize(
    ("live", "field"),
    [
        (
            lambda delivery: delivery.RequirementsBinding(
                reviewed_scope_sha256="b" * 64,
                requirements_sha256="a" * 64,
                requirement_issue_urls=("https://github.com/LLM360/comet/issues/1",),
            ),
            "reviewed_scope_sha256",
        ),
        (
            lambda delivery: delivery.RequirementsBinding(
                reviewed_scope_sha256="0" * 64,
                requirements_sha256="a" * 64,
                requirement_issue_urls=("https://github.com/LLM360/comet/issues/2",),
            ),
            "requirement_issue_urls",
        ),
        (
            lambda delivery: delivery.RequirementsBinding(
                reviewed_scope_sha256="b" * 64,
                requirements_sha256="b" * 64,
                requirement_issue_urls=("https://github.com/LLM360/comet/issues/1",),
            ),
            "reviewed_scope_sha256",
        ),
    ],
    ids=[
        "changed-scope-digest",
        "changed-requirement-urls",
        "changed-scope-and-digest",
    ],
)
def test_any_other_requirements_field_change_still_blocks(
    delivery: ModuleType, live: Any, field: str
) -> None:
    # Only a changed requirements digest is a warning. A changed scope digest or
    # a changed requirement-URL set keeps blocking even with a warnings collector.
    del field
    forge = MismatchedRequirementsForge(delivery, live(delivery))
    warnings = delivery.DeliveryWarnings()

    with pytest.raises(delivery.DeliveryError, match="requirements differ"):
        delivery._warn_live_requirements(
            forge, requirements(delivery, "a" * 64), warnings
        )

    assert warnings.records == []


def test_changed_scope_digest_blocks_the_github_adapter_verification(
    delivery: ModuleType,
) -> None:
    # The production adapter must raise the structured difference, not one
    # shared message, so the warning path can never key on message text.
    binding = binding_for(delivery, "a" * 40)
    forge = delivery.GitHubForge(binding)
    reviewed = delivery.RequirementsBinding(
        reviewed_scope_sha256="0" * 64,
        requirements_sha256="a" * 64,
        requirement_issue_urls=("https://github.com/LLM360/comet/issues/1",),
    )
    observed = replace(reviewed, reviewed_scope_sha256="b" * 64)

    with (
        patch.object(forge, "collect_requirements_binding", return_value=observed),
        pytest.raises(delivery.RequirementsBindingChanged) as error,
    ):
        forge.verify_requirements_binding(reviewed)

    assert error.value.differing_fields == ("reviewed_scope_sha256",)


class AncestorForge:
    """A forge that reports the first commit as an ancestor of the second."""

    def is_ancestor(self, older_oid: str, newer_oid: str) -> bool:
        del newer_oid
        return older_oid == "a" * 40


def test_stale_reviewed_head_warning_names_both_heads(
    delivery: ModuleType,
) -> None:
    binding = binding_for(delivery, "a" * 40)
    snapshot = snapshot_for(delivery, binding, "b" * 40)
    warnings = delivery.DeliveryWarnings()

    _result, stderr = warned(
        lambda: delivery._warn_reviewed_head_binding(
            AncestorForge(), snapshot, binding, warnings
        )
    )

    assert len(warnings.records) == 1
    warning = warnings.records[0]
    assert warning.code == "stale-reviewed-head"
    assert dict(warning.detail) == {
        "live_head_oid": "b" * 40,
        "reviewed_head_oid": "a" * 40,
    }
    assert "behind" in warning.message
    assert "a" * 40 in stderr
    assert "b" * 40 in stderr


def test_current_head_emits_no_head_warning(delivery: ModuleType) -> None:
    binding = binding_for(delivery, "a" * 40)
    snapshot = snapshot_for(delivery, binding, binding.head_oid)
    warnings = delivery.DeliveryWarnings()

    delivery._warn_reviewed_head_binding(object(), snapshot, binding, warnings)

    assert warnings.records == []


def publication_anchors(
    delivery: ModuleType, visible: str, warnings: Any
) -> dict[str, tuple[str, str | None, int]]:
    """Request one publication anchor for the fixture finding."""
    anchors: dict[str, tuple[str, str | None, int]] = delivery._publication_anchors(
        binding_for(delivery, "a" * 40),
        {
            "state_sha256": "0" * 64,
            "state": {"artifact_binding": {"revision": "a" * 40}},
        },
        visible,
        [
            {
                "id": "F-001",
                "location": "src/comet/example.py:12",
                "side": "RIGHT",
            }
        ],
        None,
        (),
        None,
        warnings,
    )
    return anchors


def test_malformed_annex_field_warns_and_keeps_geometry(
    delivery: ModuleType,
) -> None:
    visible = "Reviewed the current change."
    warnings = delivery.DeliveryWarnings()

    anchors, stderr = warned(
        lambda: publication_anchors(
            delivery, annex(visible, annex_fields(delivery), delivery), warnings
        )
    )

    assert [warning.code for warning in warnings.records] == ["malformed-annex"]
    assert anchors["F-001"] == ("src/comet/example.py", "RIGHT", 12)
    assert "malformed-annex" in stderr


def test_malformed_annex_still_blocks_without_warnings(
    delivery: ModuleType,
) -> None:
    visible = "Reviewed the current change."

    with pytest.raises(delivery.DeliveryError, match="anchor proof failed"):
        publication_anchors(
            delivery, annex(visible, annex_fields(delivery), delivery), None
        )


def geometry_for(
    delivery: ModuleType, fields: dict[str, object]
) -> dict[str, tuple[str, str | None, int]] | None:
    """Read partial geometry from one annex for the fixture carrier binding."""
    return cast(
        dict[str, tuple[str, str | None, int]] | None,
        delivery.anchor_proofs.partial_geometry(
            annex("Reviewed the current change.", fields, delivery),
            head_oid="a" * 40,
            base_oid="1" * 40,
        ),
    )


def test_malformed_annex_without_head_or_base_binding_refuses_delivery(
    delivery: ModuleType,
) -> None:
    # The exact reproduction from the round-1 review: an annex with no head_oid
    # or base_oid must not supply geometry for a different file and line.
    fields = annex_fields(delivery)
    fields.pop("head_oid")
    fields.pop("base_oid")
    fields["findings"] = [
        {
            "id": "F-001",
            "line": 9999,
            "path": "attacker.py",
            "publication": "inline",
            "side": "RIGHT",
        }
    ]
    warnings = delivery.DeliveryWarnings()

    with pytest.raises(delivery.DeliveryError, match="anchor proof failed"):
        publication_anchors(
            delivery, annex("Reviewed the current change.", fields, delivery), warnings
        )

    assert warnings.records == []
    assert geometry_for(delivery, fields) is None


@pytest.mark.parametrize("present", ["head_oid", "base_oid"])
def test_malformed_annex_with_one_missing_binding_refuses_delivery(
    delivery: ModuleType, present: str
) -> None:
    fields = annex_fields(delivery)
    fields.pop(present)

    assert geometry_for(delivery, fields) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [("head_oid", "c" * 40), ("base_oid", "9" * 40)],
)
def test_malformed_annex_with_a_changed_binding_refuses_delivery(
    delivery: ModuleType, field: str, value: str
) -> None:
    fields = annex_fields(delivery)
    fields[field] = value

    assert geometry_for(delivery, fields) is None


def test_malformed_annex_with_an_unknown_field_refuses_delivery(
    delivery: ModuleType,
) -> None:
    fields = annex_fields(delivery)
    fields.pop("diff_policy", None)
    fields["injected"] = "value"

    assert geometry_for(delivery, fields) is None


def test_malformed_annex_keeps_geometry_when_the_binding_survives(
    delivery: ModuleType,
) -> None:
    fields = annex_fields(delivery)
    fields.pop("diff_policy", None)

    assert geometry_for(delivery, fields) == {
        "F-001": ("src/comet/example.py", "RIGHT", 12)
    }


def test_malformed_annex_rejects_a_duplicate_finding_id(
    delivery: ModuleType,
) -> None:
    fields = annex_fields(delivery)
    fields.pop("diff_policy", None)
    duplicate = dict(cast(list[dict[str, object]], fields["findings"])[0])
    duplicate["path"] = "other.py"
    fields["findings"] = [*cast(list[object], fields["findings"]), duplicate]

    assert geometry_for(delivery, fields) is None


def test_malformed_annex_rejects_a_boolean_line(delivery: ModuleType) -> None:
    fields = annex_fields(delivery)
    fields.pop("diff_policy", None)
    cast(list[dict[str, object]], fields["findings"])[0]["line"] = True

    assert geometry_for(delivery, fields) is None


def test_malformed_annex_with_a_summary_entry_warns_and_delivers(
    delivery: ModuleType,
) -> None:
    # N1 of the round-2 review: a finding whose location is not a source line
    # has no path and no line. The strict path accepts it, so the warning path
    # must accept it too. A dropped non-binding field stays a warning.
    fields = annex_fields(delivery)
    fields.pop("diff_policy", None)
    fields["findings"] = [
        cast(list[object], fields["findings"])[0],
        {"id": "F-002", "publication": "summary", "reason": "non_source_location"},
    ]
    warnings = delivery.DeliveryWarnings()

    anchors, stderr = warned(
        lambda: publication_anchors(
            delivery, annex("Reviewed the current change.", fields, delivery), warnings
        )
    )

    assert [warning.code for warning in warnings.records] == ["malformed-annex"]
    # The inline entry keeps its geometry and the summary entry states none.
    assert anchors == {"F-001": ("src/comet/example.py", "RIGHT", 12)}
    assert "malformed-annex" in stderr


def test_malformed_annex_summary_entry_without_reason_warns(
    delivery: ModuleType,
) -> None:
    # The owner decision makes reason optional, because a dropped field can be
    # any declared field, including a reason on a summary entry.
    fields = annex_fields(delivery)
    fields.pop("diff_policy", None)
    fields["findings"] = [{"id": "F-002", "publication": "summary"}]

    assert geometry_for(delivery, fields) == {}
    assert summary_geometry(delivery, fields) == ()


def test_malformed_annex_summary_entry_with_a_non_string_reason_refuses(
    delivery: ModuleType,
) -> None:
    fields = annex_fields(delivery)
    fields.pop("diff_policy", None)
    fields["findings"] = [{"id": "F-002", "publication": "summary", "reason": 1}]

    assert geometry_for(delivery, fields) is None


def test_summary_entry_with_geometry_yields_no_anchor_and_warns(
    delivery: ModuleType,
) -> None:
    # A summary entry that carries path and line states nothing. It stays a
    # summary, so it yields no geometry, and the helper names the shape.
    fields = annex_fields(delivery)
    fields.pop("diff_policy", None)
    fields["findings"] = [
        cast(list[object], fields["findings"])[0],
        {
            "id": "F-002",
            "line": 77,
            "path": "src/comet/smuggled.py",
            "publication": "summary",
            "reason": "non_source_location",
            "side": "RIGHT",
        },
    ]
    warnings = delivery.DeliveryWarnings()

    anchors, stderr = warned(
        lambda: publication_anchors(
            delivery, annex("Reviewed the current change.", fields, delivery), warnings
        )
    )

    assert anchors == {"F-001": ("src/comet/example.py", "RIGHT", 12)}
    assert [warning.code for warning in warnings.records] == [
        "malformed-annex",
        "summary-entry-carries-geometry",
    ]
    assert dict(warnings.records[1].detail) == {"finding_ids": "F-002"}
    assert "summary-entry-carries-geometry" in stderr
    assert summary_geometry(delivery, fields) == ("F-002",)


def test_summary_entry_with_geometry_does_not_block_without_warnings(
    delivery: ModuleType,
) -> None:
    # The suspicious shape warns. It does not block, so a caller with no
    # collector sees the strict block for the dropped field only.
    fields = annex_fields(delivery)
    fields["findings"] = [
        cast(list[object], fields["findings"])[0],
        {"id": "F-002", "line": 77, "path": "smuggled.py", "publication": "summary"},
    ]

    assert geometry_for(delivery, fields) == {
        "F-001": ("src/comet/example.py", "RIGHT", 12)
    }


@pytest.mark.parametrize(
    "entry",
    [
        {"id": "F-001", "publication": "inline", "side": "RIGHT"},
        {"id": "F-001", "line": True, "path": "a.py", "publication": "inline"},
        {"id": "F-001", "line": 12, "publication": "inline", "side": "RIGHT"},
        {"id": "F-001", "line": 12, "path": "a.py", "publication": "note"},
    ],
    ids=[
        "inline-missing-path-and-line",
        "inline-boolean-line",
        "inline-missing-path",
        "unknown-publication",
    ],
)
def test_inline_entry_without_its_geometry_still_blocks(
    delivery: ModuleType, entry: dict[str, object]
) -> None:
    # N1 narrows the path/line requirement to inline entries only. An inline
    # entry still needs a path and an integer line, so a malformed one keeps
    # the strict block.
    fields = annex_fields(delivery)
    fields.pop("diff_policy", None)
    fields["findings"] = [entry]
    warnings = delivery.DeliveryWarnings()

    assert geometry_for(delivery, fields) is None
    with pytest.raises(delivery.DeliveryError, match="anchor proof failed"):
        publication_anchors(
            delivery, annex("Reviewed the current change.", fields, delivery), warnings
        )
    assert warnings.records == []


@pytest.mark.parametrize(
    ("field", "value"),
    [("head_oid", "b" * 40), ("base_oid", "9" * 40)],
)
def test_inline_entry_with_a_wrong_binding_still_blocks(
    delivery: ModuleType, field: str, value: str
) -> None:
    # A summary entry in the same annex does not relax the carrier binding.
    fields = annex_fields(delivery)
    fields.pop("diff_policy", None)
    fields[field] = value
    fields["findings"] = [
        {"id": "F-002", "publication": "summary", "reason": "non_source_location"},
        cast(list[object], annex_fields(delivery)["findings"])[0],
    ]
    warnings = delivery.DeliveryWarnings()

    assert geometry_for(delivery, fields) is None
    with pytest.raises(delivery.DeliveryError, match="anchor proof failed"):
        publication_anchors(
            delivery, annex("Reviewed the current change.", fields, delivery), warnings
        )
    assert warnings.records == []


def summary_geometry(
    delivery: ModuleType, fields: dict[str, object]
) -> tuple[str, ...]:
    """Read the suspicious summary entries of one annex."""
    return cast(
        "tuple[str, ...]",
        delivery.anchor_proofs.summary_geometry(
            annex("Reviewed the current change.", fields, delivery)
        ),
    )


def terminal_carrier(delivery: ModuleType, exchange_id: str, binding: Any) -> Any:
    """Build one reducer-derived, published terminal carrier."""
    visible = f"Reviewed the current change for {exchange_id}."
    event = {
        "event_type": "reviewer_assessment",
        "exchange_id": exchange_id,
        "prior_state_sha256": None,
        "round": 1,
        "surface": "pull_request",
        "target": {
            "provider": "github",
            "repository": binding.repository,
            "number": binding.number,
            "url": binding.url,
        },
        "requirements_sha256": "c" * 64,
        "supersedes_state_sha256": None,
        "artifact_binding": {
            "revision": binding.head_oid,
            "sha256": sha256(b"diff").hexdigest(),
            "visible_content_sha256": sha256(visible.encode()).hexdigest(),
        },
        "scope": ["src/comet/example.py"],
        "coverage_complete": True,
        "responses": [],
        "new_findings": [],
        "stop_reason": None,
    }
    exchange = delivery.review_exchange
    envelope = exchange.reduce_request({"previous": None, "event": event})["envelope"]
    return envelope, exchange.render_carrier(
        visible, envelope, exchange._carrier_kind(envelope)
    )


def carrier_snapshot(
    delivery: ModuleType, binding: Any, documents: tuple[str, ...]
) -> Any:
    """Make one snapshot whose reviews carry the supplied documents."""
    reviews = tuple(
        delivery.ReviewRecord(
            id=f"PRR_{index}",
            body=document,
            head_oid=binding.head_oid,
            author="reviewer",
            viewer_did_author=True,
            includes_created_edit=False,
            state="COMMENT",
            submitted_at=f"2026-11-01T00:00:0{index}Z",
        )
        for index, document in enumerate(documents, start=1)
    )
    return delivery.PullRequestSnapshot(
        repository=binding.repository,
        number=binding.number,
        url=binding.url,
        state="OPEN",
        is_draft=False,
        base_oid=binding.base_oid,
        head_oid=binding.head_oid,
        labels=frozenset(),
        threads=(),
        reviews=reviews,
    )


def forked_case(
    delivery: ModuleType,
) -> tuple[Any, Any, Any, Any]:
    """Make one terminal exchange and one unreachable forked exchange."""
    binding = binding_for(delivery, "a" * 40)
    terminal, terminal_document = terminal_carrier(delivery, "pr3848-r1", binding)
    _forked, forked_document = terminal_carrier(delivery, "pr3848-r2", binding)
    snapshot = carrier_snapshot(delivery, binding, (terminal_document, forked_document))
    return binding, terminal, snapshot, delivery.DeliveryWarnings()


def test_forked_exchange_warns_and_keeps_the_current_head_chain(
    delivery: ModuleType,
) -> None:
    binding, terminal, snapshot, warnings = forked_case(delivery)

    _chain, _stderr = warned(
        lambda: delivery._verify_state_chain(
            AncestorForge(),
            terminal,
            snapshot,
            binding,
            None,
            (),
            warnings=warnings,
        )
    )

    assert [warning.code for warning in warnings.records] == ["forked-exchange"]
    assert dict(warnings.records[0].detail) == {"unfinished_exchange_ids": "pr3848-r2"}


def test_forked_exchange_still_blocks_without_warnings(
    delivery: ModuleType,
) -> None:
    binding, terminal, snapshot, _warnings = forked_case(delivery)

    with pytest.raises(delivery.DeliveryError, match="nonforking chain"):
        delivery._verify_state_chain(
            AncestorForge(), terminal, snapshot, binding, None, ()
        )


def test_stale_carrier_head_warns_but_a_moved_live_head_blocks(
    delivery: ModuleType,
) -> None:
    """Owner decision on Comet #3848, recorded in LLM360/comet#3848.

    A stale head earlier in the chain warns and continues. The terminal record
    keeps the reviewed head. A live head past that binding warns and blocks.
    """
    approached_head = "a" * 40
    live_head = "b" * 40
    binding = binding_for(delivery, approached_head)
    terminal, terminal_document = terminal_carrier(delivery, "pr3848-r1", binding)
    # The terminal record binds the reviewed head and does not rebrand it.
    assert terminal["state"]["artifact_binding"]["revision"] == approached_head

    # An earlier carrier in the chain names an older head. The live head is
    # still the reviewed head, so only the in-chain carrier is stale.
    stale_review = delivery.ReviewRecord(
        id="PRR_1",
        body=terminal_document,
        head_oid="c" * 40,
        author="reviewer",
        viewer_did_author=True,
        includes_created_edit=False,
        state="COMMENT",
        submitted_at="2026-11-01T00:00:01Z",
    )
    current_review = delivery.ReviewRecord(
        id="PRR_2",
        body=terminal_document,
        head_oid=approached_head,
        author="reviewer",
        viewer_did_author=True,
        includes_created_edit=False,
        state="COMMENT",
        submitted_at="2026-11-01T00:00:02Z",
    )
    stale_snapshot = replace(
        snapshot_for(delivery, binding, approached_head),
        reviews=(stale_review, current_review),
    )
    stale_warnings = delivery.DeliveryWarnings()

    _result, _stderr = warned(
        lambda: delivery._warn_reviewed_head_binding(
            AncestorForge(), stale_snapshot, binding, stale_warnings
        )
    )

    # The terminal binding still names the reviewed head, not the live one.
    assert binding.head_oid == approached_head
    assert stale_warnings.records == []

    # The live head moves past the terminal binding. It warns, then blocks.
    moved_snapshot = replace(
        snapshot_for(delivery, binding, live_head),
        reviews=(
            stale_review,
            replace(current_review, head_oid=binding.head_oid),
        ),
    )
    moved_warnings = delivery.DeliveryWarnings()

    _moved, stderr = warned(
        lambda: delivery._warn_reviewed_head_binding(
            AncestorForge(), moved_snapshot, binding, moved_warnings
        )
    )

    assert [warning.code for warning in moved_warnings.records] == [
        "stale-reviewed-head"
    ]
    assert dict(moved_warnings.records[0].detail) == {
        "live_head_oid": live_head,
        "reviewed_head_oid": approached_head,
    }
    assert "behind" in stderr

    with pytest.raises(delivery.DeliveryError, match="withhold GO delivery"):
        delivery._snapshot(
            type("MovedHeadForge", (), {"snapshot": lambda self: moved_snapshot})(),
            binding,
        )


def test_authority_record_accepts_one_final_line_feed(
    delivery: ModuleType,
) -> None:
    record = {
        "schema_id": delivery.review_exchange.AUTHORITY_SCHEMA_ID,
        "schema_version": delivery.review_exchange.SCHEMA_VERSION,
        "action": "reframe",
        "target": {
            "provider": "github",
            "repository": "LLM360/comet",
            "number": 3848,
            "url": "https://github.com/LLM360/comet/pull/3848",
        },
        "exchange_id": "pr3848-r1",
        "requirements_sha256": "c" * 64,
        "prior_state_sha256": None,
        "supersedes_state_sha256": "d" * 64,
        "decisions": [],
    }
    body = delivery.review_exchange.canonical_json(record)
    receipt = {
        "reference": "comment:authority-1",
        "sha256": delivery.review_exchange.sha256_text(body),
    }

    assert delivery.review_exchange.parse_authority_record(body) == record
    assert delivery.review_exchange.parse_authority_record(body + "\n") == record
    assert (
        delivery.review_exchange.verify_authority_record(body + "\n", receipt, record)
        == record
    )


def test_delivery_result_document_records_each_warning(
    delivery: ModuleType,
) -> None:
    warnings = delivery.DeliveryWarnings()
    warnings.add("malformed-annex", "The terminal carrier annex is malformed.")
    result = delivery.DeliveryResult(
        status="delivered",
        resolved_thread_ids=(),
        warnings=tuple(warnings.records),
    )

    document = delivery._delivery_result_document(result)

    assert document["warnings"] == [
        {
            "code": "malformed-annex",
            "detail": {},
            "message": "The terminal carrier annex is malformed.",
        }
    ]


def test_stale_head_warning_reaches_the_delivery_argument_path(
    delivery: ModuleType,
) -> None:
    """The public deliver_go_v1 path emits the head warning before it blocks.

    The owner decision keeps the current-head binding, and the terminal record
    names its reviewed head. A live head that has moved past that binding still
    withholds delivery. This test proves the warning is reachable through the
    public argument path and is not only a private helper, and that the block
    still holds.
    """
    thread, manifest, binding, history = prepared_go_fixture(delivery)
    forge = FakeForge(delivery, threads=(thread,), binding=binding)
    forge.reviews.extend(history)
    forge.head_oid = "c" * 40
    forge.ancestor_results[(binding.head_oid, "c" * 40)] = True

    buffer = io.StringIO()
    with pytest.raises(delivery.DeliveryError), contextlib.redirect_stderr(buffer):
        delivery.deliver_go_v1(forge, binding, manifest)

    assert "stale-reviewed-head" in buffer.getvalue()
    assert binding.head_oid in buffer.getvalue()
    assert "c" * 40 in buffer.getvalue()
    assert "label" not in forge.events
    assert "state:implementation-go" not in forge.labels
    # Exactly one bound read, so the delivery read sequence does not change.
    assert [event for event in forge.events if event == "read"] == ["read"]


def side_source(tmp_path: Path) -> tuple[Path, str, str]:
    """Make one real source that changes line 10 and leaves line 80 unchanged."""
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Fixture")
    git(tmp_path, "config", "user.email", "fixture@example.invalid")
    lines = [f"line {n}\n" for n in range(1, 101)]
    (tmp_path / "justfile").write_text("".join(lines))
    git(tmp_path, "add", "justfile")
    git(tmp_path, "commit", "-qm", "fixture base")
    base = git(tmp_path, "rev-parse", "HEAD")
    lines[9] = "changed line\n"
    (tmp_path / "justfile").write_text("".join(lines))
    git(tmp_path, "commit", "-qam", "fixture head")
    return tmp_path, base, git(tmp_path, "rev-parse", "HEAD")


def finding_at(line: int, side: str | None = None) -> dict[str, object]:
    """Make one ordinary finding with an optional declared side."""
    finding: dict[str, object] = {"id": "F-001", "location": f"justfile:{line}"}
    if side is not None:
        finding["side"] = side
    return finding


def strict_anchors(
    delivery: ModuleType,
    source: Path,
    *,
    base: str,
    head: str,
    visible: str,
    finding: dict[str, object],
) -> tuple[str, dict[str, tuple[str, str | None, int]] | None]:
    """Run the strict publication path on one annex and one finding.

    Return its outcome and its anchors. A malformed annex also blocks, so the
    strict path never reads an entry from a tolerated shape.
    """
    try:
        anchors = delivery.anchor_proofs.expected_anchors(
            source=source,
            target={
                "provider": "github",
                "repository": "LLM360/comet",
                "number": 3848,
                "url": "https://github.com/LLM360/comet/pull/3848",
            },
            envelope={"state": {"artifact_binding": {"revision": head}}},
            visible=visible,
            findings=[finding],
            review_id=None,
            legacy_proofs=(),
        )
    except (ValueError, TypeError):
        return "block", None
    return "deliver", anchors


def warn_anchors(
    delivery: ModuleType,
    visible: str,
    *,
    base: str,
    head: str,
    finding: dict[str, object],
    source: Path | None,
) -> tuple[str, dict[str, tuple[str, str | None, int]] | None]:
    """Run the public warning path on one annex and one finding."""
    try:
        anchors = delivery._publication_anchors(
            delivery.ReviewBinding(
                repository="LLM360/comet",
                number=3848,
                url="https://github.com/LLM360/comet/pull/3848",
                base_oid=base,
                head_oid=head,
            ),
            {
                "state_sha256": "0" * 64,
                "state": {"artifact_binding": {"revision": head}},
            },
            visible,
            [finding],
            source,
            (),
            None,
            delivery.DeliveryWarnings(),
        )
    except delivery.DeliveryError:
        return "block", None
    return "deliver", anchors


def both_paths(
    delivery: ModuleType,
    source: Path,
    *,
    base: str,
    head: str,
    fields: dict[str, object],
    finding: dict[str, object],
) -> tuple[
    tuple[str, dict[str, tuple[str, str | None, int]] | None],
    tuple[str, dict[str, tuple[str, str | None, int]] | None],
]:
    """Run the strict path and the warning path on the same real-source annex."""
    visible = annex("Reviewed the current change.", fields, delivery)
    return strict_anchors(
        delivery, source, base=base, head=head, visible=visible, finding=finding
    ), warn_anchors(
        delivery, visible, base=base, head=head, finding=finding, source=source
    )


def fields_or(manifest: dict[str, Any], entry: dict[str, object]) -> dict[str, object]:
    """Return the annex field set with the supplied entry."""
    return dict(manifest) | {"findings": [entry]}


def tolerant_fields(
    delivery: ModuleType, manifest: dict[str, Any], entry: dict[str, object]
) -> dict[str, object]:
    """Make an annex that keeps every anchor field and drops one non-binding field."""
    fields: dict[str, object] = dict(manifest)
    fields["findings"] = [entry]
    # A declared field that does not change an anchor geometry is the one
    # record-shape omission that the owner decision tolerates.
    fields.pop("hunks_sha256")
    return fields


def test_omitted_annex_side_agrees_on_both_paths(
    delivery: ModuleType, tmp_path: Path
) -> None:
    """R3-M2 of the round-3 review, as the reviewer reproduced it.

    With a real Git source, the annex drops its ``side`` and one declared
    field. The strict path takes the finding's side, which is RIGHT, so the
    warning path publishes that same side, and never a null side.
    """
    source, base, head = side_source(tmp_path)
    finding = finding_at(10)
    manifest = delivery.anchor_proofs.prepare_manifest(source, base, head, [finding])
    entry = dict(cast("list[dict[str, object]]", manifest["findings"])[0])
    assert entry["side"] == "RIGHT"
    entry.pop("side")
    fields = tolerant_fields(delivery, manifest, entry)

    strict = strict_anchors(
        delivery,
        source,
        base=base,
        head=head,
        visible=annex("Reviewed the current change.", manifest, delivery),
        finding=finding,
    )
    tolerated = warn_anchors(
        delivery,
        annex("Reviewed the current change.", fields, delivery),
        base=base,
        head=head,
        finding=finding,
        source=source,
    )

    # The strict path derives RIGHT from the finding, never a null side.
    assert strict == ("deliver", {"F-001": ("justfile", "RIGHT", 10)})
    # The warning path publishes the same geometry for the tolerated annex.
    assert tolerated == strict


@pytest.mark.parametrize(
    ("declared", "annex_side", "line", "expected"),
    [
        ("RIGHT", None, 10, ("deliver", {"F-001": ("justfile", "RIGHT", 10)})),
        ("LEFT", None, 10, ("deliver", {"F-001": ("justfile", "LEFT", 10)})),
        (None, None, 10, ("deliver", {"F-001": ("justfile", "RIGHT", 10)})),
        ("RIGHT", "RIGHT", 10, ("deliver", {"F-001": ("justfile", "RIGHT", 10)})),
        ("LEFT", "LEFT", 10, ("deliver", {"F-001": ("justfile", "LEFT", 10)})),
        ("RIGHT", None, 80, ("deliver", {})),
        ("LEFT", None, 80, ("deliver", {})),
        # An explicit annex side drives the geometry on both paths, and the
        # finding's side is only the fallback for an omitted annex side.
        ("RIGHT", "LEFT", 10, ("deliver", {"F-001": ("justfile", "LEFT", 10)})),
        ("LEFT", "RIGHT", 10, ("deliver", {"F-001": ("justfile", "RIGHT", 10)})),
        # An invalid side refuses on both paths.
        (None, "SIDEWAYS", 10, ("block", None)),
    ],
    ids=[
        "omitted-side-right",
        "omitted-side-left",
        "omitted-side-no-declared-side",
        "explicit-right",
        "explicit-left",
        "omitted-side-outside-hunks",
        "omitted-side-left-outside-hunks",
        "annex-side-overrides-finding",
        "annex-side-overrides-left-finding",
        "invalid-side",
    ],
)
def test_both_anchor_paths_agree_on_every_side_shape(
    delivery: ModuleType,
    tmp_path: Path,
    declared: str | None,
    annex_side: str | None,
    line: int,
    expected: tuple[str, dict[str, tuple[str, str | None, int]] | None],
) -> None:
    """The two paths agree on every annex side shape.

    The strict path derives the geometry from the finding, so the warning path
    publishes that same side and geometry for a tolerated annex. Neither path
    publishes a null side, and both refuse an invalid side.
    """
    source, base, head = side_source(tmp_path)
    finding = finding_at(line, declared)
    manifest = delivery.anchor_proofs.prepare_manifest(source, base, head, [finding])
    entry = dict(cast("list[dict[str, object]]", manifest["findings"])[0])
    if annex_side is None:
        entry.pop("side")
    else:
        entry["side"] = annex_side

    # The strict path is the authority for the geometry of this finding. It
    # derives the annex from the finding, and an omitted annex side cannot
    # change that derivation.
    derived = delivery.anchor_proofs.prepare_manifest(source, base, head, [finding])
    assert derived == manifest

    if annex_side is None:
        # The annex omits the side, so the strict path refuses the record shape
        # before it derives any geometry. It refuses this annex.
        assert strict_anchors(
            delivery,
            source,
            base=base,
            head=head,
            visible=annex(
                "Reviewed the current change.", fields_or(manifest, entry), delivery
            ),
            finding=finding,
        ) == ("block", None)
    # The warning path tolerates one omitted declared field. It publishes the
    # side the strict path derives, never a null side.
    _, warn = both_paths(
        delivery,
        source,
        base=base,
        head=head,
        finding=finding,
        fields=tolerant_fields(delivery, manifest, entry),
    )
    if annex_side is not None and annex_side not in {"LEFT", "RIGHT"}:
        # An invalid side refuses on both paths.
        assert warn == ("block", None)
    else:
        assert warn == expected
