"""Behavior tests for pull-request GO delivery."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "pr-review" / "scripts" / "deliver_go.py"


def load_module() -> ModuleType:
    """Load the executable helper as a test module."""
    name = f"test_pr_review_go_delivery_{id(SCRIPT)}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("The GO-delivery helper cannot be loaded.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeForge:
    """Record delivery operations and expose mutable forge state."""

    def __init__(self, module: ModuleType, *, threads: tuple[Any, ...]) -> None:
        self.module = module
        self.head_oid = "b" * 40
        self.labels = {"state:implementation-no-go", "enhancement"}
        self.threads = {thread.id: thread for thread in threads}
        self.reviews: list[Any] = []
        self.events: list[str] = []
        self.fail_reply = False
        self.edit_reply_after_post = False
        self.reply_published_at: str | None = "2026-01-01T00:02:00Z"
        self.fail_resolve = False
        self.drift_head_after_resolve = False
        self.add_late_thread_after_resolve = False
        self.keep_no_go_after_label = False
        self.keep_go_after_no_go_label = False
        self.fail_label = False
        self.race_comment_after_reply = False
        self.drift_head_on_label = False
        self.fail_terminal = False
        self.edit_terminal = False
        self.duplicate_terminal = False
        self.comment_after_label = False
        self.remove_reviews_after_no_go_label = False
        self.terminal_thread_mutation: str | None = None
        self.published_terminal_comments: tuple[Any, ...] = ()
        self.requirements_failure: str | None = None

    def snapshot(self) -> Any:
        self.events.append("read")
        return self.module.PullRequestSnapshot(
            repository="owner/repository",
            number=7,
            url="https://github.com/owner/repository/pull/7",
            state="OPEN",
            is_draft=False,
            base_oid="a" * 40,
            head_oid=self.head_oid,
            labels=frozenset(self.labels),
            threads=tuple(self.threads.values()),
            reviews=tuple(self.reviews),
        )

    def collect_requirements_binding(
        self, requirement_issue_urls: tuple[str, ...]
    ) -> Any:
        self.events.append("requirements:collect")
        if self.requirements_failure is not None:
            raise RuntimeError(self.requirements_failure)
        return self.module.RequirementsBinding(
            reviewed_scope_sha256="3" * 64,
            requirements_sha256="c" * 64,
            requirement_issue_urls=requirement_issue_urls,
        )

    def verify_requirements_binding(self, expected: Any) -> None:
        self.events.append("requirements:verify")
        if self.requirements_failure is not None:
            raise RuntimeError(self.requirements_failure)

    def reply(self, thread_id: str, body: str) -> None:
        self.events.append(f"reply:{thread_id}")
        if self.fail_reply:
            raise RuntimeError("reply failed")
        thread = self.threads[thread_id]
        comment = self.module.ReviewComment(
            id="reply-1",
            body=body,
            author="reviewer",
            published_at=self.reply_published_at,
            last_edited_at=(
                "2026-01-01T00:03:00Z" if self.edit_reply_after_post else None
            ),
        )
        self.threads[thread_id] = self.module.ReviewThread(
            id=thread.id,
            is_resolved=thread.is_resolved,
            comments=(*thread.comments, comment),
        )
        if self.race_comment_after_reply:
            updated = self.threads[thread_id]
            race = self.module.ReviewComment(
                id="raced-comment", body="new concern", author="other-reviewer"
            )
            self.threads[thread_id] = self.module.ReviewThread(
                id=updated.id,
                is_resolved=updated.is_resolved,
                comments=(*updated.comments, race),
            )

    def resolve(self, thread_id: str) -> None:
        self.events.append(f"resolve:{thread_id}")
        if self.fail_resolve:
            raise RuntimeError("resolve failed")
        thread = self.threads[thread_id]
        self.threads[thread_id] = self.module.ReviewThread(
            id=thread.id,
            is_resolved=True,
            comments=thread.comments,
        )
        if self.drift_head_after_resolve:
            self.head_oid = "c" * 40
        if self.add_late_thread_after_resolve:
            self.threads["late"] = self.module.ReviewThread(
                id="late",
                is_resolved=False,
                comments=(
                    self.module.ReviewComment(
                        id="late-comment", body="late finding", author="reviewer"
                    ),
                ),
            )

    def set_implementation_go(self) -> None:
        self.events.append("labels")
        if self.fail_label:
            raise RuntimeError("label delivery failed")
        if self.comment_after_label:
            for thread_id, thread in tuple(self.threads.items()):
                if thread.is_resolved:
                    self.threads[thread_id] = replace(
                        thread,
                        comments=(
                            *thread.comments,
                            self.module.ReviewComment(
                                id="late-resolved-comment",
                                body="A late comment changed the closed conversation.",
                                author="other-reviewer",
                                viewer_did_author=False,
                            ),
                        ),
                    )
        if self.drift_head_on_label:
            self.head_oid = "c" * 40
        self.labels.add("state:implementation-go")
        if not self.keep_no_go_after_label:
            self.labels.discard("state:implementation-no-go")

    def set_implementation_no_go(self) -> None:
        self.events.append("labels:no-go")
        if self.fail_label:
            raise RuntimeError("NO-GO label delivery failed")
        self.labels.add("state:implementation-no-go")
        if not self.keep_go_after_no_go_label:
            self.labels.discard("state:implementation-go")
        if self.remove_reviews_after_no_go_label:
            self.reviews.clear()

    def publish_terminal(
        self, body: str, head_oid: str, comments: tuple[Any, ...]
    ) -> None:
        self.events.append("terminal")
        if self.fail_terminal:
            raise RuntimeError("terminal publication failed")
        published = body + ("\nedited" if self.edit_terminal else "")
        review_id = f"review-{len(self.reviews) + 1}"
        review = self.module.ReviewRecord(
            id=review_id,
            body=published,
            head_oid=head_oid,
            author="reviewer",
            viewer_did_author=True,
            includes_created_edit=self.edit_terminal,
            state="COMMENTED",
            submitted_at=f"2026-01-01T00:01:{len(self.reviews) + 1:02d}Z",
        )
        self.reviews.append(review)
        self.published_terminal_comments = comments
        for index, comment in enumerate(comments, start=1):
            root = self.module.ReviewComment(
                id=f"terminal-comment-{index}",
                body=comment.body,
                author="reviewer",
                viewer_did_author=True,
                review_head_oid=head_oid,
                review_id=review_id,
                path=comment.path,
                side=comment.side,
                line=comment.line,
                original_line=comment.line,
            )
            self.threads[f"terminal-thread-{index}"] = self.module.ReviewThread(
                id=f"terminal-thread-{index}",
                is_resolved=False,
                comments=(root,),
            )
        if comments and self.terminal_thread_mutation is not None:
            thread = self.threads["terminal-thread-1"]
            root = thread.comments[0]
            mutation = self.terminal_thread_mutation
            if mutation == "missing":
                del self.threads[thread.id]
            elif mutation == "second_comment":
                self.threads[thread.id] = replace(
                    thread,
                    comments=(
                        root,
                        self.module.ReviewComment(
                            id="unverified-comment",
                            body="Another comment.",
                            author="other-reviewer",
                            viewer_did_author=False,
                        ),
                    ),
                )
            elif mutation == "three_comments":
                self.threads[thread.id] = replace(
                    thread,
                    comments=(
                        root,
                        self.module.ReviewComment(
                            id="second-comment", body="Second.", author="reviewer"
                        ),
                        self.module.ReviewComment(
                            id="third-comment", body="Third.", author="reviewer"
                        ),
                    ),
                )
            else:
                replacements: dict[str, Any] = {
                    "foreign": {"viewer_did_author": False},
                    "wrong_review": {"review_id": "other-review"},
                    "wrong_head": {"review_head_oid": "c" * 40},
                    "wrong_body": {"body": f"{root.body}\nchanged"},
                    "wrong_path": {"path": "src/other.py"},
                    "wrong_side": {"side": "LEFT"},
                    "wrong_line": {"line": 13},
                    "wrong_original_line": {"original_line": 13},
                    "edited_root": {"last_edited_at": "2026-01-01T00:02:00Z"},
                }
                self.threads[thread.id] = replace(
                    thread,
                    comments=(replace(root, **replacements[mutation]),),
                )
        if self.duplicate_terminal:
            self.reviews.append(
                self.module.ReviewRecord(
                    id="review-duplicate",
                    body=published,
                    head_oid=head_oid,
                    author="reviewer",
                    viewer_did_author=True,
                    includes_created_edit=False,
                    state="COMMENTED",
                    submitted_at="2026-01-01T00:02:00Z",
                )
            )


class PrReviewGoDeliveryTests(unittest.TestCase):
    delivery: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.delivery = load_module()

    def setUp(self) -> None:
        self.carrier_history: dict[str, tuple[Any, ...]] = {}
        self.review_sequence = 0

    def binding(self, head_oid: str | None = None) -> Any:
        return self.delivery.ReviewBinding(
            repository="owner/repository",
            number=7,
            url="https://github.com/owner/repository/pull/7",
            base_oid="a" * 40,
            head_oid=head_oid or "b" * 40,
        )

    def requirements_binding(
        self, envelope: dict[str, Any], *requirement_issue_urls: str
    ) -> Any:
        state = envelope["state"]
        return self.delivery.RequirementsBinding(
            reviewed_scope_sha256=state["artifact_binding"]["sha256"],
            requirements_sha256=state["requirements_sha256"],
            requirement_issue_urls=tuple(requirement_issue_urls),
        )

    def thread(self) -> Any:
        return self.delivery.ReviewThread(
            id="thread-1",
            is_resolved=False,
            comments=(
                self.delivery.ReviewComment(
                    id="comment-1", body="original finding", author="reviewer"
                ),
            ),
        )

    def github_snapshot_json(self) -> str:
        return json.dumps(
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "baseRefOid": "a" * 40,
                            "headRefOid": "b" * 40,
                            "isDraft": False,
                            "labels": {
                                "nodes": [
                                    {"name": "state:implementation-no-go"},
                                    {"name": "enhancement"},
                                ],
                                "pageInfo": {"hasNextPage": False},
                            },
                            "number": 7,
                            "reviewThreads": {
                                "nodes": [
                                    {
                                        "comments": {
                                            "nodes": [
                                                {
                                                    "author": {"login": "reviewer"},
                                                    "authorAssociation": "MEMBER",
                                                    "body": "finding",
                                                    "id": "comment-1",
                                                    "fullDatabaseId": "3991324281",
                                                    "lastEditedAt": None,
                                                    "publishedAt": "2026-01-01T00:00:01Z",
                                                    "pullRequestReview": {
                                                        "id": "review-1",
                                                        "commit": {"oid": "a" * 40},
                                                    },
                                                    "viewerDidAuthor": True,
                                                }
                                            ],
                                            "pageInfo": {"hasNextPage": False},
                                        },
                                        "id": "thread-1",
                                        "isResolved": False,
                                        "path": "src/example.py",
                                        "line": None,
                                        "originalLine": 7,
                                        "diffSide": "RIGHT",
                                        "viewerCanReply": True,
                                        "viewerCanResolve": True,
                                    }
                                ],
                                "pageInfo": {"hasNextPage": False},
                            },
                            "reviews": {
                                "nodes": [
                                    {
                                        "author": {"login": "reviewer"},
                                        "authorAssociation": "MEMBER",
                                        "body": "Round review.",
                                        "commit": {"oid": "a" * 40},
                                        "id": "review-1",
                                        "includesCreatedEdit": False,
                                        "state": "COMMENTED",
                                        "submittedAt": "2026-01-01T00:00:01Z",
                                        "lastEditedAt": None,
                                        "viewerDidAuthor": True,
                                    }
                                ],
                                "pageInfo": {"hasNextPage": False},
                            },
                            "state": "OPEN",
                            "url": "https://github.com/owner/repository/pull/7",
                        }
                    }
                }
            }
        )

    def plan(self, thread: Any) -> Any:
        return self.delivery.ThreadResponse(
            thread_id=thread.id,
            conversation_sha256=self.delivery.conversation_sha256(thread),
            body="Verified on the reviewed head: the issue is fixed by the new guard.",
        )

    def owned_thread(
        self,
        *,
        contest: bool = False,
        can_reply: bool = True,
        can_resolve: bool = True,
        owned: bool = True,
        review_head_oid: str = "a" * 40,
    ) -> Any:
        comments = [
            self.delivery.ReviewComment(
                id="comment-1",
                body=(
                    "Finding.\n\n"
                    "<!-- HomericIntelligence:review-finding:v1 "
                    "exchange=exchange-7 id=F-001 -->"
                ),
                author="reviewer",
                viewer_did_author=owned,
                review_head_oid=review_head_oid,
                review_id="initial-review-1",
                path="src/example.py",
                side="RIGHT",
                line=7,
                original_line=7,
            )
        ]
        if contest:
            comments.append(
                self.delivery.ReviewComment(
                    id="contest-1",
                    body="Contest with counter-evidence.",
                    author="reviewer",
                    viewer_did_author=True,
                    review_head_oid="b" * 40,
                )
            )
        return self.delivery.ReviewThread(
            id="thread-1",
            is_resolved=False,
            comments=tuple(comments),
            viewer_can_reply=can_reply,
            viewer_can_resolve=can_resolve,
        )

    def closure(
        self,
        thread: Any,
        *,
        author_kind: str = "fix",
        reviewer_disposition: str = "resolved",
        finding_disposition: str = "required",
    ) -> Any:
        root = thread.comments[0]
        marker = self.delivery._finding_marker(root)
        finding_id = f"native:{root.id}" if marker is None else marker[1]
        return self.delivery.ThreadClosure(
            thread_id=thread.id,
            finding_id=finding_id,
            finding_exchange_id=(marker[0] if marker is not None else "exchange-7"),
            finding_state_sha256="0" * 64,
            superseding_state_sha256=None,
            origin_comment_id=root.id,
            origin_review_head_oid=root.review_head_oid,
            conversation_sha256=self.delivery.conversation_sha256(thread),
            finding_disposition=finding_disposition,
            author_answer=author_kind,
            author_artifact_revision="b" * 40,
            reviewer_disposition=reviewer_disposition,
            closure_evidence=("The terminal assessment checked the artifact.",),
            authority_receipt=None,
            author_event_review_id="author-event-1",
        )

    def carrier_record(
        self,
        identifier: str,
        envelope: dict[str, Any],
        visible: str,
        *,
        association: str = "NONE",
    ) -> Any:
        kind = (
            "state"
            if envelope["schema_id"] == self.delivery.review_exchange.STATE_SCHEMA_ID
            else "author-event"
        )
        self.review_sequence += 1
        record = self.delivery.ReviewRecord(
            id=identifier,
            body=self.delivery.review_exchange.render_carrier(visible, envelope, kind),
            head_oid=envelope["state"]["artifact_binding"]["revision"],
            author="reviewer",
            viewer_did_author=True,
            includes_created_edit=False,
            state="COMMENTED",
            author_association=association,
            submitted_at=f"2026-01-01T00:00:{self.review_sequence:02d}Z",
        )
        return record

    def carrier_threads(
        self, envelope: dict[str, Any], review_id: str
    ) -> tuple[Any, ...]:
        state = envelope["state"]
        threads = []
        for finding in state["findings"]:
            anchor = self.delivery._finding_anchor(finding["location"])
            if finding["id"].startswith("native:") or anchor is None:
                continue
            threads.append(
                self.delivery.ReviewThread(
                    id=f"{review_id}-{finding['id']}",
                    is_resolved=False,
                    comments=(
                        self.delivery.ReviewComment(
                            id=f"{review_id}-{finding['id']}-root",
                            body=(
                                f"{finding['impact']}\n\n"
                                "<!-- HomericIntelligence:review-finding:v1 "
                                f"exchange={state['exchange_id']} "
                                f"id={finding['id']} -->"
                            ),
                            author="reviewer",
                            viewer_did_author=True,
                            review_head_oid=state["artifact_binding"]["revision"],
                            review_id=review_id,
                            path=anchor[0],
                            side="RIGHT",
                            line=anchor[1],
                            original_line=anchor[1],
                        ),
                    ),
                    viewer_can_reply=True,
                    viewer_can_resolve=True,
                )
            )
        return tuple(threads)

    def completed_exchange(
        self,
        manifest: Any,
        *,
        requirements_sha256: str,
        head_oid: str = "a" * 40,
        go_eligible: bool = True,
    ) -> tuple[dict[str, Any], str]:
        exchange = self.delivery.review_exchange
        visible = "The previous head completed its review."
        envelope = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-previous-head",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": manifest.state_envelope["state"]["target"],
                    "requirements_sha256": requirements_sha256,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": head_oid,
                        "sha256": "7" * 64,
                        "visible_content_sha256": exchange.sha256_text(visible),
                    },
                    "scope": ["path:src/old.py"],
                    "coverage_complete": True,
                    "go_eligible": go_eligible,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        return envelope, visible

    def archived_suggestion_exchange(self, manifest: Any) -> tuple[dict[str, Any], str]:
        exchange = self.delivery.review_exchange
        visible = "The archived review has one nonblocking finding."
        envelope = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-archived-suggestion",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": manifest.state_envelope["state"]["target"],
                    "requirements_sha256": manifest.state_envelope["state"][
                        "requirements_sha256"
                    ],
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "a" * 40,
                        "sha256": "7" * 64,
                        "visible_content_sha256": exchange.sha256_text(visible),
                    },
                    "scope": ["path:src/old.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [
                        {
                            "id": "F-001",
                            "category": None,
                            "severity": "minor",
                            "disposition": "suggestion",
                            "material_architecture": False,
                            "location": "src/old.py:9",
                            "impact": "The old name can be clearer.",
                            "evidence": ["The old name hides its purpose."],
                            "closure_condition": None,
                            "introduction": "initial",
                        }
                    ],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        return envelope, visible

    def add_history(self, forge: FakeForge, manifest: Any) -> None:
        forge.reviews.extend(
            self.carrier_history[manifest.state_envelope["state_sha256"]]
        )

    def v1_manifest(
        self,
        thread: Any,
        closure: Any | None = None,
        *,
        include_entry: bool = True,
        state_author_kind: str | None = None,
        state_author_revision: str | None = None,
        state_reviewer_evidence: str | None = None,
    ) -> Any:
        closure = closure or self.closure(thread)
        author_kind = state_author_kind or closure.author_answer
        author_revision = state_author_revision or "b" * 40
        author_sha256 = (
            "1" * 64 if closure.reviewer_disposition == "accepted_risk" else "3" * 64
        )
        reviewer_evidence = (
            state_reviewer_evidence or "The terminal assessment checked the artifact."
        )
        entries = (closure,) if include_entry else ()
        visible = self.delivery.terminal_visible_content(self.binding(), entries)
        exchange = self.delivery.review_exchange
        initial_visible = "Round 1 review."
        initial = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": {
                        "provider": "github",
                        "repository": "owner/repository",
                        "number": 7,
                        "url": "https://github.com/owner/repository/pull/7",
                    },
                    "requirements_sha256": "c" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": thread.comments[0].review_head_oid,
                        "sha256": "1" * 64,
                        "visible_content_sha256": exchange.sha256_text(initial_visible),
                    },
                    "scope": ["path:src/example.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [
                        {
                            "id": closure.finding_id,
                            "category": None,
                            "severity": "major",
                            "disposition": "required",
                            "material_architecture": False,
                            "location": "src/example.py:7",
                            "impact": "The result can be incorrect.",
                            "evidence": ["The failing case returns 0."],
                            "closure_condition": "The failing case returns 1.",
                            "introduction": "initial",
                        }
                    ],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        author_visible = "Author response."
        author_result = exchange.reduce_request(
            {
                "previous": initial,
                "event": {
                    "event_type": "author_response",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": initial["state_sha256"],
                    "artifact_binding": {
                        "revision": author_revision,
                        "sha256": author_sha256,
                        "visible_content_sha256": exchange.sha256_text(author_visible),
                    },
                    "scope": ["path:src/example.py"],
                    "scope_change_reason": None,
                    "responses": [
                        {
                            "finding_id": closure.finding_id,
                            "kind": author_kind,
                            "evidence": ["The author supplied bound closure evidence."],
                            "tradeoff": (
                                "The author accepts a bounded tradeoff."
                                if author_kind
                                in {"fix_with_tradeoff", "risk_acceptance"}
                                else None
                            ),
                        }
                    ],
                },
            }
        )
        author = author_result["envelope"]
        if closure.reviewer_disposition == "accepted_risk":
            terminal = exchange.reduce_request(
                {
                    "previous": author,
                    "event": {
                        "event_type": "human_decision",
                        "exchange_id": "exchange-7",
                        "prior_state_sha256": author["state_sha256"],
                        "artifact_binding": {
                            **author["state"]["artifact_binding"],
                            "visible_content_sha256": exchange.sha256_text(visible),
                        },
                        "authority_receipt": closure.authority_receipt,
                        "decisions": [
                            {
                                "finding_id": closure.finding_id,
                                "kind": "accept_risk",
                                "closure_condition": None,
                            }
                        ],
                    },
                }
            )["envelope"]
        else:
            reviewer_action = (
                "accept"
                if closure.reviewer_disposition == "withdrawn"
                and author_kind == "contest"
                else (
                    "withdraw"
                    if closure.reviewer_disposition == "withdrawn"
                    else "resolve"
                )
            )
            terminal = exchange.reduce_request(
                {
                    "previous": author,
                    "event": {
                        "event_type": "reviewer_assessment",
                        "exchange_id": "exchange-7",
                        "prior_state_sha256": author["state_sha256"],
                        "round": 2,
                        "artifact_binding": {
                            **author["state"]["artifact_binding"],
                            "visible_content_sha256": exchange.sha256_text(visible),
                        },
                        "scope": ["path:src/example.py"],
                        "coverage_complete": True,
                        "go_eligible": True,
                        "responses": [
                            {
                                "finding_id": closure.finding_id,
                                "kind": reviewer_action,
                                "evidence": [reviewer_evidence],
                                "closure_condition": None,
                            }
                        ],
                        "new_findings": [],
                        "stop_reason": None,
                    },
                }
            )["envelope"]
        closure = replace(
            closure,
            finding_exchange_id=terminal["state"]["exchange_id"],
            finding_state_sha256=terminal["state_sha256"],
            superseding_state_sha256=None,
        )
        entries = (closure,) if include_entry else ()
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=visible,
            entries=entries,
            requirements_binding=self.requirements_binding(terminal),
        )
        self.carrier_history[terminal["state_sha256"]] = (
            self.carrier_record("initial-review-1", initial, initial_visible),
            self.carrier_record(
                "author-event-1", author_result["author_event"], author_visible
            ),
        )
        return manifest

    def terminal_inline_manifest(self) -> tuple[Any, Any]:
        exchange = self.delivery.review_exchange
        visible = self.delivery.terminal_visible_content(self.binding(), ())
        terminal = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-inline",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": {
                        "provider": "github",
                        "repository": "owner/repository",
                        "number": 7,
                        "url": "https://github.com/owner/repository/pull/7",
                    },
                    "requirements_sha256": "7" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "8" * 64,
                        "visible_content_sha256": exchange.sha256_text(visible),
                    },
                    "scope": ["path:src/follow.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [
                        {
                            "id": "F-001",
                            "category": None,
                            "severity": "minor",
                            "disposition": "suggestion",
                            "material_architecture": False,
                            "location": "src/follow.py:12",
                            "impact": "The name can be clearer.",
                            "evidence": ["The current name hides its purpose."],
                            "closure_condition": None,
                            "introduction": "initial",
                        }
                    ],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        inline = self.delivery.TerminalInlineComment(
            path="src/follow.py",
            side="RIGHT",
            line=12,
            body=(
                "The name can be clearer.\n\n"
                "<!-- HomericIntelligence:review-finding:v1 "
                "exchange=exchange-inline id=F-001 -->"
            ),
        )
        return (
            self.delivery.ClosureManifest(
                state_envelope=terminal,
                terminal_visible_content=visible,
                entries=(),
                requirements_binding=self.requirements_binding(terminal),
                comments=(inline,),
            ),
            inline,
        )

    def chained_author_manifest(self) -> tuple[FakeForge, Any, Any]:
        """Build a terminal review after two bound author revisions."""
        exchange = self.delivery.review_exchange
        thread = self.owned_thread()
        seed = self.v1_manifest(thread)
        initial_record, first_author_record = self.carrier_history[
            seed.state_envelope["state_sha256"]
        ]
        initial = exchange.extract_carrier(initial_record.body)
        first_author_event = exchange.extract_carrier(first_author_record.body)
        first_author = exchange.reduce_request(
            {
                "previous": initial,
                "event": self.delivery._author_event_input(first_author_event),
            }
        )["envelope"]
        second_author_visible = "The author rebased and repeated the bound answer."
        second_author = exchange.reduce_request(
            {
                "previous": first_author,
                "event": {
                    "event_type": "author_response",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": first_author["state_sha256"],
                    "artifact_binding": {
                        "revision": "c" * 40,
                        "sha256": "4" * 64,
                        "visible_content_sha256": exchange.sha256_text(
                            second_author_visible
                        ),
                    },
                    "scope": ["path:src/example.py"],
                    "scope_change_reason": None,
                    "responses": [
                        {
                            "finding_id": "F-001",
                            "kind": "fix",
                            "evidence": ["The rebased correction passes."],
                            "tradeoff": None,
                        }
                    ],
                },
            }
        )
        closure_seed = replace(
            self.closure(thread),
            author_artifact_revision="c" * 40,
            author_event_review_id="author-event-2",
        )
        binding = self.binding("c" * 40)
        terminal_visible = self.delivery.terminal_visible_content(
            binding, (closure_seed,)
        )
        terminal = exchange.reduce_request(
            {
                "previous": second_author["envelope"],
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": second_author["envelope"]["state_sha256"],
                    "round": 2,
                    "artifact_binding": {
                        **second_author["envelope"]["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(
                            terminal_visible
                        ),
                    },
                    "scope": ["path:src/example.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [
                        {
                            "finding_id": "F-001",
                            "kind": "resolve",
                            "evidence": [
                                "The terminal assessment checked the artifact."
                            ],
                            "closure_condition": None,
                        }
                    ],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        closure = replace(
            closure_seed,
            finding_state_sha256=terminal["state_sha256"],
        )
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=terminal_visible,
            entries=(closure,),
            requirements_binding=self.requirements_binding(terminal),
        )
        second_author_record = self.carrier_record(
            "author-event-2",
            second_author["author_event"],
            second_author_visible,
        )
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.head_oid = "c" * 40
        forge.reviews.extend(
            (initial_record, first_author_record, second_author_record)
        )
        return forge, binding, manifest

    def no_go_proof(
        self, *, finding_id: str = "F-001", location: str = "src/no_go.py:1"
    ) -> tuple[Any, Any]:
        exchange = self.delivery.review_exchange
        visible = "Round 1 has one required finding."
        envelope = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-no-go",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": {
                        "provider": "github",
                        "repository": "owner/repository",
                        "number": 7,
                        "url": "https://github.com/owner/repository/pull/7",
                    },
                    "requirements_sha256": "d" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "5" * 64,
                        "visible_content_sha256": exchange.sha256_text(visible),
                    },
                    "scope": ["path:src/no_go.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [
                        {
                            "id": finding_id,
                            "category": None,
                            "severity": "major",
                            "disposition": "required",
                            "material_architecture": False,
                            "location": location,
                            "impact": "The result is incorrect.",
                            "evidence": ["The test fails."],
                            "closure_condition": "The test passes.",
                            "introduction": "initial",
                        }
                    ],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        proof = self.delivery.NoGoProof(
            state_envelope=envelope,
            visible_content=visible,
            review_id="no-go-review-1",
            requirements_binding=self.requirements_binding(envelope),
        )
        return proof, self.carrier_record(proof.review_id, envelope, visible)

    def conditional_go_proof(self) -> tuple[Any, Any]:
        exchange = self.delivery.review_exchange
        visible = "The review is clean, but CI evidence is not available."
        envelope = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-conditional",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": {
                        "provider": "github",
                        "repository": "owner/repository",
                        "number": 7,
                        "url": "https://github.com/owner/repository/pull/7",
                    },
                    "requirements_sha256": "d" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "5" * 64,
                        "visible_content_sha256": exchange.sha256_text(visible),
                    },
                    "scope": ["path:src/conditional.py"],
                    "coverage_complete": True,
                    "go_eligible": False,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        proof = self.delivery.NoGoProof(
            state_envelope=envelope,
            visible_content=visible,
            review_id="conditional-review-1",
            requirements_binding=self.requirements_binding(envelope),
        )
        return proof, self.carrier_record(proof.review_id, envelope, visible)

    def authority_body(
        self,
        *,
        action: str,
        exchange_id: str,
        requirements_sha256: str,
        supersedes_state_sha256: str | None,
        decisions: list[dict[str, Any]],
        prior_state_sha256: str | None = None,
    ) -> str:
        body = self.delivery.review_exchange.canonical_json(
            {
                "schema_id": self.delivery.review_exchange.AUTHORITY_SCHEMA_ID,
                "schema_version": 1,
                "action": action,
                "target": {
                    "provider": "github",
                    "repository": "owner/repository",
                    "number": 7,
                    "url": "https://github.com/owner/repository/pull/7",
                },
                "exchange_id": exchange_id,
                "requirements_sha256": requirements_sha256,
                "prior_state_sha256": prior_state_sha256,
                "supersedes_state_sha256": supersedes_state_sha256,
                "decisions": decisions,
            }
        )
        if not isinstance(body, str):
            raise TypeError("The authority record must be text.")
        return body

    def risk_authority_prior_state_sha256(self, thread: Any) -> str:
        decisions = [
            {
                "finding_id": "F-001",
                "kind": "accept_risk",
                "closure_condition": None,
            }
        ]
        provisional_body = self.authority_body(
            action="human_decision",
            exchange_id="exchange-7",
            requirements_sha256="c" * 64,
            prior_state_sha256="0" * 64,
            supersedes_state_sha256=None,
            decisions=decisions,
        )
        provisional_receipt = {
            "reference": "review:provisional-authority",
            "sha256": self.delivery.review_exchange.sha256_text(provisional_body),
        }
        provisional_closure = replace(
            self.closure(thread),
            author_answer="risk_acceptance",
            reviewer_disposition="accepted_risk",
            closure_evidence=("The author supplied bound closure evidence.",),
            authority_receipt=provisional_receipt,
        )
        provisional = self.v1_manifest(thread, provisional_closure)
        human_events = [
            event
            for event in provisional.state_envelope["state"]["accepted_events"]
            if event["event_type"] == "human_decision"
        ]
        self.assertEqual(1, len(human_events))
        prior_state_sha256 = human_events[0]["prior_state_sha256"]
        if not isinstance(prior_state_sha256, str):
            raise TypeError("The authority event must bind a prior state.")
        return prior_state_sha256

    def round_three_manifest(self) -> tuple[Any, tuple[Any, ...], Any]:
        exchange = self.delivery.review_exchange
        binding = self.binding("c" * 40)
        threads = tuple(
            self.delivery.ReviewThread(
                id=f"thread-{number}",
                is_resolved=False,
                comments=(
                    self.delivery.ReviewComment(
                        id=f"comment-{number}",
                        body=(
                            f"Finding {number}.\n\n"
                            "<!-- HomericIntelligence:review-finding:v1 "
                            f"exchange=exchange-7 id=F-00{number} -->"
                        ),
                        author="reviewer",
                        viewer_did_author=True,
                        review_head_oid="a" * 40,
                        review_id="initial-review-1",
                        path="src/example.py",
                        side="RIGHT",
                        line=number,
                        original_line=number,
                    ),
                ),
                viewer_can_reply=True,
                viewer_can_resolve=True,
            )
            for number in (1, 2)
        )
        evidence_1_round_2 = "F-001 passes at the first correction."
        evidence_1_round_3 = "F-001 passes after the second correction."
        evidence_2_round_2 = "F-002 still fails at the first correction."
        evidence_2_round_3 = "F-002 passes at the second correction."
        entries = (
            self.delivery.ThreadClosure(
                thread_id="thread-1",
                finding_id="F-001",
                finding_exchange_id="exchange-7",
                finding_state_sha256="0" * 64,
                superseding_state_sha256=None,
                origin_comment_id="comment-1",
                origin_review_head_oid="a" * 40,
                conversation_sha256=self.delivery.conversation_sha256(threads[0]),
                finding_disposition="required",
                author_answer="fix",
                author_artifact_revision="c" * 40,
                reviewer_disposition="resolved",
                closure_evidence=(evidence_1_round_3,),
                authority_receipt=None,
                author_event_review_id="author-event-2",
            ),
            self.delivery.ThreadClosure(
                thread_id="thread-2",
                finding_id="F-002",
                finding_exchange_id="exchange-7",
                finding_state_sha256="0" * 64,
                superseding_state_sha256=None,
                origin_comment_id="comment-2",
                origin_review_head_oid="a" * 40,
                conversation_sha256=self.delivery.conversation_sha256(threads[1]),
                finding_disposition="required",
                author_answer="fix",
                author_artifact_revision="c" * 40,
                reviewer_disposition="resolved",
                closure_evidence=(evidence_2_round_3,),
                authority_receipt=None,
                author_event_review_id="author-event-2",
            ),
        )
        terminal_visible = self.delivery.terminal_visible_content(binding, entries)
        initial_visible = "Round 1 review."
        initial = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": {
                        "provider": "github",
                        "repository": "owner/repository",
                        "number": 7,
                        "url": "https://github.com/owner/repository/pull/7",
                    },
                    "requirements_sha256": "c" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "a" * 40,
                        "sha256": "1" * 64,
                        "visible_content_sha256": exchange.sha256_text(initial_visible),
                    },
                    "scope": ["path:src/example.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [
                        {
                            "id": f"F-00{number}",
                            "category": None,
                            "severity": "major",
                            "disposition": "required",
                            "material_architecture": False,
                            "location": f"src/example.py:{number}",
                            "impact": f"Case {number} is incorrect.",
                            "evidence": [f"Case {number} initially fails."],
                            "closure_condition": f"Case {number} passes.",
                            "introduction": "initial",
                        }
                        for number in (1, 2)
                    ],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        author_1_visible = "First author response."
        author_1 = exchange.reduce_request(
            {
                "previous": initial,
                "event": {
                    "event_type": "author_response",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": initial["state_sha256"],
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "2" * 64,
                        "visible_content_sha256": exchange.sha256_text(
                            author_1_visible
                        ),
                    },
                    "scope": ["path:src/example.py"],
                    "scope_change_reason": None,
                    "responses": [
                        {
                            "finding_id": f"F-00{number}",
                            "kind": "fix",
                            "evidence": [f"Author corrected case {number}."],
                            "tradeoff": None,
                        }
                        for number in (1, 2)
                    ],
                },
            }
        )
        round_2_visible = "Round 2 review."
        round_2 = exchange.reduce_request(
            {
                "previous": author_1["envelope"],
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": author_1["envelope"]["state_sha256"],
                    "round": 2,
                    "artifact_binding": {
                        **author_1["envelope"]["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(round_2_visible),
                    },
                    "scope": ["path:src/example.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [
                        {
                            "finding_id": "F-001",
                            "kind": "resolve",
                            "evidence": [evidence_1_round_2],
                            "closure_condition": None,
                        },
                        {
                            "finding_id": "F-002",
                            "kind": "still_present",
                            "evidence": [evidence_2_round_2],
                            "closure_condition": None,
                        },
                    ],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        author_2_visible = "Second author response."
        author_2 = exchange.reduce_request(
            {
                "previous": round_2,
                "event": {
                    "event_type": "author_response",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": round_2["state_sha256"],
                    "artifact_binding": {
                        "revision": "c" * 40,
                        "sha256": "3" * 64,
                        "visible_content_sha256": exchange.sha256_text(
                            author_2_visible
                        ),
                    },
                    "scope": ["path:src/example.py"],
                    "scope_change_reason": None,
                    "responses": [
                        {
                            "finding_id": "F-001",
                            "kind": "fix",
                            "evidence": ["Author revalidated case 1."],
                            "tradeoff": None,
                        },
                        {
                            "finding_id": "F-002",
                            "kind": "fix",
                            "evidence": ["Author corrected case 2 again."],
                            "tradeoff": None,
                        },
                    ],
                },
            }
        )
        terminal = exchange.reduce_request(
            {
                "previous": author_2["envelope"],
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": author_2["envelope"]["state_sha256"],
                    "round": 3,
                    "artifact_binding": {
                        **author_2["envelope"]["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(
                            terminal_visible
                        ),
                    },
                    "scope": ["path:src/example.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [
                        {
                            "finding_id": "F-001",
                            "kind": "resolve",
                            "evidence": [evidence_1_round_3],
                            "closure_condition": None,
                        },
                        {
                            "finding_id": "F-002",
                            "kind": "resolve",
                            "evidence": [evidence_2_round_3],
                            "closure_condition": None,
                        },
                    ],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        entries = tuple(
            replace(
                entry,
                finding_state_sha256=terminal["state_sha256"],
                superseding_state_sha256=None,
            )
            for entry in entries
        )
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=terminal_visible,
            entries=entries,
            requirements_binding=self.requirements_binding(terminal),
        )
        self.carrier_history[terminal["state_sha256"]] = (
            self.carrier_record("initial-review-1", initial, initial_visible),
            self.carrier_record(
                "author-event-1", author_1["author_event"], author_1_visible
            ),
            self.carrier_record("round-2-review", round_2, round_2_visible),
            self.carrier_record(
                "author-event-2", author_2["author_event"], author_2_visible
            ),
        )
        return binding, threads, manifest

    def reframed_reused_finding_manifest(
        self,
        *,
        include_historical_entry: bool = True,
    ) -> tuple[FakeForge, Any, Any, dict[str, Any], dict[str, Any], dict[str, str]]:
        exchange = self.delivery.review_exchange
        target = {
            "provider": "github",
            "repository": "owner/repository",
            "number": 7,
            "url": "https://github.com/owner/repository/pull/7",
        }
        old_visible = "The old requirements have one required finding."
        old = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-old",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": target,
                    "requirements_sha256": "1" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "a" * 40,
                        "sha256": "2" * 64,
                        "visible_content_sha256": exchange.sha256_text(old_visible),
                    },
                    "scope": ["path:src/old.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [
                        {
                            "id": "F-001",
                            "category": None,
                            "severity": "major",
                            "disposition": "required",
                            "material_architecture": False,
                            "location": "src/old.py:4",
                            "impact": "The old requirement is not satisfied.",
                            "evidence": ["The old case fails."],
                            "closure_condition": "The old case passes.",
                            "introduction": "initial",
                        }
                    ],
                    "stop_reason": "requirements_reframe",
                },
            }
        )["envelope"]
        old_thread = self.carrier_threads(old, "old-review")[0]
        authority_body = self.authority_body(
            action="reframe",
            exchange_id="exchange-new",
            requirements_sha256="3" * 64,
            supersedes_state_sha256=old["state_sha256"],
            decisions=[],
        )
        receipt = {
            "reference": "review:reframe-authority",
            "sha256": exchange.sha256_text(authority_body),
        }
        closure_seed = self.delivery.ThreadClosure(
            thread_id=old_thread.id,
            finding_id="F-001",
            finding_exchange_id="exchange-old",
            finding_state_sha256=old["state_sha256"],
            superseding_state_sha256="0" * 64,
            origin_comment_id=old_thread.comments[0].id,
            origin_review_head_oid="a" * 40,
            conversation_sha256=self.delivery.conversation_sha256(old_thread),
            finding_disposition="required",
            author_answer=None,
            author_artifact_revision=None,
            reviewer_disposition="withdrawn",
            closure_evidence=self.delivery._reframe_closure_evidence(
                old["state_sha256"]
            ),
            authority_receipt=receipt,
            author_event_review_id=None,
        )
        terminal_visible = self.delivery.terminal_visible_content(
            self.binding(), (closure_seed,) if include_historical_entry else ()
        )
        terminal = exchange.reduce_request(
            {
                "previous": old,
                "event": {
                    "event_type": "reframe",
                    "exchange_id": "exchange-new",
                    "prior_state_sha256": old["state_sha256"],
                    "round": 1,
                    "surface": "pull_request",
                    "target": target,
                    "requirements_sha256": "3" * 64,
                    "supersedes_state_sha256": old["state_sha256"],
                    "superseded_exchange_ids": [old["state"]["exchange_id"]],
                    "authority_receipt": receipt,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "3" * 64,
                        "visible_content_sha256": exchange.sha256_text(
                            terminal_visible
                        ),
                    },
                    "scope": ["path:src/new.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [
                        {
                            "id": "F-001",
                            "category": None,
                            "severity": "minor",
                            "disposition": "suggestion",
                            "material_architecture": False,
                            "location": "src/new.py:8",
                            "impact": "The new name can be clearer.",
                            "evidence": ["The name hides its purpose."],
                            "closure_condition": None,
                            "introduction": "initial",
                        }
                    ],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        closure = replace(
            closure_seed, superseding_state_sha256=terminal["state_sha256"]
        )
        inline = self.delivery.TerminalInlineComment(
            path="src/new.py",
            side="RIGHT",
            line=8,
            body=(
                "The new name can be clearer.\n\n"
                "<!-- HomericIntelligence:review-finding:v1 "
                "exchange=exchange-new id=F-001 -->"
            ),
        )
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=terminal_visible,
            entries=(closure,) if include_historical_entry else (),
            requirements_binding=self.requirements_binding(terminal),
            comments=(inline,),
        )
        authority = self.delivery.ReviewRecord(
            id="reframe-authority",
            body=authority_body,
            head_oid="b" * 40,
            author="maintainer",
            viewer_did_author=False,
            includes_created_edit=False,
            state="COMMENTED",
            author_association="OWNER",
            author_permission="ADMIN",
            submitted_at="2026-01-01T00:00:02Z",
        )
        forge = FakeForge(self.delivery, threads=(old_thread,))
        forge.reviews.extend(
            (
                self.carrier_record("old-review", old, old_visible),
                authority,
            )
        )
        return forge, manifest, old_thread, old, terminal, receipt

    def test_active_legacy_delivery_is_rejected_without_mutation(self) -> None:
        thread = self.thread()
        forge = FakeForge(self.delivery, threads=(thread,))

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go(forge, self.binding(), (self.plan(thread),))

        self.assertEqual([], forge.events)

    def test_legacy_mode_only_proves_an_unchanged_delivered_go(self) -> None:
        original = self.thread()
        response = self.delivery.ThreadResponse(
            thread_id=original.id,
            conversation_sha256=self.delivery._legacy_conversation_sha256(original),
            body="Verified historical response.",
        )
        resolved = self.delivery.ReviewThread(
            id=original.id,
            is_resolved=True,
            comments=(
                *original.comments,
                self.delivery.ReviewComment(
                    id="legacy-reply",
                    body=self.delivery._legacy_delivery_body(self.binding(), response),
                    author="reviewer",
                ),
            ),
        )
        forge = FakeForge(self.delivery, threads=(resolved,))
        forge.labels = {"state:implementation-go", "enhancement"}

        result = self.delivery.verify_legacy_go(forge, self.binding(), (response,))

        self.assertEqual("already_delivered", result.status)
        self.assertEqual(["read"], forge.events)

    def test_legacy_proof_ignores_unmarked_pre_resolved_history(self) -> None:
        handled = self.thread()
        response = self.delivery.ThreadResponse(
            thread_id=handled.id,
            conversation_sha256=self.delivery._legacy_conversation_sha256(handled),
            body="Verified historical response.",
        )
        delivered = replace(
            handled,
            is_resolved=True,
            comments=(
                *handled.comments,
                self.delivery.ReviewComment(
                    id="legacy-reply",
                    body=self.delivery._legacy_delivery_body(self.binding(), response),
                    author="reviewer",
                ),
            ),
        )
        pre_resolved = self.delivery.ReviewThread(
            id="pre-resolved-thread",
            is_resolved=True,
            comments=(
                self.delivery.ReviewComment(
                    id="old-comment",
                    body="This unrelated discussion was already resolved.",
                    author="other-reviewer",
                    viewer_did_author=False,
                ),
            ),
        )
        forge = FakeForge(self.delivery, threads=(pre_resolved, delivered))
        forge.labels = {"state:implementation-go", "enhancement"}

        result = self.delivery.verify_legacy_go(forge, self.binding(), (response,))

        self.assertEqual("already_delivered", result.status)
        self.assertEqual(["read"], forge.events)

    def test_legacy_proof_rejects_duplicate_thread_identities(self) -> None:
        thread = self.thread()
        response = self.delivery.ThreadResponse(
            thread_id=thread.id,
            conversation_sha256=self.delivery._legacy_conversation_sha256(thread),
            body="Verified historical response.",
        )
        delivered = replace(
            thread,
            is_resolved=True,
            comments=(
                *thread.comments,
                self.delivery.ReviewComment(
                    id="legacy-reply",
                    body=self.delivery._legacy_delivery_body(self.binding(), response),
                    author="reviewer",
                ),
            ),
        )
        forge = FakeForge(self.delivery, threads=(delivered,))
        forge.labels = {"state:implementation-go", "enhancement"}
        duplicate_snapshot = replace(forge.snapshot(), threads=(delivered, delivered))

        with (
            patch.object(forge, "snapshot", return_value=duplicate_snapshot),
            self.assertRaises(self.delivery.DeliveryError),
        ):
            self.delivery.verify_legacy_go(forge, self.binding(), (response,))

    def test_legacy_proof_rejects_empty_pre_resolved_history(self) -> None:
        empty = self.delivery.ReviewThread(
            id="pre-resolved-thread",
            is_resolved=True,
            comments=(),
        )
        forge = FakeForge(self.delivery, threads=(empty,))
        forge.labels = {"state:implementation-go", "enhancement"}

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.verify_legacy_go(forge, self.binding(), ())

    def test_legacy_proof_rejects_a_foreign_copy_of_the_delivery_reply(self) -> None:
        original = self.thread()
        response = self.delivery.ThreadResponse(
            thread_id=original.id,
            conversation_sha256=self.delivery._legacy_conversation_sha256(original),
            body="Verified historical response.",
        )
        copied_reply = self.delivery.ReviewComment(
            id="foreign-legacy-reply",
            body=self.delivery._legacy_delivery_body(self.binding(), response),
            author="other-reviewer",
            viewer_did_author=False,
        )
        resolved = replace(
            original,
            is_resolved=True,
            comments=(*original.comments, copied_reply),
        )
        forge = FakeForge(self.delivery, threads=(resolved,))
        forge.labels = {"state:implementation-go", "enhancement"}

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.verify_legacy_go(forge, self.binding(), (response,))

        self.assertEqual(["read"], forge.events)

    def test_legacy_proof_is_not_a_fallback_after_a_v1_carrier(self) -> None:
        original = self.thread()
        response = self.delivery.ThreadResponse(
            thread_id=original.id,
            conversation_sha256=self.delivery._legacy_conversation_sha256(original),
            body="Verified historical response.",
        )
        resolved = replace(
            original,
            is_resolved=True,
            comments=(
                *original.comments,
                self.delivery.ReviewComment(
                    id="legacy-reply",
                    body=self.delivery._legacy_delivery_body(self.binding(), response),
                    author="reviewer",
                ),
            ),
        )
        forge = FakeForge(self.delivery, threads=(resolved,))
        forge.labels = {"state:implementation-go", "enhancement"}
        _, v1_record = self.no_go_proof()
        forge.reviews.append(v1_record)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.verify_legacy_go(forge, self.binding(), (response,))

        self.assertEqual(["read"], forge.events)

    def test_legacy_mode_rejects_an_active_thread_without_mutation(self) -> None:
        thread = self.thread()
        response = self.delivery.ThreadResponse(
            thread_id=thread.id,
            conversation_sha256=self.delivery._legacy_conversation_sha256(thread),
            body="Historical response.",
        )
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.labels = {"state:implementation-go", "enhancement"}

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.verify_legacy_go(forge, self.binding(), (response,))

        self.assertEqual(["read"], forge.events)

    def test_legacy_proof_fails_closed_for_incomplete_delivery_evidence(
        self,
    ) -> None:
        original = self.thread()
        response = self.delivery.ThreadResponse(
            thread_id=original.id,
            conversation_sha256=self.delivery._legacy_conversation_sha256(original),
            body="Verified historical response.",
        )
        delivered_reply = self.delivery.ReviewComment(
            id="legacy-reply",
            body=self.delivery._legacy_delivery_body(self.binding(), response),
            author="reviewer",
        )
        resolved = replace(
            original,
            is_resolved=True,
            comments=(*original.comments, delivered_reply),
        )
        cases: tuple[tuple[set[str], tuple[Any, ...], tuple[Any, ...]], ...] = (
            ({"enhancement"}, (resolved,), (response,)),
            (
                {
                    "state:implementation-go",
                    "state:implementation-no-go",
                    "enhancement",
                },
                (resolved,),
                (response,),
            ),
            ({"state:implementation-go"}, (original,), (response,)),
            ({"state:implementation-go"}, (resolved,), ()),
            ({"state:implementation-go"}, (resolved,), (response, response)),
            (
                {"state:implementation-go"},
                (replace(resolved, comments=()),),
                (response,),
            ),
            (
                {"state:implementation-go"},
                (resolved,),
                (replace(response, conversation_sha256="f" * 64),),
            ),
            (
                {"state:implementation-go"},
                (
                    replace(
                        resolved,
                        comments=(
                            *original.comments,
                            replace(delivered_reply, body="Different reply."),
                        ),
                    ),
                ),
                (response,),
            ),
        )
        for labels, threads, responses in cases:
            forge = FakeForge(self.delivery, threads=threads)
            forge.labels = set(labels)

            with (
                self.subTest(labels=labels, threads=threads, responses=responses),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.verify_legacy_go(forge, self.binding(), responses)

            self.assertEqual(["read"], forge.events)

    def test_executable_reports_a_missing_github_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bin_directory = root / "bin"
            bin_directory.mkdir()
            (bin_directory / "python3").symlink_to(sys.executable)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_directory)
            result = subprocess.run(
                [
                    str(SCRIPT),
                    "--target-host",
                    "github.com",
                    "--target-repository",
                    "owner/repository",
                    "--expected-base-oid",
                    "a" * 40,
                    "--expected-head-oid",
                    "b" * 40,
                    "--expected-pr-url",
                    "https://github.com/owner/repository/pull/1",
                    "--prepare-manifest",
                    "1",
                ],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("gh", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_github_adapter_uses_explicit_host_and_parses_complete_snapshot(
        self,
    ) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_gh(*arguments: str) -> str:
            calls.append(arguments)
            return self.github_snapshot_json()

        with patch.object(self.delivery, "_gh", side_effect=fake_gh):
            snapshot = self.delivery.GitHubForge(self.binding()).snapshot()

        self.assertEqual("thread-1", snapshot.threads[0].id)
        self.assertEqual("finding", snapshot.threads[0].comments[0].body)
        self.assertTrue(snapshot.threads[0].viewer_can_reply)
        self.assertEqual("MEMBER", snapshot.threads[0].comments[0].author_association)
        self.assertEqual("review-1", snapshot.threads[0].comments[0].review_id)
        self.assertEqual("src/example.py", snapshot.threads[0].comments[0].path)
        self.assertEqual("RIGHT", snapshot.threads[0].comments[0].side)
        self.assertIsNone(snapshot.threads[0].comments[0].line)
        self.assertEqual(7, snapshot.threads[0].comments[0].original_line)
        self.assertEqual(
            "2026-01-01T00:00:01Z", snapshot.threads[0].comments[0].published_at
        )
        self.assertIsNone(snapshot.threads[0].comments[0].last_edited_at)
        self.assertEqual("review-1", snapshot.reviews[0].id)
        self.assertEqual("a" * 40, snapshot.reviews[0].head_oid)
        self.assertEqual("MEMBER", snapshot.reviews[0].author_association)
        self.assertEqual("2026-01-01T00:00:01Z", snapshot.reviews[0].submitted_at)
        self.assertIsNone(snapshot.reviews[0].last_edited_at)
        self.assertIn("state:implementation-no-go", snapshot.labels)
        self.assertIn("--hostname", calls[0])
        self.assertIn("github.com", calls[0])
        self.assertIn("owner=owner", calls[0])
        self.assertIn("name=repository", calls[0])
        self.assertIn("number=7", calls[0])

    def test_github_snapshot_records_current_authority_permission(self) -> None:
        authority_body = self.authority_body(
            action="human_decision",
            exchange_id="exchange-7",
            requirements_sha256="c" * 64,
            prior_state_sha256="0" * 64,
            supersedes_state_sha256=None,
            decisions=[
                {
                    "finding_id": "F-001",
                    "kind": "accept_risk",
                    "closure_condition": None,
                }
            ],
        )
        document = json.loads(self.github_snapshot_json())
        document["data"]["repository"]["pullRequest"]["reviews"]["nodes"].append(
            {
                "author": {"login": "maintainer"},
                "authorAssociation": "MEMBER",
                "body": authority_body,
                "commit": {"oid": "b" * 40},
                "id": "authority-review",
                "includesCreatedEdit": False,
                "lastEditedAt": None,
                "state": "COMMENTED",
                "submittedAt": "2026-01-01T00:00:02Z",
                "viewerDidAuthor": False,
            }
        )
        calls: list[tuple[str, ...]] = []

        def fake_gh(*arguments: str, **options: Any) -> str:
            del options
            calls.append(arguments)
            if "graphql" in arguments:
                return json.dumps(document)
            return json.dumps({"permission": "maintain"})

        with patch.object(self.delivery, "_gh", side_effect=fake_gh):
            snapshot = self.delivery.GitHubForge(self.binding()).snapshot()

        authority = next(
            review for review in snapshot.reviews if review.id == "authority-review"
        )
        self.assertEqual("MAINTAIN", authority.author_permission)
        self.assertTrue(
            any(
                "collaborators/maintainer/permission" in argument
                for call in calls
                for argument in call
            )
        )

    def test_github_adapter_rejects_incomplete_or_malformed_snapshots(self) -> None:
        cases: tuple[tuple[tuple[str | int, ...], object], ...] = (
            (("number",), 8),
            (("isDraft",), "false"),
            (("reviewThreads", "pageInfo", "hasNextPage"), True),
            (("reviewThreads", "pageInfo", "hasNextPage"), 0),
            (("reviewThreads", "pageInfo"), None),
            (("reviewThreads", "nodes"), None),
            (("reviewThreads", "nodes", 0), None),
            (("reviewThreads", "nodes", 0, "comments"), None),
            (
                ("reviewThreads", "nodes", 0, "comments", "pageInfo", "hasNextPage"),
                True,
            ),
            (
                ("reviewThreads", "nodes", 0, "comments", "pageInfo", "hasNextPage"),
                0,
            ),
            (("reviewThreads", "nodes", 0, "comments", "nodes"), None),
            (("reviewThreads", "nodes", 0, "comments", "nodes", 0), None),
            (("reviewThreads", "nodes", 0, "id"), None),
            (("reviewThreads", "nodes", 0, "isResolved"), None),
            (("reviewThreads", "nodes", 0, "path"), None),
            (("reviewThreads", "nodes", 0, "originalLine"), "7"),
            (("reviewThreads", "nodes", 0, "viewerCanReply"), "false"),
            (("reviewThreads", "nodes", 0, "viewerCanResolve"), "false"),
            (
                (
                    "reviewThreads",
                    "nodes",
                    0,
                    "comments",
                    "nodes",
                    0,
                    "viewerDidAuthor",
                ),
                "false",
            ),
            (
                (
                    "reviewThreads",
                    "nodes",
                    0,
                    "comments",
                    "nodes",
                    0,
                    "publishedAt",
                ),
                1,
            ),
            (
                (
                    "reviewThreads",
                    "nodes",
                    0,
                    "comments",
                    "nodes",
                    0,
                    "lastEditedAt",
                ),
                1,
            ),
            (("labels",), None),
            (("labels", "pageInfo", "hasNextPage"), True),
            (("labels", "pageInfo", "hasNextPage"), 0),
            (("labels", "nodes"), None),
            (("labels", "nodes", 0), None),
            (("reviews",), []),
            (("reviews", "pageInfo", "hasNextPage"), True),
            (("reviews", "pageInfo", "hasNextPage"), 0),
            (("reviews", "nodes"), None),
            (("reviews", "nodes", 0), None),
            (("reviews", "nodes", 0, "body"), None),
            (("reviews", "nodes", 0, "commit"), None),
            (("reviews", "nodes", 0, "submittedAt"), 1),
            (("reviews", "nodes", 0, "lastEditedAt"), 1),
            (("reviews", "nodes", 0, "viewerDidAuthor"), "false"),
            (("reviews", "nodes", 0, "includesCreatedEdit"), "false"),
        )
        for path, value in cases:
            document = json.loads(self.github_snapshot_json())
            target = document["data"]["repository"]["pullRequest"]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with (
                self.subTest(path=path),
                patch.object(
                    self.delivery, "_gh", return_value=json.dumps(document)
                ) as query,
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.GitHubForge(self.binding()).snapshot()
            query.assert_called_once()
        with (
            patch.object(
                self.delivery,
                "_gh",
                return_value='{"data":{"repository":{"pullRequest":null}}}',
            ),
            self.assertRaises(self.delivery.DeliveryError),
        ):
            self.delivery.GitHubForge(self.binding()).snapshot()

        for missing_reviews in (True, False):
            document = json.loads(self.github_snapshot_json())
            pull_request = document["data"]["repository"]["pullRequest"]
            if missing_reviews:
                del pull_request["reviews"]
            else:
                pull_request["reviews"] = None
            with (
                self.subTest(missing_reviews=missing_reviews),
                patch.object(
                    self.delivery, "_gh", return_value=json.dumps(document)
                ) as query,
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.GitHubForge(self.binding()).snapshot()
            query.assert_called_once()

    def test_github_command_and_live_requirements_boundaries_fail_closed(self) -> None:
        successful = subprocess.CompletedProcess(
            args=("gh",), returncode=0, stdout="result", stderr=""
        )
        with patch.object(
            self.delivery, "run_command", return_value=successful
        ) as command:
            self.assertEqual("result", self.delivery._gh("api", "endpoint"))
        command.assert_called_once_with(
            ("gh", "api", "endpoint"),
            capture_output=True,
            text=True,
            check=False,
        )

        failed = subprocess.CompletedProcess(
            args=("gh",), returncode=1, stdout="", stderr="denied"
        )
        with (
            patch.object(self.delivery, "run_command", return_value=failed) as command,
            self.assertRaises(self.delivery.DeliveryError),
        ):
            self.delivery._gh("api", "endpoint", input_text="{}")
        command.assert_called_once_with(
            ("gh", "api", "endpoint"),
            capture_output=True,
            text=True,
            check=False,
            input="{}",
        )

        for response in ("[]", '{"errors":[{"type":"FORBIDDEN"}]}'):
            with (
                self.subTest(response=response),
                patch.object(self.delivery, "_gh", return_value=response) as query,
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.GitHubForge(self.binding()).snapshot()
            query.assert_called_once()

        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        with (
            patch.object(forge, "collect_requirements_binding", return_value=object()),
            self.assertRaises(self.delivery.DeliveryError),
        ):
            self.delivery.prepare_response_manifest(forge, self.binding())
        self.assertEqual(["read"], forge.events)

        expected = self.delivery.RequirementsBinding(
            reviewed_scope_sha256="1" * 64,
            requirements_sha256="2" * 64,
            requirement_issue_urls=("https://github.com/owner/repository/issues/1",),
        )
        adapter = self.delivery.GitHubForge(self.binding())
        with patch.object(
            adapter,
            "collect_requirements_binding",
            side_effect=[
                expected,
                replace(expected, requirements_sha256="3" * 64),
            ],
        ) as collect:
            adapter.verify_requirements_binding(expected)
            with self.assertRaises(self.delivery.DeliveryError):
                adapter.verify_requirements_binding(expected)
        self.assertEqual(
            [
                expected.requirement_issue_urls,
                expected.requirement_issue_urls,
            ],
            [call.args[0] for call in collect.call_args_list],
        )

    def test_github_adapter_posts_bound_reply_and_resolution_mutations(self) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_gh(*arguments: str) -> str:
            calls.append(arguments)
            return json.dumps({"data": {}})

        forge = self.delivery.GitHubForge(self.binding())
        with patch.object(self.delivery, "_gh", side_effect=fake_gh):
            forge.reply("thread-1", "response")
            forge.resolve("thread-1")

        self.assertIn("addPullRequestReviewThreadReply", calls[0][5])
        self.assertIn("threadId=thread-1", calls[0])
        self.assertIn("body=response", calls[0])
        self.assertIn("resolveReviewThread", calls[1][5])

    def test_github_adapter_changes_only_exclusive_implementation_labels(self) -> None:
        calls: list[tuple[str, ...]] = []
        forge = self.delivery.GitHubForge(self.binding())
        snapshot = self.delivery.PullRequestSnapshot(
            repository="owner/repository",
            number=7,
            url="https://github.com/owner/repository/pull/7",
            state="OPEN",
            is_draft=False,
            base_oid="a" * 40,
            head_oid="b" * 40,
            labels=frozenset({"state:implementation-no-go", "enhancement"}),
            threads=(),
        )

        def fake_gh(*arguments: str) -> str:
            calls.append(arguments)
            return ""

        with (
            patch.object(forge, "snapshot", return_value=snapshot),
            patch.object(self.delivery, "_gh", side_effect=fake_gh),
        ):
            forge.set_implementation_go()

        self.assertEqual(
            (
                "issue",
                "edit",
                "7",
                "--repo",
                "github.com/owner/repository",
                "--add-label",
                "state:implementation-go",
                "--remove-label",
                "state:implementation-no-go",
            ),
            calls[0],
        )
        go_snapshot = replace(
            snapshot,
            labels=frozenset({"state:implementation-go", "enhancement"}),
        )
        calls.clear()
        with (
            patch.object(forge, "snapshot", return_value=go_snapshot),
            patch.object(self.delivery, "_gh", side_effect=fake_gh),
        ):
            forge.set_implementation_no_go()
        self.assertEqual(
            (
                "issue",
                "edit",
                "7",
                "--repo",
                "github.com/owner/repository",
                "--add-label",
                "state:implementation-no-go",
                "--remove-label",
                "state:implementation-go",
            ),
            calls[0],
        )

    def test_manifest_loader_rejects_non_object_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(self.delivery.DeliveryError):
                self.delivery.load_response_manifest(path, self.binding())

    def test_active_manifest_loader_rejects_legacy_and_explicit_loader_accepts_it(
        self,
    ) -> None:
        thread = self.thread()
        document: dict[str, Any] = {
            "binding": {
                "base_oid": "a" * 40,
                "head_oid": "b" * 40,
                "number": 7,
                "repository": "owner/repository",
                "url": "https://github.com/owner/repository/pull/7",
            },
            "responses": [
                {
                    "body": "verified",
                    "conversation_sha256": self.delivery.conversation_sha256(thread),
                    "thread_id": "thread-1",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "manifest.json"
            path.write_text(
                self.delivery.review_exchange.canonical_json(document),
                encoding="utf-8",
            )
            initial_bytes = path.read_bytes()
            with self.assertRaises(self.delivery.DeliveryError):
                self.delivery.load_response_manifest(path, self.binding())
            self.assertEqual(initial_bytes, path.read_bytes())
            responses = self.delivery.load_legacy_proof(path, self.binding())
            document["binding"]["head_oid"] = "c" * 40
            path.write_text(
                self.delivery.review_exchange.canonical_json(document),
                encoding="utf-8",
            )
            stale_bytes = path.read_bytes()
            with self.assertRaises(self.delivery.DeliveryError):
                self.delivery.load_legacy_proof(path, self.binding())
            self.assertEqual(stale_bytes, path.read_bytes())
            path.write_text(json.dumps({"responses": []}), encoding="utf-8")
            incomplete_bytes = path.read_bytes()
            with self.assertRaises(self.delivery.DeliveryError):
                self.delivery.load_legacy_proof(path, self.binding())
            self.assertEqual(incomplete_bytes, path.read_bytes())

        self.assertEqual("verified", responses[0].body)

    def test_argument_binding_accepts_number_and_rejects_url_drift(self) -> None:
        arguments = Namespace(
            base_oid="a" * 40,
            expected_pr_url="https://github.com/owner/repository/pull/7",
            head_oid="b" * 40,
            pull_request="7",
            target_repository="owner/repository",
        )
        self.assertEqual(self.binding(), self.delivery._binding_from_args(arguments))
        arguments.pull_request = "https://github.com/other/repository/pull/7"
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery._binding_from_args(arguments)
        self.assertEqual(
            "https://github.com/other/repository/pull/7", arguments.pull_request
        )

    def test_main_prepares_manifest_and_reports_delivery_error(self) -> None:
        output = io.StringIO()
        with (
            patch.object(self.delivery, "GitHubForge", return_value=object()),
            patch.object(
                self.delivery,
                "prepare_response_manifest",
                return_value={"responses": []},
            ),
            redirect_stdout(output),
        ):
            status = self.delivery.main(
                [
                    "--target-repository",
                    "owner/repository",
                    "--expected-pr-url",
                    "https://github.com/owner/repository/pull/7",
                    "--expected-base-oid",
                    "a" * 40,
                    "--expected-head-oid",
                    "b" * 40,
                    "--prepare-manifest",
                    "7",
                ]
            )
        self.assertEqual(0, status)
        self.assertEqual({"responses": []}, json.loads(output.getvalue()))

        errors = io.StringIO()
        with redirect_stderr(errors):
            status = self.delivery.main(
                [
                    "--target-repository",
                    "owner/repository",
                    "--expected-pr-url",
                    "https://github.com/owner/repository/pull/7",
                    "--expected-base-oid",
                    "a" * 40,
                    "--expected-head-oid",
                    "b" * 40,
                    "--responses-file",
                    "/missing/manifest.json",
                    "7",
                ]
            )
        self.assertEqual(1, status)
        self.assertIn("cannot be read", errors.getvalue())

    def test_main_reports_verified_delivery_result(self) -> None:
        output = io.StringIO()
        forge = object()
        manifest = object()
        with (
            patch.object(self.delivery, "GitHubForge", return_value=forge),
            patch.object(
                self.delivery, "load_response_manifest", return_value=manifest
            ),
            patch.object(
                self.delivery,
                "deliver_go_v1",
                return_value=self.delivery.DeliveryResult(
                    "delivered",
                    ("thread-1",),
                    terminal_review_id="review-7",
                    responded_thread_ids=("thread-1",),
                    observed_head_oid="b" * 40,
                    observed_labels=("enhancement", "state:implementation-go"),
                ),
            ) as deliver,
            redirect_stdout(output),
        ):
            status = self.delivery.main(
                [
                    "--target-repository",
                    "owner/repository",
                    "--expected-pr-url",
                    "https://github.com/owner/repository/pull/7",
                    "--expected-base-oid",
                    "a" * 40,
                    "--expected-head-oid",
                    "b" * 40,
                    "--responses-file",
                    "/bound/manifest.json",
                    "7",
                ]
            )

        self.assertEqual(0, status)
        self.assertEqual(
            {
                "label": "state:implementation-go",
                "observed_head_oid": "b" * 40,
                "observed_labels": ["enhancement", "state:implementation-go"],
                "pending_thread_ids": [],
                "reason": None,
                "recovery_read_required": False,
                "responded_thread_ids": ["thread-1"],
                "resolved_thread_ids": ["thread-1"],
                "status": "delivered",
                "terminal_review_id": "review-7",
                "uncertain_operation": None,
            },
            json.loads(output.getvalue()),
        )
        deliver.assert_called_once_with(forge, self.binding(), manifest)

    def test_main_routes_no_go_and_read_only_legacy_proofs(self) -> None:
        common = [
            "--target-repository",
            "owner/repository",
            "--expected-pr-url",
            "https://github.com/owner/repository/pull/7",
            "--expected-base-oid",
            "a" * 40,
            "--expected-head-oid",
            "b" * 40,
        ]
        forge = object()
        proof = object()
        with (
            patch.object(self.delivery, "GitHubForge", return_value=forge),
            patch.object(self.delivery, "load_no_go_proof", return_value=proof) as load,
            patch.object(
                self.delivery,
                "deliver_no_go",
                return_value=self.delivery.DeliveryResult(
                    "delivered", (), "state:implementation-no-go"
                ),
            ) as deliver,
            redirect_stdout(io.StringIO()),
        ):
            status = self.delivery.main(
                [
                    *common,
                    "--deliver-no-go",
                    "--state-carrier-file",
                    "/bound/no-go.json",
                    "7",
                ]
            )
        self.assertEqual(0, status)
        load.assert_called_once_with(Path("/bound/no-go.json"), self.binding())
        deliver.assert_called_once_with(forge, self.binding(), proof)

        responses = (object(),)
        with (
            patch.object(self.delivery, "GitHubForge", return_value=forge),
            patch.object(
                self.delivery, "load_legacy_proof", return_value=responses
            ) as load,
            patch.object(
                self.delivery,
                "verify_legacy_go",
                return_value=self.delivery.DeliveryResult("already_delivered", ()),
            ) as verify,
            redirect_stdout(io.StringIO()),
        ):
            status = self.delivery.main(
                [*common, "--verify-legacy-go", "/bound/legacy.json", "7"]
            )
        self.assertEqual(0, status)
        load.assert_called_once_with(Path("/bound/legacy.json"), self.binding())
        verify.assert_called_once_with(forge, self.binding(), responses)

    def test_main_requires_a_no_go_state_carrier(self) -> None:
        errors = io.StringIO()
        with (
            patch.object(self.delivery, "GitHubForge", return_value=object()),
            redirect_stderr(errors),
        ):
            status = self.delivery.main(
                [
                    "--target-repository",
                    "owner/repository",
                    "--expected-pr-url",
                    "https://github.com/owner/repository/pull/7",
                    "--expected-base-oid",
                    "a" * 40,
                    "--expected-head-oid",
                    "b" * 40,
                    "--deliver-no-go",
                    "7",
                ]
            )
        self.assertEqual(1, status)
        self.assertTrue(errors.getvalue())

    def test_main_rejects_cross_mode_inputs_and_reports_partial_recovery(
        self,
    ) -> None:
        common = [
            "--target-repository",
            "owner/repository",
            "--expected-pr-url",
            "https://github.com/owner/repository/pull/7",
            "--expected-base-oid",
            "a" * 40,
            "--expected-head-oid",
            "b" * 40,
        ]
        issue = "https://github.com/owner/repository/issues/1"
        cases = (
            (
                "prepare-with-state",
                ["--prepare-manifest", "--state-carrier-file", "/bound/state.json"],
            ),
            (
                "no-go-with-requirement",
                [
                    "--deliver-no-go",
                    "--state-carrier-file",
                    "/bound/state.json",
                    "--requirement-issue",
                    issue,
                ],
            ),
            (
                "legacy-with-state",
                [
                    "--verify-legacy-go",
                    "/bound/legacy.json",
                    "--state-carrier-file",
                    "/bound/state.json",
                ],
            ),
            (
                "legacy-with-requirement",
                [
                    "--verify-legacy-go",
                    "/bound/legacy.json",
                    "--requirement-issue",
                    issue,
                ],
            ),
            (
                "go-with-requirement",
                [
                    "--response-manifest",
                    "/bound/manifest.json",
                    "--requirement-issue",
                    issue,
                ],
            ),
            (
                "go-with-state",
                [
                    "--response-manifest",
                    "/bound/manifest.json",
                    "--state-carrier-file",
                    "/bound/state.json",
                ],
            ),
        )
        operations = (
            "prepare_response_manifest",
            "load_response_manifest",
            "load_no_go_proof",
            "load_legacy_proof",
            "deliver_go_v1",
            "deliver_no_go",
            "verify_legacy_go",
        )
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(self.delivery, "GitHubForge", return_value=object())
            )
            operation_mocks = [
                stack.enter_context(patch.object(self.delivery, operation))
                for operation in operations
            ]
            for name, mode in cases:
                output = io.StringIO()
                errors = io.StringIO()
                with (
                    self.subTest(name=name),
                    redirect_stdout(output),
                    redirect_stderr(errors),
                ):
                    status = self.delivery.main([*common, *mode, "7"])
                self.assertEqual(1, status)
                self.assertEqual("", output.getvalue())
                self.assertTrue(errors.getvalue())
            for operation in operation_mocks:
                operation.assert_not_called()

        report = self.delivery.DeliveryResult(
            status="partial",
            resolved_thread_ids=("thread-1",),
            terminal_review_id="review-7",
            responded_thread_ids=("thread-1",),
            pending_thread_ids=("thread-2",),
            observed_head_oid="b" * 40,
            observed_labels=("enhancement",),
            uncertain_operation="implementation label",
            recovery_read_required=True,
        )
        error = self.delivery.DeliveryError("delivery stopped", report)
        output = io.StringIO()
        errors = io.StringIO()
        with (
            patch.object(self.delivery, "GitHubForge", return_value=object()),
            patch.object(
                self.delivery, "load_response_manifest", return_value=object()
            ),
            patch.object(self.delivery, "deliver_go_v1", side_effect=error),
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            status = self.delivery.main(
                [*common, "--response-manifest", "/bound/manifest.json", "7"]
            )
        diagnostic = json.loads(errors.getvalue())
        self.assertEqual(1, status)
        self.assertEqual("", output.getvalue())
        self.assertEqual({"error", "recovery"}, set(diagnostic))
        self.assertTrue(diagnostic["error"])
        self.assertEqual(
            self.delivery._delivery_result_document(report), diagnostic["recovery"]
        )

    def test_v1_corrective_head_publishes_terminal_then_closes_and_labels(
        self,
    ) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertEqual(("thread-1",), result.resolved_thread_ids)
        self.assertLess(
            forge.events.index("terminal"), forge.events.index("reply:thread-1")
        )
        self.assertLess(
            forge.events.index("reply:thread-1"), forge.events.index("resolve:thread-1")
        )
        self.assertLess(
            forge.events.index("resolve:thread-1"), forge.events.index("labels")
        )
        reply = forge.threads["thread-1"].comments[-1].body
        self.assertRegex(
            reply.splitlines()[-1],
            r"^<!-- HomericIntelligence:pr-review-closure:v1 "
            r"exchange=exchange-7 id=F-001 source=[0-9a-f]{64} "
            r"superseding=none terminal=[0-9a-f]{64} sha256=[0-9a-f]{64} -->$",
        )
        self.assertTrue(forge.threads["thread-1"].comments[-1].viewer_did_author)
        self.assertEqual({"state:implementation-go", "enhancement"}, forge.labels)

    def test_v1_delivery_replays_chained_author_artifact_refreshes(self) -> None:
        forge, binding, manifest = self.chained_author_manifest()

        result = self.delivery.deliver_go_v1(forge, binding, manifest)

        self.assertEqual("delivered", result.status)
        self.assertTrue(forge.threads["thread-1"].is_resolved)
        self.assertEqual(1, forge.events.count("terminal"))
        self.assertEqual(1, forge.events.count("labels"))

    def test_chained_author_refreshes_require_strict_publication_order(
        self,
    ) -> None:
        forge, binding, manifest = self.chained_author_manifest()
        forge.reviews[-1] = replace(
            forge.reviews[-1], submitted_at="2026-01-01T00:00:01Z"
        )

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, binding, manifest)

        self.assertEqual(["read"], forge.events)

    def test_round_three_revalidates_prior_terminal_finding_on_current_head(
        self,
    ) -> None:
        binding, threads, manifest = self.round_three_manifest()
        forge = FakeForge(self.delivery, threads=threads)
        forge.head_oid = "c" * 40
        self.add_history(forge, manifest)
        first = next(entry for entry in manifest.entries if entry.finding_id == "F-001")

        self.assertEqual("c" * 40, first.author_artifact_revision)
        self.assertEqual("author-event-2", first.author_event_review_id)
        self.assertEqual(
            ("F-001 passes after the second correction.",),
            first.closure_evidence,
        )

        result = self.delivery.deliver_go_v1(forge, binding, manifest)

        self.assertEqual("delivered", result.status)
        self.assertEqual(("thread-1", "thread-2"), result.resolved_thread_ids)
        self.assertIn(
            "F-001 passes after the second correction.",
            forge.threads["thread-1"].comments[-1].body,
        )
        self.assertEqual(1, forge.events.count("terminal"))
        self.assertEqual(1, forge.events.count("labels"))

    def test_coverage_gap_can_reach_go_without_an_author_event(self) -> None:
        exchange = self.delivery.review_exchange
        initial_visible = "Round 1 has an evidence gap."
        initial = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-evidence",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": {
                        "provider": "github",
                        "repository": "owner/repository",
                        "number": 7,
                        "url": "https://github.com/owner/repository/pull/7",
                    },
                    "requirements_sha256": "e" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "6" * 64,
                        "visible_content_sha256": exchange.sha256_text(initial_visible),
                    },
                    "scope": ["path:src/evidence.py"],
                    "coverage_complete": False,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        entries: tuple[Any, ...] = ()
        terminal_visible = self.delivery.terminal_visible_content(
            self.binding(), entries
        )
        terminal = exchange.reduce_request(
            {
                "previous": initial,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-evidence",
                    "prior_state_sha256": initial["state_sha256"],
                    "round": 2,
                    "artifact_binding": {
                        **initial["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(
                            terminal_visible
                        ),
                    },
                    "scope": ["path:src/evidence.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=terminal_visible,
            entries=entries,
            requirements_binding=self.requirements_binding(terminal),
        )
        forge = FakeForge(self.delivery, threads=())
        forge.reviews.append(
            self.carrier_record("evidence-gap-review", initial, initial_visible)
        )

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertEqual("review-2", result.terminal_review_id)
        self.assertEqual((), forge.published_terminal_comments)
        self.assertNotIn("reply", " ".join(forge.events))
        self.assertNotIn("resolve", " ".join(forge.events))

    def test_terminal_go_atomically_publishes_and_closes_new_inline_findings(
        self,
    ) -> None:
        manifest, inline = self.terminal_inline_manifest()
        forge = FakeForge(self.delivery, threads=())

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertEqual("review-1", result.terminal_review_id)
        self.assertEqual((inline,), forge.published_terminal_comments)
        self.assertEqual(1, forge.events.count("terminal"))
        self.assertEqual(1, forge.events.count("reply:terminal-thread-1"))
        self.assertEqual(1, forge.events.count("resolve:terminal-thread-1"))
        self.assertEqual(("terminal-thread-1",), result.resolved_thread_ids)
        self.assertTrue(forge.threads["terminal-thread-1"].is_resolved)

        invalid_forge = FakeForge(self.delivery, threads=())
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(
                invalid_forge,
                self.binding(),
                replace(
                    manifest,
                    comments=(),
                    summary_finding_ids=("F-001",),
                ),
            )
        self.assertNotIn("terminal", invalid_forge.events)

    def test_terminal_visible_content_binds_static_closure_entries(self) -> None:
        thread = self.owned_thread()
        manifest = self.v1_manifest(thread)
        extra = self.delivery.ReviewComment(
            id="changed-conversation",
            body="The conversation changed after manifest preparation.",
            author="reviewer",
            viewer_did_author=True,
        )
        changed = replace(thread, comments=(*thread.comments, extra))
        changed_entry = replace(
            manifest.entries[0],
            conversation_sha256=self.delivery.conversation_sha256(changed),
        )
        forged_manifest = replace(manifest, entries=(changed_entry,))
        forge = FakeForge(self.delivery, threads=(changed,))
        self.add_history(forge, manifest)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), forged_manifest)

        self.assertEqual(["read"], forge.events)

    def test_terminal_visible_content_is_checked_during_idempotent_replay(
        self,
    ) -> None:
        thread = self.owned_thread()
        manifest = self.v1_manifest(thread)
        forge = FakeForge(self.delivery, threads=(thread,))
        self.add_history(forge, manifest)
        self.assertEqual(
            "delivered",
            self.delivery.deliver_go_v1(forge, self.binding(), manifest).status,
        )
        root = forge.threads[thread.id].comments[0]
        changed = self.delivery.ReviewComment(
            id="post-terminal-change",
            body="A different conversation is made to look closed.",
            author="reviewer",
            viewer_did_author=True,
        )
        prior = self.delivery.ReviewThread(
            id=thread.id,
            is_resolved=False,
            comments=(root, changed),
        )
        changed_entry = replace(
            manifest.entries[0],
            conversation_sha256=self.delivery.conversation_sha256(prior),
        )
        forged_manifest = replace(manifest, entries=(changed_entry,))
        response = self.delivery.ReviewComment(
            id="forged-closure",
            body=self.delivery._closure_response_body(
                self.binding(), forged_manifest, changed_entry
            ),
            author="reviewer",
            viewer_did_author=True,
            published_at="2026-01-01T00:04:00Z",
        )
        forge.threads[thread.id] = replace(
            prior, is_resolved=True, comments=(*prior.comments, response)
        )
        forge.events.clear()

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), forged_manifest)

        self.assertEqual(["read"], forge.events)

    def test_dynamic_terminal_entries_remain_valid_on_recovery_and_replay(
        self,
    ) -> None:
        manifest, _ = self.terminal_inline_manifest()
        forge = FakeForge(self.delivery, threads=())
        forge.fail_resolve = True
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)
        forge.fail_resolve = False

        recovered = self.delivery.deliver_go_v1(forge, self.binding(), manifest)
        replayed = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", recovered.status)
        self.assertEqual("already_delivered", replayed.status)
        self.assertEqual(1, forge.events.count("terminal"))

    def test_terminal_inline_readback_must_match_the_atomic_review(self) -> None:
        mutations = (
            "missing",
            "foreign",
            "wrong_review",
            "wrong_head",
            "wrong_body",
            "wrong_path",
            "wrong_side",
            "wrong_original_line",
            "edited_root",
            "second_comment",
            "three_comments",
        )
        for mutation in mutations:
            manifest, _ = self.terminal_inline_manifest()
            forge = FakeForge(self.delivery, threads=())
            forge.terminal_thread_mutation = mutation

            with (
                self.subTest(mutation=mutation),
                self.assertRaises(self.delivery.DeliveryError) as caught,
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)

            self.assertEqual("partial", caught.exception.report.status)
            self.assertEqual(1, forge.events.count("terminal"))
            self.assertFalse(any(event.startswith("reply:") for event in forge.events))
            self.assertNotIn("labels", forge.events)

    def test_terminal_inline_readback_ignores_the_mutable_current_line(self) -> None:
        manifest, _ = self.terminal_inline_manifest()
        forge = FakeForge(self.delivery, threads=())
        forge.terminal_thread_mutation = "wrong_line"

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)

    def test_terminal_inline_manifest_rejects_incomplete_or_ambiguous_carriers(
        self,
    ) -> None:
        manifest, inline = self.terminal_inline_manifest()
        cases = (
            replace(manifest, comments=(inline,) * 101),
            replace(manifest, comments=(replace(inline, body="No marker."),)),
            replace(
                manifest,
                comments=(
                    replace(
                        inline,
                        body=inline.body.replace(
                            "exchange=exchange-inline",
                            "exchange=other-exchange",
                        ),
                    ),
                ),
            ),
            replace(
                manifest,
                comments=(replace(inline, path="src/other.py"),),
            ),
            replace(manifest, comments=(inline, inline)),
            replace(manifest, summary_finding_ids=("F-001",)),
            replace(manifest, summary_finding_ids=("F-002",)),
        )
        for candidate in cases:
            forge = FakeForge(self.delivery, threads=())

            with (
                self.subTest(candidate=candidate),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), candidate)

            self.assertEqual(["read"], forge.events)

    def test_terminal_go_keeps_nonanchorable_follow_up_in_the_summary(self) -> None:
        exchange = self.delivery.review_exchange
        visible = self.delivery.terminal_visible_content(self.binding(), ())
        terminal = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-summary",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": {
                        "provider": "github",
                        "repository": "owner/repository",
                        "number": 7,
                        "url": "https://github.com/owner/repository/pull/7",
                    },
                    "requirements_sha256": "9" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "6" * 64,
                        "visible_content_sha256": exchange.sha256_text(visible),
                    },
                    "scope": ["workflow:review-delivery"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [
                        {
                            "id": "F-001",
                            "category": None,
                            "severity": "minor",
                            "disposition": "suggestion",
                            "material_architecture": False,
                            "location": "review delivery workflow",
                            "impact": "The workflow description can be clearer.",
                            "evidence": ["The concern spans more than one file."],
                            "closure_condition": None,
                            "introduction": "initial",
                        }
                    ],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=visible,
            entries=(),
            requirements_binding=self.requirements_binding(terminal),
            comments=(),
            summary_finding_ids=("F-001",),
        )
        forge = FakeForge(self.delivery, threads=())

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertEqual((), forge.published_terminal_comments)
        self.assertEqual(1, forge.events.count("terminal"))
        self.assertEqual((), result.resolved_thread_ids)

    def test_adopted_native_finding_stays_required_in_terminal_state(self) -> None:
        thread = self.delivery.ReviewThread(
            id="legacy-thread",
            is_resolved=False,
            comments=(
                self.delivery.ReviewComment(
                    id="legacy/comment:7",
                    body="Legacy required finding.",
                    author="reviewer",
                    viewer_did_author=True,
                    review_head_oid="a" * 40,
                    path="src/example.py",
                    side="RIGHT",
                    line=7,
                    original_line=7,
                ),
            ),
            viewer_can_reply=True,
            viewer_can_resolve=True,
        )
        closure = self.closure(thread)
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread, closure)
        self.add_history(forge, manifest)

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        state_finding = manifest.state_envelope["state"]["findings"][0]
        self.assertEqual("native:legacy/comment:7", state_finding["id"])
        self.assertEqual("required", state_finding["disposition"])
        self.assertEqual("delivered", result.status)

    def test_native_database_id_alias_delivers_without_carrier_changes(self) -> None:
        root = self.delivery.ReviewComment(
            id="PRRC_verified_root",
            body="Legacy required finding.",
            author="reviewer",
            viewer_did_author=True,
            review_head_oid="a" * 40,
            path="src/example.py",
            side="RIGHT",
            line=7,
            original_line=7,
            full_database_id="3991324281",
        )
        thread = self.delivery.ReviewThread(
            id="legacy-thread", is_resolved=False, comments=(root,)
        )
        closure = replace(self.closure(thread), finding_id="native:3991324281")
        manifest = self.v1_manifest(thread, closure)
        envelope_before = json.dumps(manifest.state_envelope, sort_keys=True)
        forge = FakeForge(self.delivery, threads=(thread,))
        self.add_history(forge, manifest)

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertEqual(
            envelope_before, json.dumps(manifest.state_envelope, sort_keys=True)
        )
        self.assertEqual("native:3991324281", manifest.entries[0].finding_id)
        self.assertEqual("PRRC_verified_root", manifest.entries[0].origin_comment_id)

    def test_native_database_id_alias_preserves_no_go_carrier(self) -> None:
        proof, record = self.no_go_proof(finding_id="native:3991324281")
        root = self.delivery.ReviewComment(
            id="PRRC_verified_root",
            full_database_id="3991324281",
            body="Legacy required finding.",
            author="reviewer",
            review_head_oid="b" * 40,
            path="src/no_go.py",
            side="RIGHT",
            line=1,
            original_line=1,
        )
        thread = self.delivery.ReviewThread(
            id="legacy-thread", is_resolved=False, comments=(root,)
        )
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.labels = {"state:implementation-go"}
        forge.reviews.append(record)
        body_before = record.body
        result = self.delivery.deliver_no_go(forge, self.binding(), proof)
        self.assertEqual("delivered", result.status)
        self.assertEqual(body_before, forge.reviews[0].body)
        self.assertEqual({"state:implementation-no-go"}, forge.labels)

    def native_no_go_fixture(self, location: str = "src/no_go.py:1") -> tuple[Any, Any]:
        """Adopt an exact foreign root through the real exchange reducer."""
        proof, record = self.no_go_proof(
            finding_id="native:PRRC_verified_root", location=location
        )
        root = self.delivery.ReviewComment(
            id="PRRC_verified_root",
            full_database_id="3991324281",
            body="Legacy required finding.",
            author="github-advanced-security",
            viewer_did_author=False,
            review_head_oid="b" * 40,
            review_id="bot-review",
            path="src/no_go.py",
            side="RIGHT",
            line=1,
            original_line=1,
        )
        thread = self.delivery.ReviewThread(
            id="legacy-thread",
            is_resolved=False,
            comments=(root,),
            viewer_can_reply=False,
            viewer_can_resolve=False,
        )
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.labels = {"state:implementation-go"}
        forge.reviews.append(record)
        return proof, forge

    def test_native_adoption_no_go_does_not_require_thread_ownership(self) -> None:
        for author in ("github-advanced-security", "another-reviewer"):
            with self.subTest(author=author):
                proof, forge = self.native_no_go_fixture()
                thread = forge.threads["legacy-thread"]
                forge.threads[thread.id] = replace(
                    thread, comments=(replace(thread.comments[0], author=author),)
                )
                initial_threads = dict(forge.threads)
                initial_records = list(forge.reviews)

                result = self.delivery.deliver_no_go(forge, self.binding(), proof)
                repeated = self.delivery.deliver_no_go(forge, self.binding(), proof)

                self.assertEqual("delivered", result.status)
                self.assertEqual("already_delivered", repeated.status)
                self.assertEqual(initial_threads, forge.threads)
                self.assertEqual(initial_records, forge.reviews)
                self.assertEqual({"state:implementation-no-go"}, forge.labels)
                self.assertEqual(1, forge.events.count("labels:no-go"))
                self.assertFalse(
                    any(event.startswith("reply:") for event in forge.events)
                )
                self.assertFalse(
                    any(event.startswith("resolve:") for event in forge.events)
                )

    def test_native_adoption_recovers_exact_discussion_url_without_carrier_edit(
        self,
    ) -> None:
        location = f"{self.binding().url}#discussion_r3991324281"
        proof, forge = self.native_no_go_fixture(location)
        carrier = forge.reviews[0].body
        envelope = self.delivery.review_exchange.canonical_json(proof.state_envelope)

        result = self.delivery.deliver_no_go(forge, self.binding(), proof)

        self.assertEqual("delivered", result.status)
        self.assertEqual(carrier, forge.reviews[0].body)
        self.assertEqual(
            envelope,
            self.delivery.review_exchange.canonical_json(proof.state_envelope),
        )
        self.assertFalse(forge.threads["legacy-thread"].is_resolved)

    def test_native_adoption_rejects_unbound_locations_before_label_write(self) -> None:
        url = self.binding().url
        for location in (
            f"{url}#discussion_r3991324282",
            f"{url}#discussion_r03991324281",
            f"{url}#discussion_rPRRC_verified_root",
            f"{url}?view=1#discussion_r3991324281",
            f"{url}/#discussion_r3991324281",
            "https://github.com/owner/repository/pull/8#discussion_r3991324281",
            "https://github.com/other/repository/pull/7#discussion_r3991324281",
            "https://example.com/owner/repository/pull/7#discussion_r3991324281",
            "src/other.py:1",
            "src/no_go.py:2",
        ):
            with self.subTest(location=location):
                proof, forge = self.native_no_go_fixture(location)
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_no_go(forge, self.binding(), proof)
                self.assertEqual(["read"], forge.events)

    def test_native_adoption_retains_origin_and_carrier_guards(self) -> None:
        mutations: dict[str, dict[str, Any]] = {
            "missing-root": {"id": "PRRC_other"},
            "missing-head": {"review_head_oid": None},
            "missing-side": {"side": None},
            "wrong-path": {"path": "src/other.py"},
            "wrong-line": {"original_line": 2},
            "marked-root": {
                "body": "<!-- HomericIntelligence:review-finding:v1 exchange=other id=F-001 -->"
            },
        }
        for case, changes in mutations.items():
            with self.subTest(case=case):
                proof, forge = self.native_no_go_fixture()
                thread = forge.threads["legacy-thread"]
                forge.threads[thread.id] = replace(
                    thread, comments=(replace(thread.comments[0], **changes),)
                )
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_no_go(forge, self.binding(), proof)
                self.assertEqual(["read"], forge.events)
        for changes in (
            {"viewer_did_author": False},
            {"head_oid": "c" * 40},
            {"last_edited_at": "2026-01-01T00:03:00Z"},
        ):
            with self.subTest(carrier=changes):
                proof, forge = self.native_no_go_fixture()
                forge.reviews[0] = replace(forge.reviews[0], **changes)
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_no_go(forge, self.binding(), proof)
                self.assertEqual(["read"], forge.events)

    def test_native_url_adoption_requires_complete_root_metadata(self) -> None:
        for changes in (
            {"path": None},
            {"path": "../outside.py"},
            {"original_line": None},
            {"original_line": 0},
            {"full_database_id": None},
            {"full_database_id": "3991324282"},
        ):
            with self.subTest(root=changes):
                proof, forge = self.native_no_go_fixture(
                    f"{self.binding().url}#discussion_r3991324281"
                )
                thread = forge.threads["legacy-thread"]
                forge.threads[thread.id] = replace(
                    thread, comments=(replace(thread.comments[0], **changes),)
                )
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_no_go(forge, self.binding(), proof)
                self.assertEqual(["read"], forge.events)

    def test_native_adoption_go_requires_external_foreign_thread_resolution(
        self,
    ) -> None:
        root = self.delivery.ReviewComment(
            id="PRRC_verified_root",
            body="Legacy required finding.",
            author="github-advanced-security",
            viewer_did_author=False,
            review_head_oid="a" * 40,
            path="src/example.py",
            side="RIGHT",
            line=7,
            original_line=7,
        )
        thread = self.delivery.ReviewThread(
            id="legacy-thread", is_resolved=False, comments=(root,)
        )
        manifest = self.v1_manifest(thread, include_entry=False)
        forge = FakeForge(self.delivery, threads=(thread,))
        self.add_history(forge, manifest)
        with self.assertRaisesRegex(self.delivery.DeliveryError, "foreign open"):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)
        self.assertEqual(["read"], forge.events)

        forge.threads[thread.id] = replace(thread, is_resolved=True)
        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)
        self.assertEqual("delivered", result.status)
        self.assertEqual((), result.resolved_thread_ids)
        self.assertFalse(any(event.startswith("resolve:") for event in forge.events))
        self.assertFalse(any(event.startswith("reply:") for event in forge.events))

    def test_native_alias_rejects_ambiguous_or_unverified_roots_before_writes(
        self,
    ) -> None:
        for case in (
            "missing",
            "duplicate-database",
            "duplicate-graphql",
            "cross-form",
            "foreign",
            "head",
            "path",
            "side",
            "marker",
            "origin",
            "conversation",
        ):
            with self.subTest(case=case):
                root = self.delivery.ReviewComment(
                    id="PRRC_verified_root",
                    full_database_id="3991324281",
                    body="Legacy required finding.",
                    author="reviewer",
                    review_head_oid="a" * 40,
                    path="src/example.py",
                    side="RIGHT",
                    line=7,
                    original_line=7,
                )
                thread = self.delivery.ReviewThread(
                    id="legacy-thread", is_resolved=False, comments=(root,)
                )
                closure = replace(self.closure(thread), finding_id="native:3991324281")
                manifest = self.v1_manifest(thread, closure)
                threads: tuple[Any, ...] = (thread,)
                if case == "missing":
                    threads = (
                        replace(
                            thread, comments=(replace(root, full_database_id=None),)
                        ),
                    )
                elif case.startswith("duplicate") or case == "cross-form":
                    other = replace(
                        root, id="PRRC_other", full_database_id="3991324282"
                    )
                    if case == "duplicate-database":
                        other = replace(other, full_database_id=root.full_database_id)
                    elif case == "duplicate-graphql":
                        other = replace(other, id=root.id)
                    else:
                        other = replace(other, id="3991324281")
                    threads += (replace(thread, id="other-thread", comments=(other,)),)
                elif case == "origin":
                    manifest = replace(
                        manifest,
                        entries=(
                            replace(
                                manifest.entries[0], origin_comment_id="wrong-origin"
                            ),
                        ),
                    )
                elif case == "conversation":
                    threads = (
                        replace(
                            thread, comments=(replace(root, body="Changed finding."),)
                        ),
                    )
                else:
                    updates: dict[str, dict[str, object]] = {
                        "foreign": {"viewer_did_author": False},
                        "head": {"review_head_oid": "c" * 40},
                        "path": {"path": "src/other.py"},
                        "side": {"side": None},
                        "marker": {
                            "body": "<!-- HomericIntelligence:review-finding:v1 exchange=other id=F-001 -->"
                        },
                    }
                    threads = (
                        replace(thread, comments=(replace(root, **updates[case]),)),
                    )
                forge = FakeForge(self.delivery, threads=threads)
                self.add_history(forge, manifest)
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_go_v1(forge, self.binding(), manifest)
                self.assertEqual(["read"], forge.events)

    def test_new_native_manifest_keeps_graphql_identity_with_database_alias(
        self,
    ) -> None:
        root = self.delivery.ReviewComment(
            id="PRRC_verified_root",
            full_database_id="3991324281",
            body="Legacy finding.",
            author="reviewer",
            review_head_oid="a" * 40,
        )
        thread = self.delivery.ReviewThread(
            id="legacy-thread", is_resolved=False, comments=(root,)
        )
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.delivery.prepare_response_manifest(forge, self.binding())
        self.assertEqual(
            "native:PRRC_verified_root", manifest["entries"][0]["finding_id"]
        )

    def test_native_numeric_graphql_identity_remains_opaque(self) -> None:
        root = self.delivery.ReviewComment(
            id="01",
            full_database_id="3991324281",
            body="Legacy required finding.",
            author="reviewer",
            review_head_oid="a" * 40,
            path="src/example.py",
            side="RIGHT",
            line=7,
            original_line=7,
        )
        thread = self.delivery.ReviewThread(
            id="legacy-thread", is_resolved=False, comments=(root,)
        )
        manifest = self.v1_manifest(thread)
        forge = FakeForge(self.delivery, threads=(thread,))
        self.add_history(forge, manifest)
        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)
        self.assertEqual("delivered", result.status)
        self.assertEqual("native:01", manifest.entries[0].finding_id)

    def test_snapshot_retains_verified_database_id(self) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_gh(*arguments: str) -> str:
            calls.append(arguments)
            return self.github_snapshot_json()

        with patch.object(self.delivery, "_gh", side_effect=fake_gh):
            snapshot = self.delivery.GitHubForge(self.binding()).snapshot()
        self.assertEqual(
            "3991324281",
            getattr(snapshot.threads[0].comments[0], "full_database_id", None),
        )
        self.assertIn("fullDatabaseId", " ".join(calls[0]))

    def test_snapshot_rejects_invalid_database_id(self) -> None:
        for value in (None, "", "0", "01", "-1", "+1", "1.0", " 1", 1, True):
            with self.subTest(value=value):
                data = json.loads(self.github_snapshot_json())
                comment = data["data"]["repository"]["pullRequest"]["reviewThreads"][
                    "nodes"
                ][0]["comments"]["nodes"][0]
                comment["fullDatabaseId"] = value
                with (
                    patch.object(self.delivery, "_gh", return_value=json.dumps(data)),
                    self.assertRaises(self.delivery.DeliveryError),
                ):
                    self.delivery.GitHubForge(self.binding()).snapshot()

    def test_native_finding_requires_one_matching_root(self) -> None:
        root = self.delivery.ReviewComment(
            id="legacy-comment",
            body="Legacy required finding.",
            author="reviewer",
            viewer_did_author=True,
            review_head_oid="a" * 40,
            path="src/example.py",
            side="RIGHT",
            line=7,
            original_line=7,
        )
        thread = self.delivery.ReviewThread(
            id="legacy-thread",
            is_resolved=False,
            comments=(root,),
        )
        manifest = self.v1_manifest(thread, include_entry=False)
        forge = FakeForge(self.delivery, threads=())
        self.add_history(forge, manifest)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual(["read"], forge.events)

    def test_native_finding_location_must_match_its_unique_root(self) -> None:
        root = self.delivery.ReviewComment(
            id="legacy-comment",
            body="Legacy required finding.",
            author="reviewer",
            viewer_did_author=True,
            review_head_oid="a" * 40,
            path="src/different.py",
            side="RIGHT",
            line=9,
            original_line=9,
        )
        thread = self.delivery.ReviewThread(
            id="legacy-thread",
            is_resolved=False,
            comments=(root,),
        )
        manifest = self.v1_manifest(thread)
        forge = FakeForge(self.delivery, threads=(thread,))
        self.add_history(forge, manifest)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual(["read"], forge.events)

    def test_manifest_fields_must_equal_the_verified_author_state(self) -> None:
        thread = self.owned_thread()
        valid = self.closure(thread)
        cases: tuple[tuple[Any, dict[str, Any]], ...] = (
            (replace(valid, author_answer="fix_with_tradeoff"), {}),
            (replace(valid, author_artifact_revision="c" * 40), {}),
            (replace(valid, author_event_review_id="different-review"), {}),
            (replace(valid, closure_evidence=("Caller-only evidence.",)), {}),
        )
        for closure, options in cases:
            forge = FakeForge(self.delivery, threads=(thread,))
            manifest = self.v1_manifest(
                thread,
                closure,
                state_author_kind="fix",
                state_author_revision="b" * 40,
                state_reviewer_evidence=(
                    "The terminal assessment checked the artifact."
                ),
                **options,
            )
            self.add_history(forge, manifest)
            with (
                self.subTest(closure=closure),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)
            self.assertNotIn("terminal", forge.events)

    def test_risk_acceptance_requires_an_exact_authoritative_forge_receipt(
        self,
    ) -> None:
        thread = self.owned_thread(review_head_oid="b" * 40)
        prior_state_sha256 = self.risk_authority_prior_state_sha256(thread)
        authority_body = self.authority_body(
            action="human_decision",
            exchange_id="exchange-7",
            requirements_sha256="c" * 64,
            prior_state_sha256=prior_state_sha256,
            supersedes_state_sha256=None,
            decisions=[
                {
                    "finding_id": "F-001",
                    "kind": "accept_risk",
                    "closure_condition": None,
                }
            ],
        )
        receipt = {
            "reference": "review:authority-1",
            "sha256": self.delivery.review_exchange.sha256_text(authority_body),
        }
        closure = replace(
            self.closure(thread),
            author_answer="risk_acceptance",
            reviewer_disposition="accepted_risk",
            closure_evidence=("The author supplied bound closure evidence.",),
            authority_receipt=receipt,
        )
        manifest = self.v1_manifest(thread, closure)
        cases = (
            ("OWNER", "ADMIN", True),
            ("NONE", "ADMIN", False),
            ("MEMBER", "WRITE", False),
        )
        for association, permission, succeeds in cases:
            forge = FakeForge(self.delivery, threads=(thread,))
            self.add_history(forge, manifest)
            forge.reviews.append(
                self.delivery.ReviewRecord(
                    id="authority-1",
                    body=authority_body,
                    head_oid="b" * 40,
                    author="maintainer",
                    viewer_did_author=False,
                    includes_created_edit=False,
                    state="COMMENTED",
                    author_association=association,
                    author_permission=permission,
                    submitted_at="2026-01-01T00:00:05Z",
                )
            )
            if succeeds:
                result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)
                self.assertEqual("delivered", result.status)
            else:
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_go_v1(forge, self.binding(), manifest)
                self.assertNotIn("terminal", forge.events)

    def test_authority_receipt_must_follow_its_bound_author_event(self) -> None:
        thread = self.owned_thread(review_head_oid="b" * 40)
        prior_state_sha256 = self.risk_authority_prior_state_sha256(thread)
        for record_kind in ("review", "comment"):
            self.review_sequence = 0
            reference = f"{record_kind}:authority-1"
            authority_body = self.authority_body(
                action="human_decision",
                exchange_id="exchange-7",
                requirements_sha256="c" * 64,
                prior_state_sha256=prior_state_sha256,
                supersedes_state_sha256=None,
                decisions=[
                    {
                        "finding_id": "F-001",
                        "kind": "accept_risk",
                        "closure_condition": None,
                    }
                ],
            )
            receipt = {
                "reference": reference,
                "sha256": self.delivery.review_exchange.sha256_text(authority_body),
            }
            closure = replace(
                self.closure(thread),
                author_answer="risk_acceptance",
                reviewer_disposition="accepted_risk",
                closure_evidence=("The author supplied bound closure evidence.",),
                authority_receipt=receipt,
            )
            manifest = self.v1_manifest(thread, closure)
            authority_comment = self.delivery.ReviewComment(
                id="authority-1",
                body=authority_body,
                author="maintainer",
                viewer_did_author=False,
                author_association="OWNER",
                author_permission="ADMIN",
                review_id="authority-parent",
                published_at="2026-01-01T00:00:01.500000Z",
            )
            authority_thread = self.delivery.ReviewThread(
                id="authority-thread",
                is_resolved=True,
                comments=(authority_comment,),
            )
            forge = FakeForge(
                self.delivery,
                threads=(
                    thread,
                    *((authority_thread,) if record_kind == "comment" else ()),
                ),
            )
            self.add_history(forge, manifest)
            if record_kind == "review":
                forge.reviews.append(
                    self.delivery.ReviewRecord(
                        id="authority-1",
                        body=authority_body,
                        head_oid="b" * 40,
                        author="maintainer",
                        viewer_did_author=False,
                        includes_created_edit=False,
                        state="COMMENTED",
                        author_association="OWNER",
                        author_permission="ADMIN",
                        submitted_at="2026-01-01T00:00:01.500000Z",
                    )
                )

            with self.subTest(record_kind=record_kind):
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_go_v1(forge, self.binding(), manifest)
                self.assertNotIn("terminal", forge.events)
                self.assertNotIn("labels", forge.events)

    def test_edited_authority_receipt_must_precede_persisted_terminal(self) -> None:
        thread = self.owned_thread(review_head_oid="b" * 40)
        prior_state_sha256 = self.risk_authority_prior_state_sha256(thread)
        for record_kind in ("review", "comment"):
            self.review_sequence = 0
            reference = f"{record_kind}:authority-1"
            authority_body = self.authority_body(
                action="human_decision",
                exchange_id="exchange-7",
                requirements_sha256="c" * 64,
                prior_state_sha256=prior_state_sha256,
                supersedes_state_sha256=None,
                decisions=[
                    {
                        "finding_id": "F-001",
                        "kind": "accept_risk",
                        "closure_condition": None,
                    }
                ],
            )
            receipt = {
                "reference": reference,
                "sha256": self.delivery.review_exchange.sha256_text(authority_body),
            }
            closure = replace(
                self.closure(thread),
                author_answer="risk_acceptance",
                reviewer_disposition="accepted_risk",
                closure_evidence=("The author supplied bound closure evidence.",),
                authority_receipt=receipt,
            )
            manifest = self.v1_manifest(thread, closure)
            authority_comment = self.delivery.ReviewComment(
                id="authority-1",
                body=authority_body,
                author="maintainer",
                viewer_did_author=False,
                author_association="OWNER",
                author_permission="ADMIN",
                review_id="authority-parent",
                published_at="2026-01-01T00:00:03Z",
            )
            authority_thread = self.delivery.ReviewThread(
                id="authority-thread",
                is_resolved=True,
                comments=(authority_comment,),
            )
            forge = FakeForge(
                self.delivery,
                threads=(
                    thread,
                    *((authority_thread,) if record_kind == "comment" else ()),
                ),
            )
            self.add_history(forge, manifest)
            authority_review = self.delivery.ReviewRecord(
                id="authority-1",
                body=authority_body,
                head_oid="b" * 40,
                author="maintainer",
                viewer_did_author=False,
                includes_created_edit=False,
                state="COMMENTED",
                author_association="OWNER",
                author_permission="ADMIN",
                submitted_at="2026-01-01T00:00:03Z",
            )
            if record_kind == "review":
                forge.reviews.append(authority_review)

            first = self.delivery.deliver_go_v1(forge, self.binding(), manifest)
            self.assertEqual("delivered", first.status)
            authority_record = (
                authority_review if record_kind == "review" else authority_comment
            )
            object.__setattr__(
                authority_record,
                "last_edited_at",
                "2026-01-01T00:02:00Z",
            )
            forge.events.clear()

            with self.subTest(record_kind=record_kind):
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_go_v1(forge, self.binding(), manifest)
                self.assertEqual(["read"], forge.events)

    def test_comment_authority_requires_ordered_publication(self) -> None:
        thread = self.owned_thread(review_head_oid="b" * 40)
        prior_state_sha256 = self.risk_authority_prior_state_sha256(thread)
        for published_at in (None, "2026-01-01T00:02:00Z"):
            self.review_sequence = 0
            authority_body = self.authority_body(
                action="human_decision",
                exchange_id="exchange-7",
                requirements_sha256="c" * 64,
                prior_state_sha256=prior_state_sha256,
                supersedes_state_sha256=None,
                decisions=[
                    {
                        "finding_id": "F-001",
                        "kind": "accept_risk",
                        "closure_condition": None,
                    }
                ],
            )
            receipt = {
                "reference": "comment:authority-1",
                "sha256": self.delivery.review_exchange.sha256_text(authority_body),
            }
            closure = replace(
                self.closure(thread),
                author_answer="risk_acceptance",
                reviewer_disposition="accepted_risk",
                closure_evidence=("The author supplied bound closure evidence.",),
                authority_receipt=receipt,
            )
            manifest = self.v1_manifest(thread, closure)
            authority_comment = self.delivery.ReviewComment(
                id="authority-1",
                body=authority_body,
                author="maintainer",
                viewer_did_author=False,
                author_association="OWNER",
                author_permission="ADMIN",
                review_id="authority-parent",
                published_at=published_at,
            )
            authority_thread = self.delivery.ReviewThread(
                id="authority-thread",
                is_resolved=True,
                comments=(authority_comment,),
            )
            forge = FakeForge(
                self.delivery,
                threads=(thread, authority_thread),
            )
            self.add_history(forge, manifest)

            with (
                self.subTest(published_at=published_at),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)

    def test_risk_authority_record_cannot_be_reused_across_contexts(self) -> None:
        thread = self.owned_thread(review_head_oid="b" * 40)
        valid = json.loads(
            self.authority_body(
                action="human_decision",
                exchange_id="exchange-7",
                requirements_sha256="c" * 64,
                prior_state_sha256=self.risk_authority_prior_state_sha256(thread),
                supersedes_state_sha256=None,
                decisions=[
                    {
                        "finding_id": "F-001",
                        "kind": "accept_risk",
                        "closure_condition": None,
                    }
                ],
            )
        )
        cases: list[dict[str, Any]] = []
        for field, value in (
            ("exchange_id", "other-exchange"),
            ("requirements_sha256", "f" * 64),
            ("prior_state_sha256", "f" * 64),
        ):
            record = {**valid, field: value}
            cases.append(record)
        cases.append(
            {
                **valid,
                "target": {**valid["target"], "number": 8},
            }
        )
        cases.append(
            {
                **valid,
                "decisions": [
                    {
                        "finding_id": "F-002",
                        "kind": "accept_risk",
                        "closure_condition": None,
                    }
                ],
            }
        )
        cases.append(
            {
                **valid,
                "action": "reframe",
                "supersedes_state_sha256": "e" * 64,
                "decisions": [],
            }
        )
        for authority_record in cases:
            body = self.delivery.review_exchange.canonical_json(authority_record)
            receipt = {
                "reference": "review:authority-1",
                "sha256": self.delivery.review_exchange.sha256_text(body),
            }
            closure = replace(
                self.closure(thread),
                author_answer="risk_acceptance",
                reviewer_disposition="accepted_risk",
                closure_evidence=("The author supplied bound closure evidence.",),
                authority_receipt=receipt,
            )
            manifest = self.v1_manifest(thread, closure)
            forge = FakeForge(self.delivery, threads=(thread,))
            self.add_history(forge, manifest)
            forge.reviews.append(
                self.delivery.ReviewRecord(
                    id="authority-1",
                    body=body,
                    head_oid="b" * 40,
                    author="maintainer",
                    viewer_did_author=False,
                    includes_created_edit=False,
                    state="COMMENTED",
                    author_association="OWNER",
                    author_permission="ADMIN",
                )
            )

            with (
                self.subTest(authority_record=authority_record),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)
            self.assertNotIn("terminal", forge.events)

    def test_v1_contest_is_answered_once_with_a_terminal_disposition(self) -> None:
        thread = self.owned_thread()
        closure = self.closure(
            thread, author_kind="contest", reviewer_disposition="withdrawn"
        )
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread, closure)
        self.add_history(forge, manifest)

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertRegex(
            forge.threads["thread-1"].comments[-1].body.splitlines()[-1],
            r"^<!-- HomericIntelligence:pr-review-closure:v1 "
            r"exchange=exchange-7 id=F-001 source=[0-9a-f]{64} "
            r"superseding=none terminal=[0-9a-f]{64} sha256=[0-9a-f]{64} -->$",
        )
        self.assertTrue(forge.threads["thread-1"].is_resolved)

    def test_reviewer_can_withdraw_each_corrective_author_answer(self) -> None:
        for author_kind in ("fix", "fix_with_tradeoff", "risk_acceptance"):
            thread = self.owned_thread()
            closure = self.closure(
                thread,
                author_kind=author_kind,
                reviewer_disposition="withdrawn",
            )
            manifest = self.v1_manifest(thread, closure)
            forge = FakeForge(self.delivery, threads=(thread,))
            self.add_history(forge, manifest)

            with self.subTest(author_kind=author_kind):
                result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

            self.assertEqual("delivered", result.status)
            self.assertRegex(
                forge.threads["thread-1"].comments[-1].body.splitlines()[-1],
                r"^<!-- HomericIntelligence:pr-review-closure:v1 "
                r"exchange=exchange-7 id=F-001 source=[0-9a-f]{64} "
                r"superseding=none terminal=[0-9a-f]{64} "
                r"sha256=[0-9a-f]{64} -->$",
            )
            self.assertTrue(forge.threads["thread-1"].is_resolved)

    def test_foreign_copy_of_generated_closure_reply_is_not_recovery_proof(
        self,
    ) -> None:
        thread = self.owned_thread()
        manifest = self.v1_manifest(thread)
        entry = manifest.entries[0]
        copied_reply = self.delivery.ReviewComment(
            id="foreign-copy",
            body=self.delivery._closure_response_body(self.binding(), manifest, entry),
            author="other-reviewer",
            viewer_did_author=False,
        )
        changed = replace(thread, comments=(*thread.comments, copied_reply))
        forge = FakeForge(self.delivery, threads=(changed,))
        self.add_history(forge, manifest)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertNotIn("terminal", forge.events)
        self.assertNotIn("resolve:thread-1", forge.events)

    def test_v1_preflight_rejects_foreign_or_incapable_open_threads(self) -> None:
        cases = (
            self.owned_thread(owned=False),
            self.owned_thread(can_reply=False),
            self.owned_thread(can_resolve=False),
        )
        for thread in cases:
            forge = FakeForge(self.delivery, threads=(thread,))
            manifest = self.v1_manifest(thread)
            self.add_history(forge, manifest)
            with (
                self.subTest(thread=thread),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)
            self.assertEqual(["read"], forge.events)

    def test_same_head_requirements_drift_or_collection_failure_withholds_go(
        self,
    ) -> None:
        cases = (
            "scope_body_drift",
            "closing_reference_drift",
            "linked_content_drift",
            "linked_comment_drift",
            "selected_url_set_drift",
            "collection_failure",
        )
        for failure in cases:
            thread = self.owned_thread()
            manifest = self.v1_manifest(thread)
            forge = FakeForge(self.delivery, threads=(thread,))
            forge.requirements_failure = failure
            self.add_history(forge, manifest)

            with (
                self.subTest(failure=failure),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)

            self.assertNotIn("terminal", forge.events)
            self.assertNotIn("labels", forge.events)

    def test_state_binds_the_retained_scope_and_requirements_before_delivery(
        self,
    ) -> None:
        thread = self.owned_thread()
        manifest = self.v1_manifest(thread)
        proof, record = self.no_go_proof()
        cases = (
            (
                replace(
                    manifest,
                    requirements_binding=replace(
                        manifest.requirements_binding,
                        reviewed_scope_sha256="9" * 64,
                    ),
                ),
                None,
            ),
            (
                replace(
                    manifest,
                    requirements_binding=replace(
                        manifest.requirements_binding,
                        requirements_sha256="9" * 64,
                    ),
                ),
                None,
            ),
            (
                None,
                replace(
                    proof,
                    requirements_binding=replace(
                        proof.requirements_binding,
                        reviewed_scope_sha256="9" * 64,
                    ),
                ),
            ),
            (
                None,
                replace(
                    proof,
                    requirements_binding=replace(
                        proof.requirements_binding,
                        requirements_sha256="9" * 64,
                    ),
                ),
            ),
        )
        for go_manifest, no_go_proof in cases:
            forge = FakeForge(
                self.delivery,
                threads=(
                    (thread,)
                    if go_manifest is not None
                    else self.carrier_threads(proof.state_envelope, proof.review_id)
                ),
            )
            if go_manifest is not None:
                self.add_history(forge, go_manifest)
            else:
                forge.reviews.append(record)
                forge.labels = {"state:implementation-go"}
            with (
                self.subTest(go=go_manifest is not None),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                if go_manifest is not None:
                    self.delivery.deliver_go_v1(forge, self.binding(), go_manifest)
                else:
                    self.delivery.deliver_no_go(forge, self.binding(), no_go_proof)
            self.assertNotIn("terminal", forge.events)
            self.assertNotIn("labels", forge.events)
            self.assertNotIn("labels:no-go", forge.events)

    def test_prior_anchored_finding_requires_its_atomic_origin_thread(self) -> None:
        thread = self.owned_thread()
        manifest = replace(self.v1_manifest(thread), entries=())
        forge = FakeForge(self.delivery, threads=())
        self.add_history(forge, manifest)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual(["read"], forge.events)

    def test_selected_author_event_review_cannot_own_inline_roots(self) -> None:
        thread = self.owned_thread()
        extra = self.delivery.ReviewThread(
            id="author-inline-thread",
            is_resolved=True,
            comments=(
                self.delivery.ReviewComment(
                    id="author-inline-root",
                    body="An author-event review cannot contain an inline finding.",
                    author="reviewer",
                    viewer_did_author=True,
                    review_head_oid="b" * 40,
                    review_id="author-event-1",
                    path="src/example.py",
                    side="RIGHT",
                    line=8,
                ),
            ),
        )
        manifest = self.v1_manifest(thread)
        forge = FakeForge(self.delivery, threads=(thread, extra))
        self.add_history(forge, manifest)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertNotIn("terminal", forge.events)
        self.assertNotIn("labels", forge.events)

    def test_selected_reviewer_review_rejects_unledgered_inline_roots(self) -> None:
        bodies = (
            "Unmarked extra root.",
            (
                "Wrong exchange.\n\n"
                "<!-- HomericIntelligence:review-finding:v1 "
                "exchange=other-exchange id=F-002 -->"
            ),
            (
                "Unknown finding.\n\n"
                "<!-- HomericIntelligence:review-finding:v1 "
                "exchange=exchange-7 id=F-002 -->"
            ),
        )
        for index, body in enumerate(bodies, start=1):
            thread = self.owned_thread()
            extra = self.delivery.ReviewThread(
                id=f"extra-thread-{index}",
                is_resolved=True,
                comments=(
                    self.delivery.ReviewComment(
                        id=f"extra-root-{index}",
                        body=body,
                        author="reviewer",
                        viewer_did_author=True,
                        review_head_oid="a" * 40,
                        review_id="initial-review-1",
                        path="src/extra.py",
                        side="RIGHT",
                        line=index,
                    ),
                ),
            )
            manifest = self.v1_manifest(thread)
            forge = FakeForge(self.delivery, threads=(thread, extra))
            self.add_history(forge, manifest)

            with (
                self.subTest(index=index),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)

            self.assertNotIn("terminal", forge.events)
            self.assertNotIn("labels", forge.events)

    def test_inline_finding_must_bind_its_origin_review_and_location(self) -> None:
        original = self.owned_thread()
        cases = (
            replace(
                original,
                comments=(replace(original.comments[0], review_id="other-review"),),
            ),
            replace(
                original,
                comments=(replace(original.comments[0], path="src/other.py"),),
            ),
            replace(
                original,
                comments=(replace(original.comments[0], original_line=8),),
            ),
        )
        for thread in cases:
            forge = FakeForge(self.delivery, threads=(thread,))
            manifest = self.v1_manifest(thread)
            self.add_history(forge, manifest)

            with (
                self.subTest(thread=thread),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)

            self.assertNotIn("terminal", forge.events)

    def test_inline_finding_uses_immutable_original_line(self) -> None:
        for current_line in (None, 19):
            original = self.owned_thread()
            root = replace(original.comments[0], line=current_line, original_line=7)
            thread = replace(original, comments=(root,))
            manifest = self.v1_manifest(thread)
            forge = FakeForge(self.delivery, threads=(thread,))
            self.add_history(forge, manifest)

            with self.subTest(current_line=current_line):
                result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)
                self.assertEqual("delivered", result.status)

    def test_selected_carrier_reviews_require_strict_publication_order(self) -> None:
        cases = (
            (None, "2026-01-01T00:00:02Z", "missing"),
            (
                "2026-01-01T00:00:03Z",
                "2026-01-01T00:00:02Z",
                "reversed",
            ),
            (
                "2026-01-01T00:00:02Z",
                "2026-01-01T00:00:02Z",
                "tied",
            ),
            ("not-a-time", "2026-01-01T00:00:02Z", "ambiguous"),
        )
        for initial_time, author_time, case in cases:
            thread = self.owned_thread()
            manifest = self.v1_manifest(thread)
            forge = FakeForge(self.delivery, threads=(thread,))
            initial, author = self.carrier_history[
                manifest.state_envelope["state_sha256"]
            ]
            initial = replace(initial, submitted_at=initial_time)
            author = replace(author, submitted_at=author_time)
            forge.reviews.extend((initial, author))

            with self.subTest(case=case):
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_go_v1(forge, self.binding(), manifest)
                self.assertNotIn("terminal", forge.events)
                self.assertNotIn("labels", forge.events)

    def test_reviewer_carrier_must_follow_its_author_event(self) -> None:
        binding, threads, manifest = self.round_three_manifest()
        forge = FakeForge(self.delivery, threads=threads)
        forge.head_oid = binding.head_oid
        history = list(self.carrier_history[manifest.state_envelope["state_sha256"]])
        history[2] = replace(history[2], submitted_at="2026-01-01T00:00:01.500000Z")
        forge.reviews.extend(history)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, binding, manifest)

        self.assertNotIn("terminal", forge.events)
        self.assertNotIn("labels", forge.events)

    def test_finding_marker_must_be_one_final_top_level_line(self) -> None:
        marker = (
            "<!-- HomericIntelligence:review-finding:v1 "
            "exchange=exchange-7 id=F-001 -->"
        )
        cases = (
            f"```html\n{marker}",
            f"<details>\n{marker}",
            f"<!-- hidden\n{marker}",
            f"<textarea>\n{marker}",
            f"{marker}\nvisible text",
            f"{marker}\n{marker}",
        )
        for body in cases:
            with (
                self.subTest(body=body),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery._finding_marker(
                    self.delivery.ReviewComment(
                        id="comment", body=body, author="reviewer"
                    )
                )

    def test_v1_rejects_missing_author_event_and_nonterminal_disposition(self) -> None:
        contested = self.owned_thread()
        unanswered = self.closure(
            contested, author_kind="contest", reviewer_disposition="withdrawn"
        )
        manifest = self.v1_manifest(contested, unanswered)
        forge = FakeForge(self.delivery, threads=(contested,))
        forge.reviews.extend(
            self.carrier_history[manifest.state_envelope["state_sha256"]][:1]
        )
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)
        self.assertEqual(["read"], forge.events)

        thread = self.owned_thread()
        closure = self.closure(thread)
        invalid = self.delivery.ThreadClosure(
            **{
                **closure.__dict__,
                "reviewer_disposition": "partial",
            }
        )
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.validate_closure_manifest(
                self.binding(),
                self.delivery.ClosureManifest(
                    state_envelope=self.v1_manifest(thread).state_envelope,
                    terminal_visible_content=self.v1_manifest(
                        thread
                    ).terminal_visible_content,
                    entries=(invalid,),
                    requirements_binding=self.v1_manifest(thread).requirements_binding,
                ),
                FakeForge(self.delivery, threads=(thread,)).snapshot(),
            )

    def test_v1_rejects_stale_terminal_state_before_writes(self) -> None:
        _, threads, stale = self.round_three_manifest()
        forge = FakeForge(self.delivery, threads=threads)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), stale)

        self.assertEqual(["read"], forge.events)

    def test_terminal_publication_failure_or_mismatch_withholds_label(self) -> None:
        cases = ("fail_terminal", "edit_terminal", "duplicate_terminal")
        for attribute in cases:
            thread = self.owned_thread()
            forge = FakeForge(self.delivery, threads=(thread,))
            setattr(forge, attribute, True)
            manifest = self.v1_manifest(thread)
            self.add_history(forge, manifest)
            with (
                self.subTest(attribute=attribute),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)
            self.assertNotIn("labels", forge.events)
            self.assertNotIn("reply:thread-1", forge.events)
            self.assertNotIn("resolve:thread-1", forge.events)

    def test_delivery_reports_partial_state_for_forge_races(self) -> None:
        cases = (
            "race_comment_after_reply",
            "drift_head_after_resolve",
            "add_late_thread_after_resolve",
            "drift_head_on_label",
        )
        for attribute in cases:
            thread = self.owned_thread()
            forge = FakeForge(self.delivery, threads=(thread,))
            manifest = self.v1_manifest(thread)
            self.add_history(forge, manifest)
            setattr(forge, attribute, True)

            with (
                self.subTest(attribute=attribute),
                self.assertRaises(self.delivery.DeliveryError) as caught,
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)

            self.assertEqual("partial", caught.exception.report.status)
            self.assertTrue(caught.exception.report.recovery_read_required)
            self.assertEqual(1, forge.events.count("terminal"))

    def test_write_failures_return_structured_partial_recovery_state(self) -> None:
        cases = (
            ("fail_terminal", "terminal review", (), (), ("thread-1",), None),
            ("fail_reply", "reply", (), (), ("thread-1",), "review-3"),
            (
                "fail_resolve",
                "resolve",
                ("thread-1",),
                (),
                ("thread-1",),
                "review-3",
            ),
            (
                "fail_label",
                "implementation label",
                ("thread-1",),
                ("thread-1",),
                (),
                "review-3",
            ),
        )
        for attribute, operation, responded, resolved, pending, terminal_id in cases:
            thread = self.owned_thread()
            forge = FakeForge(self.delivery, threads=(thread,))
            manifest = self.v1_manifest(thread)
            self.add_history(forge, manifest)
            setattr(forge, attribute, True)

            with self.subTest(attribute=attribute):
                try:
                    self.delivery.deliver_go_v1(forge, self.binding(), manifest)
                except self.delivery.DeliveryError as error:
                    report = error.report
                else:
                    self.fail("The injected forge write failure was accepted.")
                self.assertIsNotNone(report)
                self.assertEqual("partial", report.status)
                self.assertEqual(operation, report.uncertain_operation)
                self.assertEqual(responded, report.responded_thread_ids)
                self.assertEqual(resolved, report.resolved_thread_ids)
                self.assertEqual(pending, report.pending_thread_ids)
                self.assertEqual(terminal_id, report.terminal_review_id)
                self.assertTrue(report.recovery_read_required)
                self.assertEqual("b" * 40, report.observed_head_oid)
                self.assertIn("state:implementation-no-go", report.observed_labels)

    def test_conflicting_authored_terminal_state_withholds_go(self) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)
        exchange = self.delivery.review_exchange
        visible = "Conflicting terminal assessment."
        conflicting = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": manifest.state_envelope["state"]["target"],
                    "requirements_sha256": "c" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "9" * 64,
                        "visible_content_sha256": exchange.sha256_text(visible),
                    },
                    "scope": ["path:src/example.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        forge.reviews.append(
            self.carrier_record("conflicting-terminal", conflicting, visible)
        )

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertNotIn("terminal", forge.events)

    def test_forked_current_head_nonterminal_state_withholds_go(self) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)
        exchange = self.delivery.review_exchange
        initial = exchange.extract_carrier(forge.reviews[0].body)
        author_event = exchange.extract_carrier(forge.reviews[1].body)
        author = exchange.reduce_request(
            {
                "previous": initial,
                "event": self.delivery._author_event_input(author_event),
            }
        )["envelope"]
        visible = "A forked round says the finding is still present."
        forked = exchange.reduce_request(
            {
                "previous": author,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": author["state_sha256"],
                    "round": 2,
                    "artifact_binding": {
                        **author["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(visible),
                    },
                    "scope": ["path:src/example.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [
                        {
                            "finding_id": "F-001",
                            "kind": "still_present",
                            "evidence": ["The fork observed a remaining failure."],
                            "closure_condition": None,
                        }
                    ],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        forge.reviews.append(self.carrier_record("forked-state", forked, visible))

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertNotIn("terminal", forge.events)

    def test_historical_state_fork_withholds_go(self) -> None:
        binding, threads, manifest = self.round_three_manifest()
        forge = FakeForge(self.delivery, threads=threads)
        forge.head_oid = "c" * 40
        self.add_history(forge, manifest)
        exchange = self.delivery.review_exchange
        initial = exchange.extract_carrier(forge.reviews[0].body)
        author_event = exchange.extract_carrier(forge.reviews[1].body)
        author = exchange.reduce_request(
            {
                "previous": initial,
                "event": self.delivery._author_event_input(author_event),
            }
        )["envelope"]
        visible = "A historical fork resolved both findings."
        forked = exchange.reduce_request(
            {
                "previous": author,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": author["state_sha256"],
                    "round": 2,
                    "artifact_binding": {
                        **author["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(visible),
                    },
                    "scope": ["path:src/example.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [
                        {
                            "finding_id": finding_id,
                            "kind": "resolve",
                            "evidence": [f"{finding_id} passes on this fork."],
                            "closure_condition": None,
                        }
                        for finding_id in ("F-001", "F-002")
                    ],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        forge.reviews.append(self.carrier_record("historical-fork", forked, visible))

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, binding, manifest)

        self.assertNotIn("terminal", forge.events)

    def test_reframes_cannot_hide_a_historical_reviewer_fork(self) -> None:
        exchange = self.delivery.review_exchange
        historical_thread = self.owned_thread()
        seed = self.v1_manifest(historical_thread)
        initial_record, author_record = self.carrier_history[
            seed.state_envelope["state_sha256"]
        ]
        initial = exchange.extract_carrier(initial_record.body)
        author_event = exchange.extract_carrier(author_record.body)
        author = exchange.reduce_request(
            {
                "previous": initial,
                "event": self.delivery._author_event_input(author_event),
            }
        )["envelope"]
        branch_one = seed.state_envelope
        branch_two_visible = "A conflicting reviewer branch also resolves the finding."
        branch_two = exchange.reduce_request(
            {
                "previous": author,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": author["state_sha256"],
                    "round": 2,
                    "artifact_binding": {
                        **author["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(
                            branch_two_visible
                        ),
                    },
                    "scope": ["path:src/example.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [
                        {
                            "finding_id": "F-001",
                            "kind": "resolve",
                            "evidence": ["The conflicting branch reports a pass."],
                            "closure_condition": None,
                        }
                    ],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]

        middle_visible = "The first reframe changes the requirements."
        middle_authority_body = self.authority_body(
            action="reframe",
            exchange_id="exchange-middle",
            requirements_sha256="d" * 64,
            supersedes_state_sha256=branch_one["state_sha256"],
            decisions=[],
        )
        middle_receipt = {
            "reference": "review:middle-authority",
            "sha256": exchange.sha256_text(middle_authority_body),
        }
        middle = exchange.reduce_request(
            {
                "previous": branch_one,
                "event": {
                    "event_type": "reframe",
                    "exchange_id": "exchange-middle",
                    "prior_state_sha256": branch_one["state_sha256"],
                    "round": 1,
                    "surface": "pull_request",
                    "target": branch_one["state"]["target"],
                    "requirements_sha256": "d" * 64,
                    "supersedes_state_sha256": branch_one["state_sha256"],
                    "superseded_exchange_ids": ["exchange-7"],
                    "authority_receipt": middle_receipt,
                    "artifact_binding": {
                        **branch_one["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(middle_visible),
                    },
                    "scope": ["path:src/middle.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]

        returned_visible = "The second reframe restores the initial requirements."
        returned_authority_body = self.authority_body(
            action="reframe",
            exchange_id="exchange-returned",
            requirements_sha256="c" * 64,
            supersedes_state_sha256=middle["state_sha256"],
            decisions=[],
        )
        returned_receipt = {
            "reference": "review:returned-authority",
            "sha256": exchange.sha256_text(returned_authority_body),
        }
        returned = exchange.reduce_request(
            {
                "previous": middle,
                "event": {
                    "event_type": "reframe",
                    "exchange_id": "exchange-returned",
                    "prior_state_sha256": middle["state_sha256"],
                    "round": 1,
                    "surface": "pull_request",
                    "target": middle["state"]["target"],
                    "requirements_sha256": "c" * 64,
                    "supersedes_state_sha256": middle["state_sha256"],
                    "superseded_exchange_ids": ["exchange-7", "exchange-middle"],
                    "authority_receipt": returned_receipt,
                    "artifact_binding": {
                        **middle["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(
                            returned_visible
                        ),
                    },
                    "scope": ["path:src/returned.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]

        binding = self.binding("c" * 40)
        terminal_visible = self.delivery.terminal_visible_content(binding, ())
        terminal = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-current",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": branch_one["state"]["target"],
                    "requirements_sha256": "c" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "c" * 40,
                        "sha256": "3" * 64,
                        "visible_content_sha256": exchange.sha256_text(
                            terminal_visible
                        ),
                    },
                    "scope": ["path:src/current.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=terminal_visible,
            entries=(),
            requirements_binding=self.requirements_binding(terminal),
        )
        forge = FakeForge(
            self.delivery,
            threads=(replace(historical_thread, is_resolved=True),),
        )
        forge.head_oid = "c" * 40
        branch_one_record = self.carrier_record(
            "branch-one", branch_one, seed.terminal_visible_content
        )
        branch_two_record = self.carrier_record(
            "branch-two", branch_two, branch_two_visible
        )
        middle_record = replace(
            self.carrier_record("middle-state", middle, middle_visible),
            submitted_at="2026-01-01T00:00:06Z",
        )
        returned_record = replace(
            self.carrier_record("returned-state", returned, returned_visible),
            submitted_at="2026-01-01T00:00:08Z",
        )
        forge.reviews.extend(
            (
                initial_record,
                author_record,
                branch_one_record,
                branch_two_record,
                self.delivery.ReviewRecord(
                    id="middle-authority",
                    body=middle_authority_body,
                    head_oid="b" * 40,
                    author="maintainer",
                    viewer_did_author=False,
                    includes_created_edit=False,
                    state="COMMENTED",
                    author_association="OWNER",
                    author_permission="ADMIN",
                    submitted_at="2026-01-01T00:00:05Z",
                ),
                middle_record,
                self.delivery.ReviewRecord(
                    id="returned-authority",
                    body=returned_authority_body,
                    head_oid="b" * 40,
                    author="maintainer",
                    viewer_did_author=False,
                    includes_created_edit=False,
                    state="COMMENTED",
                    author_association="OWNER",
                    author_permission="ADMIN",
                    submitted_at="2026-01-01T00:00:07Z",
                ),
                returned_record,
            )
        )

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, binding, manifest)

        self.assertEqual(["read"], forge.events)

    def test_fresh_second_exchange_without_supersession_withholds_go(self) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)
        exchange = self.delivery.review_exchange
        visible = "An unrelated fresh exchange also claims GO."
        unrelated = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-reset",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": manifest.state_envelope["state"]["target"],
                    "requirements_sha256": "f" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "8" * 64,
                        "visible_content_sha256": exchange.sha256_text(visible),
                    },
                    "scope": ["path:src/reset.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        forge.reviews.append(
            self.carrier_record("unrelated-exchange", unrelated, visible)
        )

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertNotIn("terminal", forge.events)

    def test_foreign_or_malformed_v1_carrier_withholds_delivery(self) -> None:
        thread = self.owned_thread()
        manifest = self.v1_manifest(thread)
        for malformed in (False, True):
            forge = FakeForge(self.delivery, threads=(thread,))
            self.add_history(forge, manifest)
            if malformed:
                foreign = self.delivery.ReviewRecord(
                    id="foreign-v1",
                    body=(
                        "<!-- HomericIntelligence:review-exchange:v1 "
                        "kind=state sha256=invalid -->"
                    ),
                    head_oid="b" * 40,
                    author="other-reviewer",
                    viewer_did_author=False,
                    includes_created_edit=False,
                    state="COMMENTED",
                )
            else:
                foreign = replace(
                    forge.reviews[0],
                    id="foreign-v1",
                    viewer_did_author=False,
                    author="other-reviewer",
                )
            forge.reviews.append(foreign)

            with (
                self.subTest(malformed=malformed),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)

            self.assertNotIn("terminal", forge.events)
            self.assertNotIn("labels", forge.events)

    def test_new_head_can_start_after_an_older_completed_exchange(self) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)
        old, old_visible = self.completed_exchange(
            manifest,
            requirements_sha256=manifest.state_envelope["state"]["requirements_sha256"],
        )
        old_record = replace(
            self.carrier_record("old-terminal", old, old_visible),
            submitted_at="2025-12-31T23:59:59Z",
        )
        forge.reviews.insert(0, old_record)

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertEqual({"state:implementation-go", "enhancement"}, forge.labels)

    def test_archived_exchange_requires_its_atomic_inline_finding_root(self) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)
        old, old_visible = self.archived_suggestion_exchange(manifest)
        old_record = replace(
            self.carrier_record("old-terminal", old, old_visible),
            submitted_at="2025-12-31T23:59:59Z",
        )
        forge.reviews.insert(0, old_record)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual(["read"], forge.events)

    def test_archived_exchange_accepts_its_atomic_inline_finding_root(self) -> None:
        thread = self.owned_thread()
        manifest = self.v1_manifest(thread)
        old, old_visible = self.archived_suggestion_exchange(manifest)
        old_thread = replace(
            self.carrier_threads(old, "old-terminal")[0], is_resolved=True
        )
        forge = FakeForge(self.delivery, threads=(thread, old_thread))
        self.add_history(forge, manifest)
        old_record = replace(
            self.carrier_record("old-terminal", old, old_visible),
            submitted_at="2025-12-31T23:59:59Z",
        )
        forge.reviews.insert(0, old_record)

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertTrue(forge.threads[old_thread.id].is_resolved)

    def test_archived_exchange_must_complete_before_current_exchange_begins(
        self,
    ) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)
        old, old_visible = self.completed_exchange(
            manifest,
            requirements_sha256=manifest.state_envelope["state"]["requirements_sha256"],
        )
        forge.reviews.append(self.carrier_record("late-old-terminal", old, old_visible))

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertNotIn("terminal", forge.events)
        self.assertNotIn("labels", forge.events)

    def test_new_head_cannot_reset_a_conditional_exchange(self) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)
        old, old_visible = self.completed_exchange(
            manifest,
            requirements_sha256=manifest.state_envelope["state"]["requirements_sha256"],
            go_eligible=False,
        )
        old_record = replace(
            self.carrier_record("old-conditional", old, old_visible),
            submitted_at="2025-12-31T23:59:59Z",
        )
        forge.reviews.insert(0, old_record)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertNotIn("terminal", forge.events)
        self.assertNotIn("labels", forge.events)

    def test_new_requirements_need_an_authoritative_supersession(self) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)
        old, old_visible = self.completed_exchange(
            manifest,
            requirements_sha256="e" * 64,
        )
        forge.reviews.append(self.carrier_record("old-terminal", old, old_visible))

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertNotIn("terminal", forge.events)
        self.assertNotIn("labels", forge.events)

    def test_authoritative_reframe_can_supersede_completed_old_requirements(
        self,
    ) -> None:
        exchange = self.delivery.review_exchange
        current_seed = self.v1_manifest(self.owned_thread())
        old, old_visible = self.completed_exchange(
            current_seed,
            requirements_sha256="e" * 64,
        )
        visible = self.delivery.terminal_visible_content(self.binding(), ())
        authority_body = self.authority_body(
            action="reframe",
            exchange_id="exchange-reframed-current",
            requirements_sha256="c" * 64,
            supersedes_state_sha256=old["state_sha256"],
            decisions=[],
        )
        receipt = {
            "reference": "review:reframe-authority",
            "sha256": exchange.sha256_text(authority_body),
        }
        terminal = exchange.reduce_request(
            {
                "previous": old,
                "event": {
                    "event_type": "reframe",
                    "exchange_id": "exchange-reframed-current",
                    "prior_state_sha256": old["state_sha256"],
                    "round": 1,
                    "surface": "pull_request",
                    "target": old["state"]["target"],
                    "requirements_sha256": "c" * 64,
                    "supersedes_state_sha256": old["state_sha256"],
                    "superseded_exchange_ids": [old["state"]["exchange_id"]],
                    "authority_receipt": receipt,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "3" * 64,
                        "visible_content_sha256": exchange.sha256_text(visible),
                    },
                    "scope": ["path:src/current.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=visible,
            entries=(),
            requirements_binding=self.requirements_binding(terminal),
        )
        forge = FakeForge(self.delivery, threads=())
        forge.reviews.extend(
            (
                self.carrier_record("old-terminal", old, old_visible),
                self.delivery.ReviewRecord(
                    id="reframe-authority",
                    body=authority_body,
                    head_oid="b" * 40,
                    author="maintainer",
                    viewer_did_author=False,
                    includes_created_edit=False,
                    state="COMMENTED",
                    author_association="OWNER",
                    author_permission="ADMIN",
                    submitted_at="2026-01-01T00:00:04Z",
                ),
            )
        )

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertEqual(1, forge.events.count("terminal"))
        self.assertEqual(1, forge.events.count("labels"))

    def test_archived_exchange_cannot_reuse_selected_ancestry_identity(self) -> None:
        forge, manifest, _, _, terminal, _ = self.reframed_reused_finding_manifest()
        exchange = self.delivery.review_exchange
        duplicate_visible = "A separate completed exchange reuses the old identity."
        duplicate = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-old",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": terminal["state"]["target"],
                    "requirements_sha256": terminal["state"]["requirements_sha256"],
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "d" * 40,
                        "sha256": "4" * 64,
                        "visible_content_sha256": exchange.sha256_text(
                            duplicate_visible
                        ),
                    },
                    "scope": ["path:src/duplicate.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        duplicate_record = replace(
            self.carrier_record("duplicate-old-exchange", duplicate, duplicate_visible),
            submitted_at="2025-12-31T23:59:59Z",
        )
        forge.reviews.insert(0, duplicate_record)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertNotIn("terminal", forge.events)
        self.assertNotIn("labels", forge.events)

    def test_authoritative_reframe_can_supersede_pending_author_state(
        self,
    ) -> None:
        exchange = self.delivery.review_exchange
        thread = self.owned_thread()
        seed = self.v1_manifest(thread)
        initial_record, author_record = self.carrier_history[
            seed.state_envelope["state_sha256"]
        ]
        initial = exchange.extract_carrier(initial_record.body)
        author_event = exchange.extract_carrier(author_record.body)
        pending = exchange.reduce_request(
            {
                "previous": initial,
                "event": self.delivery._author_event_input(author_event),
            }
        )["envelope"]
        authority_body = self.authority_body(
            action="reframe",
            exchange_id="exchange-reframed",
            requirements_sha256="d" * 64,
            supersedes_state_sha256=pending["state_sha256"],
            decisions=[],
        )
        receipt = {
            "reference": "review:reframe-authority",
            "sha256": exchange.sha256_text(authority_body),
        }
        closure_seed = replace(
            self.closure(thread),
            finding_state_sha256=pending["state_sha256"],
            superseding_state_sha256="0" * 64,
            reviewer_disposition="withdrawn",
            closure_evidence=self.delivery._reframe_closure_evidence(
                pending["state_sha256"]
            ),
            authority_receipt=receipt,
        )
        terminal_visible = self.delivery.terminal_visible_content(
            self.binding(), (closure_seed,)
        )
        terminal = exchange.reduce_request(
            {
                "previous": pending,
                "event": {
                    "event_type": "reframe",
                    "exchange_id": "exchange-reframed",
                    "prior_state_sha256": pending["state_sha256"],
                    "round": 1,
                    "surface": "pull_request",
                    "target": pending["state"]["target"],
                    "requirements_sha256": "d" * 64,
                    "supersedes_state_sha256": pending["state_sha256"],
                    "superseded_exchange_ids": [pending["state"]["exchange_id"]],
                    "authority_receipt": receipt,
                    "artifact_binding": {
                        **pending["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(
                            terminal_visible
                        ),
                    },
                    "scope": ["path:src/example.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        closure = replace(
            closure_seed, superseding_state_sha256=terminal["state_sha256"]
        )
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=terminal_visible,
            entries=(closure,),
            requirements_binding=self.requirements_binding(terminal),
        )
        authority = self.delivery.ReviewRecord(
            id="reframe-authority",
            body=authority_body,
            head_oid="b" * 40,
            author="maintainer",
            viewer_did_author=False,
            includes_created_edit=False,
            state="COMMENTED",
            author_association="OWNER",
            author_permission="ADMIN",
            submitted_at="2026-01-01T00:00:03Z",
        )
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.reviews.extend((initial_record, author_record, authority))

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertTrue(forge.threads[thread.id].is_resolved)
        self.assertIn(
            "Author answer: `fix`.", forge.threads[thread.id].comments[-1].body
        )

    def test_reframe_after_selected_closure_clears_historical_author_binding(
        self,
    ) -> None:
        exchange = self.delivery.review_exchange
        thread = self.owned_thread()
        seed = self.v1_manifest(thread)
        initial_record, author_record = self.carrier_history[
            seed.state_envelope["state_sha256"]
        ]
        initial = exchange.extract_carrier(initial_record.body)
        author_event = exchange.extract_carrier(author_record.body)
        pending = exchange.reduce_request(
            {
                "previous": initial,
                "event": self.delivery._author_event_input(author_event),
            }
        )["envelope"]
        decisions = [
            {
                "finding_id": "F-001",
                "kind": "select_closure",
                "closure_condition": "The selected behavior is verified.",
            }
        ]
        human_authority_body = self.authority_body(
            action="human_decision",
            exchange_id="exchange-7",
            requirements_sha256="c" * 64,
            prior_state_sha256=pending["state_sha256"],
            supersedes_state_sha256=None,
            decisions=decisions,
        )
        human_receipt = {
            "reference": "review:select-authority",
            "sha256": exchange.sha256_text(human_authority_body),
        }
        human_visible = "A maintainer selected the authoritative closure condition."
        selected = exchange.reduce_request(
            {
                "previous": pending,
                "event": {
                    "event_type": "human_decision",
                    "exchange_id": "exchange-7",
                    "prior_state_sha256": pending["state_sha256"],
                    "artifact_binding": {
                        **pending["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(human_visible),
                    },
                    "authority_receipt": human_receipt,
                    "decisions": decisions,
                },
            }
        )["envelope"]
        reframe_authority_body = self.authority_body(
            action="reframe",
            exchange_id="exchange-reframed",
            requirements_sha256="d" * 64,
            supersedes_state_sha256=selected["state_sha256"],
            decisions=[],
        )
        reframe_receipt = {
            "reference": "review:reframe-after-selection",
            "sha256": exchange.sha256_text(reframe_authority_body),
        }
        closure_seed = replace(
            self.closure(thread),
            finding_state_sha256=selected["state_sha256"],
            superseding_state_sha256="0" * 64,
            author_answer=None,
            author_artifact_revision=None,
            reviewer_disposition="withdrawn",
            closure_evidence=self.delivery._reframe_closure_evidence(
                selected["state_sha256"]
            ),
            authority_receipt=reframe_receipt,
            author_event_review_id=None,
        )
        terminal_visible = self.delivery.terminal_visible_content(
            self.binding(), (closure_seed,)
        )
        terminal = exchange.reduce_request(
            {
                "previous": selected,
                "event": {
                    "event_type": "reframe",
                    "exchange_id": "exchange-reframed",
                    "prior_state_sha256": selected["state_sha256"],
                    "round": 1,
                    "surface": "pull_request",
                    "target": selected["state"]["target"],
                    "requirements_sha256": "d" * 64,
                    "supersedes_state_sha256": selected["state_sha256"],
                    "superseded_exchange_ids": [selected["state"]["exchange_id"]],
                    "authority_receipt": reframe_receipt,
                    "artifact_binding": {
                        **selected["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(
                            terminal_visible
                        ),
                    },
                    "scope": ["path:src/example.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=terminal_visible,
            entries=(
                replace(
                    closure_seed,
                    superseding_state_sha256=terminal["state_sha256"],
                ),
            ),
            requirements_binding=self.requirements_binding(terminal),
        )
        human_authority = self.delivery.ReviewRecord(
            id="select-authority",
            body=human_authority_body,
            head_oid="b" * 40,
            author="maintainer",
            viewer_did_author=False,
            includes_created_edit=False,
            state="COMMENTED",
            author_association="OWNER",
            author_permission="ADMIN",
            submitted_at="2026-01-01T00:00:02.500000Z",
        )
        selected_record = self.carrier_record("selected-state", selected, human_visible)
        reframe_authority = self.delivery.ReviewRecord(
            id="reframe-after-selection",
            body=reframe_authority_body,
            head_oid="b" * 40,
            author="maintainer",
            viewer_did_author=False,
            includes_created_edit=False,
            state="COMMENTED",
            author_association="OWNER",
            author_permission="ADMIN",
            submitted_at="2026-01-01T00:00:04Z",
        )
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.reviews.extend(
            (
                initial_record,
                author_record,
                human_authority,
                selected_record,
                reframe_authority,
            )
        )

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        response = forge.threads[thread.id].comments[-1].body
        self.assertIn("Author answer: `not applicable`.", response)

    def test_authoritative_reframe_withdraws_old_thread_when_finding_id_is_reused(
        self,
    ) -> None:
        exchange = self.delivery.review_exchange
        target = {
            "provider": "github",
            "repository": "owner/repository",
            "number": 7,
            "url": "https://github.com/owner/repository/pull/7",
        }
        old_visible = "The old requirements have one required finding."
        old = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-old",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": target,
                    "requirements_sha256": "1" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "a" * 40,
                        "sha256": "2" * 64,
                        "visible_content_sha256": exchange.sha256_text(old_visible),
                    },
                    "scope": ["path:src/old.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [
                        {
                            "id": "F-001",
                            "category": None,
                            "severity": "major",
                            "disposition": "required",
                            "material_architecture": False,
                            "location": "src/old.py:4",
                            "impact": "The old requirement is not satisfied.",
                            "evidence": ["The old case fails."],
                            "closure_condition": "The old case passes.",
                            "introduction": "initial",
                        }
                    ],
                    "stop_reason": "requirements_reframe",
                },
            }
        )["envelope"]
        authority_body = self.authority_body(
            action="reframe",
            exchange_id="exchange-new",
            requirements_sha256="3" * 64,
            supersedes_state_sha256=old["state_sha256"],
            decisions=[],
        )
        receipt = {
            "reference": "review:reframe-authority",
            "sha256": exchange.sha256_text(authority_body),
        }
        old_thread = self.carrier_threads(old, "old-review")[0]
        closure_seed = self.delivery.ThreadClosure(
            thread_id=old_thread.id,
            finding_id="F-001",
            finding_exchange_id="exchange-old",
            finding_state_sha256=old["state_sha256"],
            superseding_state_sha256="0" * 64,
            origin_comment_id=old_thread.comments[0].id,
            origin_review_head_oid="a" * 40,
            conversation_sha256=self.delivery.conversation_sha256(old_thread),
            finding_disposition="required",
            author_answer=None,
            author_artifact_revision=None,
            reviewer_disposition="withdrawn",
            closure_evidence=self.delivery._reframe_closure_evidence(
                old["state_sha256"]
            ),
            authority_receipt=receipt,
            author_event_review_id=None,
        )
        terminal_visible = self.delivery.terminal_visible_content(
            self.binding(), (closure_seed,)
        )
        terminal = exchange.reduce_request(
            {
                "previous": old,
                "event": {
                    "event_type": "reframe",
                    "exchange_id": "exchange-new",
                    "prior_state_sha256": old["state_sha256"],
                    "round": 1,
                    "surface": "pull_request",
                    "target": target,
                    "requirements_sha256": "3" * 64,
                    "supersedes_state_sha256": old["state_sha256"],
                    "superseded_exchange_ids": [old["state"]["exchange_id"]],
                    "authority_receipt": receipt,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "3" * 64,
                        "visible_content_sha256": exchange.sha256_text(
                            terminal_visible
                        ),
                    },
                    "scope": ["path:src/new.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [
                        {
                            "id": "F-001",
                            "category": None,
                            "severity": "minor",
                            "disposition": "suggestion",
                            "material_architecture": False,
                            "location": "src/new.py:8",
                            "impact": "The new name can be clearer.",
                            "evidence": ["The name hides its purpose."],
                            "closure_condition": None,
                            "introduction": "initial",
                        }
                    ],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        closure = replace(
            closure_seed, superseding_state_sha256=terminal["state_sha256"]
        )
        inline = self.delivery.TerminalInlineComment(
            path="src/new.py",
            side="RIGHT",
            line=8,
            body=(
                "The new name can be clearer.\n\n"
                "<!-- HomericIntelligence:review-finding:v1 "
                "exchange=exchange-new id=F-001 -->"
            ),
        )
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=terminal_visible,
            entries=(closure,),
            requirements_binding=self.requirements_binding(terminal),
            comments=(inline,),
        )
        authority = self.delivery.ReviewRecord(
            id="reframe-authority",
            body=authority_body,
            head_oid="b" * 40,
            author="maintainer",
            viewer_did_author=False,
            includes_created_edit=False,
            state="COMMENTED",
            author_association="OWNER",
            author_permission="ADMIN",
            submitted_at="2026-01-01T00:00:02Z",
        )
        forge = FakeForge(self.delivery, threads=(old_thread,))
        forge.reviews.extend(
            (
                self.carrier_record("old-review", old, old_visible),
                authority,
            )
        )

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertEqual(
            ("old-review-F-001", "terminal-thread-1"),
            result.resolved_thread_ids,
        )
        self.assertEqual(1, forge.events.count("terminal"))
        self.assertIn(f"reply:{old_thread.id}", forge.events)
        self.assertIn("reply:terminal-thread-1", forge.events)
        for thread_id in (old_thread.id, "terminal-thread-1"):
            self.assertTrue(forge.threads[thread_id].is_resolved)
            self.assertLess(
                forge.events.index("terminal"),
                forge.events.index(f"reply:{thread_id}"),
            )
            self.assertLess(
                forge.events.index(f"reply:{thread_id}"),
                forge.events.index(f"resolve:{thread_id}"),
            )
            self.assertLess(
                forge.events.index(f"resolve:{thread_id}"),
                forge.events.index("labels"),
            )
        self.assertFalse(
            any(not thread.is_resolved for thread in forge.threads.values())
        )
        old_response = forge.threads[old_thread.id].comments[-1].body
        new_response = forge.threads["terminal-thread-1"].comments[-1].body
        self.assertIn("Finding `exchange-old/F-001`: `withdrawn`", old_response)
        self.assertIn(
            "Closure basis: authoritative requirements reframe.", old_response
        )
        self.assertIn(old["state_sha256"], old_response)
        self.assertIn(terminal["state_sha256"], old_response)
        self.assertIn(receipt["reference"], old_response)
        self.assertIn(receipt["sha256"], old_response)
        self.assertIn("Finding `exchange-new/F-001`", new_response)
        self.assertNotEqual(
            old_response.splitlines()[-1], new_response.splitlines()[-1]
        )
        self.assertIsNone(closure.author_answer)
        self.assertIsNone(closure.author_artifact_revision)
        self.assertIsNone(closure.author_event_review_id)

    def test_reframe_closure_ledger_is_stable_after_terminal_digest_binding(
        self,
    ) -> None:
        _, manifest, _, _, _, _ = self.reframed_reused_finding_manifest()

        self.assertEqual(
            manifest.terminal_visible_content,
            self.delivery.terminal_visible_content(self.binding(), manifest.entries),
        )

    def test_two_authoritative_reframes_close_reused_finding_ids_by_state(
        self,
    ) -> None:
        exchange = self.delivery.review_exchange
        _, _, old_thread, old, _, first_receipt = (
            self.reframed_reused_finding_manifest()
        )
        target = old["state"]["target"]
        middle_visible = "The first reframe has one required finding."
        middle = exchange.reduce_request(
            {
                "previous": old,
                "event": {
                    "event_type": "reframe",
                    "exchange_id": "exchange-new",
                    "prior_state_sha256": old["state_sha256"],
                    "round": 1,
                    "surface": "pull_request",
                    "target": target,
                    "requirements_sha256": "3" * 64,
                    "supersedes_state_sha256": old["state_sha256"],
                    "superseded_exchange_ids": [old["state"]["exchange_id"]],
                    "authority_receipt": first_receipt,
                    "artifact_binding": {
                        "revision": "a" * 40,
                        "sha256": "3" * 64,
                        "visible_content_sha256": exchange.sha256_text(middle_visible),
                    },
                    "scope": ["path:src/middle.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [
                        {
                            "id": "F-001",
                            "category": None,
                            "severity": "major",
                            "disposition": "required",
                            "material_architecture": False,
                            "location": "src/middle.py:6",
                            "impact": "The first reframe is incomplete.",
                            "evidence": ["The middle case fails."],
                            "closure_condition": "The middle case passes.",
                            "introduction": "initial",
                        }
                    ],
                    "stop_reason": "requirements_reframe",
                },
            }
        )["envelope"]
        middle_thread = self.carrier_threads(middle, "middle-review")[0]
        second_authority_body = self.authority_body(
            action="reframe",
            exchange_id="exchange-final",
            requirements_sha256="4" * 64,
            supersedes_state_sha256=middle["state_sha256"],
            decisions=[],
        )
        second_receipt = {
            "reference": "review:second-reframe-authority",
            "sha256": exchange.sha256_text(second_authority_body),
        }
        old_closure = self.delivery.ThreadClosure(
            thread_id=old_thread.id,
            finding_id="F-001",
            finding_exchange_id="exchange-old",
            finding_state_sha256=old["state_sha256"],
            superseding_state_sha256=middle["state_sha256"],
            origin_comment_id=old_thread.comments[0].id,
            origin_review_head_oid="a" * 40,
            conversation_sha256=self.delivery.conversation_sha256(old_thread),
            finding_disposition="required",
            author_answer=None,
            author_artifact_revision=None,
            reviewer_disposition="withdrawn",
            closure_evidence=self.delivery._reframe_closure_evidence(
                old["state_sha256"]
            ),
            authority_receipt=first_receipt,
            author_event_review_id=None,
        )
        middle_closure_seed = self.delivery.ThreadClosure(
            thread_id=middle_thread.id,
            finding_id="F-001",
            finding_exchange_id="exchange-new",
            finding_state_sha256=middle["state_sha256"],
            superseding_state_sha256="0" * 64,
            origin_comment_id=middle_thread.comments[0].id,
            origin_review_head_oid="a" * 40,
            conversation_sha256=self.delivery.conversation_sha256(middle_thread),
            finding_disposition="required",
            author_answer=None,
            author_artifact_revision=None,
            reviewer_disposition="withdrawn",
            closure_evidence=self.delivery._reframe_closure_evidence(
                middle["state_sha256"]
            ),
            authority_receipt=second_receipt,
            author_event_review_id=None,
        )
        terminal_visible = self.delivery.terminal_visible_content(
            self.binding(), (old_closure, middle_closure_seed)
        )
        terminal = exchange.reduce_request(
            {
                "previous": middle,
                "event": {
                    "event_type": "reframe",
                    "exchange_id": "exchange-final",
                    "prior_state_sha256": middle["state_sha256"],
                    "round": 1,
                    "surface": "pull_request",
                    "target": target,
                    "requirements_sha256": "4" * 64,
                    "supersedes_state_sha256": middle["state_sha256"],
                    "superseded_exchange_ids": [
                        old["state"]["exchange_id"],
                        middle["state"]["exchange_id"],
                    ],
                    "authority_receipt": second_receipt,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "4" * 64,
                        "visible_content_sha256": exchange.sha256_text(
                            terminal_visible
                        ),
                    },
                    "scope": ["path:src/final.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        middle_closure = replace(
            middle_closure_seed,
            superseding_state_sha256=terminal["state_sha256"],
        )
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=terminal_visible,
            entries=(old_closure, middle_closure),
            requirements_binding=self.requirements_binding(terminal),
        )
        first_authority_body = self.authority_body(
            action="reframe",
            exchange_id="exchange-new",
            requirements_sha256="3" * 64,
            supersedes_state_sha256=old["state_sha256"],
            decisions=[],
        )
        first_authority = self.delivery.ReviewRecord(
            id="reframe-authority",
            body=first_authority_body,
            head_oid="a" * 40,
            author="maintainer",
            viewer_did_author=False,
            includes_created_edit=False,
            state="COMMENTED",
            author_association="OWNER",
            author_permission="ADMIN",
            submitted_at="2026-01-01T00:00:02Z",
        )
        second_authority = self.delivery.ReviewRecord(
            id="second-reframe-authority",
            body=second_authority_body,
            head_oid="b" * 40,
            author="maintainer",
            viewer_did_author=False,
            includes_created_edit=False,
            state="COMMENTED",
            author_association="OWNER",
            author_permission="ADMIN",
            submitted_at="2026-01-01T00:00:04Z",
        )
        self.review_sequence = 0
        old_review = self.carrier_record(
            "old-review", old, "The old requirements have one required finding."
        )
        middle_review = replace(
            self.carrier_record("middle-review", middle, middle_visible),
            submitted_at="2026-01-01T00:00:03Z",
        )
        forge = FakeForge(self.delivery, threads=(old_thread, middle_thread))
        forge.reviews.extend(
            (old_review, first_authority, middle_review, second_authority)
        )

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual(
            ("middle-review-F-001", "old-review-F-001"),
            result.resolved_thread_ids,
        )
        for thread_id, source, successor in (
            (old_thread.id, old["state_sha256"], middle["state_sha256"]),
            (
                middle_thread.id,
                middle["state_sha256"],
                terminal["state_sha256"],
            ),
        ):
            response = forge.threads[thread_id].comments[-1].body
            self.assertTrue(forge.threads[thread_id].is_resolved)
            self.assertIn(source, response)
            self.assertIn(successor, response)
            self.assertIn("id=F-001", response)
        self.assertNotEqual(
            forge.threads[old_thread.id].comments[-1].body.splitlines()[-1],
            forge.threads[middle_thread.id].comments[-1].body.splitlines()[-1],
        )

    def test_reframe_closure_preserves_source_author_event_binding(self) -> None:
        exchange = self.delivery.review_exchange
        thread = self.owned_thread()
        source_manifest = self.v1_manifest(thread)
        source = source_manifest.state_envelope
        authority_body = self.authority_body(
            action="reframe",
            exchange_id="exchange-reframed",
            requirements_sha256="d" * 64,
            supersedes_state_sha256=source["state_sha256"],
            decisions=[],
        )
        receipt = {
            "reference": "review:reframe-authority",
            "sha256": exchange.sha256_text(authority_body),
        }
        closure_seed = self.delivery.ThreadClosure(
            thread_id=thread.id,
            finding_id="F-001",
            finding_exchange_id="exchange-7",
            finding_state_sha256=source["state_sha256"],
            superseding_state_sha256="0" * 64,
            origin_comment_id=thread.comments[0].id,
            origin_review_head_oid="a" * 40,
            conversation_sha256=self.delivery.conversation_sha256(thread),
            finding_disposition="required",
            author_answer="fix",
            author_artifact_revision="b" * 40,
            reviewer_disposition="withdrawn",
            closure_evidence=self.delivery._reframe_closure_evidence(
                source["state_sha256"]
            ),
            authority_receipt=receipt,
            author_event_review_id="author-event-1",
        )
        terminal_visible = self.delivery.terminal_visible_content(
            self.binding(), (closure_seed,)
        )
        terminal = exchange.reduce_request(
            {
                "previous": source,
                "event": {
                    "event_type": "reframe",
                    "exchange_id": "exchange-reframed",
                    "prior_state_sha256": source["state_sha256"],
                    "round": 1,
                    "surface": "pull_request",
                    "target": source["state"]["target"],
                    "requirements_sha256": "d" * 64,
                    "supersedes_state_sha256": source["state_sha256"],
                    "superseded_exchange_ids": [source["state"]["exchange_id"]],
                    "authority_receipt": receipt,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "3" * 64,
                        "visible_content_sha256": exchange.sha256_text(
                            terminal_visible
                        ),
                    },
                    "scope": ["path:src/reframed.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        closure = replace(
            closure_seed,
            superseding_state_sha256=terminal["state_sha256"],
        )
        manifest = self.delivery.ClosureManifest(
            state_envelope=terminal,
            terminal_visible_content=terminal_visible,
            entries=(closure,),
            requirements_binding=self.requirements_binding(terminal),
        )
        source_review = self.carrier_record(
            "source-terminal",
            source,
            source_manifest.terminal_visible_content,
        )
        authority = self.delivery.ReviewRecord(
            id="reframe-authority",
            body=authority_body,
            head_oid="b" * 40,
            author="maintainer",
            viewer_did_author=False,
            includes_created_edit=False,
            state="COMMENTED",
            author_association="OWNER",
            author_permission="ADMIN",
            submitted_at="2026-01-01T00:00:04Z",
        )
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.reviews.extend(
            (*self.carrier_history[source["state_sha256"]], source_review, authority)
        )

        with patch.object(
            forge,
            "collect_requirements_binding",
            return_value=self.requirements_binding(terminal),
        ):
            result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertTrue(forge.threads[thread.id].is_resolved)
        response = forge.threads[thread.id].comments[-1].body
        self.assertIn("Finding `exchange-7/F-001`: `withdrawn`", response)
        self.assertIn("Author answer: `fix`.", response)
        self.assertEqual("author-event-1", closure.author_event_review_id)

    def test_reframe_closure_rejects_invalid_lineage_before_publication(self) -> None:
        cases = (
            ("exchange", {"finding_exchange_id": "exchange-other"}),
            ("source", {"finding_state_sha256": "f" * 64}),
            ("successor", {"superseding_state_sha256": "f" * 64}),
            ("disposition", {"reviewer_disposition": "resolved"}),
            ("evidence", {"closure_evidence": ("Unbound evidence.",)}),
            ("authority absent", {"authority_receipt": None}),
            (
                "authority digest",
                {
                    "authority_receipt": {
                        "reference": "review:reframe-authority",
                        "sha256": "f" * 64,
                    }
                },
            ),
            ("author answer", {"author_answer": "fix"}),
        )
        for case, changes in cases:
            forge, manifest, _, _, _, _ = self.reframed_reused_finding_manifest()
            invalid = replace(manifest.entries[0], **changes)
            manifest = replace(manifest, entries=(invalid,))

            with (
                self.subTest(case=case),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)

            self.assertNotIn("terminal", forge.events)
            self.assertFalse(
                any(event.startswith(("reply:", "resolve:")) for event in forge.events)
            )
            self.assertNotIn("labels", forge.events)

    def test_reframe_closure_rejects_invalid_thread_binding_before_publication(
        self,
    ) -> None:
        cases = (
            ("root", {"id": "other-root"}),
            ("origin review", {"review_id": "other-review"}),
            ("origin head", {"review_head_oid": "f" * 40}),
            ("path", {"path": "src/other.py"}),
            ("line", {"original_line": 9}),
        )
        for case, changes in cases:
            forge, manifest, old_thread, _, _, _ = (
                self.reframed_reused_finding_manifest()
            )
            changed = replace(
                old_thread, comments=(replace(old_thread.comments[0], **changes),)
            )
            forge.threads[old_thread.id] = changed

            with (
                self.subTest(case=case),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)

            self.assertNotIn("terminal", forge.events)
            self.assertNotIn("labels", forge.events)

        forge, manifest, _, _, _, _ = self.reframed_reused_finding_manifest()
        manifest = replace(
            manifest,
            entries=(replace(manifest.entries[0], conversation_sha256="f" * 64),),
        )
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)
        self.assertNotIn("terminal", forge.events)

    def test_reframe_closure_withholds_for_unrelated_or_foreign_open_thread(
        self,
    ) -> None:
        for case, owned in (("unrelated", True), ("foreign", False)):
            forge, manifest, old_thread, _, _, _ = (
                self.reframed_reused_finding_manifest()
            )
            root = replace(
                old_thread.comments[0],
                id=f"{case}-root",
                body=(
                    "Unrelated open finding.\n\n"
                    "<!-- HomericIntelligence:review-finding:v1 "
                    "exchange=exchange-unrelated id=F-001 -->"
                ),
                review_id=f"{case}-review",
                viewer_did_author=owned,
            )
            thread = replace(
                old_thread,
                id=f"{case}-thread",
                comments=(root,),
            )
            forge.threads[thread.id] = thread

            with (
                self.subTest(case=case),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)

            self.assertNotIn("terminal", forge.events)
            self.assertFalse(
                any(event.startswith(("reply:", "resolve:")) for event in forge.events)
            )
            self.assertNotIn("labels", forge.events)

    def test_reframe_closure_preserves_pre_resolved_historical_thread(self) -> None:
        forge, manifest, old_thread, _, _, _ = self.reframed_reused_finding_manifest(
            include_historical_entry=False
        )
        resolved = replace(old_thread, is_resolved=True)
        forge.threads[old_thread.id] = resolved

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual(("terminal-thread-1",), result.resolved_thread_ids)
        self.assertEqual(resolved, forge.threads[old_thread.id])
        self.assertNotIn(f"reply:{old_thread.id}", forge.events)
        self.assertNotIn(f"resolve:{old_thread.id}", forge.events)

    def test_reframe_closure_recovery_does_not_republish_terminal(self) -> None:
        forge, manifest, old_thread, _, _, _ = self.reframed_reused_finding_manifest()
        forge.fail_resolve = True

        with self.assertRaises(self.delivery.DeliveryError) as caught:
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("partial", caught.exception.report.status)
        self.assertEqual(1, forge.events.count("terminal"))
        self.assertIn(f"reply:{old_thread.id}", forge.events)
        forge.fail_resolve = False
        forge.events.clear()

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertNotIn("terminal", forge.events)
        self.assertNotIn(f"reply:{old_thread.id}", forge.events)
        self.assertTrue(forge.threads[old_thread.id].is_resolved)

    def test_late_comment_on_resolved_thread_withholds_go_readback(self) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)
        forge.comment_after_label = True

        with self.assertRaises(self.delivery.DeliveryError) as caught:
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertIn("labels", forge.events)
        self.assertEqual("partial", caught.exception.report.status)
        self.assertTrue(caught.exception.report.recovery_read_required)
        self.assertNotEqual(
            manifest.entries[0].conversation_sha256,
            self.delivery.conversation_sha256(forge.threads["thread-1"]),
        )

    def test_v1_delivery_resumes_closure_after_verified_terminal_publication(
        self,
    ) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)
        forge.fail_resolve = True

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual(1, forge.events.count("terminal"))
        self.assertEqual(1, forge.events.count("reply:thread-1"))
        forge.fail_resolve = False

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertEqual(1, forge.events.count("terminal"))
        self.assertEqual(1, forge.events.count("reply:thread-1"))
        self.assertEqual(2, forge.events.count("resolve:thread-1"))
        self.assertIn("labels", forge.events)

    def test_fresh_closure_reply_is_strictly_verified_before_resolution(
        self,
    ) -> None:
        cases = (
            (None, False, "missing publication time"),
            ("2026-01-01T00:01:03Z", False, "tied publication time"),
            ("2026-01-01T00:01:02Z", False, "earlier publication time"),
            ("2026-01-01T00:02:00Z", True, "edited response"),
        )
        for published_at, edited, case in cases:
            thread = self.owned_thread()
            forge = FakeForge(self.delivery, threads=(thread,))
            forge.reply_published_at = published_at
            forge.edit_reply_after_post = edited
            manifest = self.v1_manifest(thread)
            self.add_history(forge, manifest)

            with (
                self.subTest(case=case),
                self.assertRaises(self.delivery.DeliveryError) as caught,
            ):
                self.delivery.deliver_go_v1(forge, self.binding(), manifest)

            self.assertEqual("partial", caught.exception.report.status)
            self.assertIn("reply:thread-1", forge.events)
            self.assertNotIn("resolve:thread-1", forge.events)
            self.assertFalse(forge.threads[thread.id].is_resolved)

    def test_v1_delivery_recovers_an_incomplete_exclusive_go_label(self) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)
        forge.keep_no_go_after_label = True

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual(
            {"state:implementation-go", "state:implementation-no-go", "enhancement"},
            forge.labels,
        )
        forge.keep_no_go_after_label = False

        result = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", result.status)
        self.assertEqual({"state:implementation-go", "enhancement"}, forge.labels)
        self.assertEqual(1, forge.events.count("terminal"))
        self.assertEqual(1, forge.events.count("reply:thread-1"))

    def test_exact_same_head_v1_go_is_idempotently_delivered(self) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)
        first = self.delivery.deliver_go_v1(forge, self.binding(), manifest)
        forge.events.clear()

        replay = self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual("delivered", first.status)
        self.assertEqual("already_delivered", replay.status)
        self.assertEqual("review-3", replay.terminal_review_id)
        self.assertEqual(("thread-1",), replay.responded_thread_ids)
        self.assertEqual(("thread-1",), replay.resolved_thread_ids)
        self.assertEqual(["read", "requirements:verify"], forge.events)
        self.assertEqual(
            1, len([review for review in forge.reviews if review.id == "review-3"])
        )

    def test_recovered_closure_response_must_follow_terminal_without_an_edit(
        self,
    ) -> None:
        cases = (
            (None, None, "missing publication time"),
            ("2026-01-01T00:01:03Z", None, "tied publication time"),
            ("2026-01-01T00:01:02Z", None, "earlier publication time"),
            (
                "2026-01-01T00:02:00Z",
                "2026-01-01T00:03:00Z",
                "edited response",
            ),
        )
        for published_at, last_edited_at, case in cases:
            thread = self.owned_thread()
            forge = FakeForge(self.delivery, threads=(thread,))
            manifest = self.v1_manifest(thread)
            self.add_history(forge, manifest)
            first = self.delivery.deliver_go_v1(forge, self.binding(), manifest)
            self.assertEqual("delivered", first.status)
            closed = forge.threads[thread.id]
            response = replace(
                closed.comments[-1],
                published_at=published_at,
                last_edited_at=last_edited_at,
            )
            forge.threads[thread.id] = replace(
                closed, comments=(*closed.comments[:-1], response)
            )
            forge.events.clear()

            with self.subTest(case=case):
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_go_v1(forge, self.binding(), manifest)
                self.assertEqual(["read"], forge.events)

    def test_edited_review_exchange_carrier_is_never_delivery_proof(self) -> None:
        for carrier_kind in ("state", "author-event", "terminal"):
            thread = self.owned_thread()
            forge = FakeForge(self.delivery, threads=(thread,))
            manifest = self.v1_manifest(thread)
            self.add_history(forge, manifest)
            if carrier_kind == "terminal":
                first = self.delivery.deliver_go_v1(forge, self.binding(), manifest)
                self.assertEqual("delivered", first.status)
                index = -1
            else:
                index = 0 if carrier_kind == "state" else 1
            forge.reviews[index] = replace(
                forge.reviews[index],
                includes_created_edit=False,
                last_edited_at="2026-01-01T00:03:00Z",
            )
            forge.events.clear()

            with self.subTest(carrier_kind=carrier_kind):
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_go_v1(forge, self.binding(), manifest)
                self.assertEqual(["read"], forge.events)

    def test_edited_terminal_inline_root_is_rejected_during_replay(self) -> None:
        manifest, _ = self.terminal_inline_manifest()
        forge = FakeForge(self.delivery, threads=())
        self.assertEqual(
            "delivered",
            self.delivery.deliver_go_v1(forge, self.binding(), manifest).status,
        )
        closed = forge.threads["terminal-thread-1"]
        edited_root = replace(closed.comments[0], last_edited_at="2026-01-01T00:04:00Z")
        forge.threads[closed.id] = replace(
            closed, comments=(edited_root, *closed.comments[1:])
        )
        forge.events.clear()

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual(["read"], forge.events)

    def test_same_head_v1_go_rejects_premature_thread_resolution(self) -> None:
        thread = self.owned_thread()
        manifest = self.v1_manifest(thread)
        terminal_body = self.delivery.terminal_review_body(manifest)
        resolved = self.delivery.ReviewThread(
            id=thread.id,
            is_resolved=True,
            comments=thread.comments,
            viewer_can_reply=True,
            viewer_can_resolve=True,
        )
        forge = FakeForge(self.delivery, threads=(resolved,))
        forge.labels = {"state:implementation-go", "enhancement"}
        self.add_history(forge, manifest)
        forge.reviews.append(
            self.delivery.ReviewRecord(
                id="terminal-1",
                body=terminal_body,
                head_oid="b" * 40,
                author="reviewer",
                viewer_did_author=True,
                includes_created_edit=False,
                state="COMMENTED",
            )
        )

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual(["read"], forge.events)

    def test_go_label_without_current_terminal_ledger_is_not_proof(self) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.labels = {"state:implementation-go", "enhancement"}
        manifest = self.v1_manifest(thread)
        self.add_history(forge, manifest)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual(["read", "requirements:verify"], forge.events)

    def test_no_go_delivery_requires_a_verified_current_head_carrier(self) -> None:
        forge = FakeForge(self.delivery, threads=())
        forge.labels = {"state:implementation-go", "enhancement"}

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_no_go(forge, self.binding(), None)

        self.assertEqual({"state:implementation-go", "enhancement"}, forge.labels)
        self.assertEqual(["read"], forge.events)

    def test_no_go_delivery_verifies_carrier_before_exclusive_label_change(
        self,
    ) -> None:
        proof, record = self.no_go_proof()
        forge = FakeForge(
            self.delivery,
            threads=self.carrier_threads(proof.state_envelope, proof.review_id),
        )
        forge.labels = {"state:implementation-go", "enhancement"}
        forge.reviews.append(record)

        result = self.delivery.deliver_no_go(forge, self.binding(), proof)

        self.assertEqual("delivered", result.status)
        self.assertEqual("state:implementation-no-go", result.label)
        self.assertEqual("no-go-review-1", result.terminal_review_id)
        self.assertEqual({"state:implementation-no-go", "enhancement"}, forge.labels)
        self.assertEqual(1, forge.events.count("labels:no-go"))

        replay = self.delivery.deliver_no_go(forge, self.binding(), proof)
        self.assertEqual("already_delivered", replay.status)
        self.assertEqual(1, forge.events.count("labels:no-go"))

    def test_conditional_go_uses_only_the_exclusive_no_go_delivery_path(self) -> None:
        proof, record = self.conditional_go_proof()
        forge = FakeForge(self.delivery, threads=())
        forge.labels = {"state:implementation-go", "enhancement"}
        forge.reviews.append(record)

        result = self.delivery.deliver_no_go(forge, self.binding(), proof)

        self.assertEqual("delivered", result.status)
        self.assertEqual("state:implementation-no-go", result.label)
        self.assertEqual({"state:implementation-no-go", "enhancement"}, forge.labels)
        self.assertEqual(1, forge.events.count("labels:no-go"))
        self.assertNotIn("terminal", forge.events)
        self.assertNotIn("labels", forge.events)

        replay = self.delivery.deliver_no_go(forge, self.binding(), proof)
        self.assertEqual("already_delivered", replay.status)
        self.assertEqual(1, forge.events.count("labels:no-go"))

    def test_conditional_go_cannot_enter_terminal_go_delivery(self) -> None:
        proof, record = self.conditional_go_proof()
        manifest = self.delivery.ClosureManifest(
            state_envelope=proof.state_envelope,
            terminal_visible_content=proof.visible_content,
            entries=(),
            requirements_binding=proof.requirements_binding,
        )
        forge = FakeForge(self.delivery, threads=())
        forge.reviews.append(record)

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertEqual(["read"], forge.events)

    def test_eligible_go_cannot_be_used_as_a_no_go_proof(self) -> None:
        conditional, _record = self.conditional_go_proof()
        exchange = self.delivery.review_exchange
        visible = "The eligible review can deliver GO."
        event = {
            "event_type": "reviewer_assessment",
            "exchange_id": "exchange-conditional",
            "prior_state_sha256": conditional.state_envelope["state_sha256"],
            "round": 2,
            "artifact_binding": {
                **conditional.state_envelope["state"]["artifact_binding"],
                "visible_content_sha256": exchange.sha256_text(visible),
            },
            "scope": conditional.state_envelope["state"]["scope"],
            "coverage_complete": True,
            "go_eligible": True,
            "responses": [],
            "new_findings": [],
            "stop_reason": None,
        }
        terminal = exchange.reduce_request(
            {"previous": conditional.state_envelope, "event": event}
        )["envelope"]
        proof = self.delivery.NoGoProof(
            terminal,
            visible,
            "go-review-1",
            self.requirements_binding(terminal),
        )
        forge = FakeForge(self.delivery, threads=())
        forge.reviews.append(self.carrier_record(proof.review_id, terminal, visible))

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_no_go(forge, self.binding(), proof)

        self.assertNotIn("labels:no-go", forge.events)

    def test_no_go_rejects_a_proof_that_is_not_the_unique_chain_tip(self) -> None:
        proof, record = self.no_go_proof()
        exchange = self.delivery.review_exchange
        author_visible = "The author contests F-001."
        author = exchange.reduce_request(
            {
                "previous": proof.state_envelope,
                "event": {
                    "event_type": "author_response",
                    "exchange_id": "exchange-no-go",
                    "prior_state_sha256": proof.state_envelope["state_sha256"],
                    "artifact_binding": {
                        **proof.state_envelope["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(author_visible),
                    },
                    "scope": ["path:src/no_go.py"],
                    "scope_change_reason": None,
                    "responses": [
                        {
                            "finding_id": "F-001",
                            "kind": "contest",
                            "evidence": ["The stated failing case does not reproduce."],
                            "tradeoff": None,
                        }
                    ],
                },
            }
        )
        terminal_visible = "The reviewer accepts the contest."
        terminal = exchange.reduce_request(
            {
                "previous": author["envelope"],
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-no-go",
                    "prior_state_sha256": author["envelope"]["state_sha256"],
                    "round": 2,
                    "artifact_binding": {
                        **author["envelope"]["state"]["artifact_binding"],
                        "visible_content_sha256": exchange.sha256_text(
                            terminal_visible
                        ),
                    },
                    "scope": ["path:src/no_go.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [
                        {
                            "finding_id": "F-001",
                            "kind": "accept",
                            "evidence": [
                                "Independent reproduction confirms the contest."
                            ],
                            "closure_condition": None,
                        }
                    ],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        forge = FakeForge(
            self.delivery,
            threads=self.carrier_threads(proof.state_envelope, proof.review_id),
        )
        forge.labels = {"state:implementation-go", "enhancement"}
        forge.reviews.extend(
            (
                record,
                self.carrier_record(
                    "no-go-author", author["author_event"], author_visible
                ),
                self.carrier_record("later-terminal", terminal, terminal_visible),
            )
        )

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_no_go(forge, self.binding(), proof)

        self.assertNotIn("labels:no-go", forge.events)
        self.assertEqual({"state:implementation-go", "enhancement"}, forge.labels)

    def test_reframed_no_go_replays_and_revalidates_supersession_authority(
        self,
    ) -> None:
        exchange = self.delivery.review_exchange
        target = {
            "provider": "github",
            "repository": "owner/repository",
            "number": 7,
            "url": "https://github.com/owner/repository/pull/7",
        }
        old_visible = "The old requirements need a reframe."
        old = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-old",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": target,
                    "requirements_sha256": "1" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "a" * 40,
                        "sha256": "2" * 64,
                        "visible_content_sha256": exchange.sha256_text(old_visible),
                    },
                    "scope": ["path:src/old.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": "requirements_reframe",
                },
            }
        )["envelope"]
        authority_body = self.authority_body(
            action="reframe",
            exchange_id="exchange-new",
            requirements_sha256="3" * 64,
            supersedes_state_sha256=old["state_sha256"],
            decisions=[],
        )
        receipt = {
            "reference": "review:reframe-authority",
            "sha256": exchange.sha256_text(authority_body),
        }
        new_visible = "The reframed exchange has one required finding."
        reframed = exchange.reduce_request(
            {
                "previous": old,
                "event": {
                    "event_type": "reframe",
                    "exchange_id": "exchange-new",
                    "prior_state_sha256": old["state_sha256"],
                    "round": 1,
                    "surface": "pull_request",
                    "target": target,
                    "requirements_sha256": "3" * 64,
                    "supersedes_state_sha256": old["state_sha256"],
                    "superseded_exchange_ids": [old["state"]["exchange_id"]],
                    "authority_receipt": receipt,
                    "artifact_binding": {
                        "revision": "b" * 40,
                        "sha256": "4" * 64,
                        "visible_content_sha256": exchange.sha256_text(new_visible),
                    },
                    "scope": ["path:src/new.py"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [
                        {
                            "id": "F-001",
                            "category": None,
                            "severity": "major",
                            "disposition": "required",
                            "material_architecture": False,
                            "location": "src/new.py:1",
                            "impact": "The new requirement is incomplete.",
                            "evidence": ["The new case fails."],
                            "closure_condition": "The new case passes.",
                            "introduction": "initial",
                        }
                    ],
                    "stop_reason": None,
                },
            }
        )["envelope"]
        proof = self.delivery.NoGoProof(
            reframed,
            new_visible,
            "reframed-review",
            self.requirements_binding(reframed),
        )

        for association, succeeds in (("OWNER", True), ("NONE", False)):
            self.review_sequence = 0
            forge = FakeForge(
                self.delivery,
                threads=self.carrier_threads(reframed, "reframed-review"),
            )
            forge.labels = {"state:implementation-go", "enhancement"}
            forge.reviews.extend(
                (
                    self.carrier_record("old-review", old, old_visible),
                    self.carrier_record("reframed-review", reframed, new_visible),
                    self.delivery.ReviewRecord(
                        id="reframe-authority",
                        body=authority_body,
                        head_oid="b" * 40,
                        author="maintainer",
                        viewer_did_author=False,
                        includes_created_edit=False,
                        state="COMMENTED",
                        author_association=association,
                        author_permission="ADMIN",
                        submitted_at="2026-01-01T00:00:01.500000Z",
                    ),
                )
            )
            if succeeds:
                result = self.delivery.deliver_no_go(forge, self.binding(), proof)
                self.assertEqual("delivered", result.status)
            else:
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_no_go(forge, self.binding(), proof)
                self.assertNotIn("labels:no-go", forge.events)

    def test_two_reframes_cannot_branch_from_one_superseded_state(self) -> None:
        exchange = self.delivery.review_exchange
        target = {
            "provider": "github",
            "repository": "owner/repository",
            "number": 7,
            "url": "https://github.com/owner/repository/pull/7",
        }
        old_visible = "The old requirements need one authoritative reframe."
        old = exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "exchange-old",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "pull_request",
                    "target": target,
                    "requirements_sha256": "1" * 64,
                    "supersedes_state_sha256": None,
                    "artifact_binding": {
                        "revision": "a" * 40,
                        "sha256": "2" * 64,
                        "visible_content_sha256": exchange.sha256_text(old_visible),
                    },
                    "scope": ["workflow:review-delivery"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": "requirements_reframe",
                },
            }
        )["envelope"]

        def reframe(
            exchange_id: str,
            requirements_sha256: str,
            head_oid: str,
            visible: str,
            authority_id: str,
        ) -> tuple[dict[str, Any], Any]:
            authority_body = self.authority_body(
                action="reframe",
                exchange_id=exchange_id,
                requirements_sha256=requirements_sha256,
                supersedes_state_sha256=old["state_sha256"],
                decisions=[],
            )
            receipt = {
                "reference": f"review:{authority_id}",
                "sha256": exchange.sha256_text(authority_body),
            }
            envelope = exchange.reduce_request(
                {
                    "previous": old,
                    "event": {
                        "event_type": "reframe",
                        "exchange_id": exchange_id,
                        "prior_state_sha256": old["state_sha256"],
                        "round": 1,
                        "surface": "pull_request",
                        "target": target,
                        "requirements_sha256": requirements_sha256,
                        "supersedes_state_sha256": old["state_sha256"],
                        "superseded_exchange_ids": [old["state"]["exchange_id"]],
                        "authority_receipt": receipt,
                        "artifact_binding": {
                            "revision": head_oid,
                            "sha256": "4" * 64,
                            "visible_content_sha256": exchange.sha256_text(visible),
                        },
                        "scope": ["workflow:review-delivery"],
                        "coverage_complete": True,
                        "go_eligible": True,
                        "responses": [],
                        "new_findings": [],
                        "stop_reason": None,
                    },
                }
            )["envelope"]
            authority = self.delivery.ReviewRecord(
                id=authority_id,
                body=authority_body,
                head_oid=head_oid,
                author="maintainer",
                viewer_did_author=False,
                includes_created_edit=False,
                state="COMMENTED",
                author_association="OWNER",
                author_permission="ADMIN",
            )
            return envelope, authority

        selected_visible = "The selected requirements are complete."
        selected, selected_authority = reframe(
            "exchange-selected",
            "3" * 64,
            "b" * 40,
            selected_visible,
            "authority-selected",
        )
        fork_visible = "A different reframe also claims completion."
        forked, fork_authority = reframe(
            "exchange-selected",
            "5" * 64,
            "a" * 40,
            fork_visible,
            "authority-fork",
        )
        manifest = self.delivery.ClosureManifest(
            state_envelope=selected,
            terminal_visible_content=selected_visible,
            entries=(),
            requirements_binding=self.requirements_binding(selected),
        )
        forge = FakeForge(self.delivery, threads=())
        forge.reviews.extend(
            (
                self.carrier_record("old-review", old, old_visible),
                self.carrier_record("fork-review", forked, fork_visible),
                selected_authority,
                fork_authority,
            )
        )

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.binding(), manifest)

        self.assertNotIn("terminal", forge.events)

    def test_no_go_rejects_duplicate_carriers_and_reports_label_uncertainty(
        self,
    ) -> None:
        proof, record = self.no_go_proof()
        threads = self.carrier_threads(proof.state_envelope, proof.review_id)
        forge = FakeForge(self.delivery, threads=threads)
        forge.labels = {"state:implementation-go", "enhancement"}
        forge.reviews.extend(
            (
                record,
                replace(record, id="duplicate-no-go-review"),
            )
        )
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_no_go(forge, self.binding(), proof)
        self.assertNotIn("labels:no-go", forge.events)

        forge = FakeForge(self.delivery, threads=threads)
        forge.labels = {"state:implementation-go", "enhancement"}
        forge.reviews.append(record)
        forge.keep_go_after_no_go_label = True
        with self.assertRaises(self.delivery.DeliveryError) as caught:
            self.delivery.deliver_no_go(forge, self.binding(), proof)
        report = caught.exception.report
        self.assertIsNotNone(report)
        self.assertEqual("partial", report.status)
        self.assertEqual("implementation NO-GO label", report.uncertain_operation)
        self.assertTrue(report.recovery_read_required)

    def test_no_go_revalidates_its_exact_carrier_after_label_delivery(self) -> None:
        proof, record = self.no_go_proof()
        forge = FakeForge(
            self.delivery,
            threads=self.carrier_threads(proof.state_envelope, proof.review_id),
        )
        forge.labels = {"state:implementation-go", "enhancement"}
        forge.reviews.append(record)
        forge.remove_reviews_after_no_go_label = True

        with self.assertRaises(self.delivery.DeliveryError) as caught:
            self.delivery.deliver_no_go(forge, self.binding(), proof)

        report = caught.exception.report
        self.assertIsNotNone(report)
        self.assertEqual("partial", report.status)
        self.assertEqual("no-go-review-1", report.terminal_review_id)
        self.assertEqual(
            ("enhancement", "state:implementation-no-go"),
            report.observed_labels,
        )
        self.assertEqual("implementation NO-GO label", report.uncertain_operation)
        self.assertTrue(report.recovery_read_required)

    def test_adapter_rejects_a_stale_snapshot_before_label_write(self) -> None:
        forge = self.delivery.GitHubForge(self.binding())
        stale = self.delivery.PullRequestSnapshot(
            repository="owner/repository",
            number=7,
            url="https://github.com/owner/repository/pull/7",
            state="OPEN",
            is_draft=False,
            base_oid="a" * 40,
            head_oid="c" * 40,
            labels=frozenset({"state:implementation-no-go"}),
            threads=(),
        )
        with (
            patch.object(forge, "snapshot", return_value=stale),
            patch.object(self.delivery, "_gh") as command,
            self.assertRaises(self.delivery.DeliveryError),
        ):
            forge.set_implementation_go()
        command.assert_not_called()
        with (
            patch.object(forge, "snapshot", return_value=stale),
            patch.object(self.delivery, "_gh") as command,
            self.assertRaises(self.delivery.DeliveryError),
        ):
            forge.set_implementation_no_go()
        command.assert_not_called()

    def test_github_adapter_publishes_exact_terminal_comment(self) -> None:
        calls: list[tuple[tuple[str, ...], dict[str, Any]]] = []
        forge = self.delivery.GitHubForge(self.binding())
        comment = self.delivery.TerminalInlineComment(
            path="src/example.py",
            side="RIGHT",
            line=7,
            body=(
                "Finding.\n\n<!-- HomericIntelligence:review-finding:v1 "
                "exchange=exchange-7 id=F-001 -->"
            ),
        )

        def fake_gh(*arguments: str, **options: Any) -> str:
            calls.append((arguments, options))
            return "{}"

        with patch.object(self.delivery, "_gh", side_effect=fake_gh):
            forge.publish_terminal("canonical body", "b" * 40, (comment,))

        arguments, options = calls[0]
        self.assertEqual("POST", arguments[arguments.index("--method") + 1])
        self.assertIn("repos/owner/repository/pulls/7/reviews", arguments)
        self.assertEqual("-", arguments[arguments.index("--input") + 1])
        payload = json.loads(options["input_text"])
        self.assertEqual("b" * 40, payload["commit_id"])
        self.assertEqual("COMMENT", payload["event"])
        self.assertEqual("canonical body", payload["body"])
        self.assertEqual(
            [
                {
                    "path": "src/example.py",
                    "side": "RIGHT",
                    "line": 7,
                    "body": comment.body,
                }
            ],
            payload["comments"],
        )

    def test_v1_prepare_manifest_adopts_open_legacy_native_identity(self) -> None:
        thread = self.delivery.ReviewThread(
            id="legacy-thread",
            is_resolved=False,
            comments=(
                self.delivery.ReviewComment(
                    id="legacy-comment",
                    body="Legacy required finding.",
                    author="reviewer",
                    viewer_did_author=True,
                    review_head_oid="a" * 40,
                ),
            ),
            viewer_can_reply=True,
            viewer_can_resolve=True,
        )
        forge = FakeForge(self.delivery, threads=(thread,))

        manifest = self.delivery.prepare_response_manifest(
            forge, self.binding(), schema_version=1
        )

        self.assertEqual(1, manifest["schema_version"])
        self.assertEqual("native:legacy-comment", manifest["entries"][0]["finding_id"])
        self.assertIsNone(manifest["entries"][0]["finding_exchange_id"])
        self.assertIsNone(manifest["entries"][0]["finding_state_sha256"])
        self.assertIsNone(manifest["entries"][0]["superseding_state_sha256"])
        self.assertEqual("a" * 40, manifest["entries"][0]["origin_review_head_oid"])
        self.assertNotIn("body", manifest["entries"][0])
        self.assertEqual(
            self.delivery._requirements_binding_dict(
                forge.collect_requirements_binding(())
            ),
            manifest["requirements_binding"],
        )

        missing_head = replace(
            thread,
            comments=(replace(thread.comments[0], review_head_oid=None),),
        )
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.prepare_response_manifest(
                FakeForge(self.delivery, threads=(missing_head,)),
                self.binding(),
            )

    def test_v1_manifest_loader_accepts_structure_and_rejects_arbitrary_body(
        self,
    ) -> None:
        thread = self.owned_thread()
        manifest = self.v1_manifest(thread)
        document = self.delivery.closure_manifest_document(self.binding(), manifest)
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "closure.json"
            path.write_text(
                self.delivery.review_exchange.canonical_json(document),
                encoding="utf-8",
            )
            loaded = self.delivery.load_response_manifest(path, self.binding())
            document["entries"][0]["body"] = "arbitrary reviewer prose"
            path.write_text(
                self.delivery.review_exchange.canonical_json(document),
                encoding="utf-8",
            )
            with self.assertRaises(self.delivery.DeliveryError):
                self.delivery.load_response_manifest(path, self.binding())

        self.assertIsInstance(loaded, self.delivery.ClosureManifest)
        self.assertEqual("F-001", loaded.entries[0].finding_id)

    def test_v1_manifest_loader_accepts_exact_finding_state_identity(self) -> None:
        thread = self.owned_thread()
        document = self.delivery.closure_manifest_document(
            self.binding(), self.v1_manifest(thread)
        )
        document["entries"][0].update(
            {
                "finding_exchange_id": "exchange-7",
                "finding_state_sha256": "1" * 64,
                "superseding_state_sha256": None,
            }
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "closure.json"
            path.write_text(
                self.delivery.review_exchange.canonical_json(document),
                encoding="utf-8",
            )

            loaded = self.delivery.load_response_manifest(path, self.binding())

        self.assertEqual("exchange-7", loaded.entries[0].finding_exchange_id)
        self.assertEqual("1" * 64, loaded.entries[0].finding_state_sha256)
        self.assertIsNone(loaded.entries[0].superseding_state_sha256)

    def test_v1_manifest_loader_rejects_invalid_finding_state_identity(self) -> None:
        missing = object()
        cases = (
            ("missing exchange", "finding_exchange_id", missing),
            ("exchange whitespace", "finding_exchange_id", "exchange old"),
            ("missing source", "finding_state_sha256", missing),
            ("invalid source", "finding_state_sha256", "g" * 64),
            ("invalid successor", "superseding_state_sha256", "f" * 63),
        )
        for case, field, value in cases:
            document = self.delivery.closure_manifest_document(
                self.binding(), self.v1_manifest(self.owned_thread())
            )
            if value is missing:
                del document["entries"][0][field]
            else:
                document["entries"][0][field] = value
            with tempfile.TemporaryDirectory() as temporary_directory:
                path = Path(temporary_directory) / "closure.json"
                path.write_text(
                    self.delivery.review_exchange.canonical_json(document),
                    encoding="utf-8",
                )
                with (
                    self.subTest(case=case),
                    self.assertRaises(self.delivery.DeliveryError),
                ):
                    self.delivery.load_response_manifest(path, self.binding())

    def test_prepared_manifest_can_be_completed_and_loaded(self) -> None:
        thread = self.owned_thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        manifest = self.v1_manifest(thread)
        prepared = self.delivery.prepare_response_manifest(
            forge,
            self.binding(),
            requirement_issue_urls=(),
        )
        self.assertEqual("exchange-7", prepared["entries"][0]["finding_exchange_id"])
        self.assertIsNone(prepared["entries"][0]["finding_state_sha256"])
        self.assertIsNone(prepared["entries"][0]["superseding_state_sha256"])
        completed = self.delivery.closure_manifest_document(self.binding(), manifest)
        prepared.update(
            {
                "state": completed["state"],
                "terminal_visible_content": completed["terminal_visible_content"],
                "entries": completed["entries"],
                "comments": completed["comments"],
                "summary_finding_ids": completed["summary_finding_ids"],
            }
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "completed.json"
            path.write_text(
                self.delivery.review_exchange.canonical_json(prepared),
                encoding="utf-8",
            )
            loaded = self.delivery.load_response_manifest(path, self.binding())

        self.assertEqual(manifest, loaded)

    def test_no_go_proof_loader_accepts_only_the_exact_bound_schema(self) -> None:
        proof, _ = self.no_go_proof()
        document = {
            "schema_id": self.delivery.NO_GO_PROOF_SCHEMA_ID,
            "schema_version": 1,
            "binding": self.delivery._binding_dict(self.binding()),
            "review_id": proof.review_id,
            "state": proof.state_envelope,
            "visible_content": proof.visible_content,
            "requirements_binding": self.delivery._requirements_binding_dict(
                proof.requirements_binding
            ),
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "no-go.json"
            path.write_text(
                self.delivery.review_exchange.canonical_json(document),
                encoding="utf-8",
            )
            loaded = self.delivery.load_no_go_proof(path, self.binding())
            document["unknown"] = True
            path.write_text(
                self.delivery.review_exchange.canonical_json(document),
                encoding="utf-8",
            )
            with self.assertRaises(self.delivery.DeliveryError):
                self.delivery.load_no_go_proof(path, self.binding())

        self.assertEqual(proof, loaded)

    def test_v1_loaders_bound_input_before_parsing_and_require_canonical_json(
        self,
    ) -> None:
        thread = self.owned_thread()
        manifest_document = self.delivery.closure_manifest_document(
            self.binding(), self.v1_manifest(thread)
        )
        proof, _ = self.no_go_proof()
        proof_document = {
            "schema_id": self.delivery.NO_GO_PROOF_SCHEMA_ID,
            "schema_version": 1,
            "binding": self.delivery._binding_dict(self.binding()),
            "review_id": proof.review_id,
            "state": proof.state_envelope,
            "visible_content": proof.visible_content,
            "requirements_binding": self.delivery._requirements_binding_dict(
                proof.requirements_binding
            ),
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "input.json"
            path.write_bytes(b" " * (self.delivery.review_exchange.MAX_INPUT_BYTES + 1))
            oversized_size = path.stat().st_size
            for loader in (
                self.delivery.load_response_manifest,
                self.delivery.load_legacy_proof,
                self.delivery.load_no_go_proof,
            ):
                with (
                    self.subTest(loader=loader.__name__),
                    self.assertRaises(self.delivery.DeliveryError),
                ):
                    loader(path, self.binding())
                self.assertEqual(oversized_size, path.stat().st_size)
            for loader, document in (
                (self.delivery.load_response_manifest, manifest_document),
                (self.delivery.load_no_go_proof, proof_document),
            ):
                path.write_text(
                    json.dumps(document, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                noncanonical_bytes = path.read_bytes()
                with (
                    self.subTest(loader=loader.__name__),
                    self.assertRaises(self.delivery.DeliveryError),
                ):
                    loader(path, self.binding())
                self.assertEqual(noncanonical_bytes, path.read_bytes())

    def test_manifest_parser_rejects_invalid_v1_shapes_without_mutation(
        self,
    ) -> None:
        thread = self.owned_thread()
        base = self.delivery.closure_manifest_document(
            self.binding(), self.v1_manifest(thread)
        )
        entry = base["entries"][0]
        inline_manifest, inline = self.terminal_inline_manifest()
        inline_base = self.delivery.closure_manifest_document(
            self.binding(), inline_manifest
        )
        cases = (
            {**base, "unexpected": True},
            {
                key: value
                for key, value in base.items()
                if key != "requirements_binding"
            },
            {**base, "schema_version": True},
            {
                **base,
                "binding": {**base["binding"], "head_oid": "c" * 40},
            },
            {**base, "entries": {}},
            {**base, "comments": {}},
            {**base, "summary_finding_ids": {}},
            {
                **base,
                "requirements_binding": {
                    **base["requirements_binding"],
                    "reviewed_scope_sha256": "invalid",
                },
            },
            {
                **base,
                "requirements_binding": {
                    **base["requirements_binding"],
                    "requirement_issue_urls": [
                        "https://github.com/owner/repository/issues/2",
                        "https://github.com/owner/repository/issues/1",
                    ],
                },
            },
            {
                **base,
                "entries": [{**entry, "closure_evidence": []}],
            },
            {
                **base,
                "entries": [
                    {
                        **entry,
                        "authority_receipt": {
                            "reference": "review:authority",
                            "sha256": "invalid",
                        },
                    }
                ],
            },
            {
                **inline_base,
                "comments": [
                    {**self.delivery._terminal_comment_dict(inline), "path": "/tmp/x"}
                ],
            },
            {
                **inline_base,
                "comments": [
                    {**self.delivery._terminal_comment_dict(inline), "side": "BOTH"}
                ],
            },
            {
                **inline_base,
                "comments": [
                    {**self.delivery._terminal_comment_dict(inline), "line": 0}
                ],
            },
            {
                **inline_base,
                "comments": [
                    {
                        **self.delivery._terminal_comment_dict(inline),
                        "body": "x"
                        * (
                            self.delivery.review_exchange.PROVIDER_BODY_LIMITS["github"]
                            + 1
                        ),
                    }
                ],
            },
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "manifest.json"
            for document in cases:
                content = self.delivery.review_exchange.canonical_json(document)
                path.write_text(content, encoding="utf-8")
                before = path.read_bytes()

                with (
                    self.subTest(document=document),
                    self.assertRaises(self.delivery.DeliveryError),
                ):
                    self.delivery.load_response_manifest(path, self.binding())

                self.assertEqual(before, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
