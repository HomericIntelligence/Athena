#!/usr/bin/env python3
"""Deliver an exact pull-request GO decision through a bound forge adapter."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, Protocol, cast
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pr_identity import (
    pull_request_number,
    repository_from_pr_url,
    require_canonical_pull_request_url,
    require_commit_oid,
    require_github_host,
    require_github_repository,
)

_review_exchange_path = (
    Path(__file__).resolve().parents[2]
    / "review-exchange"
    / "scripts"
    / "review_exchange.py"
)
_review_exchange_spec = importlib.util.spec_from_file_location(
    "athena_pr_review_exchange", _review_exchange_path
)
if _review_exchange_spec is None or _review_exchange_spec.loader is None:
    raise RuntimeError(
        f"The review-exchange helper is unavailable: '{_review_exchange_path}'."
    )
review_exchange = importlib.util.module_from_spec(_review_exchange_spec)
sys.modules[_review_exchange_spec.name] = review_exchange
_review_exchange_spec.loader.exec_module(review_exchange)

_collect_evidence_path = Path(__file__).resolve().parent / "collect_evidence.py"
_collect_evidence_spec = importlib.util.spec_from_file_location(
    "athena_pr_collect_evidence", _collect_evidence_path
)
if _collect_evidence_spec is None or _collect_evidence_spec.loader is None:
    raise RuntimeError(
        f"The PR evidence helper is unavailable: '{_collect_evidence_path}'."
    )
collect_evidence = importlib.util.module_from_spec(_collect_evidence_spec)
sys.modules[_collect_evidence_spec.name] = collect_evidence
_collect_evidence_spec.loader.exec_module(collect_evidence)

if TYPE_CHECKING or __package__ not in {None, ""}:
    from skills._cli import argument_parser, run_command
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
    run_command = _cli.run_command

GO_LABEL = "state:implementation-go"
NO_GO_LABEL = "state:implementation-no-go"
GITHUB_HOST = "github.com"
V1_MANIFEST_SCHEMA_ID = "athena.pr-review.closure-manifest"
NO_GO_PROOF_SCHEMA_ID = "athena.pr-review.no-go-proof"
FINDING_MARKER = re.compile(
    r"<!-- HomericIntelligence:review-finding:v1 "
    r"exchange=([^\s]+) id=(F-(?:00[1-9]|0[1-9][0-9]|100)) -->"
)


class DeliveryError(RuntimeError):
    """A GO delivery precondition, write, or postcondition failed."""

    def __init__(self, message: str, report: DeliveryResult | None = None) -> None:
        super().__init__(message)
        self.report = report


@dataclass(frozen=True)
class ReviewComment:
    """One comment in one complete review-thread history."""

    id: str
    body: str
    author: str
    viewer_did_author: bool = True
    review_head_oid: str | None = None
    author_association: str = "NONE"
    review_id: str | None = None
    path: str | None = None
    side: str | None = None
    line: int | None = None
    author_permission: str | None = None
    original_line: int | None = None
    published_at: str | None = None
    last_edited_at: str | None = None


@dataclass(frozen=True)
class ReviewThread:
    """One review thread and its complete comment history."""

    id: str
    is_resolved: bool
    comments: tuple[ReviewComment, ...]
    viewer_can_reply: bool = True
    viewer_can_resolve: bool = True


@dataclass(frozen=True)
class ReviewRecord:
    """One pull-request review used as terminal delivery evidence."""

    id: str
    body: str
    head_oid: str
    author: str
    viewer_did_author: bool
    includes_created_edit: bool
    state: str
    author_association: str = "NONE"
    author_permission: str | None = None
    submitted_at: str | None = None
    last_edited_at: str | None = None


@dataclass(frozen=True)
class PullRequestSnapshot:
    """The forge state required to bind one delivery operation."""

    repository: str
    number: int
    url: str
    state: str
    is_draft: bool
    base_oid: str
    head_oid: str
    labels: frozenset[str]
    threads: tuple[ReviewThread, ...]
    reviews: tuple[ReviewRecord, ...] = ()


@dataclass(frozen=True)
class ReviewBinding:
    """The immutable pull-request identity retained by the review."""

    repository: str
    number: int
    url: str
    base_oid: str
    head_oid: str


@dataclass(frozen=True)
class ThreadResponse:
    """One precomputed response bound to one thread conversation digest."""

    thread_id: str
    conversation_sha256: str
    body: str


@dataclass(frozen=True)
class ThreadClosure:
    """One v1 thread closure bound to author and reviewer evidence."""

    thread_id: str
    finding_id: str
    finding_exchange_id: str
    finding_state_sha256: str
    superseding_state_sha256: str | None
    origin_comment_id: str
    origin_review_head_oid: str
    conversation_sha256: str
    finding_disposition: str
    author_answer: str | None
    author_artifact_revision: str | None
    reviewer_disposition: str
    closure_evidence: tuple[str, ...]
    authority_receipt: dict[str, str] | None
    author_event_review_id: str | None = None


@dataclass(frozen=True)
class TerminalInlineComment:
    """One inline finding in the atomic terminal COMMENT review."""

    path: str
    side: str
    line: int
    body: str


@dataclass(frozen=True)
class RequirementsBinding:
    """One retained live PR scope and linked-requirements binding."""

    reviewed_scope_sha256: str
    requirements_sha256: str
    requirement_issue_urls: tuple[str, ...]


@dataclass(frozen=True)
class ClosureManifest:
    """One terminal v1 state and its exact review-thread closure ledger."""

    state_envelope: dict[str, Any]
    terminal_visible_content: str
    entries: tuple[ThreadClosure, ...]
    requirements_binding: RequirementsBinding
    comments: tuple[TerminalInlineComment, ...] = ()
    summary_finding_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifiedStateChain:
    """The exact terminal ancestry and its verified finding bindings."""

    envelopes: Mapping[str, dict[str, Any]]
    selected_state_sha256s: frozenset[str]
    verified_state_sha256s: frozenset[str]
    superseding_state_sha256s: Mapping[str, str]
    finding_origin_review_ids: Mapping[tuple[str, str], str]
    author_event_review_ids: Mapping[tuple[str, str], str]
    terminal_new_finding_ids: frozenset[str]


@dataclass(frozen=True)
class VerifiedAuthorTransition:
    """One immutable author carrier and its reducer-derived logical state."""

    record: ReviewRecord
    event_envelope: dict[str, Any]
    previous_envelope: dict[str, Any]
    result_envelope: dict[str, Any]


@dataclass(frozen=True)
class NoGoProof:
    """One published current-head non-GO state carrier."""

    state_envelope: dict[str, Any]
    visible_content: str
    review_id: str
    requirements_binding: RequirementsBinding


@dataclass(frozen=True)
class DeliveryResult:
    """The verified result of a GO delivery."""

    status: str
    resolved_thread_ids: tuple[str, ...]
    label: str = GO_LABEL
    terminal_review_id: str | None = None
    responded_thread_ids: tuple[str, ...] = ()
    pending_thread_ids: tuple[str, ...] = ()
    observed_head_oid: str | None = None
    observed_labels: tuple[str, ...] = ()
    uncertain_operation: str | None = None
    recovery_read_required: bool = False
    reason: str | None = None


class Forge(Protocol):
    """The minimum bound forge capability used by the delivery state machine."""

    def snapshot(self) -> PullRequestSnapshot:
        """Read one complete pull-request snapshot."""

    def collect_requirements_binding(
        self, requirement_issue_urls: tuple[str, ...]
    ) -> RequirementsBinding:
        """Read one stable live requirements binding."""

    def verify_requirements_binding(self, expected: RequirementsBinding) -> None:
        """Fail unless the live requirements binding equals the retained binding."""

    def reply(self, thread_id: str, body: str) -> None:
        """Post one deterministic reply to one retained review thread."""

    def resolve(self, thread_id: str) -> None:
        """Resolve one retained review thread."""

    def set_implementation_go(self) -> None:
        """Apply the exclusive implementation GO state label."""

    def set_implementation_no_go(self) -> None:
        """Apply the exclusive implementation NO-GO state label."""

    def publish_terminal(
        self,
        body: str,
        head_oid: str,
        comments: tuple[TerminalInlineComment, ...],
    ) -> None:
        """Publish one exact-head terminal COMMENT review."""


def conversation_sha256(thread: ReviewThread) -> str:
    """Hash a complete conversation with a stable, length-delimited encoding."""
    payload = {
        "comments": [
            {
                "author": comment.author,
                "author_association": comment.author_association,
                "body": comment.body,
                "id": comment.id,
                "review_head_oid": comment.review_head_oid,
                "review_id": comment.review_id,
                "path": comment.path,
                "side": comment.side,
                "line": comment.line,
                "original_line": comment.original_line,
                "viewer_did_author": comment.viewer_did_author,
            }
            for comment in thread.comments
        ],
        "id": thread.id,
        "is_resolved": thread.is_resolved,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


def _legacy_conversation_sha256(thread: ReviewThread) -> str:
    payload = {
        "comments": [
            {"author": comment.author, "body": comment.body, "id": comment.id}
            for comment in thread.comments
        ],
        "id": thread.id,
        "is_resolved": thread.is_resolved,
    }
    return sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _same_binding(snapshot: PullRequestSnapshot, binding: ReviewBinding) -> bool:
    return (
        snapshot.repository.casefold() == binding.repository.casefold()
        and snapshot.number == binding.number
        and snapshot.url == binding.url
        and snapshot.state == "OPEN"
        and not snapshot.is_draft
        and snapshot.base_oid == binding.base_oid
        and snapshot.head_oid == binding.head_oid
    )


def _require_binding(snapshot: PullRequestSnapshot, binding: ReviewBinding) -> None:
    if not _same_binding(snapshot, binding):
        raise DeliveryError(
            "The pull-request identity changed or is not open; withhold GO delivery."
        )


def _snapshot(forge: Forge, binding: ReviewBinding) -> PullRequestSnapshot:
    try:
        snapshot = forge.snapshot()
    except Exception as error:
        raise DeliveryError(f"The forge snapshot failed: {error}") from error
    _require_binding(snapshot, binding)
    return snapshot


def _collect_live_requirements(
    forge: Forge, requirement_issue_urls: tuple[str, ...]
) -> RequirementsBinding:
    try:
        observed = forge.collect_requirements_binding(requirement_issue_urls)
    except DeliveryError:
        raise
    except Exception as error:
        raise DeliveryError(
            f"The live requirements binding cannot be collected: {error}"
        ) from error
    if not isinstance(observed, RequirementsBinding):
        raise DeliveryError("The forge returned an invalid live requirements binding.")
    return _requirements_binding(_requirements_binding_dict(observed))


def _verify_live_requirements(forge: Forge, expected: RequirementsBinding) -> None:
    try:
        forge.verify_requirements_binding(expected)
    except DeliveryError:
        raise
    except Exception as error:
        raise DeliveryError(
            f"The live requirements binding cannot be verified: {error}"
        ) from error


def _delivery_body(binding: ReviewBinding, response: ThreadResponse) -> str:
    """Add an exact-target marker to one reviewer response."""
    seed = json.dumps(
        {
            "body": response.body,
            "conversation_sha256": response.conversation_sha256,
            "head_oid": binding.head_oid,
            "number": binding.number,
            "repository": binding.repository,
            "thread_id": response.thread_id,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    marker = sha256(seed.encode("utf-8")).hexdigest()
    return f"{response.body.rstrip()}\n\n<!-- athena-pr-review-go-response:{marker} -->"


def _legacy_delivery_body(binding: ReviewBinding, response: ThreadResponse) -> str:
    return _delivery_body(binding, response)


def _response_is_only_conversation_change(
    before: ReviewThread, after: ReviewThread, body: str
) -> bool:
    """Return whether one exact response is the only new comment."""
    return (
        not after.is_resolved
        and after.comments[:-1] == before.comments
        and len(after.comments) == len(before.comments) + 1
        and after.comments[-1].body == body
        and after.comments[-1].viewer_did_author
    )


def _thread(snapshot: PullRequestSnapshot, thread_id: str) -> ReviewThread:
    matches = [thread for thread in snapshot.threads if thread.id == thread_id]
    if len(matches) != 1:
        raise DeliveryError("The review thread set changed during GO delivery.")
    return matches[0]


def _call_write(action: str, callback: Any, *arguments: Any) -> None:
    try:
        callback(*arguments)
    except Exception as error:
        raise DeliveryError(
            f"The forge {action} failed. The result is not retried or compensated: {error}"
        ) from error


def deliver_go(
    forge: Forge, binding: ReviewBinding, responses: Sequence[ThreadResponse]
) -> DeliveryResult:
    """Reject active legacy delivery; version 1 owns every new mutation."""
    del forge, binding, responses
    raise DeliveryError(
        "Active legacy GO delivery is not valid. Adopt open findings into version 1."
    )


def verify_legacy_go(
    forge: Forge, binding: ReviewBinding, responses: Sequence[ThreadResponse]
) -> DeliveryResult:
    """Prove one unchanged completed legacy GO without a forge mutation."""
    snapshot = _snapshot(forge, binding)
    states, author_records = _review_carriers(snapshot, binding)
    if states or author_records:
        raise DeliveryError(
            "A version-1 carrier exists; legacy proof is not an available fallback."
        )
    if GO_LABEL not in snapshot.labels or NO_GO_LABEL in snapshot.labels:
        raise DeliveryError("The legacy GO label is absent or not exclusive.")
    if any(not thread.is_resolved for thread in snapshot.threads):
        raise DeliveryError("An active legacy thread must be adopted into version 1.")
    by_id = {response.thread_id: response for response in responses}
    thread_ids = {thread.id for thread in snapshot.threads}
    if (
        len(thread_ids) != len(snapshot.threads)
        or len(by_id) != len(responses)
        or not set(by_id).issubset(thread_ids)
    ):
        raise DeliveryError("The legacy proof contains an invalid thread identity.")
    for thread in snapshot.threads:
        if not thread.comments:
            raise DeliveryError("A legacy thread has no durable history.")
        response = by_id.get(thread.id)
        if response is None:
            if any(
                "<!-- athena-pr-review-go-response:" in comment.body
                for comment in thread.comments
            ):
                raise DeliveryError(
                    "The legacy proof omits a thread with a delivery marker."
                )
            continue
        prior = ReviewThread(
            id=thread.id,
            is_resolved=False,
            comments=thread.comments[:-1],
            viewer_can_reply=thread.viewer_can_reply,
            viewer_can_resolve=thread.viewer_can_resolve,
        )
        if response.conversation_sha256 != _legacy_conversation_sha256(prior):
            raise DeliveryError("The legacy proof has a stale conversation digest.")
        historical = ThreadResponse(
            response.thread_id, response.conversation_sha256, response.body
        )
        if not thread.comments[-1].viewer_did_author or thread.comments[
            -1
        ].body != _legacy_delivery_body(binding, historical):
            raise DeliveryError(
                "The legacy thread has no exact delivered response marker."
            )
    return DeliveryResult(
        "already_delivered",
        (),
        observed_head_oid=snapshot.head_oid,
        observed_labels=tuple(sorted(snapshot.labels)),
    )


def _closure_dict(entry: ThreadClosure) -> dict[str, Any]:
    return {
        "thread_id": entry.thread_id,
        "finding_id": entry.finding_id,
        "finding_exchange_id": entry.finding_exchange_id,
        "finding_state_sha256": entry.finding_state_sha256,
        "superseding_state_sha256": entry.superseding_state_sha256,
        "origin_comment_id": entry.origin_comment_id,
        "origin_review_head_oid": entry.origin_review_head_oid,
        "conversation_sha256": entry.conversation_sha256,
        "finding_disposition": entry.finding_disposition,
        "author_answer": entry.author_answer,
        "author_artifact_revision": entry.author_artifact_revision,
        "reviewer_disposition": entry.reviewer_disposition,
        "closure_evidence": list(entry.closure_evidence),
        "authority_receipt": entry.authority_receipt,
        "author_event_review_id": entry.author_event_review_id,
    }


def _binding_dict(binding: ReviewBinding) -> dict[str, Any]:
    return {
        "repository": binding.repository,
        "number": binding.number,
        "url": binding.url,
        "base_oid": binding.base_oid,
        "head_oid": binding.head_oid,
    }


def _terminal_comment_dict(comment: TerminalInlineComment) -> dict[str, Any]:
    return {
        "path": comment.path,
        "side": comment.side,
        "line": comment.line,
        "body": comment.body,
    }


def _requirements_binding_dict(binding: RequirementsBinding) -> dict[str, Any]:
    return {
        "reviewed_scope_sha256": binding.reviewed_scope_sha256,
        "requirements_sha256": binding.requirements_sha256,
        "requirement_issue_urls": list(binding.requirement_issue_urls),
    }


def terminal_visible_content(
    binding: ReviewBinding, entries: Sequence[ThreadClosure]
) -> str:
    """Render the deterministic visible terminal ledger."""
    ordered = sorted(
        entries,
        key=lambda entry: (
            entry.finding_exchange_id,
            entry.finding_id,
            entry.thread_id,
        ),
    )
    visible_entries = []
    for entry in ordered:
        item = _closure_dict(entry)
        # The current state and a direct reframe successor can be the terminal
        # state. That state cannot contain its own digest in the text that it hashes.
        if entry.superseding_state_sha256 is None:
            del item["finding_state_sha256"]
        del item["superseding_state_sha256"]
        visible_entries.append(item)
    closure_sha256 = review_exchange.sha256_json(
        {
            "binding": _binding_dict(binding),
            "entries": visible_entries,
        }
    )
    lines = [
        "## Terminal review exchange",
        "",
        "Verdict: GO",
        f"Reviewed head: `{binding.head_oid}`",
        f"Closure ledger: `{closure_sha256}`",
    ]
    if ordered:
        lines.extend(("", "Closed findings:"))
        lines.extend(
            f"- `{entry.finding_exchange_id}/{entry.finding_id}`: "
            f"`{entry.reviewer_disposition}`"
            for entry in ordered
        )
    return "\n".join(lines)


def terminal_review_body(manifest: ClosureManifest) -> str:
    """Render and verify the terminal state carrier for one COMMENT review."""
    try:
        return cast(
            str,
            review_exchange.render_carrier(
                manifest.terminal_visible_content,
                manifest.state_envelope,
                "state",
            ),
        )
    except review_exchange.ProtocolError as error:
        raise DeliveryError(f"The terminal review state is invalid: {error}") from error


def closure_manifest_document(
    binding: ReviewBinding, manifest: ClosureManifest
) -> dict[str, Any]:
    """Return one canonical serializable v1 closure manifest."""
    return {
        "schema_id": V1_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "binding": _binding_dict(binding),
        "state": manifest.state_envelope,
        "terminal_visible_content": manifest.terminal_visible_content,
        "entries": [_closure_dict(entry) for entry in manifest.entries],
        "requirements_binding": _requirements_binding_dict(
            manifest.requirements_binding
        ),
        "comments": [_terminal_comment_dict(comment) for comment in manifest.comments],
        "summary_finding_ids": list(manifest.summary_finding_ids),
    }


def _require_manifest_string(value: object, description: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeliveryError(
            f"The v1 closure manifest contains an invalid {description}."
        )
    return value


def _require_optional_manifest_string(value: object, description: str) -> str | None:
    if value is None:
        return None
    return _require_manifest_string(value, description)


def _require_manifest_fields(
    value: object, fields: frozenset[str], description: str
) -> dict[str, Any]:
    if not isinstance(value, dict) or frozenset(value) != fields:
        raise DeliveryError(
            f"The v1 closure manifest contains invalid {description} fields."
        )
    return cast(dict[str, Any], value)


def _requirements_binding(value: object) -> RequirementsBinding:
    raw = _require_manifest_fields(
        value,
        frozenset(
            {
                "reviewed_scope_sha256",
                "requirements_sha256",
                "requirement_issue_urls",
            }
        ),
        "requirements binding",
    )
    reviewed_scope_sha256 = _require_manifest_string(
        raw["reviewed_scope_sha256"], "reviewed scope digest"
    )
    requirements_sha256 = _require_manifest_string(
        raw["requirements_sha256"], "requirements digest"
    )
    if (
        re.fullmatch(r"[0-9a-f]{64}", reviewed_scope_sha256) is None
        or re.fullmatch(r"[0-9a-f]{64}", requirements_sha256) is None
    ):
        raise DeliveryError("The v1 requirements binding has an invalid digest.")
    urls_value = raw["requirement_issue_urls"]
    if not isinstance(urls_value, list):
        raise DeliveryError(
            "The v1 requirements binding must contain an issue URL list."
        )
    urls = tuple(
        _require_manifest_string(item, "requirement issue URL") for item in urls_value
    )
    try:
        canonical_urls = collect_evidence.canonical_requirement_issue_urls(urls)
    except RuntimeError as error:
        raise DeliveryError(
            "The v1 requirements binding has an invalid issue URL."
        ) from error
    if urls != canonical_urls:
        raise DeliveryError(
            "The v1 requirement issue URLs must be one canonical sorted set."
        )
    return RequirementsBinding(
        reviewed_scope_sha256=reviewed_scope_sha256,
        requirements_sha256=requirements_sha256,
        requirement_issue_urls=urls,
    )


def _thread_closure(value: object) -> ThreadClosure:
    raw = _require_manifest_fields(
        value,
        frozenset(
            {
                "thread_id",
                "finding_id",
                "finding_exchange_id",
                "finding_state_sha256",
                "superseding_state_sha256",
                "origin_comment_id",
                "origin_review_head_oid",
                "conversation_sha256",
                "finding_disposition",
                "author_answer",
                "author_artifact_revision",
                "reviewer_disposition",
                "closure_evidence",
                "authority_receipt",
                "author_event_review_id",
            }
        ),
        "closure entry",
    )
    evidence = raw["closure_evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise DeliveryError("A v1 closure entry must contain closure evidence.")
    evidence_values = tuple(
        _require_manifest_string(item, "closure evidence") for item in evidence
    )
    authority_value = raw["authority_receipt"]
    authority: dict[str, str] | None = None
    if authority_value is not None:
        authority_raw = _require_manifest_fields(
            authority_value,
            frozenset({"reference", "sha256"}),
            "authority receipt",
        )
        reference = _require_manifest_string(
            authority_raw["reference"], "authority reference"
        )
        digest = _require_manifest_string(authority_raw["sha256"], "authority digest")
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise DeliveryError("The v1 authority receipt digest is invalid.")
        authority = {"reference": reference, "sha256": digest}
    finding_state_sha256 = _require_manifest_string(
        raw["finding_state_sha256"], "finding state digest"
    )
    superseding_state_sha256 = _require_optional_manifest_string(
        raw["superseding_state_sha256"], "superseding state digest"
    )
    if re.fullmatch(r"[0-9a-f]{64}", finding_state_sha256) is None or (
        superseding_state_sha256 is not None
        and re.fullmatch(r"[0-9a-f]{64}", superseding_state_sha256) is None
    ):
        raise DeliveryError("The v1 closure entry has an invalid state digest.")
    finding_exchange_id = _require_manifest_string(
        raw["finding_exchange_id"], "finding exchange identifier"
    )
    if re.fullmatch(r"[^\s]+", finding_exchange_id) is None:
        raise DeliveryError(
            "The v1 closure entry has an invalid finding exchange identifier."
        )
    return ThreadClosure(
        thread_id=_require_manifest_string(raw["thread_id"], "thread identifier"),
        finding_id=_require_manifest_string(raw["finding_id"], "finding identifier"),
        finding_exchange_id=finding_exchange_id,
        finding_state_sha256=finding_state_sha256,
        superseding_state_sha256=superseding_state_sha256,
        origin_comment_id=_require_manifest_string(
            raw["origin_comment_id"], "origin comment identifier"
        ),
        origin_review_head_oid=require_commit_oid(
            raw["origin_review_head_oid"], "origin review head"
        ),
        conversation_sha256=_require_manifest_string(
            raw["conversation_sha256"], "conversation digest"
        ),
        finding_disposition=_require_manifest_string(
            raw["finding_disposition"], "finding disposition"
        ),
        author_answer=_require_optional_manifest_string(
            raw["author_answer"], "author answer"
        ),
        author_artifact_revision=_require_optional_manifest_string(
            raw["author_artifact_revision"], "author artifact revision"
        ),
        reviewer_disposition=_require_manifest_string(
            raw["reviewer_disposition"], "reviewer disposition"
        ),
        closure_evidence=evidence_values,
        authority_receipt=authority,
        author_event_review_id=_require_optional_manifest_string(
            raw["author_event_review_id"], "author-event review identifier"
        ),
    )


def _terminal_inline_comment(value: object) -> TerminalInlineComment:
    raw = _require_manifest_fields(
        value,
        frozenset({"path", "side", "line", "body"}),
        "terminal inline comment",
    )
    path = _require_manifest_string(raw["path"], "terminal comment path")
    if path.startswith("/") or ".." in Path(path).parts:
        raise DeliveryError("A terminal comment path is not repository-relative.")
    side = _require_manifest_string(raw["side"], "terminal comment side")
    if side not in {"LEFT", "RIGHT"}:
        raise DeliveryError("A terminal comment side must be LEFT or RIGHT.")
    line = raw["line"]
    if type(line) is not int or line < 1:
        raise DeliveryError("A terminal comment line must be a positive integer.")
    body = _require_manifest_string(raw["body"], "terminal comment body")
    if len(body.encode("utf-8")) > review_exchange.PROVIDER_BODY_LIMITS["github"]:
        raise DeliveryError("A terminal inline comment exceeds the GitHub body limit.")
    return TerminalInlineComment(path=path, side=side, line=line, body=body)


def _finding_marker(comment: ReviewComment) -> tuple[str, str] | None:
    prefix = "<!-- HomericIntelligence:review-finding:"
    marker_lines = [
        (index, line, FINDING_MARKER.fullmatch(line))
        for index, line in enumerate(comment.body.splitlines())
        if prefix in line
    ]
    if not marker_lines:
        return None
    if len(marker_lines) != 1 or marker_lines[0][2] is None:
        raise DeliveryError(
            "The Athena review-finding marker is malformed or repeated."
        )
    index, _, match = marker_lines[0]
    lines = comment.body.splitlines()
    if index != len(lines) - 1:
        raise DeliveryError("The Athena review-finding marker is not final.")
    try:
        top_level_lines = review_exchange.top_level_markdown_lines(
            comment.body, require_closed=True
        )
    except review_exchange.ProtocolError as error:
        raise DeliveryError(
            "The Athena review-finding marker is inside an open Markdown block."
        ) from error
    if not any(line == marker_lines[0][1] for _, _, line in top_level_lines):
        raise DeliveryError("The Athena review-finding marker is not a top-level line.")
    assert match is not None
    return cast(tuple[str, str], match.groups())


def _finding_anchor(location: str) -> tuple[str, int] | None:
    path, separator, line_text = location.rpartition(":")
    if (
        not separator
        or not line_text.isascii()
        or not line_text.isdigit()
        or int(line_text) < 1
        or not path
        or path.startswith("/")
        or ".." in Path(path).parts
        or "\n" in path
        or "\r" in path
    ):
        return None
    return path, int(line_text)


def _expected_target(binding: ReviewBinding) -> dict[str, object]:
    return {
        "provider": "github",
        "repository": binding.repository,
        "number": binding.number,
        "url": binding.url,
    }


def _require_pr_envelope(
    envelope: object, binding: ReviewBinding, *, schema_id: str
) -> dict[str, Any]:
    try:
        verified = review_exchange.verify_envelope(envelope)
    except review_exchange.ProtocolError as error:
        raise DeliveryError(
            f"The review-exchange carrier is invalid: {error}"
        ) from error
    state = verified["state"]
    if verified["schema_id"] != schema_id:
        raise DeliveryError("The review-exchange carrier has the wrong record kind.")
    if state["target"] != _expected_target(binding):
        raise DeliveryError(
            "The review-exchange carrier names a different pull request."
        )
    if (
        schema_id == review_exchange.STATE_SCHEMA_ID
        and state["surface"] != "pull_request"
    ):
        raise DeliveryError("The review-exchange state is not for a pull request.")
    return cast(dict[str, Any], verified)


def _review_carriers(
    snapshot: PullRequestSnapshot, binding: ReviewBinding
) -> tuple[
    dict[str, tuple[ReviewRecord, dict[str, Any]]],
    tuple[tuple[ReviewRecord, dict[str, Any]], ...],
]:
    states: dict[str, tuple[ReviewRecord, dict[str, Any]]] = {}
    authors: list[tuple[ReviewRecord, dict[str, Any]]] = []
    carrier_ids: set[str] = set()
    for review in snapshot.reviews:
        if review_exchange.CARRIER_PREFIX not in review.body:
            continue
        if (
            review.state not in {"COMMENT", "COMMENTED"}
            or review.includes_created_edit
            or review.last_edited_at is not None
        ):
            raise DeliveryError(
                "A review-exchange carrier is not an immutable atomic COMMENT review."
            )
        if review.id in carrier_ids:
            raise DeliveryError("A review-exchange carrier identifier is duplicated.")
        carrier_ids.add(review.id)
        try:
            envelope = review_exchange.extract_carrier(review.body)
        except review_exchange.ProtocolError as error:
            raise DeliveryError(
                f"A pull-request carrier is invalid: {error}"
            ) from error
        envelope = _require_pr_envelope(
            envelope, binding, schema_id=cast(str, envelope["schema_id"])
        )
        if review.head_oid != envelope["state"]["artifact_binding"]["revision"]:
            raise DeliveryError("A pull-request carrier does not bind its review head.")
        if not review.viewer_did_author:
            raise DeliveryError(
                "A pull-request review-exchange carrier is not Athena-owned."
            )
        if envelope["schema_id"] == review_exchange.STATE_SCHEMA_ID:
            digest = cast(str, envelope["state_sha256"])
            if digest in states:
                raise DeliveryError("A reviewer round has duplicate state carriers.")
            states[digest] = (review, envelope)
        else:
            authors.append((review, envelope))
    return states, tuple(authors)


def _finding_event_fields(finding: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: finding[key]
        for key in (
            "id",
            "category",
            "severity",
            "disposition",
            "material_architecture",
            "location",
            "impact",
            "evidence",
            "closure_condition",
            "introduction",
        )
    }


def _same_envelope(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_json = cast(str, review_exchange.canonical_json(left))
    right_json = cast(str, review_exchange.canonical_json(right))
    return left_json == right_json


def _verify_carrier_review_roots(
    snapshot: PullRequestSnapshot,
    states: Mapping[str, tuple[ReviewRecord, dict[str, Any]]],
    verified_envelopes: Mapping[str, dict[str, Any]],
    verified_state_sha256s: set[str],
    selected_author_ids: set[str],
    new_finding_ids_by_state: Mapping[str, frozenset[str]],
) -> None:
    """Bind each selected carrier review to its complete atomic inline batch."""
    roots_by_review: dict[str, list[ReviewComment]] = {}
    native_roots: dict[str, list[ReviewComment]] = {}
    for thread in snapshot.threads:
        if not thread.comments:
            continue
        root = thread.comments[0]
        if _finding_marker(root) is None:
            native_roots.setdefault(root.id, []).append(root)
        if root.review_id is not None:
            roots_by_review.setdefault(root.review_id, []).append(root)
    if any(roots_by_review.get(review_id) for review_id in selected_author_ids):
        raise DeliveryError("An author-event carrier review owns an inline finding.")
    for digest in verified_state_sha256s:
        verified_envelope = verified_envelopes.get(digest)
        if verified_envelope is None:
            continue
        verified_state = verified_envelope["state"]
        for finding in verified_state["findings"]:
            finding_id = finding["id"]
            if finding_id not in new_finding_ids_by_state[
                digest
            ] or not finding_id.startswith("native:"):
                continue
            roots = native_roots.get(finding_id.removeprefix("native:"), [])
            anchor = _finding_anchor(finding["location"])
            if (
                len(roots) != 1
                or anchor is None
                or not roots[0].viewer_did_author
                or roots[0].review_head_oid is None
                or roots[0].path != anchor[0]
                or roots[0].original_line != anchor[1]
                or roots[0].side not in {"LEFT", "RIGHT"}
            ):
                raise DeliveryError(
                    "An adopted native finding has no unique matching review root."
                )
        state_record = states.get(digest)
        if state_record is None:
            continue
        review, envelope = state_record
        state = envelope["state"]
        expected: dict[str, tuple[str, int]] = {}
        for finding in state["findings"]:
            finding_id = finding["id"]
            if finding_id not in new_finding_ids_by_state[
                digest
            ] or finding_id.startswith("native:"):
                continue
            anchor = _finding_anchor(finding["location"])
            if anchor is not None:
                expected[finding_id] = anchor
        actual: set[str] = set()
        for root in roots_by_review.get(review.id, []):
            marker = _finding_marker(root)
            if marker is None:
                raise DeliveryError(
                    "A reviewer-state carrier owns an unmarked inline root."
                )
            exchange_id, finding_id = marker
            anchor = expected.get(finding_id)
            if (
                exchange_id != state["exchange_id"]
                or anchor is None
                or finding_id in actual
                or not root.viewer_did_author
                or root.review_head_oid != review.head_oid
                or root.last_edited_at is not None
                or root.path != anchor[0]
                or root.original_line != anchor[1]
                or root.side not in {"LEFT", "RIGHT"}
            ):
                raise DeliveryError(
                    "A reviewer-state carrier has an invalid inline finding batch."
                )
            actual.add(finding_id)
        if actual != set(expected):
            raise DeliveryError(
                "A reviewer-state carrier does not own its exact inline finding batch."
            )


def _try_reduce(
    previous: Mapping[str, Any] | None,
    event: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any] | None:
    try:
        result = review_exchange.reduce_request({"previous": previous, "event": event})
    except review_exchange.ProtocolError:
        return None
    envelope = cast(dict[str, Any], result["envelope"])
    return result if _same_envelope(envelope, expected) else None


def _review_stop_reasons() -> tuple[str | None, ...]:
    return (None, *sorted(review_exchange.STOP_REASONS))


def _verify_initial_state(envelope: Mapping[str, Any]) -> bool:
    state = cast(Mapping[str, Any], envelope["state"])
    for stop_reason in _review_stop_reasons():
        event = {
            "event_type": "reviewer_assessment",
            "exchange_id": state["exchange_id"],
            "prior_state_sha256": None,
            "round": 1,
            "surface": state["surface"],
            "target": state["target"],
            "requirements_sha256": state["requirements_sha256"],
            "supersedes_state_sha256": state["supersedes_state_sha256"],
            "artifact_binding": state["artifact_binding"],
            "scope": state["scope"],
            "coverage_complete": state["coverage_complete"],
            "go_eligible": state["go_eligible"],
            "responses": [],
            "new_findings": [
                _finding_event_fields(finding) for finding in state["findings"]
            ],
            "stop_reason": stop_reason,
        }
        if _try_reduce(None, event, envelope) is not None:
            return True
    return False


def _author_event_input(envelope: Mapping[str, Any]) -> dict[str, Any]:
    state = cast(Mapping[str, Any], envelope["state"])
    return {
        key: state[key]
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


def _infer_reviewer_event(
    previous: Mapping[str, Any], current: Mapping[str, Any], stop_reason: str | None
) -> dict[str, Any]:
    previous_state = cast(Mapping[str, Any], previous["state"])
    current_state = cast(Mapping[str, Any], current["state"])
    previous_ids = {finding["id"] for finding in previous_state["findings"]}
    responses = []
    for finding in current_state["findings"]:
        reviewer = finding["reviewer_response"]
        if reviewer is None or reviewer["round"] != current_state["round"]:
            continue
        responses.append(
            {
                "finding_id": finding["id"],
                "kind": reviewer["kind"],
                "evidence": reviewer["evidence"],
                "closure_condition": reviewer["closure_condition"],
            }
        )
    new_findings = [
        _finding_event_fields(finding)
        for finding in current_state["findings"]
        if finding["id"] not in previous_ids
    ]
    return {
        "event_type": "reviewer_assessment",
        "exchange_id": current_state["exchange_id"],
        "prior_state_sha256": previous["state_sha256"],
        "round": current_state["round"],
        "artifact_binding": current_state["artifact_binding"],
        "scope": current_state["scope"],
        "coverage_complete": current_state["coverage_complete"],
        "go_eligible": current_state["go_eligible"],
        "responses": responses,
        "new_findings": new_findings,
        "stop_reason": stop_reason,
    }


def _infer_reframe_event(
    previous: Mapping[str, Any], current: Mapping[str, Any], stop_reason: str | None
) -> dict[str, Any]:
    state = cast(Mapping[str, Any], current["state"])
    genesis = cast(Mapping[str, Any], state["accepted_events"][0])
    return {
        "event_type": "reframe",
        "exchange_id": state["exchange_id"],
        "prior_state_sha256": previous["state_sha256"],
        "round": 1,
        "surface": state["surface"],
        "target": state["target"],
        "requirements_sha256": state["requirements_sha256"],
        "supersedes_state_sha256": previous["state_sha256"],
        "superseded_exchange_ids": genesis["superseded_exchange_ids"],
        "authority_receipt": state["supersession_authority_receipt"],
        "artifact_binding": state["artifact_binding"],
        "scope": state["scope"],
        "coverage_complete": state["coverage_complete"],
        "go_eligible": state["go_eligible"],
        "responses": [],
        "new_findings": [
            _finding_event_fields(finding) for finding in state["findings"]
        ],
        "stop_reason": stop_reason,
    }


def _infer_human_event(
    previous: Mapping[str, Any], current: Mapping[str, Any]
) -> dict[str, Any] | None:
    previous_findings = {
        finding["id"]: finding for finding in previous["state"]["findings"]
    }
    decisions: list[dict[str, Any]] = []
    receipts: list[dict[str, str]] = []
    for finding in current["state"]["findings"]:
        before = previous_findings.get(finding["id"])
        if before is None or before == finding:
            continue
        receipt = finding["authority_receipt"]
        if receipt is None:
            return None
        receipts.append(receipt)
        if finding["state"] == "accepted_risk":
            decisions.append(
                {
                    "finding_id": finding["id"],
                    "kind": "accept_risk",
                    "closure_condition": None,
                }
            )
        elif (
            finding["state"] == "still_present"
            and finding["closure_revision"] == before["closure_revision"] + 1
            and finding["closure_condition"] != before["closure_condition"]
        ):
            decisions.append(
                {
                    "finding_id": finding["id"],
                    "kind": "select_closure",
                    "closure_condition": finding["closure_condition"],
                }
            )
        else:
            return None
    if not decisions or any(receipt != receipts[0] for receipt in receipts[1:]):
        return None
    return {
        "event_type": "human_decision",
        "exchange_id": current["state"]["exchange_id"],
        "prior_state_sha256": previous["state_sha256"],
        "artifact_binding": current["state"]["artifact_binding"],
        "authority_receipt": receipts[0],
        "decisions": decisions,
    }


def _forge_publication_time(value: str | None, subject: str) -> datetime:
    """Parse one immutable forge publication time."""
    if value is None or value != value.strip():
        raise DeliveryError(f"{subject} has no publication time.")
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        result = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise DeliveryError(f"{subject} has an invalid publication time.") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise DeliveryError(f"{subject} has an ambiguous publication time.")
    return result


def _review_submission_time(review: ReviewRecord) -> datetime:
    return _forge_publication_time(
        review.submitted_at, "A selected review-exchange carrier"
    )


def _authority_publication_time(record: ReviewComment | ReviewRecord) -> datetime:
    if isinstance(record, ReviewRecord):
        base = _forge_publication_time(
            record.submitted_at, "A selected authority review"
        )
    else:
        base = _forge_publication_time(
            record.published_at, "A selected authority comment"
        )
    publication_times = [base]
    if record.last_edited_at is not None:
        publication_times.append(
            _forge_publication_time(
                record.last_edited_at, "A selected authority record edit"
            )
        )
    return max(publication_times)


def _derive_author_transitions(
    states: Mapping[str, tuple[ReviewRecord, dict[str, Any]]],
    author_records: Sequence[tuple[ReviewRecord, dict[str, Any]]],
) -> tuple[
    dict[str, VerifiedAuthorTransition],
    dict[str, dict[str, Any]],
]:
    """Replay author carriers, including a chain of artifact refreshes."""
    logical_envelopes = {digest: envelope for digest, (_, envelope) in states.items()}
    transitions: dict[str, VerifiedAuthorTransition] = {}
    pending = list(author_records)
    while pending:
        deferred: list[tuple[ReviewRecord, dict[str, Any]]] = []
        progressed = False
        for record, event_envelope in pending:
            prior_digest = cast(str, event_envelope["state"]["prior_state_sha256"])
            previous = logical_envelopes.get(prior_digest)
            if previous is None:
                deferred.append((record, event_envelope))
                continue
            try:
                result = review_exchange.reduce_request(
                    {
                        "previous": previous,
                        "event": _author_event_input(event_envelope),
                    }
                )
            except review_exchange.ProtocolError as error:
                raise DeliveryError(
                    "A persisted author-event carrier is not reducer-derived."
                ) from error
            if not _same_envelope(
                cast(Mapping[str, Any], result["author_event"]), event_envelope
            ):
                raise DeliveryError(
                    "A persisted author-event carrier does not match its reducer event."
                )
            result_envelope = cast(dict[str, Any], result["envelope"])
            result_digest = cast(str, result_envelope["state_sha256"])
            if result_digest in logical_envelopes or result_digest in transitions:
                raise DeliveryError(
                    "Persisted author-event carriers have an ambiguous result state."
                )
            transition = VerifiedAuthorTransition(
                record=record,
                event_envelope=event_envelope,
                previous_envelope=previous,
                result_envelope=result_envelope,
            )
            transitions[result_digest] = transition
            logical_envelopes[result_digest] = result_envelope
            progressed = True
        if not progressed:
            raise DeliveryError(
                "A persisted author-event carrier has no reducer-derived predecessor."
            )
        pending = deferred
    return transitions, logical_envelopes


def _verify_carrier_publication_order(
    terminal: Mapping[str, Any],
    snapshot: PullRequestSnapshot,
    states: Mapping[str, tuple[ReviewRecord, dict[str, Any]]],
    author_records: Sequence[tuple[ReviewRecord, dict[str, Any]]],
    author_transitions: Mapping[str, VerifiedAuthorTransition],
    verified_state_sha256s: set[str],
    selected_author_ids: set[str],
    archived_terminal_sha256s: set[str],
) -> None:
    """Require a strict forge order for each selected persisted event."""
    selected_states = {
        digest: states[digest] for digest in verified_state_sha256s if digest in states
    }
    selected_authors = {
        record.id: (record, envelope)
        for record, envelope in author_records
        if record.id in selected_author_ids
    }
    publication_times = {
        f"review:{record.id}": _review_submission_time(record)
        for record, _ in (*selected_states.values(), *selected_authors.values())
    }
    current_exchange_id = terminal["state"]["exchange_id"]
    current_exchange_records = {
        f"review:{record.id}"
        for record, envelope in (*selected_states.values(), *selected_authors.values())
        if envelope["state"]["exchange_id"] == current_exchange_id
    }

    edges: set[tuple[str, str]] = set()
    author_result_records = {
        digest: f"review:{transition.record.id}"
        for digest, transition in author_transitions.items()
        if transition.record.id in selected_author_ids
    }
    for result_digest, transition in author_transitions.items():
        if transition.record.id not in selected_author_ids:
            continue
        prior_digest = cast(
            str, transition.event_envelope["state"]["prior_state_sha256"]
        )
        previous_record = selected_states.get(prior_digest)
        previous_record_id = (
            f"review:{previous_record[0].id}"
            if previous_record is not None
            else author_result_records.get(prior_digest)
        )
        if previous_record_id is None or result_digest not in author_result_records:
            raise DeliveryError(
                "A selected author-event carrier has no ordered predecessor."
            )
        edges.add((previous_record_id, f"review:{transition.record.id}"))

    for current_record, envelope in selected_states.values():
        state = envelope["state"]
        prior_digest = state["prior_state_sha256"]
        if prior_digest is None:
            prior_digest = state["supersedes_state_sha256"]
        if prior_digest is None:
            continue
        previous_record = selected_states.get(cast(str, prior_digest))
        if previous_record is not None:
            edges.add(
                (f"review:{previous_record[0].id}", f"review:{current_record.id}")
            )
            continue
        author_record_id = author_result_records.get(cast(str, prior_digest))
        if author_record_id is not None:
            edges.add((author_record_id, f"review:{current_record.id}"))
            continue
        raise DeliveryError(
            "A selected reviewer-state carrier has no ordered predecessor."
        )

    selected_envelopes = {
        digest: envelope for digest, (_, envelope) in selected_states.items()
    }
    terminal_digest = cast(str, terminal["state_sha256"])
    selected_envelopes.setdefault(terminal_digest, cast(dict[str, Any], terminal))
    authority_contexts: dict[str, dict[str, Any]] = {}
    for digest, envelope in selected_envelopes.items():
        state = envelope["state"]
        receipts = {
            receipt["reference"]: receipt
            for receipt in (
                state["supersession_authority_receipt"],
                *(finding["authority_receipt"] for finding in state["findings"]),
            )
            if receipt is not None
        }
        for reference in receipts:
            authority_record = _authority_forge_record(snapshot, reference)
            if reference not in publication_times:
                publication_times[reference] = _authority_publication_time(
                    authority_record
                )
            try:
                authority = review_exchange.parse_authority_record(
                    authority_record.body
                )
            except review_exchange.ProtocolError as error:
                raise DeliveryError(
                    "A selected authority record cannot be ordered."
                ) from error
            previous_authority = authority_contexts.setdefault(reference, authority)
            if previous_authority != authority:
                raise DeliveryError(
                    "A selected authority record has an ambiguous event context."
                )
            prior_digest = (
                authority["prior_state_sha256"] or authority["supersedes_state_sha256"]
            )
            prior_state_record = selected_states.get(cast(str, prior_digest))
            prior_record_id: str | None
            if prior_state_record is not None:
                prior_record_id = f"review:{prior_state_record[0].id}"
            else:
                prior_record_id = author_result_records.get(cast(str, prior_digest))
            if prior_record_id is None:
                raise DeliveryError(
                    "A selected authority record has no ordered predecessor."
                )
            edges.add((prior_record_id, reference))
            current_state_record = selected_states.get(digest)
            if current_state_record is not None:
                edges.add((reference, f"review:{current_state_record[0].id}"))
            if state["exchange_id"] == current_exchange_id:
                current_exchange_records.add(reference)

    for digest in archived_terminal_sha256s:
        archived_record = selected_states.get(digest)
        if archived_record is None:
            raise DeliveryError("An archived terminal state has no persisted carrier.")
        archived_record_id = f"review:{archived_record[0].id}"
        edges.update(
            (archived_record_id, current_record_id)
            for current_record_id in current_exchange_records
        )

    if len(set(publication_times.values())) != len(publication_times):
        raise DeliveryError(
            "Selected review-exchange records have an ambiguous publication order."
        )

    if any(
        publication_times[earlier] >= publication_times[later]
        for earlier, later in edges
    ):
        raise DeliveryError(
            "The selected review-exchange carrier publication order is invalid."
        )


def _verify_state_chain(
    terminal: Mapping[str, Any],
    snapshot: PullRequestSnapshot,
    binding: ReviewBinding,
) -> VerifiedStateChain:
    """Replay every persisted event that leads to one terminal reviewer state."""
    states, author_records = _review_carriers(snapshot, binding)
    author_transitions, logical_envelopes = _derive_author_transitions(
        states, author_records
    )
    terminal_digest = cast(str, terminal["state_sha256"])
    existing_terminal = logical_envelopes.get(terminal_digest)
    if existing_terminal is not None and not _same_envelope(
        existing_terminal, terminal
    ):
        raise DeliveryError("The terminal state digest has ambiguous content.")
    logical_envelopes[terminal_digest] = cast(dict[str, Any], terminal)
    envelopes = [
        terminal,
        *(
            envelope
            for _, envelope in states.values()
            if envelope["state_sha256"] != terminal["state_sha256"]
        ),
    ]
    derived_children: dict[str, set[str]] = {}
    for result_digest, transition in author_transitions.items():
        prior_digest = cast(
            str, transition.event_envelope["state"]["prior_state_sha256"]
        )
        derived_children.setdefault(prior_digest, set()).add(result_digest)
    for envelope in envelopes:
        state = envelope["state"]
        prior_digest = state["prior_state_sha256"]
        if prior_digest is None and len(state["accepted_events"]) == 1:
            prior_digest = state["supersedes_state_sha256"]
        if prior_digest is not None:
            derived_children.setdefault(cast(str, prior_digest), set()).add(
                envelope["state_sha256"]
            )
    if any(len(children) != 1 for children in derived_children.values()):
        raise DeliveryError(
            "One review-exchange state has multiple derived successors."
        )
    verified_states: set[str] = set()
    memo: dict[str, tuple[dict[str, str], frozenset[str]]] = {}
    new_finding_ids_by_state: dict[str, frozenset[str]] = {}
    finding_origins_by_state: dict[str, dict[str, str]] = {}
    active: set[str] = set()

    def verify(
        envelope: Mapping[str, Any],
    ) -> tuple[dict[str, str], frozenset[str]]:
        digest = cast(str, envelope["state_sha256"])
        if digest in memo:
            return memo[digest]
        if digest in active:
            raise DeliveryError("The review-exchange state chain contains a cycle.")
        active.add(digest)
        state = cast(Mapping[str, Any], envelope["state"])
        result: tuple[dict[str, str], frozenset[str]]
        new_finding_ids: frozenset[str]
        finding_origins: dict[str, str]
        author_transition = author_transitions.get(digest)
        if author_transition is not None:
            author_previous = author_transition.previous_envelope
            prior_map, prior_authors = verify(author_previous)
            mapped = dict(prior_map)
            for response in author_transition.event_envelope["state"]["responses"]:
                mapped[response["finding_id"]] = author_transition.record.id
            result = (
                mapped,
                prior_authors | frozenset({author_transition.record.id}),
            )
            new_finding_ids = frozenset()
            finding_origins = dict(
                finding_origins_by_state[cast(str, author_previous["state_sha256"])]
            )
        elif state["round"] == 1 and state["prior_state_sha256"] is None:
            supersession_receipt = state["supersession_authority_receipt"]
            if supersession_receipt is not None:
                _verify_authority_receipt(snapshot, supersession_receipt, envelope)
            for finding in state["findings"]:
                authority_receipt = finding["authority_receipt"]
                if authority_receipt is not None:
                    _verify_authority_receipt(snapshot, authority_receipt, envelope)
            supersedes = state["supersedes_state_sha256"]
            if supersedes is None:
                if not _verify_initial_state(envelope):
                    raise DeliveryError(
                        "The initial reviewer state is not reducer-derived."
                    )
                result = ({}, frozenset())
            else:
                reframe_previous = logical_envelopes.get(cast(str, supersedes))
                if reframe_previous is None:
                    raise DeliveryError(
                        "The reframed state has no verified superseded state."
                    )
                _, previous_authors = verify(reframe_previous)
                result = ({}, previous_authors)
                matches = 0
                for stop_reason in _review_stop_reasons():
                    event = _infer_reframe_event(
                        reframe_previous, envelope, stop_reason
                    )
                    if _try_reduce(reframe_previous, event, envelope) is not None:
                        matches += 1
                if matches != 1:
                    raise DeliveryError(
                        "The reframed state is not reducer-derived from its supersession."
                    )
            new_finding_ids = frozenset(finding["id"] for finding in state["findings"])
            state_record = states.get(digest)
            finding_origins = (
                {}
                if state_record is None
                else {finding_id: state_record[0].id for finding_id in new_finding_ids}
            )
        else:
            supersession_receipt = state["supersession_authority_receipt"]
            if supersession_receipt is not None:
                _verify_authority_receipt(snapshot, supersession_receipt, envelope)
            for finding in state["findings"]:
                authority_receipt = finding["authority_receipt"]
                if authority_receipt is not None:
                    _verify_authority_receipt(snapshot, authority_receipt, envelope)
            candidates: list[
                tuple[
                    dict[str, str],
                    frozenset[str],
                    frozenset[str],
                    dict[str, str],
                ]
            ] = []
            prior_digest = cast(str, state["prior_state_sha256"])
            continued_previous = logical_envelopes.get(prior_digest)
            if continued_previous is not None:
                prior_map, prior_authors = verify(continued_previous)
                human_event = _infer_human_event(continued_previous, envelope)
                if (
                    human_event is not None
                    and _try_reduce(continued_previous, human_event, envelope)
                    is not None
                ):
                    human_author_map = dict(prior_map)
                    current_findings = {
                        finding["id"]: finding for finding in state["findings"]
                    }
                    for decision in human_event["decisions"]:
                        finding_id = decision["finding_id"]
                        if current_findings[finding_id]["author_response"] is None:
                            human_author_map.pop(finding_id, None)
                    candidates.append(
                        (
                            human_author_map,
                            prior_authors,
                            frozenset(),
                            dict(
                                finding_origins_by_state[
                                    cast(str, continued_previous["state_sha256"])
                                ]
                            ),
                        )
                    )
                for stop_reason in _review_stop_reasons():
                    reviewer_event = _infer_reviewer_event(
                        continued_previous, envelope, stop_reason
                    )
                    if (
                        _try_reduce(continued_previous, reviewer_event, envelope)
                        is not None
                    ):
                        previous_ids = {
                            finding["id"]
                            for finding in continued_previous["state"]["findings"]
                        }
                        current_new_ids = frozenset(
                            finding["id"]
                            for finding in state["findings"]
                            if finding["id"] not in previous_ids
                        )
                        origins = dict(
                            finding_origins_by_state[
                                cast(str, continued_previous["state_sha256"])
                            ]
                        )
                        state_record = states.get(digest)
                        if state_record is not None:
                            origins.update(
                                {
                                    finding_id: state_record[0].id
                                    for finding_id in current_new_ids
                                }
                            )
                        candidates.append(
                            (
                                dict(prior_map),
                                prior_authors,
                                current_new_ids,
                                origins,
                            )
                        )
                        break
            if len(candidates) != 1:
                raise DeliveryError(
                    "The terminal state does not have one complete persisted event chain."
                )
            result = candidates[0][:2]
            new_finding_ids = candidates[0][2]
            finding_origins = candidates[0][3]
        active.remove(digest)
        memo[digest] = result
        new_finding_ids_by_state[digest] = new_finding_ids
        finding_origins_by_state[digest] = finding_origins
        verified_states.add(digest)
        return result

    author_map, selected_author_ids = verify(terminal)
    del author_map
    selected_state_sha256s = frozenset(memo)
    selected_envelopes = {
        digest: logical_envelopes[digest] for digest in selected_state_sha256s
    }
    superseding_state_sha256s: dict[str, str] = {}
    for digest, envelope in selected_envelopes.items():
        state = envelope["state"]
        supersedes = state["supersedes_state_sha256"]
        if supersedes is not None and len(state["accepted_events"]) == 1:
            superseding_state_sha256s[cast(str, supersedes)] = digest
    finding_origin_review_ids = {
        (digest, finding_id): review_id
        for digest in selected_state_sha256s
        for finding_id, review_id in finding_origins_by_state[digest].items()
    }
    author_event_review_ids = {
        (digest, finding_id): review_id
        for digest in selected_state_sha256s
        for finding_id, review_id in memo[digest][0].items()
    }
    used_author_ids = set(selected_author_ids)
    consumed_exchange_ids = {
        envelope["state"]["exchange_id"] for envelope in selected_envelopes.values()
    }
    archived_terminal_sha256s: set[str] = set()
    while unused_state_sha256s := set(states).difference(verified_states):
        unused_by_exchange: dict[str, list[dict[str, Any]]] = {}
        for digest in unused_state_sha256s:
            envelope = states[digest][1]
            exchange_id = cast(str, envelope["state"]["exchange_id"])
            unused_by_exchange.setdefault(exchange_id, []).append(envelope)
        archived = False
        for exchange_id, exchange_envelopes in unused_by_exchange.items():
            if exchange_id in consumed_exchange_ids:
                continue
            if any(
                states[envelope["state_sha256"]][0].head_oid == binding.head_oid
                for envelope in exchange_envelopes
            ):
                continue
            completed = [
                envelope
                for envelope in exchange_envelopes
                if envelope["state"]["phase"] == "complete"
                and envelope["state"]["verdict"] == "GO"
                and envelope["state"]["next_action"] == "finalize"
                and envelope["state"]["go_eligible"] is True
                and envelope["state"]["requirements_sha256"]
                == terminal["state"]["requirements_sha256"]
            ]
            if len(completed) != 1:
                continue
            before = set(verified_states)
            _, archived_authors = verify(completed[0])
            newly_verified = verified_states.difference(before)
            if not newly_verified:
                continue
            used_author_ids.update(archived_authors)
            consumed_exchange_ids.add(exchange_id)
            archived_terminal_sha256s.add(cast(str, completed[0]["state_sha256"]))
            archived = True
        if not archived:
            raise DeliveryError(
                "The persisted reviewer-state history is not one nonforking chain."
            )
    all_author_ids = {record.id for record, _ in author_records}
    if all_author_ids != used_author_ids:
        raise DeliveryError(
            "The persisted author-event history is not one nonforking chain."
        )
    _verify_carrier_publication_order(
        terminal,
        snapshot,
        states,
        author_records,
        author_transitions,
        verified_states,
        used_author_ids,
        archived_terminal_sha256s,
    )
    _verify_carrier_review_roots(
        snapshot,
        states,
        {digest: logical_envelopes[digest] for digest in verified_states},
        verified_states,
        used_author_ids,
        new_finding_ids_by_state,
    )
    return VerifiedStateChain(
        envelopes=selected_envelopes,
        selected_state_sha256s=selected_state_sha256s,
        verified_state_sha256s=frozenset(verified_states),
        superseding_state_sha256s=superseding_state_sha256s,
        finding_origin_review_ids=finding_origin_review_ids,
        author_event_review_ids=author_event_review_ids,
        terminal_new_finding_ids=new_finding_ids_by_state[
            cast(str, terminal["state_sha256"])
        ],
    )


def _terminal_state(
    binding: ReviewBinding, manifest: ClosureManifest
) -> dict[str, Any]:
    try:
        envelope = review_exchange.verify_envelope(manifest.state_envelope)
    except review_exchange.ProtocolError as error:
        raise DeliveryError(f"The v1 terminal ledger is invalid: {error}") from error
    state = envelope["state"]
    if envelope["schema_id"] != review_exchange.STATE_SCHEMA_ID:
        raise DeliveryError("The v1 terminal ledger is not a state envelope.")
    expected_target = {
        "provider": "github",
        "repository": binding.repository,
        "number": binding.number,
        "url": binding.url,
    }
    if state["surface"] != "pull_request" or state["target"] != expected_target:
        raise DeliveryError("The v1 terminal ledger is not bound to this pull request.")
    if (
        state["phase"] != "complete"
        or state["verdict"] != "GO"
        or state["next_action"] != "finalize"
        or state["go_eligible"] is not True
    ):
        raise DeliveryError("The v1 closure manifest does not contain a terminal GO.")
    if state["artifact_binding"]["revision"] != binding.head_oid:
        raise DeliveryError("The v1 terminal ledger does not bind the current head.")
    if (
        state["requirements_sha256"]
        != manifest.requirements_binding.requirements_sha256
    ):
        raise DeliveryError(
            "The terminal state does not bind the retained linked requirements."
        )
    if (
        state["artifact_binding"]["sha256"]
        != manifest.requirements_binding.reviewed_scope_sha256
    ):
        raise DeliveryError(
            "The terminal state does not bind the retained review scope."
        )
    terminal_review_body(manifest)
    return cast(dict[str, Any], state)


def _authority_forge_record(
    snapshot: PullRequestSnapshot, reference: str
) -> ReviewComment | ReviewRecord:
    """Resolve one exact authority receipt reference."""
    try:
        kind, record_id = reference.split(":", maxsplit=1)
    except ValueError as error:
        raise DeliveryError("The authority receipt reference is invalid.") from error
    records: list[ReviewComment | ReviewRecord] = []
    if kind == "review":
        records.extend(review for review in snapshot.reviews if review.id == record_id)
    elif kind == "comment":
        records.extend(
            comment
            for thread in snapshot.threads
            for comment in thread.comments
            if comment.id == record_id
        )
    else:
        raise DeliveryError("The authority receipt must name a review or comment.")
    if len(records) != 1:
        raise DeliveryError(
            "The authority receipt does not resolve to one forge record."
        )
    return records[0]


def _verify_authority_receipt(
    snapshot: PullRequestSnapshot,
    receipt: Mapping[str, str],
    envelope: Mapping[str, Any],
) -> None:
    """Require one exact repository-authoritative forge record."""
    record = _authority_forge_record(snapshot, receipt["reference"])
    try:
        review_exchange.verify_authority_record_for_state(
            record.body, receipt, envelope
        )
    except review_exchange.ProtocolError as error:
        raise DeliveryError(
            f"The authority receipt is not action-bound: {error}"
        ) from error
    if record.author_association not in {"OWNER", "MEMBER", "COLLABORATOR"}:
        raise DeliveryError("The authority receipt is not repository-authoritative.")
    if record.author_permission not in {"ADMIN", "MAINTAIN"}:
        raise DeliveryError(
            "The authority receipt author lacks current repository authority."
        )


def _reframe_closure_evidence(superseded_state_sha256: str) -> tuple[str, ...]:
    """Return the canonical evidence for one authoritative reframe withdrawal."""
    evidence = (
        f"The requirements in state `{superseded_state_sha256}` were "
        "authoritatively reframed."
    )
    return (evidence,)


def validate_closure_manifest(
    binding: ReviewBinding,
    manifest: ClosureManifest,
    snapshot: PullRequestSnapshot,
) -> dict[str, ThreadClosure]:
    """Validate one complete v1 closure ledger before any forge mutation."""
    _terminal_state(binding, manifest)
    chain = _verify_state_chain(manifest.state_envelope, snapshot, binding)
    terminal_digest = cast(str, manifest.state_envelope["state_sha256"])
    terminal_exchange_id = cast(str, manifest.state_envelope["state"]["exchange_id"])
    dynamic_terminal_identities = {
        (terminal_exchange_id, finding_id)
        for finding_id in chain.terminal_new_finding_ids
    }
    static_entries = tuple(
        entry
        for entry in manifest.entries
        if not (
            entry.finding_state_sha256 == terminal_digest
            and (entry.finding_exchange_id, entry.finding_id)
            in dynamic_terminal_identities
        )
    )
    if manifest.terminal_visible_content != terminal_visible_content(
        binding, static_entries
    ):
        raise DeliveryError(
            "The terminal visible closure ledger does not match its manifest entries."
        )
    threads = snapshot.threads
    thread_ids = [thread.id for thread in threads]
    if len(thread_ids) != len(set(thread_ids)):
        raise DeliveryError("The forge returned duplicate review-thread identifiers.")
    entry_ids = [entry.thread_id for entry in manifest.entries]
    finding_identities = [
        (entry.finding_exchange_id, entry.finding_id) for entry in manifest.entries
    ]
    if len(entry_ids) != len(set(entry_ids)) or len(finding_identities) != len(
        set(finding_identities)
    ):
        raise DeliveryError("The v1 closure manifest contains a duplicate identity.")
    closure_source_digests = {
        terminal_digest,
        *chain.superseding_state_sha256s,
    }
    expected_native_findings = {
        (digest, envelope["state"]["exchange_id"], finding["id"])
        for digest, envelope in chain.envelopes.items()
        if digest in closure_source_digests
        for finding in envelope["state"]["findings"]
        if finding["id"].startswith("native:")
    }
    actual_native_findings = {
        (
            entry.finding_state_sha256,
            entry.finding_exchange_id,
            entry.finding_id,
        )
        for entry in manifest.entries
        if entry.finding_id.startswith("native:")
    }
    if not actual_native_findings.issubset(expected_native_findings):
        raise DeliveryError(
            "The v1 closure manifest contains an unverified native finding."
        )
    maximum_entries = review_exchange.MAX_FINDINGS * (
        1 + len(chain.superseding_state_sha256s)
    )
    if len(manifest.entries) > maximum_entries:
        raise DeliveryError("The v1 closure manifest contains too many findings.")
    by_id = {thread.id: thread for thread in threads}
    unresolved = {thread.id: thread for thread in threads if not thread.is_resolved}
    for thread in unresolved.values():
        if not thread.comments or not thread.comments[0].viewer_did_author:
            raise DeliveryError(
                "A foreign open review thread remains; withhold GO delivery."
            )
        if not thread.viewer_can_reply or not thread.viewer_can_resolve:
            raise DeliveryError(
                "An Athena-owned open thread lacks reply or resolution capability."
            )
    by_thread = {entry.thread_id: entry for entry in manifest.entries}
    if not set(unresolved).issubset(by_thread) or not set(by_thread).issubset(by_id):
        raise DeliveryError(
            "The v1 closure manifest must cover every Athena-owned open thread."
        )
    review_by_id = {review.id: review for review in snapshot.reviews}
    terminal_states = {"resolved", "withdrawn", "accepted_risk", "nonblocking"}
    for thread_id, entry in by_thread.items():
        thread = by_id[thread_id]
        if entry.reviewer_disposition not in terminal_states:
            raise DeliveryError(
                "The v1 closure manifest contains a nonterminal disposition."
            )
        if entry.finding_disposition not in {"required", "suggestion", "nit", "FYI"}:
            raise DeliveryError("The v1 finding disposition is invalid.")
        if not thread.comments or thread.comments[0].id != entry.origin_comment_id:
            raise DeliveryError("The v1 closure entry does not bind the root finding.")
        root = thread.comments[0]
        if root.review_head_oid != entry.origin_review_head_oid:
            raise DeliveryError(
                "The v1 closure entry does not bind the origin review head."
            )
        conversation_matches = conversation_sha256(thread) == entry.conversation_sha256
        response_recovered = _closure_reply_recovered(
            thread, binding, manifest, entry, snapshot
        )
        if thread.is_resolved and not response_recovered:
            raise DeliveryError(
                "A resolved v1 closure entry has no verified closure response."
            )
        if not conversation_matches and not response_recovered:
            raise DeliveryError(
                "The v1 closure entry is not bound to the current conversation."
            )
        source_envelope = chain.envelopes.get(entry.finding_state_sha256)
        if source_envelope is None:
            raise DeliveryError(
                "The closure entry does not name a selected finding state."
            )
        source_state = source_envelope["state"]
        if source_state["exchange_id"] != entry.finding_exchange_id:
            raise DeliveryError("The closure entry does not bind its finding exchange.")
        source_findings = {
            finding["id"]: finding for finding in source_state["findings"]
        }
        finding = source_findings.get(entry.finding_id)
        if finding is None:
            raise DeliveryError(
                "The closure entry finding is absent from its selected state."
            )
        historical = entry.finding_state_sha256 != terminal_digest
        superseding_envelope: dict[str, Any] | None = None
        if historical:
            expected_superseding = chain.superseding_state_sha256s.get(
                entry.finding_state_sha256
            )
            if (
                expected_superseding is None
                or entry.superseding_state_sha256 != expected_superseding
            ):
                raise DeliveryError(
                    "The closure entry does not bind an exact selected reframe edge."
                )
            superseding_envelope = chain.envelopes[expected_superseding]
        elif entry.superseding_state_sha256 is not None:
            raise DeliveryError(
                "A current finding cannot name a superseding review state."
            )
        marker = _finding_marker(root)
        if marker is None:
            if entry.finding_id != f"native:{root.id}":
                raise DeliveryError(
                    "An open legacy thread must retain its native identity."
                )
        else:
            exchange_id, finding_id = marker
            if (
                exchange_id != entry.finding_exchange_id
                or finding_id != entry.finding_id
            ):
                raise DeliveryError(
                    "The inline finding marker does not match the ledger."
                )
            origin_review_id = chain.finding_origin_review_ids.get(
                (entry.finding_state_sha256, entry.finding_id)
            )
            origin_review = review_by_id.get(cast(str, origin_review_id))
            anchor = _finding_anchor(cast(str, finding["location"]))
            if (
                origin_review_id is None
                or origin_review is None
                or anchor is None
                or root.review_id != origin_review_id
                or root.review_head_oid != origin_review.head_oid
                or (root.path, root.original_line) != anchor
                or root.side not in {"LEFT", "RIGHT"}
                or not root.viewer_did_author
            ):
                raise DeliveryError(
                    "The inline finding is not bound to its atomic reviewer state."
                )
        if finding["disposition"] != entry.finding_disposition:
            raise DeliveryError(
                "The finding state and closure disposition do not agree."
            )
        if (
            marker is not None
            and finding["location"] != f"{root.path}:{root.original_line}"
        ):
            raise DeliveryError(
                "The inline finding location does not match the reviewer state."
            )
        if (
            entry.finding_id.startswith("native:")
            and entry.finding_disposition != "required"
        ):
            raise DeliveryError("An adopted legacy finding must remain required.")
        author = finding["author_response"]
        expected_answer = None if author is None else author["kind"]
        expected_revision = None if author is None else author["artifact_revision"]
        expected_author_review = chain.author_event_review_ids.get(
            (entry.finding_state_sha256, entry.finding_id)
        )
        if (
            entry.author_answer != expected_answer
            or entry.author_artifact_revision != expected_revision
            or entry.author_event_review_id != expected_author_review
        ):
            raise DeliveryError(
                "The closure entry does not match the verified author-event state."
            )
        if historical:
            assert superseding_envelope is not None
            supersession_receipt = superseding_envelope["state"][
                "supersession_authority_receipt"
            ]
            if (
                entry.reviewer_disposition != "withdrawn"
                or entry.authority_receipt != supersession_receipt
                or entry.authority_receipt is None
            ):
                raise DeliveryError(
                    "A reframed finding needs its exact authoritative withdrawal."
                )
            expected_evidence = _reframe_closure_evidence(entry.finding_state_sha256)
            if entry.closure_evidence != expected_evidence:
                raise DeliveryError(
                    "The closure evidence does not match the authoritative reframe."
                )
            _verify_authority_receipt(
                snapshot, entry.authority_receipt, superseding_envelope
            )
        else:
            if finding["state"] != entry.reviewer_disposition:
                raise DeliveryError(
                    "The terminal state and thread closure disposition do not agree."
                )
            reviewer = finding["reviewer_response"]
            if reviewer is not None:
                expected_evidence = tuple(reviewer["evidence"])
            elif author is not None:
                expected_evidence = tuple(author["evidence"])
            else:
                expected_evidence = tuple(finding["evidence"])
            if entry.closure_evidence != expected_evidence:
                raise DeliveryError(
                    "The closure evidence does not match the verified reviewer state."
                )
            if entry.authority_receipt != finding["authority_receipt"]:
                raise DeliveryError(
                    "The closure authority receipt does not match the reviewer state."
                )
            if entry.reviewer_disposition == "nonblocking":
                if entry.finding_disposition == "required":
                    raise DeliveryError(
                        "A required finding cannot become nonblocking at delivery."
                    )
            elif entry.reviewer_disposition == "accepted_risk":
                if (
                    entry.author_answer != "risk_acceptance"
                    or entry.authority_receipt is None
                ):
                    raise DeliveryError(
                        "Accepted risk needs an author request and an authority receipt."
                    )
            elif entry.reviewer_disposition == "withdrawn":
                if entry.author_answer not in {
                    "fix",
                    "fix_with_tradeoff",
                    "contest",
                    "risk_acceptance",
                }:
                    raise DeliveryError(
                        "A withdrawn finding has no verified author answer."
                    )
            elif entry.author_answer not in {"fix", "fix_with_tradeoff"}:
                raise DeliveryError(
                    "A resolved finding needs a corrective author answer."
                )
            if entry.author_answer in {"fix", "fix_with_tradeoff"}:
                if entry.origin_review_head_oid == entry.author_artifact_revision:
                    raise DeliveryError(
                        "A corrective author answer does not bind a new reviewed head."
                    )
            elif entry.author_answer == "contest":
                if entry.author_event_review_id is None:
                    raise DeliveryError(
                        "The contest answer has no verified author-event carrier."
                    )
            elif entry.author_answer == "risk_acceptance":
                if entry.reviewer_disposition not in {"withdrawn", "accepted_risk"}:
                    raise DeliveryError(
                        "An unaccepted risk request has no terminal disposition."
                    )
            elif entry.author_answer is not None:
                raise DeliveryError("The v1 author answer is invalid.")
        if not entry.closure_evidence or any(
            not evidence.strip() for evidence in entry.closure_evidence
        ):
            raise DeliveryError("The v1 closure evidence is incomplete.")
        if not historical and entry.authority_receipt is not None:
            _verify_authority_receipt(
                snapshot, entry.authority_receipt, manifest.state_envelope
            )
        response_body = _closure_response_body(binding, manifest, entry)
        if (
            len(response_body.encode("utf-8"))
            > review_exchange.PROVIDER_BODY_LIMITS["github"]
        ):
            raise DeliveryError(
                "A generated closure response exceeds the GitHub body limit."
            )
    return by_thread


def _closure_response_body(
    binding: ReviewBinding, manifest: ClosureManifest, entry: ThreadClosure
) -> str:
    answer = entry.author_answer or "not applicable"
    evidence = "\n".join(f"- {item}" for item in entry.closure_evidence)
    identity = f"{entry.finding_exchange_id}/{entry.finding_id}"
    if entry.superseding_state_sha256 is not None:
        receipt = entry.authority_receipt or {
            "reference": "not available",
            "sha256": "not available",
        }
        visible = (
            f"Finding `{identity}`: `withdrawn`.\n\n"
            "Closure basis: authoritative requirements reframe.\n\n"
            f"Superseded state: `{entry.finding_state_sha256}`.\n\n"
            f"Superseding state: `{entry.superseding_state_sha256}`.\n\n"
            f"Authority receipt: `{receipt['reference']}` with SHA-256 "
            f"`{receipt['sha256']}`.\n\n"
            f"Author answer: `{answer}`.\n\n"
            f"Closure evidence:\n{evidence}"
        )
    else:
        findings = {
            finding["id"]: finding
            for finding in manifest.state_envelope["state"]["findings"]
        }
        finding = findings.get(entry.finding_id)
        reviewer = None if finding is None else finding["reviewer_response"]
        reviewer_answer = "terminal" if reviewer is None else reviewer["kind"]
        visible = (
            f"Finding `{identity}`: `{entry.reviewer_disposition}`.\n\n"
            f"Author answer: `{answer}`.\n\n"
            f"Reviewer answer: `{reviewer_answer}`.\n\n"
            f"Closure evidence:\n{evidence}"
        )
    marker_seed = {
        "binding": _binding_dict(binding),
        "entry": _closure_dict(entry),
        "state_sha256": manifest.state_envelope["state_sha256"],
        "visible": visible,
    }
    marker = review_exchange.sha256_json(marker_seed)
    superseding = entry.superseding_state_sha256 or "none"
    return (
        f"{visible}\n\n<!-- HomericIntelligence:pr-review-closure:v1 "
        f"exchange={entry.finding_exchange_id} id={entry.finding_id} "
        f"source={entry.finding_state_sha256} superseding={superseding} "
        f"terminal={manifest.state_envelope['state_sha256']} sha256={marker} -->"
    )


def _matching_terminal_reviews(
    snapshot: PullRequestSnapshot, body: str, head_oid: str
) -> list[ReviewRecord]:
    return [
        review
        for review in snapshot.reviews
        if review.body == body
        and review.head_oid == head_oid
        and review.viewer_did_author
        and not review.includes_created_edit
        and review.state in {"COMMENT", "COMMENTED"}
    ]


def _conflicting_terminal_review(
    snapshot: PullRequestSnapshot,
    binding: ReviewBinding,
    manifest: ClosureManifest,
    body: str,
    verified_state_sha256s: frozenset[str] | set[str],
) -> bool:
    exchange_id = manifest.state_envelope["state"]["exchange_id"]
    for review in snapshot.reviews:
        if (
            not review.viewer_did_author
            or review.head_oid != binding.head_oid
            or review.body == body
        ):
            continue
        if review_exchange.CARRIER_PREFIX not in review.body:
            continue
        try:
            envelope = review_exchange.extract_carrier(review.body)
        except review_exchange.ProtocolError:
            return True
        if envelope["schema_id"] != review_exchange.STATE_SCHEMA_ID:
            continue
        state = envelope["state"]
        if (
            state["target"] == _expected_target(binding)
            and state["exchange_id"] == exchange_id
            and envelope["state_sha256"] not in verified_state_sha256s
        ):
            return True
    return False


def _validate_terminal_inline_comments(
    binding: ReviewBinding,
    manifest: ClosureManifest,
    new_finding_ids: set[str],
) -> tuple[TerminalInlineComment, ...]:
    comments = tuple(
        _terminal_inline_comment(_terminal_comment_dict(comment))
        for comment in manifest.comments
    )
    if len(comments) > review_exchange.MAX_FINDINGS:
        raise DeliveryError("The terminal review contains too many inline findings.")
    state = manifest.state_envelope["state"]
    findings = {finding["id"]: finding for finding in state["findings"]}
    finding_anchors: dict[str, tuple[str, int]] = {}
    for finding_id in new_finding_ids:
        location = cast(str, findings[finding_id]["location"])
        anchor = _finding_anchor(location)
        if anchor is not None:
            finding_anchors[finding_id] = anchor
    comment_finding_ids: list[str] = []
    for comment in comments:
        marker = _finding_marker(
            ReviewComment(id="pending", body=comment.body, author="reviewer")
        )
        if marker is None or marker[0] != state["exchange_id"]:
            raise DeliveryError(
                "A terminal inline comment has no exact exchange finding marker."
            )
        finding_id = marker[1]
        finding = findings.get(finding_id)
        if finding is None or finding_anchors.get(finding_id) != (
            comment.path,
            comment.line,
        ):
            raise DeliveryError(
                "A terminal inline comment does not bind its exact finding location."
            )
        pending_entry = ThreadClosure(
            thread_id="pending",
            finding_id=finding_id,
            finding_exchange_id=state["exchange_id"],
            finding_state_sha256=manifest.state_envelope["state_sha256"],
            superseding_state_sha256=None,
            origin_comment_id="pending",
            origin_review_head_oid=binding.head_oid,
            conversation_sha256="0" * 64,
            finding_disposition=finding["disposition"],
            author_answer=None,
            author_artifact_revision=None,
            reviewer_disposition="nonblocking",
            closure_evidence=tuple(finding["evidence"]),
            authority_receipt=None,
            author_event_review_id=None,
        )
        if (
            len(
                _closure_response_body(binding, manifest, pending_entry).encode("utf-8")
            )
            > review_exchange.PROVIDER_BODY_LIMITS["github"]
        ):
            raise DeliveryError(
                "A generated terminal closure response exceeds the GitHub body limit."
            )
        comment_finding_ids.append(finding_id)
    if comment_finding_ids != sorted(comment_finding_ids) or len(
        comment_finding_ids
    ) != len(set(comment_finding_ids)):
        raise DeliveryError(
            "Terminal inline finding comments must be unique and ordered by finding ID."
        )
    summary_ids = manifest.summary_finding_ids
    if (
        tuple(sorted(summary_ids)) != summary_ids
        or len(summary_ids) != len(set(summary_ids))
        or set(summary_ids).intersection(comment_finding_ids)
    ):
        raise DeliveryError(
            "Terminal summary finding IDs must be unique, ordered, and not inline."
        )
    if set(comment_finding_ids) != set(finding_anchors) or set(summary_ids) != (
        new_finding_ids - set(finding_anchors)
    ):
        raise DeliveryError(
            "The terminal inline and summary findings do not match their carrier locations."
        )
    return comments


def _verify_go_state_history(
    snapshot: PullRequestSnapshot,
    binding: ReviewBinding,
    manifest: ClosureManifest,
    body: str,
) -> set[str]:
    chain = _verify_state_chain(manifest.state_envelope, snapshot, binding)
    _validate_terminal_inline_comments(
        binding, manifest, set(chain.terminal_new_finding_ids)
    )
    if _conflicting_terminal_review(
        snapshot,
        binding,
        manifest,
        body,
        chain.verified_state_sha256s,
    ):
        raise DeliveryError("The current-head terminal COMMENT evidence is ambiguous.")
    return set(chain.verified_state_sha256s)


def _closure_reply_recovered(
    thread: ReviewThread,
    binding: ReviewBinding,
    manifest: ClosureManifest,
    entry: ThreadClosure,
    snapshot: PullRequestSnapshot,
) -> bool:
    if not thread.comments:
        return False
    expected = _closure_response_body(binding, manifest, entry)
    response = thread.comments[-1]
    if (
        response.body != expected
        or not response.viewer_did_author
        or response.last_edited_at is not None
    ):
        return False
    terminal_reviews = _matching_terminal_reviews(
        snapshot, terminal_review_body(manifest), binding.head_oid
    )
    if len(terminal_reviews) != 1:
        return False
    if _forge_publication_time(
        response.published_at, "A recovered closure response"
    ) <= _review_submission_time(terminal_reviews[0]):
        return False
    prior = ReviewThread(
        id=thread.id,
        is_resolved=False,
        comments=thread.comments[:-1],
        viewer_can_reply=thread.viewer_can_reply,
        viewer_can_resolve=thread.viewer_can_resolve,
    )
    return conversation_sha256(prior) == entry.conversation_sha256


def _require_closed_manifest_threads(
    snapshot: PullRequestSnapshot,
    binding: ReviewBinding,
    manifest: ClosureManifest,
    by_thread: Mapping[str, ThreadClosure],
) -> None:
    """Require each ledger thread to remain exactly closed."""
    for thread_id, entry in by_thread.items():
        thread = _thread(snapshot, thread_id)
        if not thread.is_resolved or not _closure_reply_recovered(
            thread, binding, manifest, entry, snapshot
        ):
            raise DeliveryError(
                "A closed v1 review conversation changed after its verified closure."
            )


def _manifest_with_terminal_threads(
    snapshot: PullRequestSnapshot,
    binding: ReviewBinding,
    manifest: ClosureManifest,
    terminal_review_id: str,
) -> ClosureManifest:
    """Bind the terminal inline batch to its fetched review threads."""
    state = manifest.state_envelope["state"]
    findings = {finding["id"]: finding for finding in state["findings"]}
    specifications: dict[str, TerminalInlineComment] = {}
    for comment in manifest.comments:
        marker = _finding_marker(
            ReviewComment(id="pending", body=comment.body, author="reviewer")
        )
        if marker is None:
            raise DeliveryError("A terminal inline finding marker is absent.")
        specifications[marker[1]] = comment
    terminal_threads = [
        thread
        for thread in snapshot.threads
        if thread.comments and thread.comments[0].review_id == terminal_review_id
    ]
    if len(terminal_threads) != len(specifications):
        raise DeliveryError(
            "The fetched terminal review does not contain its exact inline batch."
        )
    dynamic_entries: list[ThreadClosure] = []
    observed_ids: set[str] = set()
    for thread in terminal_threads:
        root = thread.comments[0]
        marker = _finding_marker(root)
        if marker is None:
            raise DeliveryError(
                "A fetched terminal review thread has no finding marker."
            )
        exchange_id, finding_id = marker
        specification = specifications.get(finding_id)
        finding = findings.get(finding_id)
        if (
            specification is None
            or finding is None
            or exchange_id != state["exchange_id"]
            or not root.viewer_did_author
            or root.last_edited_at is not None
            or root.review_head_oid != binding.head_oid
            or root.body != specification.body
            or root.path != specification.path
            or root.side != specification.side
            or root.original_line != specification.line
        ):
            raise DeliveryError(
                "A fetched terminal inline finding does not match its atomic review."
            )
        base_thread = replace(thread, is_resolved=False, comments=(root,))
        entry = ThreadClosure(
            thread_id=thread.id,
            finding_id=finding_id,
            finding_exchange_id=state["exchange_id"],
            finding_state_sha256=manifest.state_envelope["state_sha256"],
            superseding_state_sha256=None,
            origin_comment_id=root.id,
            origin_review_head_oid=binding.head_oid,
            conversation_sha256=conversation_sha256(base_thread),
            finding_disposition=finding["disposition"],
            author_answer=None,
            author_artifact_revision=None,
            reviewer_disposition="nonblocking",
            closure_evidence=tuple(finding["evidence"]),
            authority_receipt=None,
            author_event_review_id=None,
        )
        if len(thread.comments) == 2:
            if not _closure_reply_recovered(thread, binding, manifest, entry, snapshot):
                raise DeliveryError(
                    "A terminal inline finding has an unverified later comment."
                )
        elif len(thread.comments) != 1:
            raise DeliveryError(
                "A terminal inline finding has an ambiguous conversation."
            )
        observed_ids.add(finding_id)
        dynamic_entries.append(entry)
    if observed_ids != set(specifications):
        raise DeliveryError("The fetched terminal inline finding set is incomplete.")
    existing_ids = {
        (entry.finding_exchange_id, entry.finding_id) for entry in manifest.entries
    }
    observed_identities = {(state["exchange_id"], item) for item in observed_ids}
    if existing_ids.intersection(observed_identities):
        raise DeliveryError(
            "A terminal inline finding duplicates a supplied closure entry."
        )
    return replace(
        manifest,
        entries=tuple(
            sorted(
                (*manifest.entries, *dynamic_entries),
                key=lambda entry: (
                    entry.finding_exchange_id,
                    entry.finding_id,
                    entry.thread_id,
                ),
            )
        ),
    )


def deliver_go_v1(
    forge: Forge, binding: ReviewBinding, manifest: ClosureManifest
) -> DeliveryResult:
    """Deliver one current-head v1 terminal record, closures, and GO label."""
    initial = _snapshot(forge, binding)
    last_snapshot = initial
    body = terminal_review_body(manifest)
    matching = _matching_terminal_reviews(initial, body, binding.head_oid)
    _verify_go_state_history(initial, binding, manifest, body)
    if len(matching) > 1:
        raise DeliveryError("The current-head terminal COMMENT evidence is ambiguous.")
    if matching:
        manifest = _manifest_with_terminal_threads(
            initial, binding, manifest, matching[0].id
        )
    by_thread = validate_closure_manifest(binding, manifest, initial)
    _verify_live_requirements(forge, manifest.requirements_binding)
    open_threads = [thread for thread in initial.threads if not thread.is_resolved]
    terminal_review_id = matching[0].id if matching else None
    responded = [
        thread_id
        for thread_id, entry in by_thread.items()
        if _closure_reply_recovered(
            _thread(initial, thread_id), binding, manifest, entry, initial
        )
    ]
    resolved = [
        thread_id for thread_id in responded if _thread(initial, thread_id).is_resolved
    ]
    writes_started = False
    uncertain_operation: str | None = None

    def read() -> PullRequestSnapshot:
        nonlocal last_snapshot
        last_snapshot = _snapshot(forge, binding)
        return last_snapshot

    def write(action: str, callback: Any, *arguments: Any) -> None:
        nonlocal writes_started, uncertain_operation
        _verify_live_requirements(forge, manifest.requirements_binding)
        writes_started = True
        uncertain_operation = action
        _call_write(action, callback, *arguments)

    def complete_write() -> None:
        nonlocal uncertain_operation
        uncertain_operation = None

    def result(status: str) -> DeliveryResult:
        return DeliveryResult(
            status=status,
            resolved_thread_ids=tuple(sorted(resolved)),
            terminal_review_id=terminal_review_id,
            responded_thread_ids=tuple(sorted(responded)),
            pending_thread_ids=tuple(sorted(set(by_thread).difference(resolved))),
            observed_head_oid=last_snapshot.head_oid,
            observed_labels=tuple(sorted(last_snapshot.labels)),
        )

    def fail(error: DeliveryError) -> NoReturn:
        if not writes_started:
            raise error
        error.report = DeliveryResult(
            status="partial",
            resolved_thread_ids=tuple(sorted(resolved)),
            terminal_review_id=terminal_review_id,
            responded_thread_ids=tuple(sorted(responded)),
            pending_thread_ids=tuple(sorted(set(by_thread).difference(resolved))),
            observed_head_oid=last_snapshot.head_oid,
            observed_labels=tuple(sorted(last_snapshot.labels)),
            uncertain_operation=uncertain_operation,
            recovery_read_required=True,
            reason=str(error),
        )
        raise error

    try:
        if GO_LABEL in initial.labels:
            if len(matching) == 1 and not open_threads:
                _require_closed_manifest_threads(initial, binding, manifest, by_thread)
                if NO_GO_LABEL not in initial.labels:
                    return result("already_delivered")
                write("implementation label", forge.set_implementation_go)
                recovered = read()
                _verify_go_state_history(recovered, binding, manifest, body)
                if (
                    GO_LABEL not in recovered.labels
                    or NO_GO_LABEL in recovered.labels
                    or len(
                        _matching_terminal_reviews(recovered, body, binding.head_oid)
                    )
                    != 1
                    or any(not thread.is_resolved for thread in recovered.threads)
                ):
                    raise DeliveryError(
                        "The resumed GO label delivery was not verified."
                    )
                _require_closed_manifest_threads(
                    recovered, binding, manifest, by_thread
                )
                _verify_live_requirements(forge, manifest.requirements_binding)
                complete_write()
                return result("delivered")
            raise DeliveryError(
                "A GO label without one matching current-head terminal ledger is not proof."
            )
        if not matching:
            write(
                "terminal review",
                forge.publish_terminal,
                body,
                binding.head_oid,
                manifest.comments,
            )
            after_terminal = read()
            terminal_matches = _matching_terminal_reviews(
                after_terminal, body, binding.head_oid
            )
            _verify_go_state_history(after_terminal, binding, manifest, body)
            if len(terminal_matches) != 1:
                raise DeliveryError(
                    "The exact current-head terminal COMMENT was not verified."
                )
            terminal_review_id = terminal_matches[0].id
            manifest = _manifest_with_terminal_threads(
                after_terminal, binding, manifest, terminal_review_id
            )
            by_thread = validate_closure_manifest(binding, manifest, after_terminal)
            responded = [
                thread_id
                for thread_id, entry in by_thread.items()
                if _closure_reply_recovered(
                    _thread(after_terminal, thread_id),
                    binding,
                    manifest,
                    entry,
                    after_terminal,
                )
            ]
            resolved = [
                thread_id
                for thread_id in responded
                if _thread(after_terminal, thread_id).is_resolved
            ]
            complete_write()

        for thread_id in sorted(by_thread):
            entry = by_thread[thread_id]
            response_body = _closure_response_body(binding, manifest, entry)
            current = read()
            thread = _thread(current, thread_id)
            if thread.is_resolved:
                if not _closure_reply_recovered(
                    thread, binding, manifest, entry, current
                ):
                    raise DeliveryError(
                        "A resolved review thread has no verified v1 closure response."
                    )
                if thread_id not in responded:
                    responded.append(thread_id)
                if thread_id not in resolved:
                    resolved.append(thread_id)
                continue
            if conversation_sha256(thread) == entry.conversation_sha256:
                before_reply = thread
                write("reply", forge.reply, thread_id, response_body)
                after_snapshot = read()
                after_reply = _thread(after_snapshot, thread_id)
                if not _response_is_only_conversation_change(
                    before_reply, after_reply, response_body
                ) or not _closure_reply_recovered(
                    after_reply, binding, manifest, entry, after_snapshot
                ):
                    raise DeliveryError(
                        "The forge did not verify the exact posted v1 closure response."
                    )
                responded.append(thread_id)
                complete_write()
            elif _closure_reply_recovered(thread, binding, manifest, entry, current):
                after_reply = thread
                if thread_id not in responded:
                    responded.append(thread_id)
            else:
                raise DeliveryError(
                    "The v1 review conversation changed before its response."
                )
            current = read()
            before_resolution = _thread(current, thread_id)
            if before_resolution != after_reply:
                raise DeliveryError(
                    "The v1 review conversation changed before thread resolution."
                )
            write("resolve", forge.resolve, thread_id)
            after_resolution = _thread(read(), thread_id)
            if (
                not after_resolution.is_resolved
                or after_resolution.comments != before_resolution.comments
            ):
                raise DeliveryError(
                    "The forge did not verify exact v1 thread resolution."
                )
            resolved.append(thread_id)
            complete_write()

        current = read()
        if any(not thread.is_resolved for thread in current.threads):
            raise DeliveryError(
                "An unresolved review thread remains before terminal delivery."
            )
        _require_closed_manifest_threads(current, binding, manifest, by_thread)
        _verify_go_state_history(current, binding, manifest, body)
        if len(_matching_terminal_reviews(current, body, binding.head_oid)) != 1:
            raise DeliveryError(
                "The terminal COMMENT changed before GO label delivery."
            )
        write("implementation label", forge.set_implementation_go)
        final = read()
        if GO_LABEL not in final.labels or NO_GO_LABEL in final.labels:
            raise DeliveryError("The implementation state labels are not exclusive.")
        _verify_go_state_history(final, binding, manifest, body)
        if len(_matching_terminal_reviews(final, body, binding.head_oid)) != 1:
            raise DeliveryError("The terminal COMMENT changed after GO label delivery.")
        if any(not thread.is_resolved for thread in final.threads):
            raise DeliveryError(
                "An unresolved review thread remains after GO delivery."
            )
        _require_closed_manifest_threads(final, binding, manifest, by_thread)
        _verify_live_requirements(forge, manifest.requirements_binding)
        complete_write()
        return result("delivered")
    except DeliveryError as error:
        fail(error)


def _verify_no_go_snapshot(
    snapshot: PullRequestSnapshot,
    binding: ReviewBinding,
    proof: NoGoProof,
) -> None:
    """Verify one exact NO-GO or conditional carrier and its complete ancestry."""
    envelope = _require_pr_envelope(
        proof.state_envelope, binding, schema_id=review_exchange.STATE_SCHEMA_ID
    )
    state = envelope["state"]
    if state["requirements_sha256"] != proof.requirements_binding.requirements_sha256:
        raise DeliveryError(
            "The NO-GO state does not bind the retained linked requirements."
        )
    if (
        state["artifact_binding"]["sha256"]
        != proof.requirements_binding.reviewed_scope_sha256
    ):
        raise DeliveryError("The NO-GO state does not bind the retained review scope.")
    nonterminal_no_go = (
        state["verdict"] == "NO-GO"
        and state["phase"] != "complete"
        and state["next_action"] != "finalize"
    )
    terminal_conditional = (
        state["phase"] == "complete"
        and state["verdict"] == "CONDITIONAL GO"
        and state["next_action"] == "none"
        and state["go_eligible"] is False
    )
    if state["artifact_binding"]["revision"] != binding.head_oid or not (
        nonterminal_no_go or terminal_conditional
    ):
        raise DeliveryError(
            "The NO-GO proof is not a current nonterminal or conditional state."
        )
    try:
        body = review_exchange.render_carrier(proof.visible_content, envelope, "state")
    except review_exchange.ProtocolError as error:
        raise DeliveryError(f"The NO-GO carrier is invalid: {error}") from error
    matching = [
        review
        for review in snapshot.reviews
        if review.id == proof.review_id
        and review.body == body
        and review.head_oid == binding.head_oid
        and review.viewer_did_author
        and not review.includes_created_edit
        and review.state in {"COMMENT", "COMMENTED"}
    ]
    if len(matching) != 1:
        raise DeliveryError("The exact current-head NO-GO carrier was not verified.")
    verified_state_sha256s = set(
        _verify_state_chain(envelope, snapshot, binding).verified_state_sha256s
    )
    for review in snapshot.reviews:
        if (
            review.id == proof.review_id
            or not review.viewer_did_author
            or review.head_oid != binding.head_oid
            or review_exchange.CARRIER_PREFIX not in review.body
        ):
            continue
        try:
            other = review_exchange.extract_carrier(review.body)
        except review_exchange.ProtocolError as error:
            raise DeliveryError(
                f"A current-head carrier is invalid: {error}"
            ) from error
        if (
            other["schema_id"] == review_exchange.STATE_SCHEMA_ID
            and other["state"]["target"] == state["target"]
            and other["state"]["exchange_id"] == state["exchange_id"]
            and other["state_sha256"] not in verified_state_sha256s
        ):
            raise DeliveryError("The current reviewer round has conflicting carriers.")


def deliver_no_go(
    forge: Forge, binding: ReviewBinding, proof: NoGoProof | None
) -> DeliveryResult:
    """Apply and verify the exclusive current-head NO-GO label state."""
    initial = _snapshot(forge, binding)
    if proof is None:
        raise DeliveryError("A verified current-head NO-GO state carrier is required.")
    _verify_no_go_snapshot(initial, binding, proof)
    _verify_live_requirements(forge, proof.requirements_binding)
    if NO_GO_LABEL in initial.labels and GO_LABEL not in initial.labels:
        return DeliveryResult(
            "already_delivered",
            (),
            NO_GO_LABEL,
            terminal_review_id=proof.review_id,
            observed_head_oid=initial.head_oid,
            observed_labels=tuple(sorted(initial.labels)),
        )
    last_snapshot = initial
    try:
        _call_write("implementation NO-GO label", forge.set_implementation_no_go)
        final = _snapshot(forge, binding)
        last_snapshot = final
        _verify_no_go_snapshot(final, binding, proof)
        _verify_live_requirements(forge, proof.requirements_binding)
        if NO_GO_LABEL not in final.labels or GO_LABEL in final.labels:
            raise DeliveryError(
                "The implementation NO-GO label was not verified exactly."
            )
    except DeliveryError as error:
        error.report = DeliveryResult(
            status="partial",
            resolved_thread_ids=(),
            label=NO_GO_LABEL,
            terminal_review_id=proof.review_id,
            observed_head_oid=last_snapshot.head_oid,
            observed_labels=tuple(sorted(last_snapshot.labels)),
            uncertain_operation="implementation NO-GO label",
            recovery_read_required=True,
            reason=str(error),
        )
        raise
    return DeliveryResult(
        "delivered",
        (),
        NO_GO_LABEL,
        terminal_review_id=proof.review_id,
        observed_head_oid=final.head_oid,
        observed_labels=tuple(sorted(final.labels)),
    )


def _gh(*arguments: str, input_text: str | None = None) -> str:
    command_options: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "check": False,
    }
    if input_text is not None:
        command_options["input"] = input_text
    result = run_command(("gh", *arguments), **command_options)
    if result.returncode != 0:
        message = result.stderr.strip() or "The GitHub CLI command failed."
        raise DeliveryError(message)
    return result.stdout


def _json_object(output: str, description: str) -> dict[str, Any]:
    try:
        value = json.loads(output)
    except json.JSONDecodeError as error:
        raise DeliveryError(f"GitHub returned invalid {description}.") from error
    if not isinstance(value, dict):
        raise DeliveryError(f"GitHub returned invalid {description}.")
    errors = value.get("errors")
    if errors:
        raise DeliveryError(f"GitHub returned errors for {description}: {errors}")
    return value


def _github_boolean(value: object, description: str) -> bool:
    if type(value) is not bool:
        raise DeliveryError(f"GitHub returned invalid {description}.")
    return value


def _github_has_next_page(value: object, description: str) -> bool:
    if not isinstance(value, dict):
        raise DeliveryError(f"GitHub returned invalid {description}.")
    page_info = value.get("pageInfo")
    if not isinstance(page_info, dict):
        raise DeliveryError(f"GitHub returned invalid {description}.")
    return _github_boolean(page_info.get("hasNextPage"), description)


class GitHubForge:
    """GitHub GraphQL adapter bound to one explicit repository and pull request."""

    def __init__(self, binding: ReviewBinding, host: str = GITHUB_HOST) -> None:
        self.binding = binding
        self.host = require_github_host(host, "target host")
        self.owner, self.name = require_github_repository(
            binding.repository, "target repository"
        ).split("/", maxsplit=1)

    def _graphql(self, query: str, **variables: object) -> dict[str, Any]:
        arguments = [
            "api",
            "graphql",
            "--hostname",
            self.host,
            "-f",
            f"query={query}",
        ]
        for key, value in variables.items():
            option = "-F" if isinstance(value, int) else "-f"
            arguments.extend((option, f"{key}={value}"))
        return _json_object(_gh(*arguments), "GraphQL response")

    def _repository_permission(self, author: str) -> str:
        data = _json_object(
            _gh(
                "api",
                "--hostname",
                self.host,
                f"repos/{self.owner}/{self.name}/collaborators/"
                f"{quote(author, safe='')}/permission",
            ),
            "repository permission response",
        )
        permission = data.get("permission")
        if not isinstance(permission, str):
            raise DeliveryError("GitHub returned invalid repository permission data.")
        return permission.upper()

    def collect_requirements_binding(
        self, requirement_issue_urls: tuple[str, ...]
    ) -> RequirementsBinding:
        target = collect_evidence.ExpectedReviewTarget(
            host=self.host,
            repository=self.binding.repository,
            number=self.binding.number,
            url=self.binding.url,
        )
        observed = collect_evidence.collect_requirements_binding(
            str(self.binding.number),
            target,
            (self.binding.base_oid, self.binding.head_oid),
            requirement_issue_urls,
        )
        return RequirementsBinding(
            reviewed_scope_sha256=observed.reviewed_scope_sha256,
            requirements_sha256=observed.requirements_sha256,
            requirement_issue_urls=observed.requirement_issue_urls,
        )

    def verify_requirements_binding(self, expected: RequirementsBinding) -> None:
        observed = self.collect_requirements_binding(expected.requirement_issue_urls)
        if observed != expected:
            raise DeliveryError(
                "The live pull-request requirements differ from the reviewed binding."
            )

    def snapshot(self) -> PullRequestSnapshot:
        query = """
        query($owner:String!, $name:String!, $number:Int!) {
          repository(owner:$owner, name:$name) { pullRequest(number:$number) {
            number url state isDraft baseRefOid headRefOid
            labels(first:100) { pageInfo { hasNextPage } nodes { name } }
            reviewThreads(first:100) { pageInfo { hasNextPage } nodes {
              id isResolved viewerCanReply viewerCanResolve path line originalLine diffSide
              comments(first:100) { pageInfo { hasNextPage } nodes {
                id body publishedAt lastEditedAt author { login } authorAssociation viewerDidAuthor
                pullRequestReview { id commit { oid } }
              } }
            } }
            reviews(first:100) { pageInfo { hasNextPage } nodes {
              id body state author { login } authorAssociation viewerDidAuthor includesCreatedEdit
              submittedAt lastEditedAt
              commit { oid }
            } }
          } }
        }
        """
        data = self._graphql(
            query, owner=self.owner, name=self.name, number=self.binding.number
        )
        pull_request = cast(dict[str, Any], data.get("data", {})).get("repository", {})
        pull_request = cast(dict[str, Any], pull_request).get("pullRequest")
        if not isinstance(pull_request, dict):
            raise DeliveryError(
                "GitHub returned no pull request for the retained target."
            )
        if (
            pull_request.get("number") != self.binding.number
            or pull_request.get("url") != self.binding.url
        ):
            raise DeliveryError(
                "GitHub returned a pull request that differs from the retained target."
            )
        is_draft = _github_boolean(
            pull_request.get("isDraft"), "pull-request draft state"
        )
        review_threads_data = pull_request.get("reviewThreads")
        if _github_has_next_page(review_threads_data, "review-thread pagination data"):
            raise DeliveryError("GitHub review-thread coverage is incomplete.")
        assert isinstance(review_threads_data, dict)
        raw_threads = review_threads_data.get("nodes")
        if not isinstance(raw_threads, list):
            raise DeliveryError("GitHub returned invalid review-thread data.")
        threads: list[ReviewThread] = []
        for raw_thread in raw_threads:
            if not isinstance(raw_thread, dict):
                raise DeliveryError("GitHub returned invalid review-thread data.")
            comments_data = raw_thread.get("comments")
            if _github_has_next_page(comments_data, "review-comment pagination data"):
                raise DeliveryError("GitHub review-comment coverage is incomplete.")
            assert isinstance(comments_data, dict)
            raw_comments = comments_data.get("nodes")
            if not isinstance(raw_comments, list):
                raise DeliveryError("GitHub returned invalid review-comment data.")
            comments: list[ReviewComment] = []
            thread_path = raw_thread.get("path")
            thread_line = raw_thread.get("line")
            thread_original_line = raw_thread.get("originalLine")
            thread_side = raw_thread.get("diffSide")
            thread_is_resolved = _github_boolean(
                raw_thread.get("isResolved"), "review-thread resolution state"
            )
            viewer_can_reply = _github_boolean(
                raw_thread.get("viewerCanReply"), "review-thread reply capability"
            )
            viewer_can_resolve = _github_boolean(
                raw_thread.get("viewerCanResolve"),
                "review-thread resolution capability",
            )
            if (
                not isinstance(thread_path, str)
                or (thread_line is not None and type(thread_line) is not int)
                or (
                    thread_original_line is not None
                    and type(thread_original_line) is not int
                )
                or not isinstance(thread_side, str)
            ):
                raise DeliveryError(
                    "GitHub returned invalid review-thread location data."
                )
            for raw_comment in raw_comments:
                if (
                    not isinstance(raw_comment, dict)
                    or not isinstance(raw_comment.get("id"), str)
                    or not isinstance(raw_comment.get("body"), str)
                ):
                    raise DeliveryError("GitHub returned invalid review-comment data.")
                published_at = raw_comment.get("publishedAt")
                last_edited_at = raw_comment.get("lastEditedAt")
                if (
                    published_at is not None
                    and not isinstance(published_at, str)
                    or last_edited_at is not None
                    and not isinstance(last_edited_at, str)
                ):
                    raise DeliveryError("GitHub returned invalid review-comment data.")
                author = raw_comment.get("author") or {}
                parent_review = raw_comment.get("pullRequestReview")
                viewer_did_author = _github_boolean(
                    raw_comment.get("viewerDidAuthor"),
                    "review-comment ownership state",
                )
                comments.append(
                    ReviewComment(
                        raw_comment["id"],
                        raw_comment["body"],
                        str(author.get("login", "")),
                        viewer_did_author,
                        (
                            cast(dict[str, Any], parent_review)
                            .get("commit", {})
                            .get("oid")
                            if isinstance(parent_review, dict)
                            else None
                        ),
                        str(raw_comment.get("authorAssociation", "NONE")),
                        (
                            cast(dict[str, Any], parent_review).get("id")
                            if isinstance(parent_review, dict)
                            else None
                        ),
                        thread_path,
                        thread_side,
                        thread_line,
                        original_line=thread_original_line,
                        published_at=published_at,
                        last_edited_at=last_edited_at,
                    )
                )
            thread_id = raw_thread.get("id")
            if not isinstance(thread_id, str):
                raise DeliveryError("GitHub returned invalid review-thread data.")
            threads.append(
                ReviewThread(
                    thread_id,
                    thread_is_resolved,
                    tuple(comments),
                    viewer_can_reply,
                    viewer_can_resolve,
                )
            )
        raw_reviews = pull_request.get("reviews")
        reviews: list[ReviewRecord] = []
        if _github_has_next_page(raw_reviews, "review-record pagination data"):
            raise DeliveryError("GitHub review-record coverage is incomplete.")
        assert isinstance(raw_reviews, dict)
        review_nodes = raw_reviews.get("nodes")
        if not isinstance(review_nodes, list):
            raise DeliveryError("GitHub returned invalid review-record data.")
        for raw_review in review_nodes:
            if not isinstance(raw_review, dict):
                raise DeliveryError("GitHub returned invalid review-record data.")
            commit = raw_review.get("commit") or {}
            author = raw_review.get("author") or {}
            submitted_at = raw_review.get("submittedAt")
            last_edited_at = raw_review.get("lastEditedAt")
            viewer_did_author = _github_boolean(
                raw_review.get("viewerDidAuthor"),
                "review-record ownership state",
            )
            includes_created_edit = _github_boolean(
                raw_review.get("includesCreatedEdit"),
                "review-record edit state",
            )
            if (
                not isinstance(raw_review.get("id"), str)
                or not isinstance(raw_review.get("body"), str)
                or not isinstance(raw_review.get("state"), str)
                or not isinstance(commit, dict)
                or not isinstance(commit.get("oid"), str)
                or (submitted_at is not None and not isinstance(submitted_at, str))
                or (last_edited_at is not None and not isinstance(last_edited_at, str))
            ):
                raise DeliveryError("GitHub returned invalid review-record data.")
            reviews.append(
                ReviewRecord(
                    id=raw_review["id"],
                    body=raw_review["body"],
                    head_oid=commit["oid"],
                    author=str(author.get("login", "")),
                    viewer_did_author=viewer_did_author,
                    includes_created_edit=includes_created_edit,
                    state=raw_review["state"],
                    author_association=str(raw_review.get("authorAssociation", "NONE")),
                    submitted_at=submitted_at,
                    last_edited_at=last_edited_at,
                )
            )
        authority_authors: set[str] = set()
        authority_records: list[ReviewComment | ReviewRecord] = [
            *(comment for thread in threads for comment in thread.comments),
            *reviews,
        ]
        for record in authority_records:
            try:
                review_exchange.parse_authority_record(record.body)
            except review_exchange.ProtocolError:
                continue
            if record.author:
                authority_authors.add(record.author)
        permissions = {
            author: self._repository_permission(author)
            for author in sorted(authority_authors)
        }
        threads = [
            replace(
                thread,
                comments=tuple(
                    replace(
                        comment,
                        author_permission=permissions.get(comment.author),
                    )
                    for comment in thread.comments
                ),
            )
            for thread in threads
        ]
        reviews = [
            replace(
                review,
                author_permission=permissions.get(review.author),
            )
            for review in reviews
        ]
        raw_labels = pull_request.get("labels")
        if _github_has_next_page(raw_labels, "label pagination data"):
            raise DeliveryError("GitHub label coverage is incomplete.")
        assert isinstance(raw_labels, dict)
        labels_data = raw_labels.get("nodes")
        if not isinstance(labels_data, list) or any(
            not isinstance(label, dict) or not isinstance(label.get("name"), str)
            for label in labels_data
        ):
            raise DeliveryError("GitHub returned invalid label data.")
        labels = frozenset(
            str(label["name"])
            for label in labels_data
            if isinstance(label, dict) and isinstance(label.get("name"), str)
        )
        return PullRequestSnapshot(
            repository=self.binding.repository,
            number=self.binding.number,
            url=self.binding.url,
            state=str(pull_request.get("state")),
            is_draft=is_draft,
            base_oid=require_commit_oid(pull_request.get("baseRefOid"), "baseRefOid"),
            head_oid=require_commit_oid(pull_request.get("headRefOid"), "headRefOid"),
            labels=labels,
            threads=tuple(threads),
            reviews=tuple(reviews),
        )

    def reply(self, thread_id: str, body: str) -> None:
        query = """
        mutation($threadId:ID!, $body:String!) {
          addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$threadId, body:$body}) {
            comment { id body }
          }
        }
        """
        self._graphql(query, threadId=thread_id, body=body)

    def resolve(self, thread_id: str) -> None:
        query = """
        mutation($threadId:ID!) {
          resolveReviewThread(input:{threadId:$threadId}) { thread { id isResolved } }
        }
        """
        self._graphql(query, threadId=thread_id)

    def set_implementation_go(self) -> None:
        snapshot = self.snapshot()
        _require_binding(snapshot, self.binding)
        arguments = [
            "issue",
            "edit",
            str(self.binding.number),
            "--repo",
            f"{self.host}/{self.binding.repository}",
            "--add-label",
            GO_LABEL,
        ]
        if NO_GO_LABEL in snapshot.labels:
            arguments.extend(("--remove-label", NO_GO_LABEL))
        _gh(*arguments)

    def set_implementation_no_go(self) -> None:
        snapshot = self.snapshot()
        _require_binding(snapshot, self.binding)
        arguments = [
            "issue",
            "edit",
            str(self.binding.number),
            "--repo",
            f"{self.host}/{self.binding.repository}",
            "--add-label",
            NO_GO_LABEL,
        ]
        if GO_LABEL in snapshot.labels:
            arguments.extend(("--remove-label", GO_LABEL))
        _gh(*arguments)

    def publish_terminal(
        self,
        body: str,
        head_oid: str,
        comments: tuple[TerminalInlineComment, ...],
    ) -> None:
        payload = {
            "commit_id": head_oid,
            "event": "COMMENT",
            "body": body,
            "comments": [_terminal_comment_dict(comment) for comment in comments],
        }
        _gh(
            "api",
            "--hostname",
            self.host,
            "--method",
            "POST",
            f"repos/{self.owner}/{self.name}/pulls/{self.binding.number}/reviews",
            "--input",
            "-",
            input_text=review_exchange.canonical_json(payload),
        )


def _manifest_value(value: object, description: str) -> str:
    if not isinstance(value, str) or not value:
        raise DeliveryError(f"The response manifest contains an invalid {description}.")
    return value


def _read_json_document(path: Path, description: str, *, canonical: bool) -> Any:
    try:
        with path.open("rb") as stream:
            content = stream.read(review_exchange.MAX_INPUT_BYTES + 1)
        document = review_exchange.parse_json_bytes(content)
    except (OSError, review_exchange.ProtocolError) as error:
        raise DeliveryError(f"The {description} cannot be read: {error}") from error
    if canonical:
        canonical_content = review_exchange.canonical_json(document).encode("utf-8")
        if content not in {canonical_content, canonical_content + b"\n"}:
            raise DeliveryError(f"The {description} is not canonical JSON.")
    return document


def load_response_manifest(path: Path, binding: ReviewBinding) -> ClosureManifest:
    """Load and validate one version-1 closure manifest."""
    document = _read_json_document(path, "response manifest", canonical=True)
    if isinstance(document, dict) and document.get("schema_id") is not None:
        v1 = _require_manifest_fields(
            document,
            frozenset(
                {
                    "schema_id",
                    "schema_version",
                    "binding",
                    "state",
                    "terminal_visible_content",
                    "entries",
                    "requirements_binding",
                    "comments",
                    "summary_finding_ids",
                }
            ),
            "top-level",
        )
        if (
            v1["schema_id"] != V1_MANIFEST_SCHEMA_ID
            or v1["schema_version"] != 1
            or type(v1["schema_version"]) is not int
        ):
            raise DeliveryError("The v1 closure-manifest schema is not supported.")
        raw_binding = _require_manifest_fields(
            v1["binding"], frozenset(_binding_dict(binding)), "binding"
        )
        if raw_binding != _binding_dict(binding):
            raise DeliveryError(
                "The response manifest is not bound to the requested pull request."
            )
        entries_value = v1["entries"]
        if not isinstance(entries_value, list):
            raise DeliveryError("The v1 closure manifest must contain an entry list.")
        comments_value = v1["comments"]
        if not isinstance(comments_value, list):
            raise DeliveryError(
                "The v1 closure manifest must contain a terminal comment list."
            )
        summary_value = v1["summary_finding_ids"]
        if not isinstance(summary_value, list):
            raise DeliveryError(
                "The v1 closure manifest must contain a summary finding list."
            )
        return ClosureManifest(
            state_envelope=review_exchange.verify_envelope(v1["state"]),
            terminal_visible_content=_require_manifest_string(
                v1["terminal_visible_content"], "terminal visible content"
            ),
            entries=tuple(_thread_closure(raw) for raw in entries_value),
            requirements_binding=_requirements_binding(v1["requirements_binding"]),
            comments=tuple(_terminal_inline_comment(raw) for raw in comments_value),
            summary_finding_ids=tuple(
                _require_manifest_string(item, "summary finding identifier")
                for item in summary_value
            ),
        )
    raise DeliveryError(
        "A new delivery requires a version-1 closure manifest. "
        "Use legacy input only for explicit read-only verification."
    )


def load_legacy_proof(path: Path, binding: ReviewBinding) -> tuple[ThreadResponse, ...]:
    """Load the historical three-field manifest for read-only verification."""
    document = _read_json_document(path, "legacy proof", canonical=False)
    if not isinstance(document, dict) or frozenset(document) != {
        "binding",
        "responses",
    }:
        raise DeliveryError("The legacy proof has invalid fields.")
    legacy_binding = document["binding"]
    if not isinstance(legacy_binding, dict) or legacy_binding != _binding_dict(binding):
        raise DeliveryError("The legacy proof is not bound to the pull request.")
    raw_responses = document["responses"]
    if not isinstance(raw_responses, list):
        raise DeliveryError("The legacy proof must contain a response list.")
    responses: list[ThreadResponse] = []
    for raw in raw_responses:
        if not isinstance(raw, dict) or frozenset(raw) != {
            "thread_id",
            "conversation_sha256",
            "body",
        }:
            raise DeliveryError("The legacy proof contains an invalid response.")
        responses.append(
            ThreadResponse(
                _manifest_value(raw.get("thread_id"), "thread identifier"),
                _manifest_value(raw.get("conversation_sha256"), "conversation digest"),
                _manifest_value(raw.get("body"), "response body"),
            )
        )
    return tuple(responses)


def load_no_go_proof(path: Path, binding: ReviewBinding) -> NoGoProof:
    """Load one strict version-1 proof for a published non-GO round."""
    document = _read_json_document(path, "NO-GO proof", canonical=True)
    proof = _require_manifest_fields(
        document,
        frozenset(
            {
                "schema_id",
                "schema_version",
                "binding",
                "review_id",
                "state",
                "visible_content",
                "requirements_binding",
            }
        ),
        "NO-GO proof",
    )
    if (
        proof["schema_id"] != NO_GO_PROOF_SCHEMA_ID
        or proof["schema_version"] != 1
        or type(proof["schema_version"]) is not int
    ):
        raise DeliveryError("The NO-GO proof schema is not supported.")
    raw_binding = _require_manifest_fields(
        proof["binding"], frozenset(_binding_dict(binding)), "NO-GO binding"
    )
    if raw_binding != _binding_dict(binding):
        raise DeliveryError("The NO-GO proof is not bound to this pull request.")
    return NoGoProof(
        state_envelope=_require_pr_envelope(
            proof["state"], binding, schema_id=review_exchange.STATE_SCHEMA_ID
        ),
        visible_content=_require_manifest_string(
            proof["visible_content"], "NO-GO visible content"
        ),
        review_id=_require_manifest_string(proof["review_id"], "NO-GO review ID"),
        requirements_binding=_requirements_binding(proof["requirements_binding"]),
    )


def prepare_response_manifest(
    forge: Forge,
    binding: ReviewBinding,
    *,
    schema_version: int = 1,
    requirement_issue_urls: Sequence[str] = (),
) -> dict[str, object]:
    """Return a read-only response template for every current open thread."""
    snapshot = _snapshot(forge, binding)
    if schema_version != 1:
        raise DeliveryError("The response-manifest schema version is not supported.")
    requirements_binding = _collect_live_requirements(
        forge,
        tuple(requirement_issue_urls),
    )
    entries: list[dict[str, object]] = []
    for thread in snapshot.threads:
        if thread.is_resolved:
            continue
        if not thread.comments:
            raise DeliveryError("An open review thread has no root finding.")
        root = thread.comments[0]
        marker = _finding_marker(root)
        finding_id = f"native:{root.id}" if marker is None else marker[1]
        try:
            origin_review_head_oid = require_commit_oid(
                root.review_head_oid, "origin review head"
            )
        except RuntimeError as error:
            raise DeliveryError(
                "An open review finding has no exact origin review head."
            ) from error
        entries.append(
            {
                "thread_id": thread.id,
                "finding_id": finding_id,
                "finding_exchange_id": None if marker is None else marker[0],
                "finding_state_sha256": None,
                "superseding_state_sha256": None,
                "origin_comment_id": root.id,
                "origin_review_head_oid": origin_review_head_oid,
                "conversation_sha256": conversation_sha256(thread),
                "finding_disposition": "required",
                "author_answer": None,
                "author_artifact_revision": None,
                "reviewer_disposition": None,
                "closure_evidence": [],
                "authority_receipt": None,
                "author_event_review_id": None,
            }
        )
    return {
        "schema_id": V1_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "binding": _binding_dict(binding),
        "state": None,
        "terminal_visible_content": "",
        "entries": entries,
        "requirements_binding": _requirements_binding_dict(requirements_binding),
        "comments": [],
        "summary_finding_ids": [],
    }


def _binding_from_args(args: argparse.Namespace) -> ReviewBinding:
    repository = require_github_repository(
        args.target_repository, "--target-repository"
    )
    number = pull_request_number(args.pull_request)
    if (
        args.pull_request.startswith("https://")
        and repository_from_pr_url(args.pull_request, number).casefold()
        != repository.casefold()
    ):
        raise DeliveryError(
            "The pull-request URL does not match the target repository."
        )
    url = require_canonical_pull_request_url(
        args.expected_pr_url, repository, number, "--expected-pr-url"
    )
    if args.pull_request.startswith("https://") and args.pull_request != url:
        raise DeliveryError("The pull-request URL does not match the expected URL.")
    return ReviewBinding(
        repository=repository,
        number=number,
        url=url,
        base_oid=require_commit_oid(args.base_oid, "--expected-base-oid"),
        head_oid=require_commit_oid(args.head_oid, "--expected-head-oid"),
    )


def _delivery_result_document(result: DeliveryResult) -> dict[str, object]:
    """Return the stable machine-readable delivery result."""
    return {
        "status": result.status,
        "label": result.label,
        "terminal_review_id": result.terminal_review_id,
        "responded_thread_ids": list(result.responded_thread_ids),
        "resolved_thread_ids": list(result.resolved_thread_ids),
        "pending_thread_ids": list(result.pending_thread_ids),
        "observed_head_oid": result.observed_head_oid,
        "observed_labels": list(result.observed_labels),
        "uncertain_operation": result.uncertain_operation,
        "recovery_read_required": result.recovery_read_required,
        "reason": result.reason,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("--target-repository", required=True)
    parser.add_argument("--target-host", default=GITHUB_HOST)
    parser.add_argument("pull_request")
    parser.add_argument("--expected-pr-url", required=True)
    parser.add_argument(
        "--base-oid", "--expected-base-oid", dest="base_oid", required=True
    )
    parser.add_argument(
        "--head-oid", "--expected-head-oid", dest="head_oid", required=True
    )
    delivery_input = parser.add_mutually_exclusive_group(required=True)
    delivery_input.add_argument(
        "--response-manifest",
        "--manifest",
        "--responses-file",
        dest="response_manifest",
        type=Path,
    )
    delivery_input.add_argument("--prepare-manifest", action="store_true")
    delivery_input.add_argument("--verify-legacy-go", type=Path)
    delivery_input.add_argument("--deliver-no-go", action="store_true")
    parser.add_argument("--state-carrier-file", type=Path)
    parser.add_argument(
        "--requirement-issue",
        action="append",
        default=[],
        metavar="ISSUE_URL",
    )
    parser.add_argument("--schema-version", type=int, choices=(1,), default=1)
    args = parser.parse_args(argv)
    try:
        binding = _binding_from_args(args)
        forge = GitHubForge(binding, args.target_host)
        if args.prepare_manifest:
            if args.state_carrier_file is not None:
                raise DeliveryError(
                    "A state-carrier file is valid only for NO-GO delivery."
                )
            print(
                review_exchange.canonical_json(
                    prepare_response_manifest(
                        forge,
                        binding,
                        schema_version=args.schema_version,
                        requirement_issue_urls=args.requirement_issue,
                    )
                )
            )
            return 0
        if args.deliver_no_go:
            if args.requirement_issue:
                raise DeliveryError(
                    "Requirement issue inputs are valid only during manifest preparation."
                )
            if args.state_carrier_file is None:
                raise DeliveryError("NO-GO delivery requires --state-carrier-file.")
            result = deliver_no_go(
                forge, binding, load_no_go_proof(args.state_carrier_file, binding)
            )
        elif args.verify_legacy_go is not None:
            if args.requirement_issue:
                raise DeliveryError(
                    "Requirement issue inputs are valid only during manifest preparation."
                )
            if args.state_carrier_file is not None:
                raise DeliveryError(
                    "A state-carrier file is valid only for NO-GO delivery."
                )
            result = verify_legacy_go(
                forge,
                binding,
                load_legacy_proof(args.verify_legacy_go, binding),
            )
        else:
            if args.requirement_issue:
                raise DeliveryError(
                    "Requirement issue inputs are valid only during manifest preparation."
                )
            if args.state_carrier_file is not None:
                raise DeliveryError(
                    "A state-carrier file is valid only for NO-GO delivery."
                )
            if args.response_manifest is None:
                raise DeliveryError("The response manifest path is missing.")
            manifest = load_response_manifest(args.response_manifest, binding)
            result = deliver_go_v1(forge, binding, manifest)
    except (DeliveryError, RuntimeError, TypeError, ValueError) as error:
        if isinstance(error, DeliveryError) and error.report is not None:
            print(
                json.dumps(
                    {
                        "error": str(error),
                        "recovery": _delivery_result_document(error.report),
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
        else:
            print(error, file=sys.stderr)
        return 1
    print(json.dumps(_delivery_result_document(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
