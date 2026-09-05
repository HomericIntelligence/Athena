#!/usr/bin/env python3
"""Collect GitHub pull-request metadata and immutable review evidence."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import IO, Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from materialize_snapshot import (
    MaterializedSnapshot,
    materialize_snapshot,
    remove_snapshot,
)
from pr_identity import (
    COMMIT_OID,
    pull_request_number,
    repository_from_pr_url,
    require_canonical_pull_request_url,
    require_commit_oid,
    require_github_repository,
    validate_pr_identifier,
)

from skills._cli import (
    argument_parser,
    git_read_arguments,
    git_read_environment,
    require_complete_git_history,
    require_unambiguous_git_merge_base,
    run_command,
)

# Keep this query below GitHub's GraphQL complexity budget. Strict callers bind
# changed paths to local immutable Git objects. Earlier callers use the REST
# file-list fallback only for backward compatibility.
FIELDS = (
    "number,title,body,state,isDraft,author,baseRefName,headRefName,"
    "baseRefOid,headRefOid,reviews,statusCheckRollup,closingIssuesReferences,url"
)
ISSUE_FIELDS = "id,number,url,title,body,state"
READ_CHUNK_SIZE = 64 * 1024
LINKED_ISSUE_COMMENT_PAGE_SIZE = 100
MAX_LINKED_ISSUE_COMMENT_PAGES = 10
MAX_LINKED_ISSUE_COMMENTS = 1_000
MAX_LINKED_ISSUE_COMMENT_PAGE_BYTES = 256 * 1024
MAX_LINKED_ISSUE_COMMENT_BYTES = 1024 * 1024
MAX_LINKED_ISSUE_COMMENT_STDERR_BYTES = 16 * 1024
LINKED_ISSUE_COMMENT_REQUEST_TIMEOUT_SECONDS = 30.0
PROVIDER_POLL_SECONDS = 0.01
PROVIDER_READER_JOIN_SECONDS = 1.0
MAX_LINKED_REQUIREMENT_METADATA_BYTES = 256 * 1024
MAX_LINKED_REQUIREMENT_REQUESTS = 48
MAX_LINKED_REQUIREMENT_PAGES = 24
MAX_LINKED_REQUIREMENT_COMMENTS = 2_000
MAX_LINKED_REQUIREMENT_BYTES = 2 * 1024 * 1024
MAX_CHANGED_PATH_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_CHANGED_PATHS = 10_000
MAX_CHANGED_PATH_STDERR_BYTES = 16 * 1024
CHANGED_PATH_REQUEST_TIMEOUT_SECONDS = 30.0
MAX_CHECK_RUN_BYTES = 2 * 1024 * 1024
MAX_CHECK_RUN_PAGES = 100
MAX_CHECK_RUNS = 10_000
MAX_CHECK_RUN_STDERR_BYTES = 16 * 1024
CHECK_RUN_REQUEST_TIMEOUT_SECONDS = 30.0


class LinkedRequirementsCoverageGap(RuntimeError):
    """A linked requirement exceeds bounded evidence collection limits."""


class ChangedPathCoverageGap(RuntimeError):
    """Changed paths exceed the bounded immutable-evidence collector."""


class CheckEvidenceCoverageGap(RuntimeError):
    """GitHub checks cannot be bound completely to the reviewed head."""


@dataclass
class LinkedRequirementBudget:
    """This budget controls both strict evidence reads from the provider."""

    pages: int = 0
    comments: int = 0
    bytes_read: int = 0
    requests: int = 0

    def remaining_bytes(self) -> int:
        """Return remaining aggregate provider-output capacity."""
        return MAX_LINKED_REQUIREMENT_BYTES - self.bytes_read

    def reserve_request(self) -> None:
        """Reserve one bounded provider request before issuing it."""
        if self.requests >= MAX_LINKED_REQUIREMENT_REQUESTS:
            raise LinkedRequirementsCoverageGap(
                "The linked issue requirements exceed the safe aggregate request limit."
            )
        self.requests += 1

    def reserve_comment_page(self) -> None:
        """Reserve one aggregate comment page and its provider request."""
        if self.pages >= MAX_LINKED_REQUIREMENT_PAGES:
            raise LinkedRequirementsCoverageGap(
                "The linked issue requirements exceed the safe aggregate page limit."
            )
        self.reserve_request()

    def record_bytes(self, count: int) -> None:
        """Account for one provider response without crossing the byte budget."""
        if count > self.remaining_bytes():
            raise LinkedRequirementsCoverageGap(
                "The linked issue requirements exceed the safe aggregate byte limit."
            )
        self.bytes_read += count

    def record_comment_page(self, count: int) -> None:
        """Account for one successful provider page and its item count."""
        if self.comments + count > MAX_LINKED_REQUIREMENT_COMMENTS:
            raise LinkedRequirementsCoverageGap(
                "The linked issue requirements exceed the safe aggregate comment limit."
            )
        self.pages += 1
        self.comments += count


@dataclass
class ProviderStream:
    """This record contains one bounded asynchronous output stream."""

    maximum_bytes: int
    output: bytearray = field(default_factory=bytearray)
    overflowed: threading.Event = field(default_factory=threading.Event)
    completed: threading.Event = field(default_factory=threading.Event)
    error: OSError | ValueError | None = None


@dataclass
class ChangedPathStream:
    """Incrementally validate a bounded null-byte-delimited Git path manifest."""

    maximum_bytes: int
    maximum_paths: int
    bytes_read: int = 0
    paths: list[bytes] = field(default_factory=list)
    seen_paths: set[bytes] = field(default_factory=set)
    trailing: bytearray = field(default_factory=bytearray)
    limit_error: str | None = None
    overflowed: threading.Event = field(default_factory=threading.Event)
    completed: threading.Event = field(default_factory=threading.Event)
    error: OSError | RuntimeError | ValueError | None = None


@dataclass(frozen=True)
class ImmutableIdentity:
    """This record binds evidence to a review artifact and its exact revisions."""

    repository: str
    number: int
    url: str
    base_oid: str
    head_oid: str

    def as_json(self) -> dict[str, object]:
        """Return the stable, serializable evidence binding."""
        return {
            "forge_host": "github.com",
            "repository": self.repository,
            "number": self.number,
            "url": self.url,
            "state": "OPEN",
            "base_oid": self.base_oid,
            "head_oid": self.head_oid,
        }


@dataclass(frozen=True)
class ExpectedReviewTarget:
    """This record identifies the immutable GitHub target for strict collection."""

    host: str
    repository: str
    number: int
    url: str

    def repository_argument(self) -> str:
        """Return the fully qualified repository argument accepted by gh."""
        return f"{self.host}/{self.repository}"


@dataclass(frozen=True)
class ChangedPathManifest:
    """This record describes a canonical changed-path manifest from Git objects."""

    paths: tuple[str, ...]
    sha256: str

    def as_json(self) -> dict[str, object]:
        """Return the manifest binding carried with strict evidence."""
        return {
            "encoding": "utf-8-nul",
            "count": len(self.paths),
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class ReviewScope:
    """This record binds mutable review-context fields to an evidence collection."""

    fields: dict[str, Any]
    sha256: str

    def as_json(self) -> dict[str, object]:
        """Return the revalidated review-context binding."""
        return {"fields": self.fields, "sha256": self.sha256}


@dataclass(frozen=True)
class LinkedRequirements:
    """This record binds the canonical content of each linked issue used as requirements."""

    items: tuple[LinkedRequirement, ...]
    sha256: str

    def as_json(self) -> dict[str, object]:
        """Return the serializable linked-requirements binding."""
        return {
            "count": len(self.items),
            "items": [item.as_json() for item in self.items],
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class LinkedRequirement:
    """This record contains one linked issue identity and its requirements digest."""

    id: str
    repository: str
    number: int
    url: str
    content_sha256: str

    def as_json(self) -> dict[str, str | int]:
        """Return the individual requirement record carried in review evidence."""
        return {
            "content_sha256": self.content_sha256,
            "id": self.id,
            "number": self.number,
            "repository": self.repository,
            "url": self.url,
        }


def metadata_error(metadata: object, *, require_immutable_identity: bool) -> str | None:
    """Return a diagnostic when GitHub returns partial pull-request metadata."""
    if not isinstance(metadata, dict):
        return "The pull-request metadata must be a JSON object."
    required_types = {
        "number": int,
        "title": str,
        "state": str,
        "author": dict,
        "baseRefName": str,
        "headRefName": str,
        "statusCheckRollup": list,
        "url": str,
    }
    invalid = [
        field
        for field, expected_type in required_types.items()
        if not isinstance(metadata.get(field), expected_type)
    ]
    author = metadata.get("author")
    if not isinstance(author, dict) or not isinstance(author.get("login"), str):
        invalid.append("author.login")
    if invalid:
        return (
            "GitHub returned pull-request metadata fields that are incomplete or not valid: "
            + ", ".join(f"'{field}'" for field in sorted(set(invalid)))
            + "."
        )
    if metadata["state"] != "OPEN":
        return f"Pull request {metadata['number']} is not open."
    identity_fields = ("baseRefOid", "headRefOid")
    identity_values = [metadata.get(field) for field in identity_fields]
    has_identity = any(value is not None for value in identity_values)
    if require_immutable_identity or has_identity:
        invalid_identity = [
            field
            for field, value in zip(identity_fields, identity_values, strict=True)
            if not isinstance(value, str) or COMMIT_OID.fullmatch(value) is None
        ]
        if invalid_identity:
            return (
                "GitHub returned immutable pull-request identity fields that are "
                "incomplete or not valid: "
                + ", ".join(f"'{field}'" for field in invalid_identity)
                + "."
            )
    if require_immutable_identity:
        body = metadata.get("body")
        closing_issues = metadata.get("closingIssuesReferences")
        scope_invalid: list[str] = []
        if "body" not in metadata or (body is not None and not isinstance(body, str)):
            scope_invalid.append("body")
        if not isinstance(metadata.get("isDraft"), bool):
            scope_invalid.append("isDraft")
        if not isinstance(closing_issues, list) or not all(
            isinstance(issue, dict) for issue in closing_issues
        ):
            scope_invalid.append("closingIssuesReferences")
        if scope_invalid:
            return (
                "GitHub returned review-scope fields that are incomplete or not valid: "
                + ", ".join(f"'{field}'" for field in scope_invalid)
                + "."
            )
    return None


def immutable_identity(
    metadata: dict[str, Any], repository: str, *, require_immutable_identity: bool
) -> ImmutableIdentity | None:
    """Build a validated identity when immutable revisions are available."""
    base_oid = metadata.get("baseRefOid")
    head_oid = metadata.get("headRefOid")
    if base_oid is None and head_oid is None and not require_immutable_identity:
        return None
    if not isinstance(base_oid, str) or not isinstance(head_oid, str):
        raise TypeError("GitHub returned incomplete immutable pull-request identity.")
    number = metadata.get("number")
    url = metadata.get("url")
    if not isinstance(number, int) or not isinstance(url, str):
        raise TypeError("GitHub returned incomplete pull-request identity.")
    return ImmutableIdentity(
        repository=repository,
        number=number,
        url=url,
        base_oid=base_oid,
        head_oid=head_oid,
    )


def expected_identity(
    parser: Any, base_oid: str | None, head_oid: str | None
) -> tuple[str, str] | None:
    """Validate the optional immutable identity supplied by resolve_pr.py."""
    if (base_oid is None) != (head_oid is None):
        parser.error("Specify --expected-base-oid and --expected-head-oid together.")
    if base_oid is None or head_oid is None:
        return None
    if COMMIT_OID.fullmatch(base_oid) is None:
        parser.error(
            "--expected-base-oid must be a Git commit object identifier that contains "
            "40 lowercase hexadecimal characters."
        )
    if COMMIT_OID.fullmatch(head_oid) is None:
        parser.error(
            "--expected-head-oid must be a Git commit object identifier that contains "
            "40 lowercase hexadecimal characters."
        )
    return base_oid, head_oid


def expected_target(
    parser: Any,
    identity: tuple[str, str] | None,
    host: str | None,
    repository: str | None,
    number: int | None,
    url: str | None,
) -> ExpectedReviewTarget | None:
    """Require the resolved GitHub target when immutable object identifiers are supplied."""
    if identity is None:
        if (
            host is not None
            or repository is not None
            or number is not None
            or url is not None
        ):
            parser.error(
                "If you specify an expected target, also specify --expected-base-oid "
                "and --expected-head-oid."
            )
        return None
    if host is None or repository is None or number is None or url is None:
        parser.error(
            "With --expected-base-oid and --expected-head-oid, specify "
            "--expected-host, --expected-repository, --expected-pr-number, and "
            "--expected-pr-url."
        )
    assert host is not None
    assert repository is not None
    assert number is not None
    assert url is not None
    if host != "github.com":
        parser.error("'--expected-host' must be 'github.com'.")
    try:
        canonical_repository = require_github_repository(
            repository, "--expected-repository"
        )
    except RuntimeError as error:
        parser.error(str(error))
    if number < 1:
        parser.error("--expected-pr-number must be a positive pull-request number.")
    try:
        canonical_url = require_canonical_pull_request_url(
            url, canonical_repository, number, "--expected-pr-url"
        )
    except RuntimeError as error:
        parser.error(str(error))
    return ExpectedReviewTarget(
        host=host,
        repository=canonical_repository,
        number=number,
        url=canonical_url,
    )


def ensure_expected_identity(
    identity: ImmutableIdentity | None, expected: tuple[str, str] | None
) -> None:
    """Fail closed when collected revisions differ from the resolved pull request."""
    if expected is None:
        return
    if identity is None:
        raise RuntimeError("GitHub did not return an immutable pull-request identity.")
    if (identity.base_oid, identity.head_oid) != expected:
        raise RuntimeError(
            "The immutable pull-request identity does not match the expected base "
            "object identifier and head object identifier."
        )


def ensure_expected_target(
    identity: ImmutableIdentity | None, target: ExpectedReviewTarget | None
) -> None:
    """Fail closed when collected artifact identity differs from the resolved target."""
    if target is None:
        return
    if identity is None:
        raise RuntimeError("GitHub did not return an immutable pull-request identity.")
    if (
        identity.repository.casefold() != target.repository.casefold()
        or identity.number != target.number
        or identity.url != target.url
    ):
        raise RuntimeError(
            "The pull-request identity does not match the expected target."
        )


def review_scope(metadata: dict[str, Any]) -> ReviewScope:
    """Bind mutable issue fields and scope fields so they cannot change during review."""
    closing_issues = metadata.get("closingIssuesReferences")
    if not isinstance(closing_issues, list):
        raise TypeError("GitHub returned incomplete review-scope fields.")
    try:
        canonical_issues = sorted(
            json.dumps(
                issue,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            for issue in closing_issues
        )
        fields: dict[str, Any] = {
            "title": metadata["title"],
            "body": metadata.get("body"),
            "closingIssuesReferences": [
                json.loads(issue) for issue in canonical_issues
            ],
            "state": metadata["state"],
            "isDraft": metadata["isDraft"],
            "baseRefName": metadata["baseRefName"],
            "headRefName": metadata["headRefName"],
        }
        canonical_scope = json.dumps(
            fields,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "GitHub returned review-scope fields that are not valid."
        ) from error
    return ReviewScope(
        fields=fields,
        sha256=sha256(canonical_scope.encode("utf-8")).hexdigest(),
    )


def linked_issue_reference(issue: object) -> tuple[str, str, int, str]:
    """Return one validated canonical linked-issue identity."""
    if not isinstance(issue, dict):
        raise TypeError("GitHub returned a linked issue reference that is not valid.")
    issue_id = issue.get("id")
    repository_data = issue.get("repository")
    number = issue.get("number")
    url = issue.get("url")
    if (
        not isinstance(issue_id, str)
        or not issue_id
        or not isinstance(repository_data, dict)
        or isinstance(number, bool)
        or not isinstance(number, int)
    ):
        raise RuntimeError("GitHub returned an incomplete linked issue reference.")
    owner_data = repository_data.get("owner")
    name = repository_data.get("name")
    owner = owner_data.get("login") if isinstance(owner_data, dict) else None
    if (
        not isinstance(owner, str)
        or not owner
        or not isinstance(name, str)
        or not name
        or number < 1
        or not isinstance(url, str)
    ):
        raise RuntimeError("GitHub returned an incomplete linked issue reference.")
    try:
        repository = require_github_repository(
            f"{owner}/{name}", "GitHub linked issue repository"
        )
    except RuntimeError as error:
        raise RuntimeError(
            "GitHub returned a linked issue repository that is not valid."
        ) from error
    canonical_url = f"https://github.com/{repository}/issues/{number}"
    if url != canonical_url:
        raise RuntimeError("GitHub returned a linked issue URL that is not valid.")
    return issue_id, repository, number, canonical_url


def canonical_json(value: object, label: str) -> str:
    """Serialize provider data canonically or reject malformed content."""
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"The data for {label} is not valid.") from error


def drain_provider_stream(stream: IO[bytes], capture: ProviderStream) -> None:
    """Read one provider pipe without allowing it to grow without bound."""
    try:
        while True:
            read_size = min(
                READ_CHUNK_SIZE, capture.maximum_bytes - len(capture.output) + 1
            )
            if read_size <= 0:
                capture.overflowed.set()
                return
            chunk = stream.read(read_size)
            if not chunk:
                return
            if len(capture.output) + len(chunk) > capture.maximum_bytes:
                capture.overflowed.set()
                return
            capture.output.extend(chunk)
    except (OSError, ValueError) as error:
        capture.error = error
    finally:
        try:
            stream.close()
        except OSError:
            # A different cleanup path can close this pipe first. Ignore the error.
            pass
        capture.completed.set()


def validate_changed_path(entry: bytes) -> None:
    """Reject an empty or unsafe Git-relative path entry."""
    if not entry:
        raise RuntimeError("Git returned an empty changed path.")
    if entry.startswith(b"/") or any(
        component in {b".", b".."} for component in entry.split(b"/")
    ):
        raise RuntimeError("Git returned an unsafe changed path.")


def drain_changed_path_stream(stream: IO[bytes], capture: ChangedPathStream) -> None:
    """Incrementally collect one bounded, null-byte-delimited Git path manifest."""
    try:
        while True:
            read_size = min(
                READ_CHUNK_SIZE, capture.maximum_bytes - capture.bytes_read + 1
            )
            if read_size <= 0:
                capture.limit_error = (
                    "The changed-path manifest exceeds the safe byte limit."
                )
                capture.overflowed.set()
                return
            chunk = stream.read(read_size)
            if not chunk:
                if capture.trailing:
                    raise RuntimeError(
                        "Git returned a null-byte-delimited changed-path manifest that "
                        "is not valid."
                    )
                return
            if capture.bytes_read + len(chunk) > capture.maximum_bytes:
                capture.limit_error = (
                    "The changed-path manifest exceeds the safe byte limit."
                )
                capture.overflowed.set()
                return
            capture.bytes_read += len(chunk)
            entries = (bytes(capture.trailing) + chunk).split(b"\0")
            capture.trailing = bytearray(entries.pop())
            for entry in entries:
                validate_changed_path(entry)
                if entry in capture.seen_paths:
                    raise RuntimeError("Git returned duplicate changed paths.")
                if len(capture.paths) >= capture.maximum_paths:
                    capture.limit_error = (
                        "The changed-path manifest exceeds the safe path limit."
                    )
                    capture.overflowed.set()
                    return
                capture.seen_paths.add(entry)
                capture.paths.append(entry)
    except (OSError, RuntimeError, ValueError) as error:
        capture.error = error
    finally:
        try:
            stream.close()
        except (OSError, ValueError):
            # A different cleanup path can close this pipe first. Ignore the error.
            pass
        capture.completed.set()


def reap_provider(
    process: subprocess.Popen[bytes],
    streams: Sequence[IO[bytes]],
    readers: Sequence[threading.Thread],
) -> None:
    """Kill and reap a failed provider request without leaking reader threads."""
    if process.poll() is None:
        process.kill()
    for stream in streams:
        try:
            stream.close()
        except (OSError, ValueError):
            # A reader can close this pipe first. Ignore the error.
            pass
    process.wait()
    for reader in readers:
        reader.join(PROVIDER_READER_JOIN_SECONDS)


def provider_return_code(
    process: subprocess.Popen[bytes],
    stdout: ProviderStream | ChangedPathStream,
    stderr: ProviderStream,
    stdout_limit_error: str,
    *,
    timeout_seconds: float,
    stderr_limit_error: str,
    deadline_error: str,
    output_error: str,
    coverage_gap: type[RuntimeError],
) -> int:
    """Wait for bounded output and a completed provider before the deadline."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        if stdout.overflowed.is_set():
            path_limit_error = (
                stdout.limit_error if isinstance(stdout, ChangedPathStream) else None
            )
            raise coverage_gap(path_limit_error or stdout_limit_error)
        if stderr.overflowed.is_set():
            raise coverage_gap(stderr_limit_error)
        if stdout.error is not None:
            if isinstance(stdout.error, RuntimeError):
                raise stdout.error
            raise RuntimeError(output_error)
        if stderr.error is not None:
            raise RuntimeError(output_error)
        return_code = process.poll()
        if (
            return_code is not None
            and stdout.completed.is_set()
            and stderr.completed.is_set()
        ):
            return process.wait()
        if time.monotonic() >= deadline:
            raise coverage_gap(deadline_error)
        time.sleep(PROVIDER_POLL_SECONDS)


