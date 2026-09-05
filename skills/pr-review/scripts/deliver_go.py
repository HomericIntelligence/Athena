#!/usr/bin/env python3
"""Deliver an exact pull-request GO decision through a bound forge adapter."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pr_identity import (
    pull_request_number,
    repository_from_pr_url,
    require_canonical_pull_request_url,
    require_commit_oid,
    require_github_host,
    require_github_repository,
)

from skills._cli import argument_parser, run_command

GO_LABEL = "state:implementation-go"
NO_GO_LABEL = "state:implementation-no-go"
GITHUB_HOST = "github.com"


class DeliveryError(RuntimeError):
    """A GO delivery precondition, write, or postcondition failed."""


@dataclass(frozen=True)
class ReviewComment:
    """One comment in one complete review-thread history."""

    id: str
    body: str
    author: str


@dataclass(frozen=True)
class ReviewThread:
    """One review thread and its complete comment history."""

    id: str
    is_resolved: bool
    comments: tuple[ReviewComment, ...]


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
class DeliveryResult:
    """The verified result of a GO delivery."""

    status: str
    resolved_thread_ids: tuple[str, ...]
    label: str = GO_LABEL


def auto_merge_eligible(merge_readiness: dict[str, Any] | None) -> bool:
    """Return whether repository policy allows auto-merge."""
    return (
        isinstance(merge_readiness, dict)
        and merge_readiness.get("review_decision") == "APPROVED"
    )


class Forge(Protocol):
    """The minimum bound forge capability used by the delivery state machine."""

    def snapshot(self) -> PullRequestSnapshot:
        """Read one complete pull-request snapshot."""

    def reply(self, thread_id: str, body: str) -> None:
        """Post one deterministic reply to one retained review thread."""

    def resolve(self, thread_id: str) -> None:
        """Resolve one retained review thread."""

    def set_implementation_go(self) -> None:
        """Apply the exclusive implementation GO state label."""


def conversation_sha256(thread: ReviewThread) -> str:
    """Hash a complete conversation with a stable, length-delimited encoding."""
    payload = {
        "comments": [
            {"author": comment.author, "body": comment.body, "id": comment.id}
            for comment in thread.comments
        ],
        "id": thread.id,
        "is_resolved": thread.is_resolved,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


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


def _response_map(
    snapshot: PullRequestSnapshot, responses: Sequence[ThreadResponse]
) -> dict[str, ThreadResponse]:
    thread_ids = [thread.id for thread in snapshot.threads]
    if len(thread_ids) != len(set(thread_ids)):
        raise DeliveryError("The forge returned duplicate review-thread identifiers.")
    unresolved = {
        thread.id: thread for thread in snapshot.threads if not thread.is_resolved
    }
    by_id: dict[str, ThreadResponse] = {}
    for response in responses:
        if (
            not isinstance(response.thread_id, str)
            or not isinstance(response.conversation_sha256, str)
            or not isinstance(response.body, str)
        ):
            raise DeliveryError("The response manifest contains an invalid response.")
        if response.thread_id in by_id:
            raise DeliveryError("The response manifest contains a duplicate thread.")
        if response.thread_id not in unresolved:
            raise DeliveryError(
                "The response manifest does not match the current threads."
            )
        if not response.body.strip():
            raise DeliveryError("The response manifest contains an empty response.")
        if response.conversation_sha256 != conversation_sha256(
            unresolved[response.thread_id]
        ):
            raise DeliveryError(
                "The response manifest is not bound to the current conversation."
            )
        by_id[response.thread_id] = response
    missing = sorted(set(unresolved).difference(by_id))
    if missing:
        raise DeliveryError(
            "The response manifest does not cover every unresolved review thread."
        )
    return by_id


def _has_response(thread: ReviewThread, body: str) -> bool:
    return any(comment.body == body for comment in thread.comments)


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


def _response_is_only_conversation_change(
    before: ReviewThread, after: ReviewThread, body: str
) -> bool:
    """Return whether one exact response is the only new comment."""
    return (
        not after.is_resolved
        and after.comments[:-1] == before.comments
        and len(after.comments) == len(before.comments) + 1
        and after.comments[-1].body == body
    )


def _recovered_response_body(
    thread: ReviewThread, binding: ReviewBinding
) -> str | None:
    """Return the body of one exact prior delivery response at the thread tip."""
    if not thread.comments:
        return None
    delivered = thread.comments[-1].body
    separator = "\n\n<!-- athena-pr-review-go-response:"
    if separator not in delivered or not delivered.endswith(" -->"):
        return None
    body, _ = delivered.rsplit(separator, maxsplit=1)
    prior = ReviewThread(thread.id, False, thread.comments[:-1])
    response = ThreadResponse(thread.id, conversation_sha256(prior), body)
    return body if _delivery_body(binding, response) == delivered else None


def _thread(snapshot: PullRequestSnapshot, thread_id: str) -> ReviewThread:
    matches = [thread for thread in snapshot.threads if thread.id == thread_id]
    if len(matches) != 1:
        raise DeliveryError("The review thread set changed during GO delivery.")
    return matches[0]


def _call_write(action: str, callback: Any, *arguments: str) -> None:
    try:
        callback(*arguments)
    except Exception as error:
        raise DeliveryError(
            f"The forge {action} failed. The result is not retried or compensated: {error}"
        ) from error


def deliver_go(
    forge: Forge, binding: ReviewBinding, responses: Sequence[ThreadResponse]
) -> DeliveryResult:
    """Reply to and resolve every open thread, then apply and verify GO.

    Every write is preceded by an exact-head read. A failed or indeterminate write
    stops the operation. The caller must inspect the forge before any later action.
    """
    initial = _snapshot(forge, binding)
    if GO_LABEL in initial.labels:
        raise DeliveryError(
            "A pre-existing GO label cannot prove this delivery. "
            "Inspect the bound thread and label history before another action."
        )

    response_by_id = _response_map(initial, responses)
    resolved: list[str] = []
    for thread_id in sorted(response_by_id):
        response = response_by_id[thread_id]
        body = _delivery_body(binding, response)
        current = _snapshot(forge, binding)
        thread = _thread(current, thread_id)
        if thread.is_resolved:
            raise DeliveryError("The review thread changed before its response.")
        if conversation_sha256(thread) != response.conversation_sha256:
            raise DeliveryError("The review conversation changed before its response.")
        recovered_body = _recovered_response_body(thread, binding)
        if recovered_body is not None and recovered_body == response.body:
            after_reply = thread
        else:
            if _has_response(thread, body):
                raise DeliveryError(
                    "The response manifest contains an ambiguous prior response."
                )
            before_reply = thread
            _call_write("reply", forge.reply, thread_id, body)
            current = _snapshot(forge, binding)
            after_reply = _thread(current, thread_id)
            if not _response_is_only_conversation_change(
                before_reply, after_reply, body
            ):
                raise DeliveryError(
                    "The forge did not verify the exact posted review response."
                )
        current = _snapshot(forge, binding)
        before_resolution = _thread(current, thread_id)
        if before_resolution != after_reply:
            raise DeliveryError(
                "The review conversation changed before thread resolution."
            )
        _call_write("resolve", forge.resolve, thread_id)
        after_resolution_snapshot = _snapshot(forge, binding)
        after_resolution = _thread(after_resolution_snapshot, thread_id)
        if (
            not after_resolution.is_resolved
            or after_resolution.comments != before_resolution.comments
        ):
            raise DeliveryError(
                "The forge did not verify exact review-thread resolution."
            )
        resolved.append(thread_id)

    current = _snapshot(forge, binding)
    if any(not thread.is_resolved for thread in current.threads):
        raise DeliveryError(
            "An unresolved review thread remains; withhold GO delivery."
        )

    _snapshot(forge, binding)
    _call_write("implementation label", forge.set_implementation_go)
    final = _snapshot(forge, binding)
    if GO_LABEL not in final.labels:
        raise DeliveryError("The implementation GO label was not verified.")
    if NO_GO_LABEL in final.labels:
        raise DeliveryError("The implementation state labels are not exclusive.")
    if any(not thread.is_resolved for thread in final.threads):
        raise DeliveryError("An unresolved review thread remains after label delivery.")
    return DeliveryResult("delivered", tuple(resolved))


def _gh(*arguments: str) -> str:
    result = run_command(
        ("gh", *arguments), capture_output=True, text=True, check=False
    )
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

    def snapshot(self) -> PullRequestSnapshot:
        query = """
        query($owner:String!, $name:String!, $number:Int!) {
          repository(owner:$owner, name:$name) { pullRequest(number:$number) {
            number url state isDraft baseRefOid headRefOid
            labels(first:100) { pageInfo { hasNextPage } nodes { name } }
            reviewThreads(first:100) { pageInfo { hasNextPage } nodes {
              id isResolved comments(first:100) { pageInfo { hasNextPage } nodes {
                id body author { login }
              } }
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
        if pull_request.get("reviewThreads", {}).get("pageInfo", {}).get("hasNextPage"):
            raise DeliveryError("GitHub review-thread coverage is incomplete.")
        raw_threads = pull_request.get("reviewThreads", {}).get("nodes")
        if not isinstance(raw_threads, list):
            raise DeliveryError("GitHub returned invalid review-thread data.")
        threads: list[ReviewThread] = []
        for raw_thread in raw_threads:
            if not isinstance(raw_thread, dict):
                raise DeliveryError("GitHub returned invalid review-thread data.")
            comments_data = raw_thread.get("comments")
            if not isinstance(comments_data, dict) or comments_data.get(
                "pageInfo", {}
            ).get("hasNextPage"):
                raise DeliveryError("GitHub review-comment coverage is incomplete.")
            raw_comments = comments_data.get("nodes")
            if not isinstance(raw_comments, list):
                raise DeliveryError("GitHub returned invalid review-comment data.")
            comments: list[ReviewComment] = []
            for raw_comment in raw_comments:
                if (
                    not isinstance(raw_comment, dict)
                    or not isinstance(raw_comment.get("id"), str)
                    or not isinstance(raw_comment.get("body"), str)
                ):
                    raise DeliveryError("GitHub returned invalid review-comment data.")
                author = raw_comment.get("author") or {}
                comments.append(
                    ReviewComment(
                        raw_comment["id"],
                        raw_comment["body"],
                        str(author.get("login", "")),
                    )
                )
            thread_id = raw_thread.get("id")
            if not isinstance(thread_id, str) or not isinstance(
                raw_thread.get("isResolved"), bool
            ):
                raise DeliveryError("GitHub returned invalid review-thread data.")
            threads.append(
                ReviewThread(thread_id, raw_thread["isResolved"], tuple(comments))
            )
        raw_labels = pull_request.get("labels")
        if not isinstance(raw_labels, dict) or raw_labels.get("pageInfo", {}).get(
            "hasNextPage"
        ):
            raise DeliveryError("GitHub label coverage is incomplete.")
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
            is_draft=bool(pull_request.get("isDraft")),
            base_oid=require_commit_oid(pull_request.get("baseRefOid"), "baseRefOid"),
            head_oid=require_commit_oid(pull_request.get("headRefOid"), "headRefOid"),
            labels=labels,
            threads=tuple(threads),
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


def _manifest_value(value: object, description: str) -> str:
    if not isinstance(value, str) or not value:
        raise DeliveryError(f"The response manifest contains an invalid {description}.")
    return value


def load_response_manifest(
    path: Path, binding: ReviewBinding
) -> tuple[ThreadResponse, ...]:
    """Load and validate a JSON response manifest for one exact binding."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DeliveryError(f"The response manifest cannot be read: {error}") from error
    if isinstance(document, dict):
        raw_responses = document.get("responses")
        raw_binding = document.get("binding")
        if not isinstance(raw_binding, dict) or any(
            raw_binding.get(key) != value
            for key, value in {
                "repository": binding.repository,
                "number": binding.number,
                "url": binding.url,
                "base_oid": binding.base_oid,
                "head_oid": binding.head_oid,
            }.items()
        ):
            raise DeliveryError(
                "The response manifest is not bound to the requested pull request."
            )
    else:
        raw_responses = None
    if not isinstance(raw_responses, list):
        raise DeliveryError("The response manifest must contain a response list.")
    responses: list[ThreadResponse] = []
    for raw in raw_responses:
        if not isinstance(raw, dict):
            raise DeliveryError("The response manifest contains an invalid response.")
        responses.append(
            ThreadResponse(
                _manifest_value(raw.get("thread_id"), "thread identifier"),
                _manifest_value(raw.get("conversation_sha256"), "conversation digest"),
                _manifest_value(raw.get("body"), "response body"),
            )
        )
    return tuple(responses)


def prepare_response_manifest(
    forge: Forge, binding: ReviewBinding
) -> dict[str, object]:
    """Return a read-only response template for every current open thread."""
    snapshot = _snapshot(forge, binding)
    responses: list[dict[str, object]] = []
    for thread in snapshot.threads:
        if thread.is_resolved:
            continue
        responses.append(
            {
                "body": _recovered_response_body(thread, binding) or "",
                "comments": [
                    {
                        "author": comment.author,
                        "body": comment.body,
                        "id": comment.id,
                    }
                    for comment in thread.comments
                ],
                "conversation_sha256": conversation_sha256(thread),
                "thread_id": thread.id,
            }
        )
    return {
        "binding": {
            "base_oid": binding.base_oid,
            "head_oid": binding.head_oid,
            "number": binding.number,
            "repository": binding.repository,
            "url": binding.url,
        },
        "responses": responses,
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
    args = parser.parse_args(argv)
    try:
        binding = _binding_from_args(args)
        forge = GitHubForge(binding, args.target_host)
        if args.prepare_manifest:
            print(json.dumps(prepare_response_manifest(forge, binding), sort_keys=True))
            return 0
        if args.response_manifest is None:
            raise DeliveryError("The response manifest path is missing.")
        responses = load_response_manifest(args.response_manifest, binding)
        result = deliver_go(forge, binding, responses)
    except (DeliveryError, RuntimeError, TypeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "label": result.label,
                "resolved_thread_ids": result.resolved_thread_ids,
                "status": result.status,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
