#!/usr/bin/env python3
"""Bind a realign assessment to one selected commit or worktree overlay."""

from __future__ import annotations

import errno
import hashlib
import importlib.util
import json
import os
import queue
import re
import signal
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any, cast

if __package__ not in {None, ""}:
    from skills._cli import (
        argument_parser,
        git_read_arguments,
        git_read_environment,
    )
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
    git_read_arguments = _cli.git_read_arguments
    git_read_environment = _cli.git_read_environment


SELECTOR_FORBIDDEN = ("..", "^@", "^!", "@{", ":")
CANDIDATE_ID = re.compile(r"[A-Z][A-Z0-9_-]{2,63}\Z")
REALIGN_CANDIDATE_ID = re.compile(r"RLG-[0-9]{3}\Z")
MAX_GIT_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_PATH_COUNT = 250_000
GIT_TIMEOUT_SECONDS = 30.0
ASSESSMENT_TIMEOUT_SECONDS = 300.0
ASSESSMENT_SCHEMA_VERSION = 1
INTERNAL_FILE_READ_COMMAND = "__athena_read_bound_file"
INTERNAL_FILE_ABSENT = "ATHENA_INTERNAL_FILE_ABSENT"
INTERNAL_FILE_SYMLINK = "ATHENA_INTERNAL_FILE_SYMLINK"
INTERNAL_FILE_BOUNDARY = "ATHENA_INTERNAL_FILE_BOUNDARY"


@dataclass(frozen=True)
class SnapshotFileEntry:
    """One regular file read from an explicitly bound source."""

    path: str
    source_kind: str
    content: bytes
    object_id: str | None = None
    mode: str | None = None


class SourcePathAbsentError(RuntimeError):
    """A selected worktree path disappeared during capture."""


class SourcePathSymlinkError(RuntimeError):
    """A selected worktree path is a symbolic-link boundary."""


class SourcePathBoundaryError(RuntimeError):
    """A selected worktree path is not a regular file."""


def _run_bounded_process(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    output_limit: int,
    deadline: float | None,
    operation: str,
) -> bytes:
    """Run one contained process with bounded output, time, and cleanup."""
    if os.name != "posix":
        raise RuntimeError(
            f"The host cannot provide contained process cleanup for the {operation}."
        )
    failure: BaseException | None = None
    try:
        process = subprocess.Popen(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(environment),
            start_new_session=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            f"The required command is not available: '{command[0]}'."
        ) from error
    if process.stdout is None or process.stderr is None:
        process.kill()
        process.wait()
        raise RuntimeError(f"The {operation} did not expose output.")
    chunks: queue.Queue[tuple[str, str, bytes | Exception | None]] = queue.Queue(
        maxsize=4
    )
    stop_readers = threading.Event()

    def enqueue_output(
        item: tuple[str, str, bytes | Exception | None],
    ) -> None:
        """Queue output while allowing bounded failure cleanup."""
        while not stop_readers.is_set():
            try:
                chunks.put(item, timeout=0.05)
            except queue.Full:
                continue
            return

    def read_output(name: str, stream: Any) -> None:
        try:
            while chunk := stream.read(64 * 1024):
                enqueue_output((name, "data", chunk))
                if stop_readers.is_set():
                    return
        # Transfer each stream failure to the coordinating thread.
        except Exception as error:  # noqa: BLE001
            enqueue_output((name, "error", error))
        else:
            enqueue_output((name, "done", None))

    readers = [
        threading.Thread(
            target=read_output,
            args=("stdout", process.stdout),
            name="realign-process-stdout-reader",
            daemon=True,
        ),
        threading.Thread(
            target=read_output,
            args=("stderr", process.stderr),
            name="realign-process-stderr-reader",
            daemon=True,
        ),
    ]
    for reader in readers:
        reader.start()
    stdout: list[bytes] = []
    stderr: list[bytes] = []
    byte_count = 0
    completed_readers = 0
    command_deadline = time.monotonic() + GIT_TIMEOUT_SECONDS
    if deadline is not None:
        command_deadline = min(command_deadline, deadline)

    def stop_process_tree() -> None:
        """Stop the isolated process group or the direct process."""
        pid = getattr(process, "pid", None)
        if isinstance(pid, int):
            try:
                os.killpg(pid, signal.SIGKILL)
                return
            except (PermissionError, ProcessLookupError):
                pass
        if process.poll() is None:
            process.kill()

    try:
        while completed_readers < len(readers):
            remaining = command_deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"The {operation} exceeded its time limit.")
            try:
                event = chunks.get(timeout=remaining)
            except queue.Empty as error:
                raise RuntimeError(
                    f"The {operation} exceeded its time limit."
                ) from error
            name, kind, payload = event
            if kind == "error":
                assert isinstance(payload, Exception)
                raise RuntimeError(f"The {operation} {name} read failed.") from payload
            if kind == "done":
                completed_readers += 1
                continue
            assert kind == "data" and isinstance(payload, bytes)
            content = payload
            byte_count += len(content)
            if byte_count > output_limit:
                raise RuntimeError(f"The {operation} exceeded its output limit.")
            (stdout if name == "stdout" else stderr).append(content)
        remaining = command_deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f"The {operation} exceeded its time limit.")
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"The {operation} exceeded its time limit.") from error
        if returncode != 0:
            message = b"".join(stderr).decode("utf-8", errors="replace").strip()
            raise RuntimeError(message or f"The {operation} failed.")
    except BaseException as error:
        failure = error
        stop_process_tree()
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"The failed {operation} process could not be reaped."
            ) from error
        raise
    finally:
        stop_readers.set()
        if failure is not None:
            stop_process_tree()
        cleanup_deadline = time.monotonic() + 1.0
        for reader in readers:
            reader.join(timeout=max(0.0, cleanup_deadline - time.monotonic()))
        if any(reader.is_alive() for reader in readers):
            cleanup_error = RuntimeError(
                f"The {operation} output readers could not be stopped."
            )
            if failure is not None:
                raise cleanup_error from failure
            raise cleanup_error
        close_errors: list[OSError] = []
        for stream in (process.stdout, process.stderr):
            try:
                stream.close()
            except OSError as error:
                close_errors.append(error)
        if close_errors:
            cleanup_error = RuntimeError(
                f"The {operation} output streams could not be closed: {close_errors[0]}"
            )
            if failure is not None:
                raise cleanup_error from failure
            raise cleanup_error from close_errors[0]
    return b"".join(stdout)


