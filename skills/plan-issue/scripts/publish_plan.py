#!/usr/bin/env python3
"""Publish or recover one exact prepared plan comment through one adapter."""

from __future__ import annotations

import copy
import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Protocol, cast

PLAN_SCRIPTS = Path(__file__).resolve().parent
SKILLS_ROOT = PLAN_SCRIPTS.parents[1]

_issue_exchange_path = SKILLS_ROOT / "review-exchange" / "scripts" / "issue_exchange.py"
_issue_exchange_spec = importlib.util.spec_from_file_location(
    "athena_plan_issue_exchange", _issue_exchange_path
)
if _issue_exchange_spec is None or _issue_exchange_spec.loader is None:
    raise RuntimeError(
        f"The issue-exchange helper is unavailable: '{_issue_exchange_path}'."
    )
issue_exchange = importlib.util.module_from_spec(_issue_exchange_spec)
sys.modules[_issue_exchange_spec.name] = issue_exchange
_issue_exchange_spec.loader.exec_module(issue_exchange)
review_exchange = issue_exchange.review_exchange

_snapshot_path = SKILLS_ROOT / "review-exchange" / "scripts" / "mk_issue_snapshot.py"
_snapshot_spec = importlib.util.spec_from_file_location(
    "athena_plan_issue_snapshot", _snapshot_path
)
if _snapshot_spec is None or _snapshot_spec.loader is None:
    raise RuntimeError(f"The issue snapshot helper is unavailable: '{_snapshot_path}'.")
mk_issue_snapshot = importlib.util.module_from_spec(_snapshot_spec)
sys.modules[_snapshot_spec.name] = mk_issue_snapshot
_snapshot_spec.loader.exec_module(mk_issue_snapshot)

if TYPE_CHECKING or __package__ not in {None, ""}:
    from skills._cli import argument_parser, run_command
else:
    _cli_path = SKILLS_ROOT / "_cli.py"
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

RESULT_SCHEMA_ID: Final[str] = "athena.plan-issue.publication-adapter"
RECEIPT_SCHEMA_ID: Final[str] = "athena.plan-issue.publication-receipt"
SCHEMA_VERSION: Final[int] = 1
GITHUB_PROVIDER: Final[str] = "github"
MAX_INPUT_BYTES: Final[int] = review_exchange.MAX_INPUT_BYTES

RECEIPT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_id",
        "schema_version",
        "stage",
        "action",
        "artifact",
        "target",
        "actor_id",
        "requirements_sha256",
        "precondition_sha256",
        "operation_sha256",
        "submitted_body_sha256",
        "comment_id",
        "url",
        "comment_count",
        "comments",
        "marker_comment_sha256",
        "foreign_marker_comment_count",
    }
)


class PublicationError(RuntimeError):
    """A controlled publication failure with its exit class."""

    def __init__(self, message: str, *, operational: bool = False) -> None:
        super().__init__(message)
        self.operational = operational


_PUBLICATION_PROVIDER_ERRORS = (
    PublicationError,
    OSError,
    RuntimeError,
    TimeoutError,
    subprocess.SubprocessError,
    review_exchange.ProtocolError,
    review_exchange.OperationalError,
)


class ReadOnlyForge(Protocol):
    """The only forge capability that recovery receives."""

    def snapshot(self) -> dict[str, Any]:
        """Read one complete fresh issue snapshot."""


class Forge(ReadOnlyForge, Protocol):
    """The minimum write capability that publication uses."""

    def create_comment(self, body: str) -> tuple[str, str]:
        """Create one issue comment with exact text and return its identity."""

    def update_comment(self, comment_id: str, body: str) -> tuple[str, str]:
        """Replace one issue comment with exact text and return its identity."""


def _single_line_diagnostic(error: BaseException) -> str:
    """Return one printable diagnostic line."""
    return "".join(
        character if character.isprintable() else ascii(character)[1:-1]
        for character in str(error)
    )