def bounded_gh_output(
    arguments: Sequence[str],
    *,
    maximum_bytes: int,
    limit_error: str,
    timeout_seconds: float | None = None,
    stderr_maximum_bytes: int | None = None,
    stderr_limit_error: str = (
        "The linked issue response exceeds the safe standard-error limit."
    ),
    deadline_error: str = "The linked issue provider exceeded the safe deadline.",
    output_error: str = "The tool cannot read linked issue provider output.",
    unavailable_output_error: str = (
        "The GitHub CLI process did not provide linked issue output."
    ),
    operating_system_error: str = "The tool cannot collect linked issue comments",
    coverage_gap: type[RuntimeError] = LinkedRequirementsCoverageGap,
) -> bytes:
    """Run one deadline-bound GitHub request with bounded output streams."""
    command = ["gh", *arguments]
    effective_timeout = (
        LINKED_ISSUE_COMMENT_REQUEST_TIMEOUT_SECONDS
        if timeout_seconds is None
        else timeout_seconds
    )
    effective_stderr_maximum_bytes = (
        MAX_LINKED_ISSUE_COMMENT_STDERR_BYTES
        if stderr_maximum_bytes is None
        else stderr_maximum_bytes
    )
    try:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "The required command is not available: "
                f"'{error.filename or command[0]}'."
            ) from error
        stdout = process.stdout
        stderr = process.stderr
        if stdout is None or stderr is None:
            process.kill()
            process.wait()
            raise RuntimeError(unavailable_output_error)
        stdout_capture = ProviderStream(maximum_bytes)
        stderr_capture = ProviderStream(effective_stderr_maximum_bytes)
        readers = (
            threading.Thread(
                target=drain_provider_stream,
                args=(stdout, stdout_capture),
                daemon=True,
            ),
            threading.Thread(
                target=drain_provider_stream,
                args=(stderr, stderr_capture),
                daemon=True,
            ),
        )
        for reader in readers:
            reader.start()
        try:
            return_code = provider_return_code(
                process,
                stdout_capture,
                stderr_capture,
                limit_error,
                timeout_seconds=effective_timeout,
                stderr_limit_error=stderr_limit_error,
                deadline_error=deadline_error,
                output_error=output_error,
                coverage_gap=coverage_gap,
            )
        except BaseException:
            reap_provider(process, (stdout, stderr), readers)
            raise
        for reader in readers:
            reader.join(PROVIDER_READER_JOIN_SECONDS)
        if return_code != 0:
            message = (
                bytes(stderr_capture.output).decode("utf-8", errors="replace").strip()
            )
            raise RuntimeError(
                message
                or f"The GitHub CLI command failed. Command: gh {' '.join(arguments)}"
            )
        return bytes(stdout_capture.output)
    except OSError as error:
        raise RuntimeError(
            f"{operating_system_error}. "
            f"The operation returned this diagnostic.\n{error}"
        ) from error


