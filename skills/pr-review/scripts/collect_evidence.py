#!/usr/bin/env python3
"""Collect GitHub PR metadata and immutable review evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys
import threading
import time
from typing import Any, IO, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pr_identity import (
    COMMIT_OID,
    pull_request_number,
    require_canonical_pull_request_url,
    require_commit_oid,
    require_github_repository,
    repository_from_pr_url,
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
# changed paths to local immutable Git objects; legacy callers retain the REST
# file-list fallback for backwards compatibility only.
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
MAX_LINKED_REQUIREMENT_BODY_BYTES = 256 * 1024
MAX_LINKED_REQUIREMENT_REQUESTS = 48
MAX_LINKED_REQUIREMENT_PAGES = 24
MAX_LINKED_REQUIREMENT_COMMENTS = 2_000
MAX_LINKED_REQUIREMENT_BYTES = 2 * 1024 * 1024


class LinkedRequirementsCoverageGap(RuntimeError):
    """A linked requirement exceeds bounded evidence collection limits."""


@dataclass
class LinkedRequirementBudget:
    """One cumulative provider budget shared by both strict evidence reads."""

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
                "linked issue requirements exceed the safe aggregate request limit"
            )
        self.requests += 1

    def reserve_comment_page(self) -> None:
        """Reserve one aggregate comment page and its provider request."""
        if self.pages >= MAX_LINKED_REQUIREMENT_PAGES:
            raise LinkedRequirementsCoverageGap(
                "linked issue requirements exceed the safe aggregate page limit"
            )
        self.reserve_request()

    def record_bytes(self, count: int) -> None:
        """Account for one provider response without crossing the byte budget."""
        if count > self.remaining_bytes():
            raise LinkedRequirementsCoverageGap(
                "linked issue requirements exceed the safe aggregate byte limit"
            )
        self.bytes_read += count

    def record_comment_page(self, count: int) -> None:
        """Account for one successful provider page and its item count."""
        if self.comments + count > MAX_LINKED_REQUIREMENT_COMMENTS:
            raise LinkedRequirementsCoverageGap(
                "linked issue requirements exceed the safe aggregate comment limit"
            )
        self.pages += 1
        self.comments += count


@dataclass
class ProviderStream:
    """One bounded asynchronous stdout or stderr capture."""

    maximum_bytes: int
    output: bytearray = field(default_factory=bytearray)
    overflowed: threading.Event = field(default_factory=threading.Event)
    completed: threading.Event = field(default_factory=threading.Event)
    error: OSError | ValueError | None = None


@dataclass(frozen=True)
class ImmutableIdentity:
    """The review artifact and exact revisions that evidence is bound to."""

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
    """The immutable GitHub artifact target resolved before strict collection."""

    host: str
    repository: str
    number: int
    url: str

    def repository_argument(self) -> str:
        """Return the fully qualified repository argument accepted by gh."""
        return f"{self.host}/{self.repository}"


@dataclass(frozen=True)
class ChangedPathManifest:
    """A canonical, immutable changed-path manifest derived from Git objects."""

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
    """Canonical mutable review-context fields bound to an evidence collection."""

    fields: dict[str, Any]
    sha256: str

    def as_json(self) -> dict[str, object]:
        """Return the revalidated review-context binding."""
        return {"fields": self.fields, "sha256": self.sha256}


@dataclass(frozen=True)
class LinkedRequirements:
    """Canonical content binding for every linked issue used as requirements."""

    items: tuple["LinkedRequirement", ...]
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
    """One linked issue's stable identity and content-only requirements digest."""

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
    """Return a diagnostic when GitHub returns partial PR metadata."""
    if not isinstance(metadata, dict):
        return "PR metadata must be a JSON object"
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
        return "GitHub returned incomplete or invalid PR metadata fields: " + ", ".join(
            sorted(set(invalid))
        )
    if metadata["state"] != "OPEN":
        return f"pull request {metadata['number']} is not open"
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
                "GitHub returned incomplete or invalid immutable PR identity fields: "
                + ", ".join(invalid_identity)
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
                "GitHub returned incomplete or invalid review-scope fields: "
                + ", ".join(scope_invalid)
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
        raise RuntimeError("GitHub returned incomplete immutable pull-request identity")
    number = metadata.get("number")
    url = metadata.get("url")
    if not isinstance(number, int) or not isinstance(url, str):
        raise RuntimeError("GitHub returned incomplete pull-request identity")
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
        parser.error(
            "--expected-base-oid and --expected-head-oid must be supplied together"
        )
    if base_oid is None or head_oid is None:
        return None
    if COMMIT_OID.fullmatch(base_oid) is None:
        parser.error("--expected-base-oid must be a lowercase 40-hex Git commit OID")
    if COMMIT_OID.fullmatch(head_oid) is None:
        parser.error("--expected-head-oid must be a lowercase 40-hex Git commit OID")
    return base_oid, head_oid