def _git_bytes(
    repository_root: Path, *arguments: str, deadline: float | None = None
) -> bytes:
    """Run one sanitized read-only Git command and return raw output."""
    command = [
        "git",
        "-c",
        "core.fsmonitor=false",
        *git_read_arguments(),
        "-C",
        os.fspath(repository_root),
        *arguments,
    ]
    return _run_bounded_process(
        command,
        environment=git_read_environment(),
        output_limit=MAX_GIT_OUTPUT_BYTES,
        deadline=deadline,
        operation="read-only Git command",
    )


def _git_text(
    repository_root: Path, *arguments: str, deadline: float | None = None
) -> str:
    """Run one sanitized Git command and return one textual value."""
    return (
        _git_bytes(repository_root, *arguments, deadline=deadline)
        .decode("utf-8", errors="surrogateescape")
        .removesuffix("\n")
    )


def _repository_root(repository_root: Path, *, deadline: float | None = None) -> Path:
    """Return and verify the canonical repository root."""
    root = Path(os.path.realpath(os.fspath(repository_root)))
    observed = Path(_git_text(root, "rev-parse", "--show-toplevel", deadline=deadline))
    if Path(os.path.realpath(os.fspath(observed))) != root:
        raise RuntimeError(f"The path is not the repository root: '{root}'.")
    return root


def normalize_repo_tree_path(raw_path: str) -> str:
    """Return one confined repository-tree path without pathspec semantics."""
    if not isinstance(raw_path, str) or not raw_path or "\x00" in raw_path:
        raise RuntimeError(f"The repository path is not valid: {raw_path!r}.")
    if (
        raw_path.startswith(":")
        or Path(raw_path).is_absolute()
        or PureWindowsPath(raw_path).is_absolute()
    ):
        raise RuntimeError(f"The repository path is not valid: {raw_path!r}.")
    components = raw_path.split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise RuntimeError(f"The repository path is not valid: {raw_path!r}.")
    return "/".join(components)


def _target_path(raw_path: str | None) -> str:
    """Return the internal repository-root sentinel or one confined target."""
    if raw_path in {None, "."}:
        return "."
    return normalize_repo_tree_path(raw_path)


def _pathspec(path: str) -> tuple[str, ...]:
    """Return an exact repository-rooted literal Git pathspec."""
    if path == ".":
        return ()
    return (f":(top,literal){path}",)


def _selected_commit(
    repository_root: Path, selector: str, *, deadline: float | None = None
) -> str:
    """Resolve one safe selector once to an immutable commit OID."""
    if (
        not selector
        or selector.startswith("-")
        or any(fragment in selector for fragment in SELECTOR_FORBIDDEN)
    ):
        raise RuntimeError(f"The selected Git reference is not valid: {selector!r}.")
    commit_oid = _git_text(
        repository_root,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{selector}^{{commit}}",
        deadline=deadline,
    )
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit_oid):
        raise RuntimeError("The selected Git reference did not resolve to one commit.")
    return commit_oid


def _commit_tree(
    repository_root: Path, commit_oid: str, *, deadline: float | None = None
) -> str:
    """Return the immutable tree OID for one already resolved commit."""
    tree_oid = _git_text(
        repository_root,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{commit_oid}^{{tree}}",
        deadline=deadline,
    )
    if not re.fullmatch(r"[0-9a-f]{40,64}", tree_oid):
        raise RuntimeError("The selected commit did not resolve to one tree.")
    return tree_oid


def _parse_tree_records(document: bytes) -> list[dict[str, str]]:
    """Parse null-delimited ls-tree records without interpreting path bytes."""
    entries: list[dict[str, str]] = []
    offset = 0
    while offset < len(document):
        record_end = document.find(b"\0", offset)
        if record_end == -1:
            record_end = len(document)
        record = document[offset:record_end]
        offset = record_end + 1
        if not record:
            continue
        if len(entries) >= MAX_PATH_COUNT:
            raise RuntimeError("The assessment exceeded its path limit.")
        try:
            metadata, raw_path = record.split(b"\t", maxsplit=1)
            mode, object_type, object_id = metadata.decode("ascii").split(" ")
        except (ValueError, UnicodeDecodeError) as error:
            raise RuntimeError("Git returned malformed tree metadata.") from error
        entries.append(
            {
                "path": os.fsdecode(raw_path),
                "mode": mode,
                "object_type": object_type,
                "object_id": object_id,
            }
        )
    return entries


def _selected_inventory_entries(
    repository_root: Path,
    commit_oid: str,
    target: str,
    *,
    deadline: float | None = None,
) -> list[dict[str, Any]]:
    """Return the recursively selected immutable tree inventory."""
    records = _parse_tree_records(
        _git_bytes(
            repository_root,
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            commit_oid,
            "--",
            *_pathspec(target),
            deadline=deadline,
        )
    )
    entries: list[dict[str, Any]] = []
    for record in records:
        kind = "file"
        if record["mode"] == "120000":
            kind = "symlink"
        elif record["mode"] == "160000" or record["object_type"] == "commit":
            kind = "submodule"
        elif record["object_type"] != "blob":
            kind = "other"
        entries.append(
            {
                **record,
                "kind": kind,
                "source_kind": "selected_commit_tree",
                "commit_oid": commit_oid,
            }
        )
    return entries