def paginated_issue_comments(
    repository: str, number: int, budget: LinkedRequirementBudget | None = None
) -> list[dict[str, Any]]:
    """Read bounded linked-issue comments through explicit canonical pages."""
    collection_budget = budget if budget is not None else LinkedRequirementBudget()
    comments: list[dict[str, Any]] = []
    bytes_read = 0
    for page in range(1, MAX_LINKED_ISSUE_COMMENT_PAGES + 2):
        remaining_bytes = MAX_LINKED_ISSUE_COMMENT_BYTES - bytes_read
        aggregate_remaining_bytes = collection_budget.remaining_bytes()
        if remaining_bytes <= 0:
            raise LinkedRequirementsCoverageGap(
                "The linked issue comments exceed the safe byte limit."
            )
        if aggregate_remaining_bytes <= 0:
            raise LinkedRequirementsCoverageGap(
                "The linked issue requirements exceed the safe aggregate byte limit."
            )
        collection_budget.reserve_comment_page()
        response = bounded_gh_output(
            (
                "api",
                "--hostname",
                "github.com",
                "--method",
                "GET",
                (
                    f"repos/{repository}/issues/{number}/comments?"
                    f"per_page={LINKED_ISSUE_COMMENT_PAGE_SIZE}&page={page}"
                ),
            ),
            maximum_bytes=min(
                MAX_LINKED_ISSUE_COMMENT_PAGE_BYTES,
                remaining_bytes,
                aggregate_remaining_bytes,
            ),
            limit_error="The linked issue comments exceed the safe byte limit.",
        )
        bytes_read += len(response)
        collection_budget.record_bytes(len(response))
        try:
            page_comments = json.loads(response)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "GitHub returned linked issue comment pages that are not valid."
            ) from error
        if not isinstance(page_comments, list):
            raise TypeError(
                "GitHub returned linked issue comment pages that are not valid."
            )
        if not all(isinstance(comment, dict) for comment in page_comments):
            raise RuntimeError(
                "GitHub returned a linked issue comment that is not valid."
            )
        if page > MAX_LINKED_ISSUE_COMMENT_PAGES:
            if page_comments:
                raise LinkedRequirementsCoverageGap(
                    "The linked issue comments exceed the safe page limit."
                )
            return comments
        if len(comments) + len(page_comments) > MAX_LINKED_ISSUE_COMMENTS:
            raise LinkedRequirementsCoverageGap(
                "The linked issue comments exceed the safe comment limit."
            )
        collection_budget.record_comment_page(len(page_comments))
        comments.extend(page_comments)
        if len(page_comments) < LINKED_ISSUE_COMMENT_PAGE_SIZE:
            return comments
    raise AssertionError(
        "The bounded linked issue comment pagination did not terminate."
    )