def _read_bytes(path: str, description: str) -> bytes:
    """Read one bounded prepared document or receipt."""
    try:
        if path == "-":
            content = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with Path(path).open("rb") as stream:
                content = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as error:
        raise PublicationError(f"The {description} cannot be read: {error}") from error
    if len(content) > MAX_INPUT_BYTES:
        raise PublicationError(f"The {description} is larger than 1 MiB.")
    return content


def _parse_document(content: bytes, description: str) -> dict[str, Any]:
    """Parse one exact JSON object without normalization."""
    try:
        value = review_exchange.parse_json_bytes(content)
    except review_exchange.ProtocolError as error:
        raise PublicationError(str(error)) from error
    if not isinstance(value, dict):
        raise PublicationError(f"The {description} must be one JSON object.")
    return cast(dict[str, Any], value)


def load_prepared_document(path: str) -> dict[str, Any]:
    """Load one exact prepared-plan document from a file or standard input."""
    return _parse_document(_read_bytes(path, "prepared document"), "prepared document")


def _read_receipt(path: Path) -> dict[str, Any]:
    """Read one receipt through a symlink-free regular-file path."""
    try:
        metadata = path.lstat()
    except OSError as error:
        raise PublicationError(
            f"The attempt receipt cannot be read: {error}"
        ) from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise PublicationError("The attempt receipt is not a regular file.")
    if metadata.st_nlink != 1:
        raise PublicationError("The attempt receipt has an unsafe link count.")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            content = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as error:
        raise PublicationError(
            f"The attempt receipt cannot be read: {error}"
        ) from error
    if len(content) > MAX_INPUT_BYTES:
        raise PublicationError("The attempt receipt is larger than 1 MiB.")
    return _validate_receipt(_parse_document(content, "attempt receipt"))


def _require_receipt_directory(component: Path) -> os.stat_result:
    """Reject a symbolic link or a non-directory component of the receipt path."""
    try:
        metadata = component.lstat()
    except OSError as error:
        raise PublicationError(
            f"The attempt receipt parent cannot be read: {error}"
        ) from error
    if stat.S_ISLNK(metadata.st_mode):
        raise PublicationError("The attempt receipt path contains a symbolic link.")
    if not stat.S_ISDIR(metadata.st_mode):
        raise PublicationError(
            "The attempt receipt path contains a non-directory component."
        )
    return metadata


def _validated_receipt_path(value: str) -> Path:
    """Return one safe dedicated attempt-receipt path.

    The components of the path at and below the current directory must be real
    directories and must not be symbolic links. Components above the current
    directory are trusted. The selected parent is always checked, even when it
    is outside the current directory.
    """
    if not value or "\0" in value:
        raise PublicationError("The attempt receipt path is empty or unsafe.")
    path = Path(value)
    if not path.name or path.name in {".", ".."}:
        raise PublicationError("The attempt receipt path has no safe file name.")
    parent = path.parent
    absolute_parent = Path(os.path.abspath(str(parent)))
    absolute_cwd = Path(os.path.abspath(str(Path.cwd())))
    try:
        tail = absolute_parent.relative_to(absolute_cwd)
    except ValueError:
        tail = None
    if tail is not None and tail.parts:
        components = [
            absolute_cwd.joinpath(*tail.parts[: index + 1])
            for index in range(len(tail.parts))
        ]
    else:
        components = [absolute_parent]
    for component in components:
        parent_metadata = _require_receipt_directory(component)
    if parent_metadata.st_mode & stat.S_IWOTH:
        raise PublicationError("The attempt receipt parent is world-writable.")
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return path
    except OSError as error:
        raise PublicationError(
            f"The attempt receipt path cannot be read: {error}"
        ) from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise PublicationError("The attempt receipt path is not a regular file.")
    return path