def _canonical_digest(value: Any) -> str:
    """Return a deterministic SHA-256 digest for one JSON-compatible value."""
    document = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8", errors="surrogateescape")
    return hashlib.sha256(document).hexdigest()


def assessment_report_digest(report: Mapping[str, Any]) -> str:
    """Return the identity that an approval must bind separately from a report."""
    return _canonical_digest(dict(report))


def _open_parent(repository_root: Path, relative_path: str) -> tuple[int, str]:
    """Open a repository path parent without following a symbolic link."""
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise RuntimeError(
            "The host cannot inspect repository paths without following symbolic links."
        )
    components = normalize_repo_tree_path(relative_path).split("/")
    descriptor = os.open(repository_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in components[:-1]:
            child = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor, components[-1]


def _write_all(descriptor: int, document: bytes) -> None:
    """Write all bytes to one internal worker descriptor."""
    offset = 0
    while offset < len(document):
        offset += os.write(descriptor, document[offset:])


def _internal_read_bound_file(
    repository_root: Path, relative_path: str, byte_limit: int
) -> int:
    """Read one confined regular file inside a killable worker process."""
    try:
        parent, filename = _open_parent(repository_root, relative_path)
        try:
            descriptor = os.open(
                filename,
                os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0),
                dir_fd=parent,
            )
        finally:
            os.close(parent)
    except FileNotFoundError:
        print(INTERNAL_FILE_ABSENT, file=sys.stderr)
        return 20
    except OSError as error:
        if error.errno == errno.ELOOP:
            print(INTERNAL_FILE_SYMLINK, file=sys.stderr)
            return 21
        raise
    try:
        opened_mode = os.fstat(descriptor).st_mode
        if not stat.S_ISREG(opened_mode):
            print(INTERNAL_FILE_BOUNDARY, file=sys.stderr)
            return 22
        _write_all(1, f"{stat.S_IMODE(opened_mode):04o}\n".encode("ascii"))
        byte_count = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            byte_count += len(chunk)
            if byte_count > byte_limit:
                print(
                    "The source file exceeded the file byte limit.",
                    file=sys.stderr,
                )
                return 23
            _write_all(1, chunk)
    finally:
        os.close(descriptor)
    return 0


def _bounded_file_snapshot(
    repository_root: Path,
    relative_path: str,
    *,
    deadline: float | None = None,
    byte_limit: int | None = None,
) -> SnapshotFileEntry:
    """Read one confined regular file through a contained worker process."""
    limit = MAX_FILE_BYTES if byte_limit is None else byte_limit
    command = [
        sys.executable,
        os.path.abspath(__file__),
        INTERNAL_FILE_READ_COMMAND,
        os.fspath(repository_root),
        relative_path,
        str(limit),
    ]
    try:
        document = _run_bounded_process(
            command,
            environment=git_read_environment(),
            output_limit=limit + 1024,
            deadline=deadline,
            operation="bounded source-file read",
        )
    except RuntimeError as error:
        message = str(error)
        if message == INTERNAL_FILE_ABSENT:
            raise SourcePathAbsentError(
                f"The source path does not exist: '{relative_path}'."
            ) from error
        if message == INTERNAL_FILE_SYMLINK:
            raise SourcePathSymlinkError(
                f"The source path is a symbolic link: '{relative_path}'."
            ) from error
        if message == INTERNAL_FILE_BOUNDARY:
            raise SourcePathBoundaryError(
                f"The source path is not a regular file: '{relative_path}'."
            ) from error
        raise
    raw_mode, separator, content = document.partition(b"\n")
    if separator != b"\n" or re.fullmatch(rb"[0-7]{4}", raw_mode) is None:
        raise RuntimeError("The bounded source-file worker returned malformed output.")
    return SnapshotFileEntry(
        path=relative_path,
        source_kind="worktree_overlay",
        content=content,
        mode=raw_mode.decode("ascii"),
    )


def _worktree_snapshot_entry(
    repository_root: Path,
    relative_path: str,
    *,
    deadline: float | None = None,
) -> SnapshotFileEntry:
    """Read one regular worktree file without following symbolic links."""
    return _bounded_file_snapshot(
        repository_root,
        relative_path,
        deadline=deadline,
        byte_limit=MAX_FILE_BYTES,
    )


def _worktree_paths(
    repository_root: Path,
    scopes: Sequence[str],
    *,
    deadline: float | None = None,
) -> list[str]:
    """Return selected tracked and non-ignored untracked worktree paths."""
    pathspecs = (
        ()
        if "." in scopes
        else tuple(pathspec for scope in scopes for pathspec in _pathspec(scope))
    )
    tracked = _git_bytes(
        repository_root, "ls-files", "-z", "--", *pathspecs, deadline=deadline
    )
    untracked = _git_bytes(
        repository_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
        *pathspecs,
        deadline=deadline,
    )
    paths: set[str] = set()
    for document in (tracked, untracked):
        offset = 0
        while offset < len(document):
            path_end = document.find(b"\0", offset)
            if path_end == -1:
                path_end = len(document)
            raw_path = document[offset:path_end]
            offset = path_end + 1
            if not raw_path:
                continue
            paths.add(os.fsdecode(raw_path))
            if len(paths) > MAX_PATH_COUNT:
                raise RuntimeError("The assessment exceeded its path limit.")
    return sorted(paths)


