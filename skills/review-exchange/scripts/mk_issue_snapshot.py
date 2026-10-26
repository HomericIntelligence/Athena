#!/usr/bin/env python3
"""Build the canonical issue-snapshot document for an issue-plan exchange.

This helper is the only supported producer of an issue snapshot. An agent must
not build, edit, or normalize a snapshot by hand.

The normalization rules below are pinned. Two sessions that run this helper on
the same issue produce byte-identical snapshot documents, and therefore one
`requirements_sha256`.

Endpoint family
    Every record comes from the GitHub REST API through the GitHub CLI. The
    helper issues no GraphQL query and reads no other endpoint family.

Issue identity
    `target.issue_id` is the REST `node_id` of the issue. `target.number` is
    the issue number. `target.url` is `https://github.com/<owner>/<repo>/issues/<number>`,
    and the helper rejects a provider `html_url` that differs from it.

Actor identity
    The actor comes from `gh api user`. The actor `id`, every comment `id`, and
    every comment author `id` are the stringified REST integer identities.

Comment pagination
    The helper reads `repos/<owner>/<repo>/issues/<number>/comments` with
    `per_page=100`. It stops only on a page with fewer than 100 comments, and it
    sets `comments_complete` to `true` only after that short page.

Issue body
    `issue.title` and `issue.body` are the exact REST strings. The helper trims
    nothing, repairs nothing, and normalizes nothing. GitHub returns a null body
    for an issue without a description. A null body becomes the empty string.

Acceptance criteria
    The helper reads one acceptance-criteria section. A heading is an ATX heading
    whose level is between 2 and 6. A heading name is the text after the hashes,
    with surrounding spaces removed, with one trailing colon removed, and with
    the result case folded. The accepted names are `acceptance criteria`,
    `acceptance criteria checklist`, `acceptance criteria (ac)`, `ac`, and `acs`.
    The first matching heading in document order wins. The section ends at the
    next heading whose level is less than or equal to the section heading level,
    or at the end of the body. An item marker is `-`, `*`, `+`, or a run of one to
    nine digits followed by `.` or by `)`. A marker must be followed by at least
    one space or a tab. An item line must start at column 0, and an indented line
    is a nested or a continued line. The helper does not fold continuation
    lines, and it ignores every line in the section that is not an item line.
    The criterion text is the item content after the marker and after one leading
    task checkbox (`[ ]`, `[x]`, or `[X]`) that is followed by a space, with
    surrounding spaces removed. An item whose text is empty is not a criterion.
    The criterion identities are `AC-001`, `AC-002`, and so on in document order.
    Every criterion has the literal `source` value `body`. A body with no
    matching heading yields an empty list, and the helper does not fail.

Repository authority
    A comment author is authoritative only when both conditions hold. The REST
    `author_association` is `OWNER`, `MEMBER`, or `COLLABORATOR`, and the
    repository permission for that login is `ADMIN` or `MAINTAIN`. The helper
    reads each qualifying login once, in first-seen document order, and it caps
    the number of lookups. The helper fails closed. A missing capability, a
    rejected request, or a response without a permission value stops the run. The
    helper never defaults the authority flag to `true` or to `false` after a
    failed lookup. The requirement digest does not depend on this flag.

Reads
    The helper reads every provider response as bytes, caps one response, caps the
    accumulated responses, caps the standard error, and applies a request
    timeout and one overall deadline. The helper decodes each response with a
    strict UTF-8 decode and parses it with `review_exchange.parse_json_bytes`,
    which rejects duplicate JSON keys, so no lossy decode and no duplicate key
    can change the requirement digest.

Failures
    A GitLab locator fails with a message that names the missing adapter. The
    helper stops on an operational failure and prints no snapshot.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import quote

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import review_exchange

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

ProtocolError = review_exchange.ProtocolError
OperationalError = review_exchange.OperationalError

SNAPSHOT_SCHEMA_ID = "athena.issue-exchange.snapshot"
SCHEMA_VERSION = 1
GITHUB_HOST = "github.com"
GITHUB_REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+\Z")
GITHUB_PROVIDER = "github"
ISSUE_STATES = frozenset({"open", "closed"})

ACCEPTANCE_MIN_HEADING_LEVEL = 2
ACCEPTANCE_MAX_HEADING_LEVEL = 6
ACCEPTANCE_HEADING_NAMES = (
    "acceptance criteria",
    "acceptance criteria checklist",
    "acceptance criteria (ac)",
    "ac",
    "acs",
)
ACCEPTANCE_BULLET_MARKERS = ("-", "*", "+")
ACCEPTANCE_ITEM_MARKERS = (*ACCEPTANCE_BULLET_MARKERS, "[1-9][0-9]{0,8}[.)]")

AUTHORITY_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
AUTHORITY_PERMISSIONS = frozenset({"ADMIN", "MAINTAIN"})

COMMENT_PAGE_SIZE = 100
MAX_COMMENT_PAGES = 20
MAX_COMMENTS = 2000
MAX_PAGE_BYTES = 1048576
MAX_TOTAL_BYTES = 16777216
MAX_STDERR_BYTES = 16384
REQUEST_TIMEOUT_SECONDS = 30.0
SNAPSHOT_DEADLINE_SECONDS = 120.0
MAX_AUTHORITY_LOOKUPS = 64

AUTHORITY_CAPABILITY_MESSAGE = (
    "The snapshot producer needs repository administration read. "
    "Authenticate `gh` with that access."
)

_HEADING_PATTERN = re.compile(r"^(#{1,6})(?=[ \t]|\Z)")
_ITEM_MARKER_PATTERN = "|".join(
    [re.escape(marker) for marker in ACCEPTANCE_BULLET_MARKERS]
    + [ACCEPTANCE_ITEM_MARKERS[-1]]
)
_ITEM_PATTERN = re.compile(r"^(?:" + _ITEM_MARKER_PATTERN + r")[ \t]+(.*)$")
_CHECKBOX_PATTERN = re.compile(r"^\[(?: |x|X)\] ")


@dataclass
class _ReadBudget:
    """Accumulated provider bytes for one bounded snapshot run."""

    total: int = 0


def require_github_host(value: object, label: str) -> str:
    """Return the supported canonical GitHub hostname or fail closed."""
    if value != GITHUB_HOST:
        raise ProtocolError(f"The value for {label} must be '{GITHUB_HOST}'.")
    return GITHUB_HOST


def require_github_repository(value: object, label: str) -> str:
    """Return a canonical GitHub repository or reject unsafe input."""
    if not isinstance(value, str) or GITHUB_REPOSITORY.fullmatch(value) is None:
        raise ProtocolError(
            f"The value for {label} must use the canonical GitHub OWNER/REPOSITORY "
            "format."
        )
    return value


def require_issue_number(value: object) -> int:
    """Return a positive issue number or fail closed."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProtocolError("The issue number must be a positive integer.")
    return value