def _fsync_directory(path: Path) -> None:
    """Persist one directory entry after an atomic receipt promotion."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_new_receipt(path: Path, document: Mapping[str, Any]) -> None:
    """Create one durable phase-one receipt without replacing an existing path."""
    content = (review_exchange.canonical_json(document) + "\n").encode("utf-8")
    descriptor, staging_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".partial", dir=path.parent
    )
    staging = Path(staging_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(staging, path)
        finally:
            staging.unlink()
        _fsync_directory(path.parent)
    except FileExistsError:
        raise
    except OSError:
        try:
            staging.unlink()
        except OSError:
            # Retain the original failure; the staging path is only cleanup evidence.
            pass
        raise


def _replace_receipt(path: Path, document: Mapping[str, Any]) -> None:
    """Promote one complete phase-two receipt with an atomic replacement."""
    content = (review_exchange.canonical_json(document) + "\n").encode("utf-8")
    descriptor, staging_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".partial", dir=path.parent
    )
    staging = Path(staging_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise PublicationError("The attempt receipt changed before promotion.")
        os.replace(staging, path)
        _fsync_directory(path.parent)
    except OSError:
        try:
            staging.unlink()
        except OSError:
            # Retain the original failure; the staging path is only cleanup evidence.
            pass
        raise


def _update_receipt(
    path: Path,
    expected: Mapping[str, Any],
    comment_id: str,
    url: str,
) -> None:
    """Record the returned comment identity in the phase-two receipt."""
    current = _read_receipt(path)
    for field in (
        "operation_sha256",
        "target",
        "actor_id",
        "submitted_body_sha256",
    ):
        if current[field] != expected[field]:
            raise PublicationError(
                "The attempt receipt does not bind the current publication."
            )
    if (
        current["stage"] != "pre_write"
        or current["comment_id"] is not None
        or current["url"] is not None
    ):
        raise PublicationError("The attempt receipt is not in its phase-one state.")
    updated = {
        **current,
        "stage": "post_response",
        "comment_id": comment_id,
        "url": url,
    }
    _replace_receipt(path, updated)


def _validate_receipt(value: object) -> dict[str, Any]:
    """Validate one complete plan publication attempt receipt."""
    if not isinstance(value, Mapping) or set(value) != RECEIPT_FIELDS:
        raise PublicationError("The attempt receipt fields are not supported.")
    if value["schema_id"] != RECEIPT_SCHEMA_ID:
        raise PublicationError("The attempt receipt schema is not supported.")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise PublicationError("The attempt receipt version is not supported.")
    if value["stage"] not in {"pre_write", "post_response"}:
        raise PublicationError("The attempt receipt stage is not supported.")
    if value["action"] not in {"create", "update"}:
        raise PublicationError("The attempt receipt action is not supported.")
    if value["artifact"] != "plan":
        raise PublicationError("The attempt receipt artifact is not supported.")
    if not isinstance(value["target"], Mapping):
        raise PublicationError("The attempt receipt target is not valid.")
    if not isinstance(value["actor_id"], str) or not value["actor_id"]:
        raise PublicationError("The attempt receipt actor is not valid.")
    for field in (
        "requirements_sha256",
        "precondition_sha256",
        "operation_sha256",
        "submitted_body_sha256",
        "marker_comment_sha256",
    ):
        digest = value[field]
        if not isinstance(digest, str) or len(digest) != 64:
            raise PublicationError(f"The attempt receipt {field} is not valid.")
        try:
            int(digest, 16)
        except ValueError as error:
            raise PublicationError(
                f"The attempt receipt {field} is not valid."
            ) from error
    comment_id = value["comment_id"]
    url = value["url"]
    if (comment_id is None) != (url is None):
        raise PublicationError("The attempt receipt comment identity is incomplete.")
    if value["stage"] == "pre_write" and comment_id is not None:
        raise PublicationError("A pre-write receipt cannot contain an identity.")
    if value["stage"] == "post_response" and comment_id is None:
        raise PublicationError("A post-response receipt needs an identity.")
    if comment_id is not None and (not isinstance(comment_id, str) or not comment_id):
        raise PublicationError("The attempt receipt comment identity is not valid.")
    if url is not None and (not isinstance(url, str) or not url):
        raise PublicationError("The attempt receipt comment URL is not valid.")
    comment_count = value["comment_count"]
    if type(comment_count) is not int or comment_count < 0:
        raise PublicationError("The attempt receipt comment count is not valid.")
    comments = value["comments"]
    if not isinstance(comments, list):
        raise PublicationError("The attempt receipt inventory is not valid.")
    seen: set[str] = set()
    for record in comments:
        if not isinstance(record, Mapping) or set(record) != {
            "id",
            "author_id",
            "body_sha256",
            "marker_count",
        }:
            raise PublicationError("The attempt receipt inventory record is not valid.")
        record_id = record["id"]
        author_id = record["author_id"]
        body_sha256 = record["body_sha256"]
        marker_count = record["marker_count"]
        if not isinstance(record_id, str) or not record_id:
            raise PublicationError("The attempt receipt inventory ID is not valid.")
        if record_id in seen:
            raise PublicationError("The attempt receipt inventory has a duplicate ID.")
        seen.add(record_id)
        if not isinstance(author_id, str) or not author_id:
            raise PublicationError("The attempt receipt inventory author is not valid.")
        if not isinstance(body_sha256, str) or len(body_sha256) != 64:
            raise PublicationError("The attempt receipt inventory digest is not valid.")
        try:
            int(body_sha256, 16)
        except ValueError as error:
            raise PublicationError(
                "The attempt receipt inventory digest is not valid."
            ) from error
        if type(marker_count) is not int or marker_count < 1:
            raise PublicationError(
                "The attempt receipt inventory marker count is not valid."
            )
    if comment_count != len(comments):
        raise PublicationError("The attempt receipt comment count does not match.")
    foreign_count = value["foreign_marker_comment_count"]
    if type(foreign_count) is not int or foreign_count < 0:
        raise PublicationError("The attempt receipt foreign count is not valid.")
    return dict(value)


def _receipt_document(
    prepared: Mapping[str, Any], inventory: Mapping[str, Any]
) -> dict[str, Any]:
    """Build one exact phase-one attempt receipt."""
    operation = prepared["operation"]
    return {
        "schema_id": RECEIPT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "stage": "pre_write",
        "action": operation["action"],
        "artifact": operation["artifact"],
        "target": copy.deepcopy(prepared["target"]),
        "actor_id": prepared["actor_id"],
        "requirements_sha256": prepared["requirements_sha256"],
        "precondition_sha256": prepared["precondition_sha256"],
        "operation_sha256": operation["operation_sha256"],
        "submitted_body_sha256": operation["body_sha256"],
        "comment_id": None,
        "url": None,
        "comment_count": inventory["comment_count"],
        "comments": copy.deepcopy(inventory["comments"]),
        "marker_comment_sha256": inventory["marker_comment_sha256"],
        "foreign_marker_comment_count": inventory["foreign_marker_comment_count"],
    }


def _result(
    status: str,
    prepared: Mapping[str, Any] | None,
    *,
    comment_id: str | None = None,
    url: str | None = None,
    receipt_path: str | None = None,
    receipt_stage: str | None = None,
    receipt_has_comment_identity: bool = False,
    preflight_code: str | None = None,
    recovery: str | None = None,
    retry_allowed: bool = False,
    diagnostics: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return one stable adapter result envelope."""
    operation = None if prepared is None else prepared["operation"]
    return {
        "schema_id": RESULT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "action": None if operation is None else operation["action"],
        "artifact": None if operation is None else operation["artifact"],
        "comment_id": comment_id,
        "url": url,
        "receipt_path": receipt_path,
        "receipt_stage": receipt_stage,
        "receipt_has_comment_identity": receipt_has_comment_identity,
        "operation_sha256": (
            None if operation is None else operation["operation_sha256"]
        ),
        "submitted_body_sha256": (
            None if operation is None else operation["body_sha256"]
        ),
        "preflight_code": preflight_code,
        "recovery": recovery,
        "retry_allowed": retry_allowed,
        "diagnostics": [dict(diagnostic) for diagnostic in diagnostics],
    }