def structured_error(error: str, details: str) -> None:
    """Emit a machine-readable, fail-closed evidence error."""
    print(json.dumps({"error": error, "details": details}, sort_keys=True))


def linked_issue_metadata(
    repository: str, number: int, budget: LinkedRequirementBudget
) -> dict[str, Any]:
    """Read bounded linked-issue metadata through the shared provider budget."""
    aggregate_remaining_bytes = budget.remaining_bytes()
    if aggregate_remaining_bytes <= 0:
        raise LinkedRequirementsCoverageGap(
            "The linked issue requirements exceed the safe aggregate byte limit."
        )
    budget.reserve_request()
    response = bounded_gh_output(
        (
            "issue",
            "view",
            str(number),
            "--repo",
            f"github.com/{repository}",
            "--json",
            ISSUE_FIELDS,
        ),
        maximum_bytes=min(
            MAX_LINKED_REQUIREMENT_METADATA_BYTES, aggregate_remaining_bytes
        ),
        limit_error="The linked issue metadata exceeds the safe metadata byte limit.",
    )
    budget.record_bytes(len(response))
    try:
        issue_data = json.loads(response)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "GitHub returned a linked issue that is not valid."
        ) from error
    if not isinstance(issue_data, dict):
        raise TypeError("GitHub returned a linked issue that is not valid.")
    return issue_data