def expected_target(
    parser: Any,
    identity: tuple[str, str] | None,
    host: str | None,
    repository: str | None,
    number: int | None,
    url: str | None,
) -> ExpectedReviewTarget | None:
    """Require the resolved GitHub target whenever immutable OIDs are supplied."""
    if identity is None:
        if (
            host is not None
            or repository is not None
            or number is not None
            or url is not None
        ):
            parser.error(
                "--expected-host, --expected-repository, --expected-pr-number, and "
                "--expected-pr-url require immutable expected OIDs"
            )
        return None
    if host is None or repository is None or number is None or url is None:
        parser.error(
            "--expected-host, --expected-repository, --expected-pr-number, and "
            "--expected-pr-url are required with immutable expected OIDs"
        )
    assert host is not None
    assert repository is not None
    assert number is not None
    assert url is not None
    if host != "github.com":
        parser.error("--expected-host must be github.com")
    try:
        canonical_repository = require_github_repository(
            repository, "--expected-repository"
        )
    except RuntimeError as error:
        parser.error(str(error))
    if number < 1:
        parser.error("--expected-pr-number must be a positive pull-request number")
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
    """Fail closed when collected revisions differ from the resolved PR."""
    if expected is None:
        return
    if identity is None:
        raise RuntimeError("GitHub returned no immutable pull-request identity")
    if (identity.base_oid, identity.head_oid) != expected:
        raise RuntimeError(
            "immutable pull-request identity does not match the expected base/head OIDs"
        )


def ensure_expected_target(
    identity: ImmutableIdentity | None, target: ExpectedReviewTarget | None
) -> None:
    """Fail closed when collected artifact identity differs from the resolved target."""
    if target is None:
        return
    if identity is None:
        raise RuntimeError("GitHub returned no immutable pull-request identity")
    if (
        identity.repository.casefold() != target.repository.casefold()
        or identity.number != target.number
        or identity.url != target.url
    ):
        raise RuntimeError("pull-request identity does not match the expected target")


def review_scope(metadata: dict[str, Any]) -> ReviewScope:
    """Bind mutable issue/scope fields so they cannot drift during review."""
    closing_issues = metadata.get("closingIssuesReferences")
    if not isinstance(closing_issues, list):
        raise RuntimeError("GitHub returned incomplete review-scope fields")
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
        raise RuntimeError("GitHub returned invalid review-scope fields") from error
    return ReviewScope(
        fields=fields,
        sha256=sha256(canonical_scope.encode("utf-8")).hexdigest(),
    )


def linked_issue_reference(issue: object) -> tuple[str, str, int, str]:
    """Return one validated canonical linked-issue identity."""
    if not isinstance(issue, dict):
        raise RuntimeError("GitHub returned an invalid linked issue reference")
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
        raise RuntimeError("GitHub returned an incomplete linked issue reference")
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
        raise RuntimeError("GitHub returned an incomplete linked issue reference")
    try:
        repository = require_github_repository(
            f"{owner}/{name}", "GitHub linked issue repository"
        )
    except RuntimeError as error:
        raise RuntimeError(
            "GitHub returned an invalid linked issue repository"
        ) from error
    canonical_url = f"https://github.com/{repository}/issues/{number}"
    if url != canonical_url:
        raise RuntimeError("GitHub returned an invalid linked issue URL")
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
        raise RuntimeError(f"GitHub returned invalid {label}") from error


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
            pass
    process.wait()
    for reader in readers:
        reader.join(PROVIDER_READER_JOIN_SECONDS)


