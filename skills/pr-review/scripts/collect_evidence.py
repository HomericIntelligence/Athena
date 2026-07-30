#!/usr/bin/env python3
"""Collect GitHub PR metadata and immutable review evidence."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import re
import sys
from typing import Any, Sequence
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pr_identity import repository_from_pr_url, validate_pr_identifier
from skills._cli import argument_parser, run_command


# Keep this query below GitHub's GraphQL complexity budget. Strict callers bind
# changed paths to local immutable Git objects; legacy callers retain the REST
# file-list fallback for backwards compatibility only.
FIELDS = (
    "number,title,body,state,isDraft,author,baseRefName,headRefName,"
    "baseRefOid,headRefOid,reviews,statusCheckRollup,closingIssuesReferences,url"
)
COMMIT_OID = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class ImmutableIdentity:
    """The review artifact and exact revisions that evidence is bound to."""

    repository: str
    number: int
    url: str
    base_oid: str
    head_oid: str

    def as_json(self) -> dict[str, str | int]:
        """Return the stable, serializable evidence binding."""
        return {
            "repository": self.repository,
            "number": self.number,
            "url": self.url,
            "state": "OPEN",
            "base_oid": self.base_oid,
            "head_oid": self.head_oid,
        }


@dataclass(frozen=True)
class ChangedPathManifest:
    """A canonical, immutable changed-path manifest derived from Git objects."""

    paths: tuple[str, ...]
    sha256: str

    def as_json(self) -> dict[str, str | int]:
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


def requested_number(identifier: str) -> int:
    """Return the validated PR number encoded by the user-provided identifier."""
    if identifier.isdigit():
        return int(identifier)
    path = urlparse(identifier).path.rstrip("/")
    return int(path.rsplit("/", maxsplit=1)[-1])


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


def git_bytes(*arguments: str) -> bytes:
    """Run a read-only Git query and return its byte-exact stdout."""
    result: Any = run_command(["git", *arguments], capture_output=True, check=False)
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


def immutable_changed_paths(base_oid: str, head_oid: str) -> ChangedPathManifest:
    """Derive a NUL-safe changed-path set from immutable local commit objects."""
    for oid in (base_oid, head_oid):
        git_bytes("cat-file", "-e", f"{oid}^{{commit}}")
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
    canonical_entries = sorted(entries)
    if len(canonical_entries) != len(set(canonical_entries)):
        raise RuntimeError("Git returned duplicate changed paths")
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
    parser.add_argument("pull_request", metavar="PR_NUMBER_OR_URL")
    arguments = parser.parse_args(argv)
    pull_request = arguments.pull_request
    expected = expected_identity(
        parser, arguments.expected_base_oid, arguments.expected_head_oid
    )
    require_immutable_identity = expected is not None
    try:
        validate_pr_identifier(pull_request)
        metadata = json.loads(gh("pr", "view", pull_request, "--json", FIELDS))
        metadata_problem = metadata_error(
            metadata, require_immutable_identity=require_immutable_identity
        )
        if metadata_problem:
            print(
                json.dumps(
                    {
                        "error": "incomplete PR metadata",
                        "details": metadata_problem,
                    },
                    sort_keys=True,
                )
            )
            return 1
        repository_data = json.loads(gh("repo", "view", "--json", "nameWithOwner"))
        repository = repository_data.get("nameWithOwner")
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
        if number != requested_number(pull_request):
            raise RuntimeError(
                "GitHub returned a pull request different from the requested identifier"
            )
        identity = immutable_identity(
            metadata,
            repository,
            require_immutable_identity=require_immutable_identity,
        )
        ensure_expected_identity(identity, expected)
        reviewed_scope = review_scope(metadata) if expected is not None else None
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
        final_metadata = json.loads(gh("pr", "view", pull_request, "--json", FIELDS))
        final_problem = metadata_error(
            final_metadata, require_immutable_identity=require_immutable_identity
        )
        if final_problem:
            raise RuntimeError(final_problem)
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
        final_scope = review_scope(final_metadata) if expected is not None else None
        if final_scope != reviewed_scope:
            raise RuntimeError("review scope changed while collecting evidence")
    except (RuntimeError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 1
    evidence: dict[str, object] = {
        "changed_files": changed_files,
        "changed_paths": changed_files,
        "checks": checks,
        "pull_request": metadata,
    }
    if identity is not None:
        evidence["reviewed_identity"] = identity.as_json()
    if reviewed_scope is not None:
        evidence["reviewed_scope"] = reviewed_scope.as_json()
    if changed_path_manifest is not None:
        evidence["changed_path_manifest"] = changed_path_manifest.as_json()
    if check_evidence is not None:
        evidence["check_evidence"] = check_evidence
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