def linked_requirements(
    metadata: dict[str, Any], budget: LinkedRequirementBudget | None = None
) -> LinkedRequirements:
    """Bind every linked issue's requirement content and complete comment history."""
    references = metadata.get("closingIssuesReferences")
    if not isinstance(references, list):
        raise TypeError("GitHub returned incomplete linked issue references.")
    identities = sorted(linked_issue_reference(issue) for issue in references)
    if len(identities) != len(set(identities)):
        raise RuntimeError("GitHub returned duplicate linked issue references.")
    collection_budget = budget if budget is not None else LinkedRequirementBudget()
    items: list[LinkedRequirement] = []
    for expected_id, repository, number, expected_url in identities:
        issue_data = linked_issue_metadata(repository, number, collection_budget)
        issue_id = issue_data.get("id")
        body = issue_data.get("body")
        if (
            issue_id != expected_id
            or issue_data.get("number") != number
            or issue_data.get("url") != expected_url
            or not isinstance(issue_data.get("title"), str)
            or (body is not None and not isinstance(body, str))
            or not isinstance(issue_data.get("state"), str)
        ):
            raise RuntimeError("GitHub returned incomplete linked issue requirements.")
        comments = sorted(
            canonical_json(comment, "linked issue comment")
            for comment in paginated_issue_comments(
                repository, number, collection_budget
            )
        )
        content = {
            "body": body,
            "comments": [json.loads(comment) for comment in comments],
            "state": issue_data["state"],
            "title": issue_data["title"],
        }
        items.append(
            LinkedRequirement(
                id=expected_id,
                repository=repository,
                number=number,
                url=expected_url,
                content_sha256=sha256(
                    canonical_json(content, "linked issue requirements").encode("utf-8")
                ).hexdigest(),
            )
        )
    document = canonical_json(
        [item.as_json() for item in items], "linked issue requirements"
    )
    return LinkedRequirements(
        items=tuple(items), sha256=sha256(document.encode("utf-8")).hexdigest()
    )