def provider_return_code(
    process: subprocess.Popen[bytes],
    stdout: ProviderStream,
    stderr: ProviderStream,
    stdout_limit_error: str,
) -> int:
    """Wait for bounded output and a completed provider before the deadline."""
    deadline = time.monotonic() + LINKED_ISSUE_COMMENT_REQUEST_TIMEOUT_SECONDS
    while True:
        if stdout.overflowed.is_set():
            raise LinkedRequirementsCoverageGap(stdout_limit_error)
        if stderr.overflowed.is_set():
            raise LinkedRequirementsCoverageGap(
                "linked issue response exceeds the safe stderr limit"
            )
        if stdout.error is not None or stderr.error is not None:
            raise RuntimeError("cannot read linked issue provider output")
        return_code = process.poll()
        if (
            return_code is not None
            and stdout.completed.is_set()
            and stderr.completed.is_set()
        ):
            return process.wait()
        if time.monotonic() >= deadline:
            raise LinkedRequirementsCoverageGap(
                "linked issue provider exceeded the safe provider deadline"
            )
        time.sleep(PROVIDER_POLL_SECONDS)


def bounded_gh_output(
    arguments: Sequence[str], *, maximum_bytes: int, limit_error: str
) -> bytes:
    """Run one deadline-bound GitHub request with bounded stdout and stderr."""
    command = ["gh", *arguments]
    try:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                f"required command unavailable: {error.filename or command[0]}"
            ) from error
        stdout = process.stdout
        stderr = process.stderr
        if stdout is None or stderr is None:
            process.kill()
            process.wait()
            raise RuntimeError("GitHub did not provide linked issue provider output")
        stdout_capture = ProviderStream(maximum_bytes)
        stderr_capture = ProviderStream(MAX_LINKED_ISSUE_COMMENT_STDERR_BYTES)
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
                process, stdout_capture, stderr_capture, limit_error
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
            raise RuntimeError(message or f"gh {' '.join(arguments)} failed")
        return bytes(stdout_capture.output)
    except OSError as error:
        raise RuntimeError(f"cannot collect linked issue comments: {error}") from error


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
                "linked issue comments exceed the safe byte limit"
            )
        if aggregate_remaining_bytes <= 0:
            raise LinkedRequirementsCoverageGap(
                "linked issue requirements exceed the safe aggregate byte limit"
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
            limit_error="linked issue comments exceed the safe byte limit",
        )
        bytes_read += len(response)
        collection_budget.record_bytes(len(response))
        try:
            page_comments = json.loads(response)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "GitHub returned invalid linked issue comment pages"
            ) from error
        if not isinstance(page_comments, list):
            raise RuntimeError("GitHub returned invalid linked issue comment pages")
        if not all(isinstance(comment, dict) for comment in page_comments):
            raise RuntimeError("GitHub returned an invalid linked issue comment")
        if page > MAX_LINKED_ISSUE_COMMENT_PAGES:
            if page_comments:
                raise LinkedRequirementsCoverageGap(
                    "linked issue comments exceed the safe page limit"
                )
            return comments
        if len(comments) + len(page_comments) > MAX_LINKED_ISSUE_COMMENTS:
            raise LinkedRequirementsCoverageGap(
                "linked issue comments exceed the safe comment limit"
            )
        collection_budget.record_comment_page(len(page_comments))
        comments.extend(page_comments)
        if len(page_comments) < LINKED_ISSUE_COMMENT_PAGE_SIZE:
            return comments
    raise AssertionError("bounded linked issue comment pagination did not terminate")


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
            "linked issue requirements exceed the safe aggregate byte limit"
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
        limit_error="linked issue metadata exceeds the safe metadata byte limit",
    )
    budget.record_bytes(len(response))
    try:
        issue_data = json.loads(response)
    except json.JSONDecodeError as error:
        raise RuntimeError("GitHub returned an invalid linked issue") from error
    if not isinstance(issue_data, dict):
        raise RuntimeError("GitHub returned an invalid linked issue")
    return issue_data