def _validated_prepared(value: object) -> dict[str, Any]:
    """Validate one prepared document through its public reducer projection."""
    try:
        return issue_exchange.validate_prepared_document(value)
    except review_exchange.ProtocolError as error:
        raise PublicationError(str(error)) from error


def _document_payload(body: str) -> bytes:
    """Build exact UTF-8 request bytes for one body without locale encoding."""
    document = review_exchange.canonical_json({"body": body})
    try:
        round_trip = review_exchange.parse_json_bytes(document.encode("utf-8"))
    except review_exchange.ProtocolError as error:
        raise PublicationError(str(error)) from error
    if not isinstance(round_trip, dict) or round_trip.get("body") != body:
        raise PublicationError("The exact prepared body did not survive encoding.")
    return document.encode("utf-8")


class GitHubForge:
    """The controlled GitHub issue-comment adapter."""

    def __init__(self, target: Mapping[str, Any]) -> None:
        if target.get("provider") != GITHUB_PROVIDER:
            raise PublicationError("The publication provider is not supported.")
        try:
            self.host = mk_issue_snapshot.require_github_host(
                target.get("host"), "target host"
            )
            self.repository = mk_issue_snapshot.require_github_repository(
                target.get("repository"), "target repository"
            )
            self.number = mk_issue_snapshot.require_issue_number(target.get("number"))
        except review_exchange.ProtocolError as error:
            raise PublicationError(str(error)) from error
        self.target = dict(target)
        self.owner, self.name = self.repository.split("/", maxsplit=1)

    def snapshot(self) -> dict[str, Any]:
        """Read one complete canonical issue snapshot."""
        try:
            return mk_issue_snapshot.build_snapshot(
                self.repository,
                self.number,
                self.host,
                time.monotonic() + mk_issue_snapshot.SNAPSHOT_DEADLINE_SECONDS,
            )
        except review_exchange.ProtocolError as error:
            raise PublicationError(str(error)) from error
        except review_exchange.OperationalError as error:
            raise PublicationError(str(error), operational=True) from error

    def _write(
        self,
        method: str,
        path: str,
        body: str,
        *,
        expected_comment_id: str | None = None,
    ) -> tuple[str, str]:
        """Send one exact UTF-8 request document on standard input."""
        payload = _document_payload(body)
        try:
            completed = cast(
                "subprocess.CompletedProcess[bytes]",
                run_command(
                    (
                        "gh",
                        "api",
                        "--hostname",
                        self.host,
                        "--method",
                        method,
                        path,
                        "--input",
                        "-",
                    ),
                    input=payload,
                    capture_output=True,
                    check=False,
                    text=False,
                ),
            )
        except RuntimeError as error:
            raise PublicationError(str(error), operational=True) from error
        if completed.returncode != 0:
            detail = (completed.stderr or b"").decode("utf-8", errors="replace").strip()
            raise PublicationError(detail or "The GitHub write request failed.")
        try:
            value = review_exchange.parse_json_bytes(completed.stdout or b"")
        except review_exchange.ProtocolError as error:
            raise PublicationError("GitHub returned invalid write content.") from error
        if not isinstance(value, dict):
            raise PublicationError("GitHub returned invalid write content.")
        identity = value.get("id")
        if isinstance(identity, bool) or not isinstance(identity, int) or identity < 1:
            raise PublicationError("GitHub returned no comment identity.")
        comment_id = str(identity)
        expected_url = f"{self.target['url']}#issuecomment-{comment_id}"
        url = value.get("html_url")
        if url != expected_url:
            raise PublicationError("GitHub returned a comment URL that does not bind.")
        if expected_comment_id is not None and comment_id != expected_comment_id:
            raise PublicationError("GitHub returned a different comment identity.")
        return comment_id, cast(str, url)

    def create_comment(self, body: str) -> tuple[str, str]:
        """Create one issue comment with exact text."""
        return self._write(
            "POST",
            f"repos/{self.owner}/{self.name}/issues/{self.number}/comments",
            body,
        )

    def update_comment(self, comment_id: str, body: str) -> tuple[str, str]:
        """Replace one retained issue comment with exact text."""
        if not comment_id.isdigit():
            raise PublicationError("The retained comment identity is not numeric.")
        return self._write(
            "PATCH",
            f"repos/{self.owner}/{self.name}/issues/comments/{comment_id}",
            body,
            expected_comment_id=comment_id,
        )


