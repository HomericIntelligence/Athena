#!/usr/bin/env python3
"""Resolve a change-review scope without changing repository or Git state."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from operator import index
from pathlib import Path
from typing import Protocol, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from skills._cli import (
    argument_parser,
    git_read_arguments,
    git_read_environment,
    run_command,
)

READ_CHUNK_SIZE = 1024 * 1024
ERROR_OUTPUT_LIMIT = 16 * 1024
MAX_METADATA_RECORD_BYTES = 128 * 1024
MAX_WORKTREE_CANDIDATES = 50_000


def git_bytes(*arguments: str, repository_root: Path | None = None) -> bytes:
    """Run Git and return its raw stdout or raise a concise error."""
    command = git_command(arguments, repository_root)
    result = run_command(
        command,
        capture_output=True,
        env=git_read_environment(),
        text=False,
        check=False,
    )
    stdout = cast(bytes, result.stdout)
    stderr = cast(bytes, result.stderr)
    if result.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"git {' '.join(arguments)} failed")
    return stdout


def git_text(*arguments: str, repository_root: Path | None = None) -> str:
    """Run Git and decode a single-line textual response."""
    output = git_bytes(*arguments, repository_root=repository_root).decode(
        "utf-8", errors="surrogateescape"
    )
    return output.removesuffix("\n")


def path_list(document: bytes) -> list[str]:
    """Return sorted Git NUL-delimited paths without lossy shell parsing."""
    return sorted(os.fsdecode(path) for path in document.split(b"\0") if path)


@dataclass(frozen=True)
class PathEntry:
    """One no-follow worktree or immutable Git-object manifest entry."""

    path: str
    kind: str
    target: str | None = None
    object_id: str | None = None
    mode: str | None = None


@dataclass(frozen=True)
class ContentFingerprint:
    """Bounded identity for an arbitrarily large byte stream."""

    length: int
    digest: str


@dataclass(frozen=True)
class ScopeCapture:
    """One complete observed scope capture used to detect worktree races."""

    paths: tuple[str, ...]
    tracked_paths: tuple[str, ...]
    untracked_paths: tuple[str, ...]
    path_entries: tuple[PathEntry, ...]
    tracked_diff: ContentFingerprint
    scope_digest: str


def content_fingerprint(chunks: Iterable[bytes]) -> ContentFingerprint:
    """Return a bounded SHA-256 identity for streamed bytes."""
    digest = sha256()
    length = 0
    for chunk in chunks:
        digest.update(chunk)
        length += len(chunk)
    return ContentFingerprint(length=length, digest=digest.hexdigest())


def git_command(arguments: Sequence[str], repository_root: Path | None) -> list[str]:
    """Build one Git command without shell interpolation."""
    command = [
        "git",
        "-c",
        "core.fsmonitor=false",
        *git_read_arguments(),
    ]
    if repository_root is not None:
        command.extend(("-C", os.fspath(repository_root)))
    command.extend(arguments)
    return command


def git_stream_fingerprint(
    *arguments: str, repository_root: Path | None = None
) -> ContentFingerprint:
    """Fingerprint Git output without retaining a complete diff in memory."""
    command = git_command(arguments, repository_root)
    try:
        with tempfile.TemporaryFile() as error_output:
            try:
                process = subprocess.Popen(
                    command,
                    env=git_read_environment(),
                    stdout=subprocess.PIPE,
                    stderr=error_output,
                )
            except FileNotFoundError as error:
                raise RuntimeError(
                    f"required command unavailable: {error.filename or command[0]}"
                ) from error
            try:
                stdout = process.stdout
                if stdout is None:
                    raise RuntimeError("Git did not provide stdout for scope capture")
                try:
                    fingerprint = content_fingerprint(
                        iter(lambda: stdout.read(READ_CHUNK_SIZE), b"")
                    )
                finally:
                    stdout.close()
                return_code = process.wait()
            except BaseException:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                raise
            if return_code != 0:
                error_output.seek(0)
                message = (
                    error_output.read(ERROR_OUTPUT_LIMIT)
                    .decode("utf-8", errors="replace")
                    .strip()
                )
                raise RuntimeError(message or f"git {' '.join(arguments)} failed")
            return fingerprint
    except OSError as error:
        raise RuntimeError(f"cannot stream git output: {error}") from error


def consume_git_nul_records(
    arguments: Sequence[str],
    repository_root: Path,
    consume: Callable[[bytes], None],
) -> None:
    """Pass Git NUL records to a consumer without buffering command output."""
    command = git_command(arguments, repository_root)
    try:
        with tempfile.TemporaryFile() as error_output:
            try:
                process = subprocess.Popen(
                    command,
                    env=git_read_environment(),
                    stdout=subprocess.PIPE,
                    stderr=error_output,
                )
            except FileNotFoundError as error:
                raise RuntimeError(
                    f"required command unavailable: {error.filename or command[0]}"
                ) from error
            stdout = process.stdout
            if stdout is None:
                process.kill()
                process.wait()
                raise RuntimeError("Git did not provide stdout for scope capture")
            pending = b""
            try:
                while chunk := stdout.read(READ_CHUNK_SIZE):
                    pending += chunk
                    records = pending.split(b"\0")
                    pending = records.pop()
                    if len(pending) > MAX_METADATA_RECORD_BYTES:
                        raise RuntimeError(
                            "Git metadata record exceeds the safe scope limit"
                        )
                    for record in records:
                        if record:
                            if len(record) > MAX_METADATA_RECORD_BYTES:
                                raise RuntimeError(
                                    "Git metadata record exceeds the safe scope limit"
                                )
                            consume(record)
                if pending:
                    raise RuntimeError("unterminated Git metadata record")
                return_code = process.wait()
            except BaseException:
                stdout.close()
                if process.poll() is None:
                    process.kill()
                    process.wait()
                raise
            stdout.close()
            if return_code != 0:
                error_output.seek(0)
                message = (
                    error_output.read(ERROR_OUTPUT_LIMIT)
                    .decode("utf-8", errors="replace")
                    .strip()
                )
                raise RuntimeError(message or f"git {' '.join(arguments)} failed")
    except OSError as error:
        raise RuntimeError(f"cannot stream git metadata: {error}") from error


def pathspec_arguments(arguments: list[str], paths: Sequence[str]) -> list[str]:
    """Append repository-rooted literal pathspecs without pathspec injection."""
    literal_paths = [] if "." in paths else [f":(top,literal){path}" for path in paths]
    return [*arguments, "--", *literal_paths]


def normalized_paths(repository_root: Path, paths: Sequence[str]) -> list[str]:
    """Keep lexical filters inside the repository without following symlinks."""
    root = Path(os.path.abspath(os.fspath(repository_root)))
    normalized: list[str] = []
    for raw_path in paths:
        candidate = Path(raw_path)
        absolute_candidate = (
            candidate if candidate.is_absolute() else repository_root / candidate
        )
        resolved = Path(os.path.normpath(os.fspath(absolute_candidate)))
        try:
            relative = resolved.relative_to(root)
        except ValueError as error:
            raise RuntimeError(f"path outside repository: {raw_path!r}") from error
        normalized.append(relative.as_posix())
    return sorted(set(normalized))


def verified_commit(reference: str, repository_root: Path | None = None) -> str:
    """Resolve one non-option Git reference to an immutable commit OID."""
    if not reference or reference.startswith("-"):
        raise RuntimeError(f"invalid Git reference: {reference!r}")
    return git_text(
        "rev-parse",
        "--verify",
        f"{reference}^{{commit}}",
        repository_root=repository_root,
    )


def range_revisions(value: str, repository_root: Path) -> tuple[str, str]:
    """Resolve the required BASE..HEAD notation to immutable commit OIDs."""
    if value.count("..") != 1:
        raise RuntimeError("range must use exactly one BASE..HEAD separator")
    base_reference, head_reference = value.split("..", maxsplit=1)
    return (
        verified_commit(base_reference, repository_root),
        verified_commit(head_reference, repository_root),
    )


def tracked_paths(
    scope: str,
    base: str,
    head: str,
    paths: Sequence[str],
    repository_root: Path,
) -> list[str]:
    """Return the tracked paths selected by the requested scope."""
    if scope == "worktree":
        return list(worktree_tracked_capture(head, paths, repository_root).paths)
    elif scope == "staged":
        arguments = [
            "-c",
            "diff.autoRefreshIndex=false",
            "diff",
            "--cached",
            "--no-ext-diff",
            "--no-textconv",
            "--ignore-submodules=none",
            "--name-only",
            "-z",
            "--no-renames",
            head,
        ]
    else:
        arguments = [
            "-c",
            "diff.autoRefreshIndex=false",
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--ignore-submodules=none",
            "--name-only",
            "-z",
            "--no-renames",
            f"{base}..{head}",
        ]
    return path_list(
        git_bytes(
            *pathspec_arguments(arguments, paths), repository_root=repository_root
        )
    )


def tracked_diff(
    scope: str,
    base: str,
    head: str,
    paths: Sequence[str],
    repository_root: Path,
) -> ContentFingerprint:
    """Fingerprint the selected tracked change without buffering its full diff."""
    if scope == "worktree":
        return worktree_tracked_capture(head, paths, repository_root).fingerprint
    elif scope == "staged":
        arguments = [
            "-c",
            "diff.autoRefreshIndex=false",
            "diff",
            "--cached",
            "--binary",
            "--no-ext-diff",
            "--no-textconv",
            "--ignore-submodules=none",
            "--no-renames",
            head,
        ]
    else:
        arguments = [
            "-c",
            "diff.autoRefreshIndex=false",
            "diff",
            "--binary",
            "--no-ext-diff",
            "--no-textconv",
            "--ignore-submodules=none",
            "--no-renames",
            f"{base}..{head}",
        ]
    return git_stream_fingerprint(
        *pathspec_arguments(arguments, paths), repository_root=repository_root
    )


def untracked_paths(paths: Sequence[str], repository_root: Path) -> list[str]:
    """Return bounded non-ignored untracked paths selected by worktree scope."""
    selected: list[str] = []

    def consume(record: bytes) -> None:
        if len(selected) >= MAX_WORKTREE_CANDIDATES:
            raise RuntimeError(
                "untracked path limit "
                f"({MAX_WORKTREE_CANDIDATES}) reached; rerun with narrower PATH arguments"
            )
        selected.append(os.fsdecode(record))

    consume_git_nul_records(
        pathspec_arguments(["ls-files", "--others", "--exclude-standard", "-z"], paths),
        repository_root,
        consume,
    )
    return sorted(selected)


class Digest(Protocol):
    """Minimal hashlib protocol used by the canonical scope digest."""

    def update(self, data: bytes) -> None:
        """Add bytes to the digest state."""

    def hexdigest(self) -> str:
        """Return the final hexadecimal digest."""


def add_digest_part(digest: Digest, label: bytes, value: bytes) -> None:
    """Frame one digest part so inputs cannot collide by concatenation."""
    digest.update(label)
    digest.update(b"\0")
    digest.update(str(len(value)).encode("ascii"))
    digest.update(b"\0")
    digest.update(value)
    digest.update(b"\0")


def path_components(relative_path: str) -> tuple[str, ...]:
    """Return a verified repository-relative path split into lexical components."""
    components = Path(relative_path).parts
    if not components or any(component in {".", ".."} for component in components):
        raise RuntimeError(f"invalid repository path: {relative_path!r}")
    return components


def close_descriptor_quietly(descriptor: int) -> None:
    """Release a descriptor during error handling without masking its cause."""
    try:
        os.close(descriptor)
    except OSError:
        # Cleanup must not mask the exception that triggered this path.
        pass


def nofollow_parent_descriptor(
    repository_root: Path, relative_path: str
) -> tuple[int, str]:
    """Open a path's parent without following any repository symlink."""
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise RuntimeError(
            "host cannot inspect repository paths without following links"
        )
    components = path_components(relative_path)
    descriptor: int | None = os.open(
        repository_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        for component in components[:-1]:
            assert descriptor is not None
            try:
                child_descriptor = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            except (NotImplementedError, TypeError) as error:
                raise RuntimeError(
                    "host cannot inspect repository paths without following links"
                ) from error
            try:
                os.close(descriptor)
            except OSError:
                # `close()` leaves descriptor state unspecified on error; do not
                # retry the parent descriptor, but never leak the opened child.
                descriptor = None
                close_descriptor_quietly(child_descriptor)
                raise
            descriptor = child_descriptor
    except (OSError, RuntimeError):
        if descriptor is not None:
            close_descriptor_quietly(descriptor)
        raise
    assert descriptor is not None
    return descriptor, components[-1]


def worktree_path_entry(repository_root: Path, relative_path: str) -> PathEntry:
    """Describe a path without following repository or target symlinks."""
    try:
        parent_descriptor, filename = nofollow_parent_descriptor(
            repository_root, relative_path
        )
    except (FileNotFoundError, NotADirectoryError):
        return PathEntry(relative_path, "absent")
    try:
        try:
            mode = os.lstat(filename, dir_fd=parent_descriptor).st_mode
        except (NotImplementedError, TypeError) as error:
            raise RuntimeError(
                "host cannot inspect repository paths without following links"
            ) from error
        except FileNotFoundError:
            return PathEntry(relative_path, "absent")
        if stat.S_ISLNK(mode):
            try:
                target = os.readlink(filename, dir_fd=parent_descriptor)
            except (NotImplementedError, TypeError) as error:
                raise RuntimeError(
                    "host cannot inspect repository links without following them"
                ) from error
            return PathEntry(
                relative_path,
                "symlink",
                target=os.fsdecode(target),
            )
        if stat.S_ISREG(mode):
            return PathEntry(
                relative_path,
                "file",
                mode=f"{stat.S_IMODE(mode):04o}",
            )
        return PathEntry(relative_path, "other")
    finally:
        os.close(parent_descriptor)


def worktree_path_entries(
    repository_root: Path, paths: Sequence[str]
) -> tuple[PathEntry, ...]:
    """Describe every selected repository object without dereferencing links."""
    return tuple(worktree_path_entry(repository_root, path) for path in paths)


def git_object_kind(mode: str, object_type: str) -> str:
    """Classify an immutable Git object without treating a link as a file."""
    if mode == "120000":
        return "git-symlink"
    if mode == "160000" or object_type == "commit":
        return "git-submodule"
    if object_type == "blob":
        return "git-blob"
    return "git-other"


def nul_records(document: bytes) -> list[bytes]:
    """Split a Git NUL-delimited record stream while preserving path bytes."""
    return [record for record in document.split(b"\0") if record]


def index_entry_map(
    paths: Sequence[str], repository_root: Path
) -> dict[str, PathEntry]:
    """Return immutable index-object metadata without reading worktree bytes."""
    arguments = ["ls-files", "--stage", "-z"]
    entries: dict[str, PathEntry] = {}
    for record in nul_records(
        git_bytes(
            *pathspec_arguments(arguments, paths), repository_root=repository_root
        )
    ):
        try:
            header, raw_path = record.split(b"\t", maxsplit=1)
            raw_mode, raw_object_id, raw_stage = header.split()
        except ValueError as error:
            raise RuntimeError(
                "invalid Git index entry while resolving scope"
            ) from error
        path = os.fsdecode(raw_path)
        stage = raw_stage.decode("ascii")
        if stage != "0":
            raise RuntimeError(f"unmerged index entry in selected scope: {path}")
        mode = raw_mode.decode("ascii")
        object_id = raw_object_id.decode("ascii")
        entries[path] = PathEntry(
            path,
            git_object_kind(mode, "commit" if mode == "160000" else "blob"),
            object_id=object_id,
            mode=mode,
        )
    return entries


def index_path_entries(
    paths: Sequence[str], repository_root: Path
) -> tuple[PathEntry, ...]:
    """Return immutable index-object metadata for each selected staged path."""
    if not paths:
        return ()
    entries = index_entry_map(paths, repository_root)
    return tuple(entries.get(path, PathEntry(path, "absent")) for path in paths)


def head_tree_entry_map(
    head: str, paths: Sequence[str], repository_root: Path
) -> dict[str, PathEntry]:
    """Return immutable recursive head-tree metadata for selected paths."""
    arguments = ["ls-tree", "-r", "-z", head]
    entries: dict[str, PathEntry] = {}
    for record in nul_records(
        git_bytes(
            *pathspec_arguments(arguments, paths), repository_root=repository_root
        )
    ):
        try:
            header, raw_path = record.split(b"\t", maxsplit=1)
            raw_mode, raw_type, raw_object_id = header.split()
        except ValueError as error:
            raise RuntimeError(
                "invalid Git tree entry while resolving scope"
            ) from error
        path = os.fsdecode(raw_path)
        mode = raw_mode.decode("ascii")
        object_type = raw_type.decode("ascii")
        entries[path] = PathEntry(
            path,
            git_object_kind(mode, object_type),
            object_id=raw_object_id.decode("ascii"),
            mode=mode,
        )
    return entries


def head_tree_path_entries(
    head: str, paths: Sequence[str], repository_root: Path
) -> tuple[PathEntry, ...]:
    """Return immutable head-tree metadata for each selected range path."""
    if not paths:
        return ()
    entries = head_tree_entry_map(head, paths, repository_root)
    return tuple(entries.get(path, PathEntry(path, "absent")) for path in paths)


@dataclass(frozen=True)
class WorktreeMetadata:
    """Bounded immutable metadata needed to compare raw worktree candidates."""

    head_entries: dict[str, PathEntry]
    index_entries: dict[str, PathEntry]
    skip_worktree_paths: frozenset[str]
    intent_to_add_paths: frozenset[str]


def add_worktree_candidate(candidates: set[str], path: str) -> None:
    """Bound worktree metadata memory before retaining another candidate path."""
    if path in candidates:
        return
    if len(candidates) >= MAX_WORKTREE_CANDIDATES:
        raise RuntimeError(
            "worktree candidate limit "
            f"({MAX_WORKTREE_CANDIDATES}) reached; rerun with narrower PATH arguments"
        )
    candidates.add(path)


def parse_head_tree_record(record: bytes) -> PathEntry:
    """Decode one streamed `git ls-tree -z` record."""
    try:
        header, raw_path = record.split(b"\t", maxsplit=1)
        raw_mode, raw_type, raw_object_id = header.split()
    except ValueError as error:
        raise RuntimeError("invalid Git tree entry while resolving scope") from error
    path = os.fsdecode(raw_path)
    mode = raw_mode.decode("ascii")
    object_type = raw_type.decode("ascii")
    return PathEntry(
        path,
        git_object_kind(mode, object_type),
        object_id=raw_object_id.decode("ascii"),
        mode=mode,
    )


def parse_tagged_index_record(record: bytes) -> tuple[PathEntry, bool]:
    """Decode one streamed `git ls-files --stage -t -z` record."""
    try:
        raw_tag, raw_entry = record.split(b" ", maxsplit=1)
        header, raw_path = raw_entry.split(b"\t", maxsplit=1)
        raw_mode, raw_object_id, raw_stage = header.split()
    except ValueError as error:
        raise RuntimeError("invalid Git index entry while resolving scope") from error
    path = os.fsdecode(raw_path)
    stage = raw_stage.decode("ascii")
    if stage != "0":
        raise RuntimeError(f"unmerged index entry in selected scope: {path}")
    mode = raw_mode.decode("ascii")
    return (
        PathEntry(
            path,
            git_object_kind(mode, "commit" if mode == "160000" else "blob"),
            object_id=raw_object_id.decode("ascii"),
            mode=mode,
        ),
        raw_tag == b"S",
    )


def worktree_metadata(
    head: str, paths: Sequence[str], repository_root: Path
) -> WorktreeMetadata:
    """Stream bounded HEAD/index metadata without reading worktree bytes."""
    candidates: set[str] = set()
    head_entries: dict[str, PathEntry] = {}
    index_entries: dict[str, PathEntry] = {}
    skip_worktree_paths: set[str] = set()
    staged_change_paths: set[str] = set()

    def consume_head(record: bytes) -> None:
        entry = parse_head_tree_record(record)
        add_worktree_candidate(candidates, entry.path)
        head_entries[entry.path] = entry

    def consume_index(record: bytes) -> None:
        entry, skip_worktree = parse_tagged_index_record(record)
        add_worktree_candidate(candidates, entry.path)
        index_entries[entry.path] = entry
        if skip_worktree:
            skip_worktree_paths.add(entry.path)

    def consume_staged_change(record: bytes) -> None:
        path = os.fsdecode(record)
        if path not in candidates:
            raise RuntimeError(
                f"staged change path was missing from worktree scope metadata: {path}"
            )
        staged_change_paths.add(path)

    consume_git_nul_records(
        pathspec_arguments(["ls-tree", "-r", "-z", head], paths),
        repository_root,
        consume_head,
    )
    consume_git_nul_records(
        pathspec_arguments(["ls-files", "--stage", "-t", "-z"], paths),
        repository_root,
        consume_index,
    )
    consume_git_nul_records(
        pathspec_arguments(
            [
                "-c",
                "diff.autoRefreshIndex=false",
                "diff",
                "--cached",
                "--no-ext-diff",
                "--no-textconv",
                "--ignore-submodules=none",
                "--name-only",
                "-z",
                "--no-renames",
                "--ita-invisible-in-index",
                head,
            ],
            paths,
        ),
        repository_root,
        consume_staged_change,
    )
    intent_to_add_paths = frozenset(
        path
        for path in index_entries
        if path not in head_entries and path not in staged_change_paths
    )
    return WorktreeMetadata(
        head_entries=head_entries,
        index_entries=index_entries,
        skip_worktree_paths=frozenset(skip_worktree_paths),
        intent_to_add_paths=intent_to_add_paths,
    )


@dataclass(frozen=True)
class FileSnapshot:
    """A regular file's streamed content identity and optional Git blob OID."""

    fingerprint: ContentFingerprint
    object_id: str | None
    mode: str


@dataclass(frozen=True)
class WorktreePathSnapshot:
    """No-follow worktree metadata plus raw content identity where applicable."""

    entry: PathEntry
    content: ContentFingerprint | None = None
    object_id: str | None = None


@dataclass(frozen=True)
class WorktreeTrackedCapture:
    """One bounded representation of all worktree changes relative to HEAD."""

    paths: tuple[str, ...]
    fingerprint: ContentFingerprint


def git_object_format(repository_root: Path) -> str:
    """Return a supported Git object hash format before hashing raw blobs."""
    object_format = git_text(
        "rev-parse", "--show-object-format", repository_root=repository_root
    )
    try:
        hashlib.new(object_format)
    except ValueError as error:
        raise RuntimeError(
            f"unsupported Git object format for worktree review: {object_format}"
        ) from error
    return object_format


def git_blob_object_id(contents: bytes, object_format: str) -> str:
    """Return the Git blob object ID for already-bounded bytes such as a link target."""
    digest = hashlib.new(object_format)
    digest.update(f"blob {len(contents)}\0".encode("ascii"))
    digest.update(contents)
    return digest.hexdigest()


def stable_file_stat(before: os.stat_result, after: os.stat_result) -> bool:
    """Report whether a file descriptor retained its immutable read identity."""
    return (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) == (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )


def read_regular_file_snapshot_without_following(
    repository_root: Path,
    relative_path: str,
    object_format: str | None = None,
) -> FileSnapshot:
    """Fingerprint a regular file without following links or blocking on a FIFO."""
    nonblocking_value = getattr(os, "O_NONBLOCK", None)
    try:
        if nonblocking_value is None:
            raise TypeError
        nonblocking_flag = index(nonblocking_value)
    except TypeError as error:
        raise RuntimeError(
            "host cannot inspect repository files without nonblocking open support"
        ) from error
    parent_descriptor, filename = nofollow_parent_descriptor(
        repository_root, relative_path
    )
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(
                filename,
                os.O_RDONLY | os.O_NOFOLLOW | nonblocking_flag,
                dir_fd=parent_descriptor,
            )
        except (NotImplementedError, TypeError) as error:
            raise RuntimeError(
                "host cannot inspect repository paths without following links"
            ) from error
    finally:
        try:
            os.close(parent_descriptor)
        except OSError:
            if descriptor is not None:
                close_descriptor_quietly(descriptor)
            raise
    assert descriptor is not None
    try:
        initial_stat = os.fstat(descriptor)
        if not stat.S_ISREG(initial_stat.st_mode):
            raise RuntimeError(f"untracked path is not a regular file: {relative_path}")
        content_digest = sha256()
        object_digest = (
            hashlib.new(object_format) if object_format is not None else None
        )
        if object_digest is not None:
            object_digest.update(f"blob {initial_stat.st_size}\0".encode("ascii"))
        content_length = 0
        while chunk := os.read(descriptor, READ_CHUNK_SIZE):
            content_digest.update(chunk)
            if object_digest is not None:
                object_digest.update(chunk)
            content_length += len(chunk)
        final_stat = os.fstat(descriptor)
        if content_length != initial_stat.st_size or not stable_file_stat(
            initial_stat, final_stat
        ):
            raise RuntimeError(
                f"repository file changed while resolving scope: {relative_path}"
            )
        return FileSnapshot(
            fingerprint=ContentFingerprint(
                length=content_length, digest=content_digest.hexdigest()
            ),
            object_id=object_digest.hexdigest() if object_digest is not None else None,
            mode=f"{stat.S_IMODE(final_stat.st_mode):04o}",
        )
    finally:
        os.close(descriptor)


def read_regular_file_without_following(
    repository_root: Path, relative_path: str
) -> ContentFingerprint:
    """Return a bounded content identity for a regular no-follow repository file."""
    return read_regular_file_snapshot_without_following(
        repository_root, relative_path
    ).fingerprint


def worktree_path_snapshot(
    repository_root: Path, relative_path: str, object_format: str
) -> WorktreePathSnapshot:
    """Capture raw worktree state without asking Git to convert a worktree file."""
    entry = worktree_path_entry(repository_root, relative_path)
    if entry.kind == "file":
        snapshot = read_regular_file_snapshot_without_following(
            repository_root, relative_path, object_format
        )
        return WorktreePathSnapshot(
            entry=PathEntry(entry.path, "file", mode=snapshot.mode),
            content=snapshot.fingerprint,
            object_id=snapshot.object_id,
        )
    if entry.kind == "symlink":
        if entry.target is None:
            raise RuntimeError(
                f"repository link changed while resolving scope: {relative_path}"
            )
        contents = os.fsencode(entry.target)
        return WorktreePathSnapshot(
            entry=entry,
            content=content_fingerprint((contents,)),
            object_id=git_blob_object_id(contents, object_format),
        )
    return WorktreePathSnapshot(entry=entry)


def git_mode_for_worktree_file(entry: PathEntry) -> str:
    """Map a regular filesystem mode to Git's executable-bit-only mode."""
    if entry.kind != "file" or entry.mode is None:
        raise RuntimeError(f"invalid worktree file entry: {entry.path}")
    return "100755" if int(entry.mode, 8) & 0o111 else "100644"


def worktree_matches_entry(
    snapshot: WorktreePathSnapshot, tree_entry: PathEntry | None
) -> bool:
    """Compare raw no-follow worktree state to one immutable tree entry."""
    if tree_entry is None:
        return snapshot.entry.kind == "absent"
    if tree_entry.kind == "git-blob":
        return (
            snapshot.entry.kind == "file"
            and snapshot.object_id == tree_entry.object_id
            and git_mode_for_worktree_file(snapshot.entry) == tree_entry.mode
        )
    if tree_entry.kind == "git-symlink":
        return (
            snapshot.entry.kind == "symlink"
            and snapshot.object_id == tree_entry.object_id
            and tree_entry.mode == "120000"
        )
    raise RuntimeError(
        f"worktree scope cannot safely compare Git object kind for {tree_entry.path}"
    )


def add_content_fingerprint(
    digest: Digest, label: bytes, fingerprint: ContentFingerprint
) -> None:
    """Frame a stream identity without retaining its original bytes."""
    add_digest_part(digest, label + b"-length", str(fingerprint.length).encode("ascii"))
    add_digest_part(digest, label + b"-sha256", fingerprint.digest.encode("ascii"))


def add_worktree_snapshot(digest: Digest, snapshot: WorktreePathSnapshot) -> None:
    """Bind raw worktree metadata and content to a tracked-capture digest."""
    entry = snapshot.entry
    add_digest_part(digest, b"path", os.fsencode(entry.path))
    add_digest_part(digest, b"kind", entry.kind.encode("ascii"))
    if entry.target is not None:
        add_digest_part(digest, b"target", os.fsencode(entry.target))
    if entry.mode is not None:
        add_digest_part(digest, b"mode", entry.mode.encode("ascii"))
    if snapshot.object_id is not None:
        add_digest_part(digest, b"object-id", snapshot.object_id.encode("ascii"))
    if snapshot.content is not None:
        add_content_fingerprint(digest, b"content", snapshot.content)


def worktree_tracked_capture(
    head: str, paths: Sequence[str], repository_root: Path
) -> WorktreeTrackedCapture:
    """Compare raw worktree state to HEAD without invoking Git diff filters."""
    object_format = git_object_format(repository_root)
    metadata = worktree_metadata(head, paths, repository_root)
    candidates = sorted(set(metadata.head_entries).union(metadata.index_entries))
    digest = sha256()
    add_digest_part(digest, b"schema", b"athena-change-review-worktree-v1")
    add_digest_part(digest, b"object-format", object_format.encode("ascii"))
    selected_paths: list[str] = []
    content_length = 0
    for path in candidates:
        snapshot = worktree_path_snapshot(repository_root, path, object_format)
        head_entry = metadata.head_entries.get(path)
        index_entry = metadata.index_entries.get(path)
        if (
            head_entry is not None
            and head_entry.kind == "git-submodule"
            or index_entry is not None
            and index_entry.kind == "git-submodule"
        ):
            raise RuntimeError(
                "worktree scope cannot safely determine submodule state for "
                f"{path}; use --staged or --range"
            )
        index_differs_from_head = index_entry != head_entry
        if path in metadata.skip_worktree_paths and snapshot.entry.kind == "absent":
            if index_differs_from_head:
                raise RuntimeError(
                    "worktree scope cannot safely inspect staged change in "
                    f"skip-worktree path {path}; use --staged"
                )
            continue
        if (
            index_differs_from_head
            and path not in metadata.intent_to_add_paths
            and not worktree_matches_entry(snapshot, index_entry)
        ):
            raise RuntimeError(
                "worktree scope cannot safely inspect staged change whose live "
                f"bytes differ from the index for {path}; use --staged"
            )
        if worktree_matches_entry(snapshot, head_entry):
            continue
        selected_paths.append(path)
        add_worktree_snapshot(digest, snapshot)
        if snapshot.content is not None:
            content_length += snapshot.content.length
    return WorktreeTrackedCapture(
        paths=tuple(selected_paths),
        fingerprint=ContentFingerprint(
            length=content_length, digest=digest.hexdigest()
        ),
    )


def untracked_content(
    repository_root: Path, relative_path: str
) -> tuple[bytes, ContentFingerprint]:
    """Return a bounded no-follow content representation for an untracked path."""
    entry = worktree_path_entry(repository_root, relative_path)
    if entry.kind == "symlink":
        if entry.target is None:
            raise RuntimeError(
                f"untracked link changed while resolving scope: {relative_path}"
            )
        return b"symlink", content_fingerprint((os.fsencode(entry.target),))
    if entry.kind == "file":
        return b"file", read_regular_file_without_following(
            repository_root, relative_path
        )
    raise RuntimeError(f"untracked path changed while resolving scope: {relative_path}")


def scope_digest(
    scope: str,
    base: str,
    head: str,
    paths: Sequence[str],
    tracked: ContentFingerprint,
    repository_root: Path,
    entries: Sequence[PathEntry],
    untracked: Sequence[str],
) -> str:
    """Bind the selected manifest, tracked diff, and untracked contents to SHA-256."""
    digest = sha256()
    add_digest_part(digest, b"schema", b"athena-change-review-scope-v3")
    add_digest_part(digest, b"scope", scope.encode("utf-8"))
    add_digest_part(digest, b"base", base.encode("ascii"))
    add_digest_part(digest, b"head", head.encode("ascii"))
    for path in paths:
        add_digest_part(digest, b"path", os.fsencode(path))
    add_content_fingerprint(digest, b"tracked-diff", tracked)
    for entry in entries:
        add_digest_part(digest, b"entry-path", os.fsencode(entry.path))
        add_digest_part(digest, b"entry-kind", entry.kind.encode("ascii"))
        if entry.target is not None:
            add_digest_part(digest, b"entry-target", os.fsencode(entry.target))
        if entry.object_id is not None:
            add_digest_part(digest, b"entry-object-id", entry.object_id.encode("ascii"))
        if entry.mode is not None:
            add_digest_part(digest, b"entry-mode", entry.mode.encode("ascii"))
    for path in untracked:
        kind, content = untracked_content(repository_root, path)
        add_digest_part(digest, b"untracked-path", os.fsencode(path))
        add_digest_part(digest, b"untracked-kind", kind)
        add_content_fingerprint(digest, b"untracked-content", content)
    return digest.hexdigest()


def capture_scope(
    scope: str,
    base: str,
    head: str,
    paths: Sequence[str],
    repository_root: Path,
) -> ScopeCapture:
    """Capture one complete scope observation for a later stability comparison."""
    if scope == "worktree":
        tracked_capture = worktree_tracked_capture(head, paths, repository_root)
        selected_tracked_paths = list(tracked_capture.paths)
        tracked = tracked_capture.fingerprint
    else:
        selected_tracked_paths = tracked_paths(
            scope, base, head, paths, repository_root
        )
        tracked = tracked_diff(scope, base, head, paths, repository_root)
    selected_untracked_paths = (
        untracked_paths(paths, repository_root) if scope == "worktree" else []
    )
    all_paths = sorted(set(selected_tracked_paths).union(selected_untracked_paths))
    if scope == "worktree":
        entries = worktree_path_entries(repository_root, all_paths)
    elif scope == "staged":
        entries = index_path_entries(all_paths, repository_root)
    else:
        entries = head_tree_path_entries(head, all_paths, repository_root)
    return ScopeCapture(
        paths=tuple(all_paths),
        tracked_paths=tuple(selected_tracked_paths),
        untracked_paths=tuple(selected_untracked_paths),
        path_entries=entries,
        tracked_diff=tracked,
        scope_digest=scope_digest(
            scope,
            base,
            head,
            all_paths,
            tracked,
            repository_root,
            entries,
            selected_untracked_paths,
        ),
    )


def entry_documents(entries: Sequence[PathEntry]) -> list[dict[str, str]]:
    """Render no-follow path metadata for the JSON scope manifest."""
    documents: list[dict[str, str]] = []
    for entry in entries:
        document = {"kind": entry.kind, "path": entry.path}
        if entry.target is not None:
            document["target"] = entry.target
        if entry.object_id is not None:
            document["object_id"] = entry.object_id
        if entry.mode is not None:
            document["mode"] = entry.mode
        documents.append(document)
    return documents


def resolve_scope(
    scope: str, range_value: str | None, selected_paths: Sequence[str]
) -> dict[str, object]:
    """Resolve the selected paths and content identity for one review scope."""
    repository_root = Path(git_text("rev-parse", "--show-toplevel")).resolve()
    paths = normalized_paths(repository_root, selected_paths)
    if scope == "range":
        if range_value is None:
            raise RuntimeError("range scope requires BASE..HEAD")
        base, head = range_revisions(range_value, repository_root)
    else:
        head = verified_commit("HEAD", repository_root)
        base = head

    first_capture = capture_scope(scope, base, head, paths, repository_root)
    second_capture = capture_scope(scope, base, head, paths, repository_root)
    if first_capture != second_capture:
        raise RuntimeError("change scope changed while resolving; retry the review")
    if scope != "range" and verified_commit("HEAD", repository_root) != head:
        raise RuntimeError("HEAD changed while resolving; retry the review")
    return {
        "base": base,
        "content_source": (
            "worktree"
            if scope == "worktree"
            else "index"
            if scope == "staged"
            else "head-tree"
        ),
        "head": head,
        "path_entries": entry_documents(second_capture.path_entries),
        "paths": list(second_capture.paths),
        "scope": scope,
        "scope_digest": second_capture.scope_digest,
        "tracked_paths": list(second_capture.tracked_paths),
        "untracked_paths": list(second_capture.untracked_paths),
        "untracked_scope": "included" if scope == "worktree" else "excluded",
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the requested review scope and return its JSON manifest."""
    parser = argument_parser(description=__doc__)
    scope_group = parser.add_mutually_exclusive_group()
    scope_group.add_argument("--worktree", action="store_true")
    scope_group.add_argument("--staged", action="store_true")
    scope_group.add_argument("--range", dest="range_value", metavar="BASE..HEAD")
    parser.add_argument("paths", metavar="PATH", nargs="*")
    arguments = parser.parse_args(argv)
    scope = (
        "range"
        if arguments.range_value is not None
        else "staged"
        if arguments.staged
        else "worktree"
    )
    try:
        print(
            json.dumps(
                resolve_scope(scope, arguments.range_value, arguments.paths),
                sort_keys=True,
            )
        )
    except (OSError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