def linked_requirements(
    metadata: dict[str, Any], budget: LinkedRequirementBudget | None = None
) -> LinkedRequirements:
    """Bind every linked issue's requirement content and complete comment history."""
    references = metadata.get("closingIssuesReferences")
    if not isinstance(references, list):
        raise RuntimeError("GitHub returned incomplete linked issue references")
    identities = sorted(linked_issue_reference(issue) for issue in references)
    if len(identities) != len(set(identities)):
        raise RuntimeError("GitHub returned duplicate linked issue references")
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
            raise RuntimeError("GitHub returned incomplete linked issue requirements")
        if (
            isinstance(body, str)
            and len(body.encode("utf-8", errors="surrogatepass"))
            > MAX_LINKED_REQUIREMENT_BODY_BYTES
        ):
            raise LinkedRequirementsCoverageGap(
                "linked issue metadata exceeds the safe body limit"
            )
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


def git_bytes(*arguments: str) -> bytes:
    """Run a read-only Git query and return its byte-exact stdout."""
    result: Any = run_command(
        ["git", *git_read_arguments(), *arguments],
        capture_output=True,
        check=False,
        env=git_read_environment(),
    )
    if result.returncode != 0:
        stderr = result.stderr
        if isinstance(stderr, bytes):
            message = stderr.decode("utf-8", errors="replace").strip()
        else:
            message = str(stderr).strip()
        raise RuntimeError(message or f"git {' '.join(arguments)} failed")
    stdout = result.stdout
    if not isinstance(stdout, bytes):
        raise RuntimeError("git returned non-byte output for immutable path evidence")
    return stdout


def immutable_range_paths(base_oid: str, head_oid: str) -> list[bytes]:
    """Return validated NUL-safe paths from one immutable Git diff range."""
    raw_paths = git_bytes(
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
    )
    if raw_paths and not raw_paths.endswith(b"\0"):
        raise RuntimeError(
            "Git returned a malformed NUL-delimited changed-path manifest"
        )
    entries = raw_paths[:-1].split(b"\0") if raw_paths else []
    if any(not entry for entry in entries):
        raise RuntimeError("Git returned an empty changed path")
    if any(
        entry.startswith(b"/")
        or any(component in {b".", b".."} for component in entry.split(b"/"))
        for entry in entries
    ):
        raise RuntimeError("Git returned an unsafe changed path")
    if len(entries) != len(set(entries)):
        raise RuntimeError("Git returned duplicate changed paths")
    return entries


def immutable_changed_paths(base_oid: str, head_oid: str) -> ChangedPathManifest:
    """Bind the union of author-intent and current-target immutable paths."""
    require_complete_git_history()
    for oid in (base_oid, head_oid):
        git_bytes("cat-file", "-e", f"{oid}^{{commit}}")
    merge_base = require_commit_oid(
        require_unambiguous_git_merge_base(base_oid, head_oid), "immutable merge base"
    )
    git_bytes("cat-file", "-e", f"{merge_base}^{{commit}}")
    author_intent_paths = immutable_range_paths(merge_base, head_oid)
    current_target_paths = immutable_range_paths(base_oid, head_oid)
    canonical_entries = sorted(set(author_intent_paths) | set(current_target_paths))
    try:
        paths = tuple(entry.decode("utf-8") for entry in canonical_entries)
    except UnicodeDecodeError as error:
        raise RuntimeError("Git returned a non-UTF-8 changed path") from error
    canonical_bytes = b"".join(entry + b"\0" for entry in canonical_entries)
    return ChangedPathManifest(paths=paths, sha256=sha256(canonical_bytes).hexdigest())