def publish(
    prepared_value: object,
    receipt_path: str,
    *,
    forge: Forge | None = None,
) -> dict[str, Any]:
    """Publish one exact prepared plan comment once, then verify exact readback."""
    prepared = _validated_prepared(prepared_value)
    operation = prepared["operation"]
    if prepared["target"]["provider"] != GITHUB_PROVIDER:
        return _result(
            "no_write",
            prepared,
            receipt_path=receipt_path,
            preflight_code="unsupported_provider",
            diagnostics=[
                {
                    "code": "unsupported_provider",
                    "message": "The publication adapter supports only GitHub.",
                }
            ],
        )
    if operation["artifact"] != "plan":
        raise PublicationError("Only a prepared plan operation can be published.")
    if operation["action"] not in {"create", "update"}:
        raise PublicationError("The prepared plan action is not supported.")
    body = operation["body"]
    _document_payload(body)
    path = _validated_receipt_path(receipt_path)
    adapter = GitHubForge(prepared["target"]) if forge is None else forge
    try:
        fresh = adapter.snapshot()
    except PublicationError:
        raise
    except _PUBLICATION_PROVIDER_ERRORS as error:
        raise PublicationError(
            "The fresh issue snapshot cannot be read.", operational=True
        ) from error
    preflight = issue_exchange.publication_preflight(
        {"prepared": prepared, "snapshot": fresh}
    )
    if preflight["status"] != "matched":
        return _result(
            "no_write",
            prepared,
            receipt_path=str(path),
            preflight_code=cast(str, preflight["preflight_code"]),
            diagnostics=cast(Sequence[Mapping[str, Any]], preflight["diagnostics"]),
        )
    inventory = issue_exchange.plan_marker_inventory(
        {"snapshot": fresh, "artifact": "plan"}
    )
    receipt = _receipt_document(prepared, inventory)
    try:
        _write_new_receipt(path, receipt)
    except FileExistsError:
        return _result(
            "no_write",
            prepared,
            receipt_path=str(path),
            preflight_code="receipt_identity_conflict",
            retry_allowed=True,
            diagnostics=[
                {
                    "code": "receipt_identity_conflict",
                    "message": "The dedicated attempt receipt path already exists.",
                }
            ],
        )
    except PublicationError:
        raise
    except OSError as error:
        raise PublicationError(
            f"The attempt receipt cannot be created: {error}", operational=True
        ) from error
    try:
        if operation["action"] == "create":
            comment_id, url = adapter.create_comment(body)
        else:
            comment_id, url = adapter.update_comment(operation["comment_id"], body)
        if (
            not isinstance(comment_id, str)
            or not comment_id
            or not isinstance(url, str)
            or not url
        ):
            raise PublicationError("The provider returned no comment identity.")
    except _PUBLICATION_PROVIDER_ERRORS as error:
        return _result(
            "unknown_outcome",
            prepared,
            receipt_path=str(path),
            receipt_stage="pre_write",
            preflight_code=None,
            retry_allowed=False,
            diagnostics=[
                {
                    "code": "write_response_lost",
                    "message": f"The provider write result is unknown: {error}",
                }
            ],
        )
    try:
        _update_receipt(path, receipt, comment_id, url)
    except _PUBLICATION_PROVIDER_ERRORS as error:
        return _result(
            "unknown_outcome",
            prepared,
            comment_id=comment_id,
            url=url,
            receipt_path=str(path),
            receipt_stage="pre_write",
            receipt_has_comment_identity=False,
            retry_allowed=False,
            diagnostics=[
                {
                    "code": "receipt_post_write_unrecorded",
                    "message": (
                        f"The returned comment identity could not be recorded: {error}"
                    ),
                }
            ],
        )
    try:
        readback = adapter.snapshot()
    except _PUBLICATION_PROVIDER_ERRORS as error:
        return _result(
            "unknown_outcome",
            prepared,
            comment_id=comment_id,
            url=url,
            receipt_path=str(path),
            receipt_stage="post_response",
            receipt_has_comment_identity=True,
            retry_allowed=False,
            diagnostics=[
                {
                    "code": "readback_unavailable",
                    "message": f"The publication readback is unavailable: {error}",
                }
            ],
        )
    verification = issue_exchange.verify_publication(
        {"prepared": prepared, "snapshot": readback}
    )
    if verification["status"] == "verified":
        verified_receipt = verification["receipt"]
        return _result(
            "verified",
            prepared,
            comment_id=verified_receipt["comment_id"],
            url=verified_receipt["url"],
            receipt_path=str(path),
            receipt_stage="post_response",
            receipt_has_comment_identity=True,
            retry_allowed=False,
        )
    return _result(
        "unknown_outcome",
        prepared,
        comment_id=comment_id,
        url=url,
        receipt_path=str(path),
        receipt_stage="post_response",
        receipt_has_comment_identity=True,
        retry_allowed=False,
        diagnostics=cast(Sequence[Mapping[str, Any]], verification["diagnostics"]),
    )