def bounded_git_path_manifest(
    arguments: Sequence[str], *, cwd: Path | None = None
) -> list[bytes]:
    """Collect one immutable Git path manifest without unbounded buffering."""
    command = ["git", *git_read_arguments(), *arguments]
    try:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=git_read_environment(),
                cwd=cwd,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "The required command is not available: "
                f"'{error.filename or command[0]}'."
            ) from error
        stdout = process.stdout
        stderr = process.stderr
        if stdout is None or stderr is None:
            process.kill()
            process.wait()
            raise RuntimeError(
                "The Git process did not provide the required output streams."
            )
        stdout_capture = ChangedPathStream(
            MAX_CHANGED_PATH_MANIFEST_BYTES, MAX_CHANGED_PATHS
        )
        stderr_capture = ProviderStream(MAX_CHANGED_PATH_STDERR_BYTES)
        readers = (
            threading.Thread(
                target=drain_changed_path_stream,
                args=(stdout, stdout_capture),
                daemon=True,
            ),
            threading.Thread(
                target=drain_provider_stream,
                args=(stderr, stderr_capture),
                daemon=True,
            ),
        )
        for reader in readers:
            reader.start()
        try:
            return_code = provider_return_code(
                process,
                stdout_capture,
                stderr_capture,
                "The changed-path manifest exceeds the safe byte limit.",
                timeout_seconds=CHANGED_PATH_REQUEST_TIMEOUT_SECONDS,
                stderr_limit_error=(
                    "The changed-path response exceeds the safe standard-error limit."
                ),
                deadline_error=(
                    "The changed-path provider exceeded the safe deadline."
                ),
                output_error="The tool cannot read immutable changed-path output.",
                coverage_gap=ChangedPathCoverageGap,
            )
        except BaseException:
            reap_provider(process, (stdout, stderr), readers)
            raise
        for reader in readers:
            reader.join(PROVIDER_READER_JOIN_SECONDS)
        if return_code != 0:
            message = (
                bytes(stderr_capture.output).decode("utf-8", errors="replace").strip()
            )
            raise RuntimeError(
                message or f"The Git command failed. Command: git {' '.join(arguments)}"
            )
        return stdout_capture.paths
    except OSError as error:
        raise RuntimeError(
            "The tool cannot collect immutable changed paths. "
            f"The operation returned this diagnostic.\n{error}"
        ) from error


def git_bytes(*arguments: str, cwd: Path | None = None) -> bytes:
    """Run a read-only Git query and return its byte-exact standard output."""
    result: Any = run_command(
        ["git", *git_read_arguments(), *arguments],
        capture_output=True,
        check=False,
        env=git_read_environment(),
        cwd=cwd,
    )
    if result.returncode != 0:
        stderr = result.stderr
        if isinstance(stderr, bytes):
            message = stderr.decode("utf-8", errors="replace").strip()
        else:
            message = str(stderr).strip()
        raise RuntimeError(
            message or f"The Git command failed. Command: git {' '.join(arguments)}"
        )
    stdout = result.stdout
    if not isinstance(stdout, bytes):
        raise TypeError("Git returned non-byte output for immutable path evidence.")
    return stdout


def immutable_range_paths(
    base_oid: str, head_oid: str, *, cwd: Path | None = None
) -> list[bytes]:
    """Return validated null-byte-safe paths from one immutable Git diff range."""
    return bounded_git_path_manifest(
        (
            "-c",
            "diff.external=",
            "-c",
            "diff.autoRefreshIndex=false",
            "diff",
            "--name-only",
            "-z",
            "--no-renames",
            "--ignore-submodules=none",
            "--no-ext-diff",
            "--no-textconv",
            base_oid,
            head_oid,
        ),
        cwd=cwd,
    )


def immutable_changed_paths(
    base_oid: str, head_oid: str, *, cwd: Path | None = None
) -> ChangedPathManifest:
    """Bind the union of author-intent and current-target immutable paths."""
    require_complete_git_history(cwd=cwd)
    for oid in (base_oid, head_oid):
        git_bytes("cat-file", "-e", f"{oid}^{{commit}}", cwd=cwd)
    merge_base = require_commit_oid(
        require_unambiguous_git_merge_base(base_oid, head_oid, cwd=cwd),
        "immutable merge base",
    )
    git_bytes("cat-file", "-e", f"{merge_base}^{{commit}}", cwd=cwd)
    author_intent_paths = immutable_range_paths(merge_base, head_oid, cwd=cwd)
    current_target_paths = immutable_range_paths(base_oid, head_oid, cwd=cwd)
    canonical_entries = sorted(set(author_intent_paths) | set(current_target_paths))
    try:
        paths = tuple(entry.decode("utf-8") for entry in canonical_entries)
    except UnicodeDecodeError as error:
        raise RuntimeError(
            "Git returned a changed path that is not valid 'UTF-8'."
        ) from error
    canonical_bytes = b"".join(entry + b"\0" for entry in canonical_entries)
    return ChangedPathManifest(paths=paths, sha256=sha256(canonical_bytes).hexdigest())


def local_immutable_objects_available(base_oid: str, head_oid: str) -> bool:
    """Return whether the caller already has both immutable commit objects."""
    try:
        for oid in (base_oid, head_oid):
            git_bytes("cat-file", "-e", f"{oid}^{{commit}}")
    except RuntimeError:
        return False
    return True


def strict_changed_paths(
    metadata: dict[str, Any],
    expected: tuple[str, str],
    target: ExpectedReviewTarget,
) -> tuple[ChangedPathManifest, MaterializedSnapshot | None]:
    """Derive strict paths locally or from a verified host-owned materialized snapshot."""
    base_oid, head_oid = expected
    if local_immutable_objects_available(base_oid, head_oid):
        return immutable_changed_paths(base_oid, head_oid), None
    base_ref = metadata.get("baseRefName")
    if not isinstance(base_ref, str):
        raise TypeError(
            "GitHub returned a pull-request base reference that is not valid."
        )
    snapshot = materialize_snapshot(
        repository=target.repository,
        number=target.number,
        base_ref=base_ref,
        base_oid=base_oid,
        head_oid=head_oid,
    )
    try:
        return immutable_changed_paths(
            base_oid, head_oid, cwd=snapshot.source_path
        ), snapshot
    except BaseException:
        remove_snapshot(snapshot.root)
        raise