def gh(*arguments: str, accepted_codes: tuple[int, ...] = (0,)) -> str:
    result = run_command(
        ["gh", *arguments], capture_output=True, text=True, check=False
    )
    if result.returncode not in accepted_codes:
        raise RuntimeError(result.stderr.strip() or f"gh {' '.join(arguments)} failed")
    return result.stdout


def pr_metadata(
    pull_request: str, target: ExpectedReviewTarget | None
) -> dict[str, Any]:
    """Read one PR through the retained target when strict evidence is required."""
    command = ["pr", "view", pull_request]
    if target is not None:
        command.extend(("--repo", target.repository_argument()))
    command.extend(("--json", FIELDS))
    metadata = json.loads(gh(*command))
    if not isinstance(metadata, dict):
        raise RuntimeError("GitHub returned an invalid pull-request object")
    return metadata


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument(
        "--expected-base-oid",
        metavar="BASE_OID",
        help="immutable base revision returned by resolve_pr.py",
    )
    parser.add_argument(
        "--expected-head-oid",
        metavar="HEAD_OID",
        help="immutable head revision returned by resolve_pr.py",
    )
    parser.add_argument(
        "--expected-host",
        metavar="HOST",
        help="canonical GitHub host returned by resolve_pr.py",
    )
    parser.add_argument(
        "--expected-repository",
        metavar="OWNER/REPOSITORY",
        help="canonical GitHub repository returned by resolve_pr.py",
    )
    parser.add_argument(
        "--expected-pr-number",
        metavar="NUMBER",
        type=int,
        help="canonical pull-request number returned by resolve_pr.py",
    )
    parser.add_argument(
        "--expected-pr-url",
        metavar="URL",
        help="canonical pull-request URL returned by resolve_pr.py",
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
                    "requested pull request does not match the expected target number"
                )
            if pull_request.startswith("https://"):
                if pull_request != target.url:
                    raise RuntimeError(
                        "requested pull request does not match the expected target URL"
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
            raise RuntimeError("GitHub returned incomplete repository or PR identity")
        pull_repository = repository_from_pr_url(url, number)
        if pull_repository.casefold() != repository.casefold():
            raise RuntimeError(
                f"pull request {url} does not belong to current repository {repository}"
            )
        if number != requested:
            raise RuntimeError(
                "GitHub returned a pull request different from the requested identifier"
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
        check_evidence: dict[str, str] | None = None
        if expected is not None:
            changed_path_manifest = immutable_changed_paths(*expected)
            changed_files = list(changed_path_manifest.paths)
            # `gh pr checks` does not identify the commit it describes. Do not
            # attribute that mutable endpoint's output to the reviewed head.
            checks: list[object] = []
            check_evidence = {
                "status": "coverage_gap",
                "reason": "no head-bound check evidence was collected",
                "head_oid": expected[1],
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
                raise RuntimeError("GitHub returned invalid check evidence")
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
                "immutable pull-request identity changed while collecting evidence"
            )
        ensure_expected_identity(final_identity, expected)
        ensure_expected_target(final_identity, target)
        final_scope = review_scope(final_metadata) if expected is not None else None
        if final_scope != reviewed_scope:
            raise RuntimeError("review scope changed while collecting evidence")
        final_linked_requirements = (
            linked_requirements(final_metadata, linked_requirement_budget)
            if expected is not None
            else None
        )
        if final_linked_requirements != reviewed_linked_requirements:
            raise RuntimeError(
                "linked issue requirements changed while collecting evidence"
            )
    except LinkedRequirementsCoverageGap as error:
        structured_error("linked issue requirements coverage gap", str(error))
        return 1
    except (RuntimeError, json.JSONDecodeError) as error:
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
    if check_evidence is not None:
        evidence["check_evidence"] = check_evidence
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