def recover(
    prepared_value: object,
    receipt_path: str,
    *,
    forge: ReadOnlyForge | None = None,
) -> dict[str, Any]:
    """Classify one plan publication outcome without any write capability."""
    prepared = _validated_prepared(prepared_value)
    operation = prepared["operation"]
    if operation["artifact"] != "plan":
        raise PublicationError("Only a plan publication can be recovered.")
    if prepared["target"]["provider"] != GITHUB_PROVIDER:
        raise PublicationError("The recovery adapter supports only GitHub.")
    path = _validated_receipt_path(receipt_path)
    receipt = _read_receipt(path)
    adapter = GitHubForge(prepared["target"]) if forge is None else forge
    try:
        fresh = adapter.snapshot()
    except PublicationError:
        raise
    except _PUBLICATION_PROVIDER_ERRORS as error:
        raise PublicationError(
            "The fresh issue snapshot cannot be read.", operational=True
        ) from error
    classification = issue_exchange.classify_plan_recovery(
        {"prepared": prepared, "snapshot": fresh, "receipt": receipt}
    )
    return _result(
        cast(str, classification["status"]),
        prepared,
        comment_id=cast(str | None, classification["candidate_comment_id"]),
        url=cast(str | None, classification["candidate_url"]),
        receipt_path=str(path),
        receipt_stage=cast(str, receipt["stage"]),
        receipt_has_comment_identity=receipt["comment_id"] is not None,
        recovery=cast(str, classification["classification"]),
        retry_allowed=False,
        diagnostics=cast(Sequence[Mapping[str, Any]], classification["diagnostics"]),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the controlled plan publication adapter."""
    parser = argument_parser(
        description="Publish or recover one exact prepared plan comment."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    publish_parser = subparsers.add_parser(
        "publish", help="Publish one exact prepared plan document once."
    )
    publish_parser.add_argument(
        "prepared", help="The exact prepared-plan JSON document, or '-'."
    )
    publish_parser.add_argument(
        "--receipt", required=True, help="One dedicated attempt-receipt path."
    )
    recover_parser = subparsers.add_parser(
        "recover", help="Classify one plan publication outcome without a write."
    )
    recover_parser.add_argument(
        "prepared", help="The exact prepared-plan JSON document, or '-'."
    )
    recover_parser.add_argument(
        "--receipt", required=True, help="The retained attempt-receipt path."
    )
    arguments = parser.parse_args(argv)
    try:
        prepared = load_prepared_document(arguments.prepared)
        if arguments.command == "publish":
            result = publish(prepared, arguments.receipt)
        else:
            result = recover(prepared, arguments.receipt)
    except PublicationError as error:
        print(_single_line_diagnostic(error), file=sys.stderr)
        return 2 if error.operational else 1
    except (
        review_exchange.ProtocolError,
        review_exchange.OperationalError,
        RuntimeError,
        OSError,
    ) as error:
        print(_single_line_diagnostic(error), file=sys.stderr)
        return 2
    review_exchange.write_utf8_stdout(review_exchange.canonical_json(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