def gh(*arguments: str, accepted_codes: tuple[int, ...] = (0,)) -> str:
    result = run_command(
        ["gh", *arguments], capture_output=True, text=True, check=False
    )
    if result.returncode not in accepted_codes:
        raise RuntimeError(
            result.stderr.strip()
            or f"The GitHub CLI command failed. Command: gh {' '.join(arguments)}"
        )
    return result.stdout


def head_bound_check_runs(repository: str, head_oid: str) -> list[dict[str, Any]]:
    """Return complete GitHub check-run evidence bound to one immutable commit."""
    total_count: int | None = None
    runs: list[dict[str, Any]] = []
    run_ids: set[int] = set()
    bytes_read = 0
    for page_number in range(1, MAX_CHECK_RUN_PAGES + 2):
        if page_number > MAX_CHECK_RUN_PAGES:
            raise CheckEvidenceCoverageGap(
                "GitHub check runs exceed the safe page limit."
            )
        remaining_bytes = MAX_CHECK_RUN_BYTES - bytes_read
        if remaining_bytes <= 0:
            raise CheckEvidenceCoverageGap(
                "GitHub check runs exceed the safe aggregate byte limit."
            )
        try:
            response = bounded_gh_output(
                (
                    "api",
                    "--hostname",
                    "github.com",
                    "--method",
                    "GET",
                    "-H",
                    "Accept: application/vnd.github+json",
                    (
                        f"repos/{repository}/commits/{head_oid}/check-runs?"
                        f"per_page=100&page={page_number}"
                    ),
                ),
                maximum_bytes=remaining_bytes,
                limit_error="The GitHub check-run response exceeds the safe byte limit.",
                timeout_seconds=CHECK_RUN_REQUEST_TIMEOUT_SECONDS,
                stderr_maximum_bytes=MAX_CHECK_RUN_STDERR_BYTES,
                stderr_limit_error=(
                    "The GitHub check-run response exceeds the safe standard-error limit."
                ),
                deadline_error=(
                    "The GitHub check-run provider exceeded the safe deadline."
                ),
                output_error="The tool cannot read GitHub check-run provider output.",
                unavailable_output_error=(
                    "The GitHub CLI process did not provide check-run output."
                ),
                operating_system_error="The tool cannot collect GitHub check runs",
                coverage_gap=CheckEvidenceCoverageGap,
            )
        except RuntimeError as error:
            if isinstance(error, CheckEvidenceCoverageGap):
                raise
            raise CheckEvidenceCoverageGap(
                "GitHub did not return readable check evidence for the head object identifier."
            ) from error
        bytes_read += len(response)
        try:
            page = json.loads(response)
        except json.JSONDecodeError as error:
            raise CheckEvidenceCoverageGap(
                "GitHub did not return readable check evidence for the head object identifier."
            ) from error
        if not isinstance(page, dict):
            raise CheckEvidenceCoverageGap(
                "GitHub returned a check-run page that is not valid."
            )
        page_total = page.get("total_count")
        page_runs = page.get("check_runs")
        if (
            isinstance(page_total, bool)
            or not isinstance(page_total, int)
            or page_total < 0
            or not isinstance(page_runs, list)
        ):
            raise CheckEvidenceCoverageGap(
                "GitHub returned incomplete check-run evidence."
            )
        if total_count is None:
            total_count = page_total
            if total_count > MAX_CHECK_RUNS:
                raise CheckEvidenceCoverageGap(
                    "GitHub check runs exceed the safe run limit."
                )
        elif page_total != total_count:
            raise CheckEvidenceCoverageGap(
                "GitHub returned inconsistent check-run totals."
            )
        for run in page_runs:
            if not isinstance(run, dict):
                raise CheckEvidenceCoverageGap(
                    "GitHub returned a check run that is not valid."
                )
            run_id = run.get("id")
            run_head_oid = run.get("head_sha")
            if (
                isinstance(run_id, bool)
                or not isinstance(run_id, int)
                or run_id < 1
                or run_id in run_ids
                or not isinstance(run.get("name"), str)
                or not run["name"]
                or not isinstance(run.get("status"), str)
                or not isinstance(run.get("conclusion"), str | type(None))
                or not isinstance(run_head_oid, str)
                or COMMIT_OID.fullmatch(run_head_oid) is None
            ):
                raise CheckEvidenceCoverageGap(
                    "GitHub returned incomplete check-run evidence."
                )
            if run_head_oid != head_oid:
                raise CheckEvidenceCoverageGap(
                    "GitHub returned a check run that is bound to a different head "
                    "object identifier."
                )
            run_ids.add(run_id)
            runs.append(run)
        if len(runs) == total_count:
            return runs
        if not page_runs:
            raise CheckEvidenceCoverageGap(
                "GitHub returned partial check-run evidence."
            )
    raise AssertionError("The bounded check-run pagination did not terminate.")