def canonical_issue_url(repository: str, number: int) -> str:
    """Return the canonical public issue URL from a trusted target."""
    return f"https://{GITHUB_HOST}/{repository}/issues/{number}"


def _gh_json(arguments: Sequence[str], purpose: str, budget: _ReadBudget) -> Any:
    """Return one bounded, strictly decoded provider response."""
    try:
        result = run_command(
            arguments,
            capture_output=True,
            text=False,
            check=False,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise OperationalError(
            "The GitHub request exceeded the safe request deadline."
        ) from error
    standard_error = cast(bytes, result.stderr or b"")
    if len(standard_error) > MAX_STDERR_BYTES:
        raise OperationalError(
            f"The GitHub {purpose} diagnostic exceeds the standard error byte limit."
        )
    payload = cast(bytes, result.stdout or b"")
    if result.returncode != 0:
        detail = standard_error.decode("utf-8", errors="replace").strip()
        raise OperationalError(detail or f"The GitHub {purpose} request failed.")
    if len(payload) > MAX_PAGE_BYTES:
        raise OperationalError(
            f"The GitHub {purpose} response exceeds the response byte limit."
        )
    budget.total += len(payload)
    if budget.total > MAX_TOTAL_BYTES:
        raise OperationalError(
            "The snapshot producer reached the accumulated response byte limit."
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise OperationalError("The GitHub response is not valid UTF-8.") from error
    try:
        return review_exchange.parse_json_bytes(text.encode("utf-8"))
    except review_exchange.ProtocolError as error:
        raise OperationalError(
            f"GitHub returned {purpose} content that is not valid JSON."
        ) from error


def _gh_get(path: str, purpose: str, budget: _ReadBudget) -> Any:
    """Return one parsed GitHub REST GET response."""
    return _gh_json(
        ("gh", "api", "--hostname", GITHUB_HOST, "--method", "GET", path),
        purpose,
        budget,
    )


def _require_deadline(deadline: float) -> None:
    """Stop the run when the overall deadline is reached."""
    if time.monotonic() >= deadline:
        raise OperationalError(
            "The snapshot producer reached its overall operation deadline."
        )


def _require_string(value: object, label: str) -> str:
    """Return one nonempty provider string or fail closed."""
    if not isinstance(value, str) or not value:
        raise OperationalError(f"GitHub returned no {label}.")
    return value


def _require_integer_identity(value: object, label: str) -> str:
    """Return one stringified REST integer identity or fail closed."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise OperationalError(f"GitHub returned no integer {label}.")
    return str(value)


def _actor_record(budget: _ReadBudget) -> dict[str, str]:
    """Return the authenticated actor from the provider user record."""
    value = _gh_get("user", "authenticated actor", budget)
    if not isinstance(value, dict):
        raise OperationalError("GitHub returned an invalid authenticated actor.")
    return {
        "id": _require_integer_identity(value.get("id"), "actor identity"),
        "login": _require_string(value.get("login"), "actor login"),
    }


def _issue_record(
    repository: str, number: int, host: str, budget: _ReadBudget
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the issue record and the target from one provider issue read."""
    value = _gh_get(f"repos/{repository}/issues/{number}", "issue", budget)
    if not isinstance(value, dict):
        raise OperationalError("GitHub returned an invalid issue record.")
    url = canonical_issue_url(repository, number)
    html_url = value.get("html_url")
    if html_url != url:
        raise OperationalError(
            f"GitHub returned an issue URL that is not canonical: {html_url!r}."
        )
    state = value.get("state")
    if state not in ISSUE_STATES:
        raise OperationalError(
            f"GitHub returned an unsupported issue state: {state!r}."
        )
    title = value.get("title")
    # GitHub returns a null body for an issue without a description. The
    # reducer accepts an empty body, so map null to the empty string.
    body = value.get("body")
    if body is None:
        body = ""
    if not isinstance(title, str) or not isinstance(body, str):
        raise OperationalError("GitHub returned an incomplete issue record.")
    target = {
        "provider": GITHUB_PROVIDER,
        "host": host,
        "repository": repository,
        "issue_id": _require_string(value.get("node_id"), "issue node identity"),
        "number": number,
        "url": url,
    }
    issue = {
        "state": state,
        "title": title,
        "body": body,
        "acceptance_criteria": _acceptance_criteria(body),
    }
    return issue, target


def _comment_pages(
    repository: str,
    number: int,
    budget: _ReadBudget,
    deadline: float,
) -> list[dict[str, Any]]:
    """Return every provider comment in document order."""
    comments: list[dict[str, Any]] = []
    for page in range(1, MAX_COMMENT_PAGES + 1):
        _require_deadline(deadline)
        value = _gh_get(
            f"repos/{repository}/issues/{number}/comments?"
            f"per_page={COMMENT_PAGE_SIZE}&page={page}",
            f"comment page {page}",
            budget,
        )
        if not isinstance(value, list) or not all(
            isinstance(item, dict) for item in value
        ):
            raise OperationalError(
                f"GitHub returned comment page {page} that is not valid."
            )
        if len(value) > COMMENT_PAGE_SIZE:
            raise OperationalError(
                f"GitHub returned more than {COMMENT_PAGE_SIZE} comments on page "
                f"{page}."
            )
        comments.extend(cast(list[dict[str, Any]], value))
        if len(comments) > MAX_COMMENTS:
            raise OperationalError(
                "The snapshot producer reached the retained comment cap."
            )
        # Only a short page proves that the provider has no more comments.
        if len(value) < COMMENT_PAGE_SIZE:
            return comments
    raise OperationalError(
        "The snapshot producer reached the comment pagination page cap."
    )


def _heading_level(line: str) -> int | None:
    """Return the level of an ATX heading line, or None for other lines."""
    match = _HEADING_PATTERN.match(line)
    return None if match is None else len(match.group(1))


def _heading_name(text: str) -> str:
    """Return the case-folded acceptance-criteria heading name."""
    name = text.strip()
    if name.endswith(":"):
        name = name[:-1].strip()
    return name.casefold()


def _acceptance_item(line: str) -> str | None:
    """Return the criterion text for one item line, or None for other lines."""
    match = _ITEM_PATTERN.match(line)
    if match is None:
        return None
    text = match.group(1)
    checkbox = _CHECKBOX_PATTERN.match(text)
    if checkbox is not None:
        text = text[checkbox.end() :]
    text = text.strip()
    return text or None


def _acceptance_criteria(body: str) -> list[dict[str, str]]:
    """Return the pinned acceptance criteria of the issue body."""
    lines = body.split("\n")
    section: int | None = None
    section_level = 0
    for index, line in enumerate(lines):
        level = _heading_level(line)
        if level is None or not (
            ACCEPTANCE_MIN_HEADING_LEVEL <= level <= ACCEPTANCE_MAX_HEADING_LEVEL
        ):
            continue
        if _heading_name(line[level:]) in ACCEPTANCE_HEADING_NAMES:
            section = index
            section_level = level
            break
    if section is None:
        return []
    texts: list[str] = []
    for line in lines[section + 1 :]:
        level = _heading_level(line)
        if level is not None and level <= section_level:
            break
        text = _acceptance_item(line)
        if text is not None:
            texts.append(text)
    return [
        {"id": f"AC-{index:03d}", "text": text, "source": "body"}
        for index, text in enumerate(texts, start=1)
    ]


def _comment_association(value: Mapping[str, Any]) -> str:
    """Return the provider association of one comment author."""
    association = value.get("author_association")
    return association if isinstance(association, str) else ""


def _comment_login(value: Mapping[str, Any]) -> str:
    """Return the provider login of one comment author."""
    author = value.get("user")
    if not isinstance(author, dict):
        raise OperationalError("GitHub returned a comment without an author.")
    login = author.get("login")
    return login if isinstance(login, str) else ""


def _qualifying_logins(comments: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return each qualifying login once, in first-seen document order."""
    logins: list[str] = []
    for comment in comments:
        if _comment_association(comment) not in AUTHORITY_ASSOCIATIONS:
            continue
        login = _comment_login(comment)
        if not login:
            raise OperationalError(AUTHORITY_CAPABILITY_MESSAGE)
        if login not in logins:
            logins.append(login)
    return logins


def _authority_for_logins(
    repository: str,
    comments: Sequence[dict[str, Any]],
    budget: _ReadBudget,
    deadline: float,
) -> dict[str, bool]:
    """Return the proven repository authority for each qualifying login."""
    logins = _qualifying_logins(comments)
    if len(logins) > MAX_AUTHORITY_LOOKUPS:
        raise OperationalError(
            "The snapshot producer reached the repository authority lookup cap."
        )
    authority: dict[str, bool] = {}
    for login in logins:
        _require_deadline(deadline)
        try:
            value = _gh_get(
                f"repos/{repository}/collaborators/{quote(login, safe='')}/permission",
                "repository permission",
                budget,
            )
        except OperationalError as error:
            # The lookup is the only proof of repository authority, so an
            # unreadable answer fails closed.
            raise OperationalError(AUTHORITY_CAPABILITY_MESSAGE) from error
        if not isinstance(value, dict):
            raise OperationalError(AUTHORITY_CAPABILITY_MESSAGE)
        permission = value.get("permission")
        if not isinstance(permission, str):
            raise OperationalError(AUTHORITY_CAPABILITY_MESSAGE)
        authority[login] = permission.upper() in AUTHORITY_PERMISSIONS
    return authority


def _comment_record(
    value: Mapping[str, Any],
    repository: str,
    number: int,
    authority: Mapping[str, bool],
) -> dict[str, Any]:
    """Return one snapshot comment with its proven authority flag."""
    comment_id = _require_integer_identity(value.get("id"), "comment identity")
    url = f"{canonical_issue_url(repository, number)}#issuecomment-{comment_id}"
    if value.get("html_url") != url:
        raise OperationalError(
            "GitHub returned a comment URL that does not match its identity: "
            f"{value.get('html_url')!r}."
        )
    login = _comment_login(value)
    author = cast(dict[str, Any], value.get("user"))
    body = value.get("body")
    if not isinstance(body, str):
        raise OperationalError("GitHub returned a comment without a body.")
    qualifying = _comment_association(value) in AUTHORITY_ASSOCIATIONS
    return {
        "id": comment_id,
        "url": url,
        "author": {
            "id": _require_integer_identity(author.get("id"), "author identity"),
            "login": login,
            "is_authority": qualifying and authority.get(login, False),
        },
        "body": body,
    }


def build_snapshot(
    repository: str, number: int, host: str, deadline: float
) -> dict[str, Any]:
    """Return the canonical issue snapshot document for one issue."""
    budget = _ReadBudget()
    actor = _actor_record(budget)
    issue, target = _issue_record(repository, number, host, budget)
    values = _comment_pages(repository, number, budget, deadline)
    authority = _authority_for_logins(repository, values, budget, deadline)
    return {
        "schema_id": SNAPSHOT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "target": target,
        "actor": actor,
        "issue": issue,
        "comments": [
            _comment_record(value, repository, number, authority) for value in values
        ],
        "comments_complete": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Produce one snapshot on standard output."""
    parser = argument_parser(description="Build the canonical issue-snapshot document.")
    parser.add_argument("--repo", help="The canonical GitHub OWNER/REPOSITORY value.")
    parser.add_argument("--number", type=int, help="The positive issue number.")
    parser.add_argument("--host", default=GITHUB_HOST, help="The issue host.")
    parser.add_argument("--provider", default=GITHUB_PROVIDER, help="The provider.")
    arguments = parser.parse_args(argv)
    try:
        if arguments.provider != GITHUB_PROVIDER:
            raise OperationalError(
                f"The issue snapshot producer has no {arguments.provider!r} adapter. "
                "Only the 'github' provider is supported."
            )
        repository = require_github_repository(arguments.repo, "repository")
        number = require_issue_number(arguments.number)
        snapshot = build_snapshot(
            repository,
            number,
            require_github_host(arguments.host, "host"),
            time.monotonic() + SNAPSHOT_DEADLINE_SECONDS,
        )
        review_exchange.write_utf8_stdout(
            review_exchange.canonical_json(snapshot) + "\n"
        )
    except review_exchange.ProtocolError as error:
        print(review_exchange._single_line_diagnostic(error), file=sys.stderr)
        return 1
    except (review_exchange.OperationalError, RuntimeError, OSError) as error:
        print(review_exchange._single_line_diagnostic(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