def _worktree_inventory(
    repository_root: Path,
    head_oid: str,
    target: str,
    evidence_paths: Sequence[str] = (),
    *,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Return a content-bound worktree overlay inventory."""
    scopes = tuple(dict.fromkeys((target, *evidence_paths)))
    paths = _worktree_paths(repository_root, scopes, deadline=deadline)
    entries: list[dict[str, Any]] = []
    total_bytes = 0
    for path in paths:
        try:
            snapshot = _worktree_snapshot_entry(
                repository_root, path, deadline=deadline
            )
        except SourcePathAbsentError:
            entries.append(
                {
                    "path": path,
                    "kind": "absent",
                    "source_kind": "worktree_overlay",
                    "head_oid": head_oid,
                }
            )
            continue
        except SourcePathSymlinkError:
            parent, filename = _open_parent(repository_root, path)
            try:
                target_value = os.readlink(filename, dir_fd=parent)
            finally:
                os.close(parent)
            entries.append(
                {
                    "path": path,
                    "kind": "symlink",
                    "target": os.fsdecode(target_value),
                    "source_kind": "worktree_overlay",
                    "head_oid": head_oid,
                }
            )
            continue
        except SourcePathBoundaryError:
            entries.append(
                {
                    "path": path,
                    "kind": "boundary",
                    "source_kind": "worktree_overlay",
                    "head_oid": head_oid,
                }
            )
            continue
        entries.append(
            {
                "path": path,
                "kind": "file",
                "mode": snapshot.mode,
                "byte_length": len(snapshot.content),
                "content_sha256": hashlib.sha256(snapshot.content).hexdigest(),
                "source_kind": "worktree_overlay",
                "head_oid": head_oid,
            }
        )
        total_bytes += len(snapshot.content)
        if total_bytes > MAX_TOTAL_BYTES:
            raise RuntimeError("The assessment exceeded its aggregate byte limit.")
    pathspecs = (
        ()
        if "." in scopes
        else tuple(pathspec for scope in scopes for pathspec in _pathspec(scope))
    )
    status = _git_bytes(
        repository_root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        *pathspecs,
        deadline=deadline,
    )
    identity = {
        "entries": entries,
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "target": target,
        "evidence_paths": list(evidence_paths),
    }
    return {
        **identity,
        "inventory_digest": _canonical_digest(entries),
        "overlay_digest": _canonical_digest(identity),
    }


def _binding_evidence_paths(binding: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the exact declared source-evidence paths from one binding."""
    raw_paths = binding.get("evidence_paths")
    if not isinstance(raw_paths, list) or not all(
        isinstance(path, str) for path in raw_paths
    ):
        raise TypeError("The source evidence-path binding is malformed.")
    paths = tuple(normalize_repo_tree_path(path) for path in raw_paths)
    if len(paths) != len(set(paths)) or list(paths) != raw_paths:
        raise RuntimeError("The source evidence-path binding is stale.")
    return paths


def resolve_source_binding(
    repository_root: Path,
    *,
    reference: str | None = None,
    target: str | None = ".",
    evidence_paths: Sequence[str] = (),
    _deadline: float | None = None,
) -> dict[str, Any]:
    """Bind one selected commit tree or the current worktree overlay."""
    root = _repository_root(repository_root, deadline=_deadline)
    normalized_target = _target_path(target)
    normalized_evidence_paths = tuple(
        dict.fromkeys(normalize_repo_tree_path(path) for path in evidence_paths)
    )
    if reference is not None:
        commit_oid = _selected_commit(root, reference, deadline=_deadline)
        tree_oid = _commit_tree(root, commit_oid, deadline=_deadline)
        entries = _selected_inventory_entries(
            root, commit_oid, normalized_target, deadline=_deadline
        )
        inventory_digest = _canonical_digest(entries)
        binding: dict[str, Any] = {
            "repository_root": os.fspath(root),
            "source_kind": "selected_commit_tree",
            "selector": reference,
            "commit_oid": commit_oid,
            "tree_oid": tree_oid,
            "target": normalized_target,
            "evidence_paths": list(normalized_evidence_paths),
            "inventory_digest": inventory_digest,
        }
        return {**binding, "source_digest": _canonical_digest(binding)}

    head_oid = _selected_commit(root, "HEAD", deadline=_deadline)
    tree_oid = _commit_tree(root, head_oid, deadline=_deadline)
    first_inventory = _worktree_inventory(
        root,
        head_oid,
        normalized_target,
        normalized_evidence_paths,
        deadline=_deadline,
    )
    observed_head_oid = _selected_commit(root, "HEAD", deadline=_deadline)
    observed_tree_oid = _commit_tree(root, observed_head_oid, deadline=_deadline)
    inventory = _worktree_inventory(
        root,
        observed_head_oid,
        normalized_target,
        normalized_evidence_paths,
        deadline=_deadline,
    )
    final_head_oid = _selected_commit(root, "HEAD", deadline=_deadline)
    final_tree_oid = _commit_tree(root, final_head_oid, deadline=_deadline)
    if (
        head_oid != observed_head_oid
        or head_oid != final_head_oid
        or tree_oid != observed_tree_oid
        or tree_oid != final_tree_oid
        or first_inventory != inventory
    ):
        raise RuntimeError("The worktree assessment source changed during binding.")
    binding = {
        "repository_root": os.fspath(root),
        "source_kind": "worktree_overlay",
        "head_oid": head_oid,
        "tree_oid": tree_oid,
        "target": normalized_target,
        "evidence_paths": list(normalized_evidence_paths),
        "inventory_digest": inventory["inventory_digest"],
        "overlay_digest": inventory["overlay_digest"],
        "overlay_paths": [entry["path"] for entry in inventory["entries"]],
    }
    return {**binding, "source_digest": _canonical_digest(binding)}


def _verify_selected_binding(
    repository_root: Path,
    binding: Mapping[str, Any],
    *,
    deadline: float | None = None,
) -> tuple[str, str]:
    """Verify the recorded commit and tree without resolving the original ref again."""
    bound_root = binding.get("repository_root")
    selector = binding.get("selector")
    commit_oid = binding.get("commit_oid")
    tree_oid = binding.get("tree_oid")
    inventory_digest = binding.get("inventory_digest")
    source_digest = binding.get("source_digest")
    if not all(
        isinstance(value, str)
        for value in (
            bound_root,
            selector,
            commit_oid,
            tree_oid,
            inventory_digest,
            source_digest,
        )
    ):
        raise TypeError("The selected source binding is malformed.")
    assert isinstance(bound_root, str)
    assert isinstance(selector, str)
    assert isinstance(commit_oid, str)
    assert isinstance(tree_oid, str)
    assert isinstance(inventory_digest, str)
    assert isinstance(source_digest, str)
    if bound_root != os.fspath(repository_root):
        raise RuntimeError("The selected source repository binding is stale.")
    target = _target_path(cast(str | None, binding.get("target")))
    evidence_paths = _binding_evidence_paths(binding)
    expected_binding = {
        "repository_root": bound_root,
        "source_kind": "selected_commit_tree",
        "selector": selector,
        "commit_oid": commit_oid,
        "tree_oid": tree_oid,
        "target": target,
        "evidence_paths": list(evidence_paths),
        "inventory_digest": inventory_digest,
    }
    if source_digest != _canonical_digest(expected_binding):
        raise RuntimeError("The selected source binding is stale.")
    observed_commit = _selected_commit(repository_root, commit_oid, deadline=deadline)
    observed_tree = _commit_tree(repository_root, observed_commit, deadline=deadline)
    if observed_commit != commit_oid or observed_tree != tree_oid:
        raise RuntimeError("The selected source binding is stale.")
    entries = _selected_inventory_entries(
        repository_root, commit_oid, target, deadline=deadline
    )
    if _canonical_digest(entries) != inventory_digest:
        raise RuntimeError("The selected source inventory is stale.")
    return commit_oid, tree_oid


def _verify_worktree_binding(
    repository_root: Path,
    binding: Mapping[str, Any],
    *,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Require the current worktree to match one complete recorded binding."""
    target = _target_path(cast(str | None, binding.get("target")))
    evidence_paths = _binding_evidence_paths(binding)
    current = resolve_source_binding(
        repository_root,
        target=target,
        evidence_paths=evidence_paths,
        _deadline=deadline,
    )
    if dict(binding) != current:
        raise RuntimeError("The worktree assessment source is stale.")
    return current


def snapshot_file_entry(
    repository_root: Path,
    binding: Mapping[str, Any],
    raw_path: str,
    *,
    deadline: float | None = None,
) -> SnapshotFileEntry:
    """Read one selected-commit blob without reading checkout bytes."""
    root = _repository_root(repository_root, deadline=deadline)
    if binding.get("source_kind") != "selected_commit_tree":
        raise RuntimeError("A selected-commit binding is required for this read.")
    commit_oid, _ = _verify_selected_binding(root, binding, deadline=deadline)
    path = normalize_repo_tree_path(raw_path)
    records = _parse_tree_records(
        _git_bytes(
            root,
            "ls-tree",
            "-z",
            "--full-tree",
            commit_oid,
            "--",
            *_pathspec(path),
            deadline=deadline,
        )
    )
    exact = [record for record in records if record["path"] == path]
    if len(exact) != 1:
        raise RuntimeError(f"The selected source path is not one file: '{path}'.")
    record = exact[0]
    if record["mode"] == "120000":
        raise RuntimeError(f"The selected source path is a symbolic link: '{path}'.")
    if record["mode"] == "160000" or record["object_type"] == "commit":
        raise RuntimeError(f"The selected source path is a submodule: '{path}'.")
    if record["object_type"] != "blob":
        raise RuntimeError(f"The selected source path is not a blob: '{path}'.")
    byte_length = int(
        _git_text(root, "cat-file", "-s", record["object_id"], deadline=deadline)
    )
    if byte_length > MAX_FILE_BYTES:
        raise RuntimeError(f"The source file exceeded the file byte limit: '{path}'.")
    content = _git_bytes(
        root, "cat-file", "blob", record["object_id"], deadline=deadline
    )
    if len(content) != byte_length:
        raise RuntimeError(f"The selected source file changed size: '{path}'.")
    return SnapshotFileEntry(
        path=path,
        source_kind="selected_commit_tree",
        content=content,
        object_id=record["object_id"],
        mode=record["mode"],
    )


def inventory_manifest(
    repository_root: Path, binding: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the complete inventory for the recorded assessment target."""
    root = _repository_root(repository_root)
    target = _target_path(cast(str | None, binding.get("target")))
    source_kind = binding.get("source_kind")
    if source_kind == "selected_commit_tree":
        commit_oid, _ = _verify_selected_binding(root, binding)
        entries = _selected_inventory_entries(root, commit_oid, target)
        digest = _canonical_digest(entries)
        return {
            "source_kind": source_kind,
            "target": target,
            "entries": entries,
            "inventory_digest": digest,
        }
    if source_kind == "worktree_overlay":
        current = _verify_worktree_binding(root, binding)
        evidence_paths = _binding_evidence_paths(binding)
        inventory = {
            "source_kind": source_kind,
            "target": target,
            **_worktree_inventory(
                root, cast(str, current["head_oid"]), target, evidence_paths
            ),
        }
        _verify_worktree_binding(root, binding)
        if inventory["overlay_digest"] != binding.get("overlay_digest"):
            raise RuntimeError("The worktree assessment source is stale.")
        return inventory
    raise RuntimeError("The assessment source kind is not valid.")


def guidance_snapshot_manifest(
    repository_root: Path,
    binding: Mapping[str, Any],
    paths: Sequence[str],
) -> list[dict[str, Any]]:
    """Read guidance and architecture files from only the bound source."""
    root = _repository_root(repository_root)
    source_kind = binding.get("source_kind")
    normalized_paths = tuple(normalize_repo_tree_path(path) for path in paths)
    if len(normalized_paths) > MAX_PATH_COUNT:
        raise RuntimeError("The assessment exceeded its path limit.")
    scopes = (
        _target_path(cast(str | None, binding.get("target"))),
        *_binding_evidence_paths(binding),
    )
    if any(not _path_is_in_scope(path, scopes) for path in normalized_paths):
        raise RuntimeError("A guidance path is outside the bound source evidence.")
    if source_kind == "worktree_overlay":
        _verify_worktree_binding(root, binding)
    manifest: list[dict[str, Any]] = []
    total_bytes = 0
    for path in normalized_paths:
        if source_kind == "selected_commit_tree":
            entry = snapshot_file_entry(root, binding, path)
            identity = {
                "commit_oid": binding["commit_oid"],
                "tree_oid": binding["tree_oid"],
            }
        elif source_kind == "worktree_overlay":
            entry = _worktree_snapshot_entry(root, path)
            identity = {
                "head_oid": binding["head_oid"],
                "overlay_digest": binding["overlay_digest"],
            }
        else:
            raise RuntimeError("The assessment source kind is not valid.")
        manifest.append(
            {
                "path": path,
                "source_kind": source_kind,
                **identity,
                "byte_length": len(entry.content),
                "content_sha256": hashlib.sha256(entry.content).hexdigest(),
            }
        )
        total_bytes += len(entry.content)
        if total_bytes > MAX_TOTAL_BYTES:
            raise RuntimeError("The assessment exceeded its aggregate byte limit.")
    if source_kind == "worktree_overlay":
        _verify_worktree_binding(root, binding)
    return manifest


def validation_manifest(
    *,
    available: bool,
    source_digest: str | None = None,
    reason: str | None = None,
    receipts: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Separate static-assessment continuation from repair validation eligibility."""
    copied_receipts = [dict(receipt) for receipt in receipts]
    if not available:
        if not isinstance(reason, str) or not reason.strip():
            raise RuntimeError("Unavailable validation requires a reason.")
        return {
            "status": "unavailable",
            "source_digest": source_digest,
            "reason": reason,
            "receipts": [],
            "static_assessment": {"continue": True},
            "repair_eligibility": False,
        }
    if not isinstance(source_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", source_digest
    ):
        raise RuntimeError("Available validation requires one source digest.")
    required_fields = {
        "source_digest",
        "argv",
        "environment",
        "exit_status",
        "stdout",
        "stderr",
    }
    for receipt in copied_receipts:
        argv = receipt.get("argv")
        environment = receipt.get("environment")
        exit_status = receipt.get("exit_status")
        if (
            not required_fields.issubset(receipt)
            or receipt.get("source_digest") != source_digest
            or not isinstance(argv, list)
            or not argv
            or not all(isinstance(argument, str) and argument for argument in argv)
            or not isinstance(environment, Mapping)
            or not environment
            or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in environment.items()
            )
            or isinstance(exit_status, bool)
            or not isinstance(exit_status, int)
            or not isinstance(receipt.get("stdout"), str)
            or not isinstance(receipt.get("stderr"), str)
        ):
            raise RuntimeError("A validation receipt is incomplete or mismatched.")
    successful = bool(copied_receipts) and all(
        receipt["exit_status"] == 0 for receipt in copied_receipts
    )
    return {
        "status": "available",
        "source_digest": source_digest,
        "reason": None,
        "receipts": copied_receipts,
        "static_assessment": {"continue": True},
        "repair_eligibility": successful,
    }


def _selected_candidates(
    report: Mapping[str, Any], candidate_ids: Sequence[str]
) -> tuple[list[str], list[str], list[Mapping[str, Any]]]:
    """Validate explicit candidate IDs and return their confined paths."""
    if not candidate_ids or len(set(candidate_ids)) != len(candidate_ids):
        raise RuntimeError("Repair candidate IDs must be explicit and unique.")
    if any(
        CANDIDATE_ID.fullmatch(candidate_id) is None for candidate_id in candidate_ids
    ):
        raise RuntimeError("A repair candidate ID is malformed.")
    raw_candidates = report.get("candidates")
    if not isinstance(raw_candidates, list):
        raise TypeError("The assessment report does not contain candidates.")
    if len(raw_candidates) > MAX_PATH_COUNT:
        raise RuntimeError("The assessment exceeded its candidate limit.")
    candidates: dict[str, tuple[list[str], Mapping[str, Any]]] = {}
    candidate_path_count = 0
    source = report.get("source")
    source_digest = source.get("source_digest") if isinstance(source, Mapping) else None
    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, Mapping):
            raise TypeError("The assessment report contains a malformed candidate.")
        candidate_id = raw_candidate.get("id")
        raw_paths = raw_candidate.get("paths")
        dependencies = raw_candidate.get("dependencies")
        evidence = raw_candidate.get("evidence")
        correction = raw_candidate.get("correction")
        route = raw_candidate.get("route")
        if (
            not isinstance(candidate_id, str)
            or CANDIDATE_ID.fullmatch(candidate_id) is None
            or candidate_id in candidates
            or not isinstance(raw_paths, list)
            or not raw_paths
            or not all(isinstance(path, str) for path in raw_paths)
            or route not in {"realign", "simplify"}
            or (
                route == "realign"
                and REALIGN_CANDIDATE_ID.fullmatch(candidate_id) is None
            )
            or raw_candidate.get("status") not in {"open", "resolved"}
            or not isinstance(dependencies, list)
            or not all(isinstance(item, str) for item in dependencies)
            or not isinstance(evidence, list)
            or not evidence
            or not isinstance(correction, Mapping)
            or not correction
        ):
            raise RuntimeError("The assessment report contains a malformed candidate.")
        if route == "simplify" and (
            raw_candidate.get("category") != "simplification"
            or raw_candidate.get("action")
            not in {"delete", "consolidate", "reuse", "simplify"}
            or not isinstance(raw_candidate.get("binding"), Mapping)
            or raw_candidate["binding"].get("source_digest") != source_digest
            or not isinstance(raw_candidate.get("validation"), Mapping)
            or not raw_candidate["validation"]
            or not isinstance(raw_candidate.get("public_interface"), Mapping)
            or raw_candidate["public_interface"].get("published") is not False
            or not isinstance(raw_candidate.get("rollback"), Mapping)
            or not raw_candidate["rollback"]
        ):
            raise RuntimeError(
                "The assessment report contains an incompatible simplify candidate."
            )
        candidate_path_count += len(raw_paths)
        if candidate_path_count > MAX_PATH_COUNT:
            raise RuntimeError("The assessment exceeded its candidate-path limit.")
        if (
            any(CANDIDATE_ID.fullmatch(item) is None for item in dependencies)
            or len(dependencies) != len(set(dependencies))
            or candidate_id in dependencies
        ):
            raise RuntimeError("A repair candidate dependency is malformed.")
        candidates[candidate_id] = (
            [normalize_repo_tree_path(path) for path in raw_paths],
            raw_candidate,
        )
    unknown = [
        candidate_id for candidate_id in candidate_ids if candidate_id not in candidates
    ]
    if unknown:
        raise RuntimeError(f"The repair candidate is unknown: '{unknown[0]}'.")
    selected_set = set(candidate_ids)
    ordered_closure_ids: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(candidate_id: str) -> None:
        if candidate_id in visiting:
            raise RuntimeError("The repair candidate dependency graph is cyclic.")
        if candidate_id in visited:
            return
        visiting.add(candidate_id)
        candidate = candidates[candidate_id][1]
        for dependency in cast(list[str], candidate["dependencies"]):
            dependency_record = candidates.get(dependency)
            if dependency_record is None or (
                dependency not in selected_set
                and dependency_record[1].get("status") != "resolved"
            ):
                raise RuntimeError("A repair candidate dependency is not satisfied.")
            visit(dependency)
        visiting.remove(candidate_id)
        visited.add(candidate_id)
        ordered_closure_ids.append(candidate_id)

    for candidate_id in candidate_ids:
        visit(candidate_id)
    ordered_ids = [
        candidate_id
        for candidate_id in ordered_closure_ids
        if candidate_id in selected_set
    ]
    paths = sorted(
        {path for candidate_id in ordered_ids for path in candidates[candidate_id][0]}
    )
    if len(paths) > MAX_PATH_COUNT:
        raise RuntimeError("The assessment exceeded its path limit.")
    selected = [candidates[candidate_id][1] for candidate_id in ordered_ids]
    if any(candidate.get("status") != "open" for candidate in selected):
        raise RuntimeError("A selected repair candidate is not open.")
    closure = [candidates[candidate_id][1] for candidate_id in ordered_closure_ids]
    return ordered_ids, paths, closure


def _path_is_in_scope(path: str, scopes: Sequence[str]) -> bool:
    """Return whether a path is inside one declared repository-tree scope."""
    return "." in scopes or any(
        path == scope or path.startswith(f"{scope}/") for scope in scopes
    )


def _verify_candidate_evidence(
    repository_root: Path,
    source: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    *,
    deadline: float | None = None,
) -> None:
    """Re-read exact candidate files and verify their recorded content evidence."""
    target = _target_path(cast(str | None, source.get("target")))
    scopes = (target, *_binding_evidence_paths(source))
    source_kind = source.get("source_kind")
    if source_kind == "worktree_overlay":
        _verify_worktree_binding(repository_root, source, deadline=deadline)
    total_bytes = 0
    for candidate in candidates:
        paths = [normalize_repo_tree_path(path) for path in candidate["paths"]]
        if any(not _path_is_in_scope(path, scopes) for path in paths):
            raise RuntimeError("A repair candidate path is outside the assessed scope.")
        raw_evidence = candidate["evidence"]
        if not isinstance(raw_evidence, list):
            raise TypeError("A repair candidate has malformed evidence.")
        evidence: dict[str, str] = {}
        for item in raw_evidence:
            if (
                not isinstance(item, Mapping)
                or not isinstance(item.get("path"), str)
                or not isinstance(item.get("content_sha256"), str)
            ):
                raise TypeError("A repair candidate has malformed evidence.")
            path = normalize_repo_tree_path(cast(str, item["path"]))
            digest = cast(str, item["content_sha256"])
            if path in evidence or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise RuntimeError("A repair candidate has malformed evidence.")
            evidence[path] = digest
        if set(evidence) != set(paths):
            raise RuntimeError("A repair candidate does not bind each affected path.")
        for path in paths:
            if source_kind == "selected_commit_tree":
                content = snapshot_file_entry(
                    repository_root, source, path, deadline=deadline
                ).content
            else:
                content = _worktree_snapshot_entry(
                    repository_root, path, deadline=deadline
                ).content
            total_bytes += len(content)
            if total_bytes > MAX_TOTAL_BYTES:
                raise RuntimeError("The assessment exceeded its aggregate byte limit.")
            if hashlib.sha256(content).hexdigest() != evidence[path]:
                raise RuntimeError("A repair candidate has stale content evidence.")
    if source_kind == "worktree_overlay":
        _verify_worktree_binding(repository_root, source, deadline=deadline)


def _verify_validation_manifest(validation: Any, source_digest: str) -> None:
    """Require complete successful receipts for the exact assessment source."""
    if not isinstance(validation, Mapping):
        raise TypeError("The assessment report is not repair-eligible.")
    receipts = validation.get("receipts")
    if not isinstance(receipts, list):
        raise TypeError("The assessment report is not repair-eligible.")
    rebuilt = validation_manifest(
        available=validation.get("status") == "available",
        source_digest=source_digest,
        reason=cast(str | None, validation.get("reason")),
        receipts=receipts,
    )
    if dict(validation) != rebuilt or not rebuilt["repair_eligibility"]:
        raise RuntimeError("The assessment report is not repair-eligible.")


def _candidate_overlap(
    repository_root: Path,
    paths: Sequence[str],
    *,
    deadline: float | None = None,
) -> bool:
    """Return whether candidate paths overlap mutable checkout state."""
    status = _git_bytes(
        repository_root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        *(f":(top,literal){path}" for path in paths),
        deadline=deadline,
    )
    return bool(status)


def repair_preflight(
    repository_root: Path,
    report: Mapping[str, Any],
    candidate_ids: Sequence[str],
    *,
    approved_report_digest: str | None = None,
    _deadline: float | None = None,
) -> dict[str, Any]:
    """Rebind a report and reject stale evidence or overlapping user work."""
    deadline = (
        time.monotonic() + ASSESSMENT_TIMEOUT_SECONDS
        if _deadline is None
        else _deadline
    )
    root = _repository_root(repository_root, deadline=deadline)
    schema_version = report.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != ASSESSMENT_SCHEMA_VERSION:
        raise RuntimeError("The assessment report schema version is not supported.")
    source = report.get("source")
    if not isinstance(source, Mapping):
        raise TypeError("The assessment report source binding is malformed.")
    if not isinstance(
        approved_report_digest, str
    ) or approved_report_digest != assessment_report_digest(report):
        raise RuntimeError(
            "The approved assessment report binding is missing or stale."
        )
    selected_ids, paths, candidates = _selected_candidates(report, candidate_ids)
    source_digest = source.get("source_digest")
    if not isinstance(source_digest, str):
        raise TypeError("The assessment source digest is malformed.")
    _verify_validation_manifest(report.get("validation"), source_digest)
    source_kind = source.get("source_kind")
    isolated_start: str | None = None
    if source_kind == "selected_commit_tree":
        isolated_start, _ = _verify_selected_binding(root, source, deadline=deadline)
    elif source_kind == "worktree_overlay":
        _verify_worktree_binding(root, source, deadline=deadline)
    else:
        raise RuntimeError("The assessment report source kind is not valid.")
    _verify_candidate_evidence(root, source, candidates, deadline=deadline)
    if _candidate_overlap(root, paths, deadline=deadline):
        raise RuntimeError("A repair candidate path overlaps existing work.")
    return {
        "status": "eligible",
        "source_kind": source_kind,
        "candidate_ids": selected_ids,
        "candidate_paths": paths,
        "isolated_worktree_start_oid": isolated_start,
    }


def _read_report(path: Path, *, deadline: float | None = None) -> Mapping[str, Any]:
    """Read one JSON assessment report."""
    absolute_path = Path(os.path.abspath(os.fspath(path)))
    root = absolute_path.parent
    relative_path = absolute_path.name
    if not relative_path:
        raise RuntimeError("The assessment report path does not name a file.")
    raw_document = _bounded_file_snapshot(
        root,
        relative_path,
        deadline=deadline,
        byte_limit=MAX_FILE_BYTES,
    ).content
    document = json.loads(raw_document.decode("utf-8"))
    if not isinstance(document, Mapping):
        raise TypeError("The assessment report must be a JSON object.")
    return document


def main(argv: Sequence[str] | None = None) -> int:
    """Emit one source binding or verify one repair preflight."""
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    if raw_arguments[:1] == [INTERNAL_FILE_READ_COMMAND]:
        try:
            if len(raw_arguments) != 4:
                raise RuntimeError("The bounded source-file request is malformed.")
            byte_limit = int(raw_arguments[3])
            if byte_limit < 0:
                raise RuntimeError("The bounded source-file limit is not valid.")
            return _internal_read_bound_file(
                Path(raw_arguments[1]), raw_arguments[2], byte_limit
            )
        except (OSError, RuntimeError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    parser = argument_parser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    bind_parser = subparsers.add_parser(
        "bind", help="Bind one read-only assessment source."
    )
    bind_parser.add_argument("target", nargs="?", default=".")
    bind_parser.add_argument("--ref", dest="reference")
    bind_parser.add_argument("--guidance", action="append", default=[], metavar="PATH")
    preflight_parser = subparsers.add_parser(
        "repair-preflight", help="Verify selected repair candidates."
    )
    preflight_parser.add_argument("report", type=Path)
    preflight_parser.add_argument(
        "--candidate", action="append", required=True, dest="candidate_ids"
    )
    preflight_parser.add_argument("--approved-report-digest", required=True)
    arguments = parser.parse_args(raw_arguments)
    try:
        deadline = (
            time.monotonic() + ASSESSMENT_TIMEOUT_SECONDS
            if arguments.command == "repair-preflight"
            else None
        )
        repository_root = Path(
            _git_text(Path.cwd(), "rev-parse", "--show-toplevel", deadline=deadline)
        )
        if arguments.command == "bind":
            source = resolve_source_binding(
                repository_root,
                reference=arguments.reference,
                target=arguments.target,
                evidence_paths=arguments.guidance,
            )
            result = {
                "schema_version": ASSESSMENT_SCHEMA_VERSION,
                "source": source,
                "inventory": inventory_manifest(repository_root, source),
                "guidance": guidance_snapshot_manifest(
                    repository_root, source, arguments.guidance
                ),
                "validation": validation_manifest(
                    available=False,
                    source_digest=source["source_digest"],
                    reason="Validation execution was not requested by this binding command.",
                ),
            }
        else:
            result = repair_preflight(
                repository_root,
                _read_report(arguments.report, deadline=deadline),
                arguments.candidate_ids,
                approved_report_digest=arguments.approved_report_digest,
                _deadline=deadline,
            )
    except (
        OSError,
        RuntimeError,
        TypeError,
        UnicodeError,
        json.JSONDecodeError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