def pr_metadata(
    pull_request: str, target: ExpectedReviewTarget | None
) -> dict[str, Any]:
    """Read one pull request through the retained target when strict evidence is required."""
    command = ["pr", "view", pull_request]
    if target is not None:
        command.extend(("--repo", target.repository_argument()))
    command.extend(("--json", FIELDS))
    metadata = json.loads(gh(*command))
    if not isinstance(metadata, dict):
        raise TypeError("GitHub returned a pull-request object that is not valid.")
    return metadata


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument(
        "--expected-base-oid",
        metavar="BASE_OID",
        help="Use the immutable base revision from 'resolve_pr.py'.",
    )
    parser.add_argument(
        "--expected-head-oid",
        metavar="HEAD_OID",
        help="Use the immutable head revision from 'resolve_pr.py'.",
    )
    parser.add_argument(
        "--expected-host",
        metavar="HOST",
        help="Use the canonical GitHub host from 'resolve_pr.py'.",
    )
    parser.add_argument(
        "--expected-repository",
        metavar="OWNER/REPOSITORY",
        help="Use the canonical GitHub repository from 'resolve_pr.py'.",
    )
    parser.add_argument(
        "--expected-pr-number",
        metavar="NUMBER",
        type=int,
        help="Use the canonical pull-request number from 'resolve_pr.py'.",
    )
    parser.add_argument(
        "--expected-pr-url",
        metavar="URL",
        help="Use the canonical pull-request URL from 'resolve_pr.py'.",
    )
    parser.add_argument("pull_request", metavar="PR_NUMBER_OR_URL")
    arguments = parser.parse_args(argv)
    pull_request = arguments.pull_request
    expected = expected_identity(
        parser, arguments.expected_base_oid, arguments.expected_head_oid
    )
    target = expected_target(
        parser,
        expected,
        arguments.expected_host,
        arguments.expected_repository,
        arguments.expected_pr_number,
        arguments.expected_pr_url,
    )
    require_immutable_identity = expected is not None
    try:
        validate_pr_identifier(pull_request)
        requested = pull_request_number(pull_request)
        if target is not None:
            if requested != target.number:
                raise RuntimeError(
                    "The requested pull request does not match the expected target "
                    "number."
                )
            if pull_request.startswith("https://") and pull_request != target.url:
                raise RuntimeError(
                    "The requested pull request does not match the expected target URL."
                )
        metadata = pr_metadata(pull_request, target)
        metadata_problem = metadata_error(
            metadata, require_immutable_identity=require_immutable_identity
        )
        if metadata_problem:
            structured_error("incomplete PR metadata", metadata_problem)
            return 1
        if target is None:
            repository_data = json.loads(gh("repo", "view", "--json", "nameWithOwner"))
            repository = repository_data.get("nameWithOwner")
        else:
            repository = target.repository
        number = metadata.get("number")
        url = metadata.get("url")
        if (
            not isinstance(repository, str)
            or not isinstance(number, int)
            or not isinstance(url, str)
        ):
            raise TypeError(
                "GitHub returned an incomplete repository or pull-request identity."
            )
        pull_repository = repository_from_pr_url(url, number)
        if pull_repository.casefold() != repository.casefold():
            raise RuntimeError(
                f"Pull request '{url}' is not in the current repository '{repository}'."
            )
        if number != requested:
            raise RuntimeError(
                "GitHub returned a pull request that is different from the requested "
                "identifier."
            )
        identity = immutable_identity(
            metadata,
            repository,
            require_immutable_identity=require_immutable_identity,
        )
        ensure_expected_identity(identity, expected)
        ensure_expected_target(identity, target)
        reviewed_scope = review_scope(metadata) if expected is not None else None
        linked_requirement_budget = (
            LinkedRequirementBudget() if expected is not None else None
        )
        reviewed_linked_requirements = (
            linked_requirements(metadata, linked_requirement_budget)
            if expected is not None
            else None
        )
        changed_path_manifest: ChangedPathManifest | None = None
        source_snapshot: MaterializedSnapshot | None = None
        check_evidence: dict[str, str | int] | None = None
        if expected is not None:
            assert target is not None
            changed_path_manifest, source_snapshot = strict_changed_paths(
                metadata, expected, target
            )
            changed_files = list(changed_path_manifest.paths)
            try:
                checks = head_bound_check_runs(repository, expected[1])
            except CheckEvidenceCoverageGap as error:
                checks = []
                check_evidence = {
                    "status": "coverage_gap",
                    "reason": str(error),
                    "head_oid": expected[1],
                }
            else:
                check_evidence = {
                    "status": "head_bound",
                    "head_oid": expected[1],
                    "count": len(checks),
                }
        else:
            changed_files = [
                line
                for line in gh(
                    "api",
                    "--paginate",
                    f"repos/{repository}/pulls/{number}/files",
                    "--jq",
                    ".[].filename",
                ).splitlines()
                if line
            ]
            checks = json.loads(
                gh(
                    "pr",
                    "checks",
                    pull_request,
                    "--json",
                    "name,state,startedAt,completedAt,link,workflow",
                    accepted_codes=(0, 1, 8),
                )
            )
            if not isinstance(checks, list):
                raise RuntimeError("GitHub returned check evidence that is not valid.")
        final_metadata = pr_metadata(pull_request, target)
        final_problem = metadata_error(
            final_metadata, require_immutable_identity=require_immutable_identity
        )
        if final_problem:
            structured_error("incomplete PR metadata", final_problem)
            return 1
        final_identity = immutable_identity(
            final_metadata,
            repository,
            require_immutable_identity=require_immutable_identity,
        )
        if final_identity != identity:
            raise RuntimeError(
                "The immutable pull-request identity changed during evidence collection."
            )
        ensure_expected_identity(final_identity, expected)
        ensure_expected_target(final_identity, target)
        final_scope = review_scope(final_metadata) if expected is not None else None
        if final_scope != reviewed_scope:
            raise RuntimeError("The review scope changed during evidence collection.")
        final_linked_requirements = (
            linked_requirements(final_metadata, linked_requirement_budget)
            if expected is not None
            else None
        )
        if final_linked_requirements != reviewed_linked_requirements:
            raise RuntimeError(
                "The linked issue requirements changed during evidence collection."
            )
    except ChangedPathCoverageGap as error:
        structured_error("changed path coverage gap", str(error))
        return 1
    except LinkedRequirementsCoverageGap as error:
        structured_error("linked issue requirements coverage gap", str(error))
        return 1
    except (RuntimeError, TypeError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 1
    evidence: dict[str, object] = {
        "changed_files": changed_files,
        "changed_paths": changed_files,
        "checks": checks,
        "pull_request": final_metadata,
    }
    if identity is not None:
        evidence["reviewed_identity"] = identity.as_json()
    if reviewed_scope is not None:
        evidence["reviewed_scope"] = reviewed_scope.as_json()
    if reviewed_linked_requirements is not None:
        evidence["reviewed_linked_requirements"] = (
            reviewed_linked_requirements.as_json()
        )
    if changed_path_manifest is not None:
        evidence["changed_path_manifest"] = changed_path_manifest.as_json()
    if source_snapshot is not None:
        evidence["source_snapshot"] = source_snapshot.as_json()
    if check_evidence is not None:
        evidence["check_evidence"] = check_evidence
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
