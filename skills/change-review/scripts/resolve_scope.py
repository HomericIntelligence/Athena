#!/usr/bin/env python3
"""Resolve a change-review scope without changing repository or Git state."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
from typing import Protocol, Sequence, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from skills._cli import argument_parser, run_command


def git_bytes(*arguments: str, repository_root: Path | None = None) -> bytes:
    """Run Git and return its raw stdout or raise a concise error."""
    command = ["git"]
    if repository_root is not None:
        command.extend(("-C", os.fspath(repository_root)))
    command.extend(arguments)
    result = run_command(command, capture_output=True, text=False, check=False)
    stdout = cast(bytes, result.stdout)
    stderr = cast(bytes, result.stderr)
    if result.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"git {' '.join(arguments)} failed")
    return stdout


def git_text(*arguments: str, repository_root: Path | None = None) -> str:
    """Run Git and decode a single-line textual response."""
    return (
        git_bytes(*arguments, repository_root=repository_root)
        .decode("utf-8", errors="surrogateescape")
        .strip()
    )


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
class ScopeCapture:
    """One complete observed scope capture used to detect worktree races."""

    paths: tuple[str, ...]
    tracked_paths: tuple[str, ...]
    untracked_paths: tuple[str, ...]
    path_entries: tuple[PathEntry, ...]
    tracked_diff: bytes
    scope_digest: str


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
            head,
        ]
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
) -> bytes:
    """Return the exact binary-safe tracked diff selected by the scope."""
    if scope == "worktree":
        arguments = [
            "-c",
            "diff.autoRefreshIndex=false",
            "diff",
            "--binary",
            "--no-ext-diff",
            "--no-textconv",
            "--ignore-submodules=none",
            "--no-renames",
            head,
        ]
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
    return git_bytes(
        *pathspec_arguments(arguments, paths), repository_root=repository_root
    )


def untracked_paths(paths: Sequence[str], repository_root: Path) -> list[str]:
    """Return non-ignored untracked paths selected by the default scope."""
    arguments = ["ls-files", "--others", "--exclude-standard", "-z"]
    return path_list(
        git_bytes(
            *pathspec_arguments(arguments, paths), repository_root=repository_root
        )
    )


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


def nofollow_parent_descriptor(
    repository_root: Path, relative_path: str
) -> tuple[int, str]:
    """Open a path's parent without following any repository symlink."""
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise RuntimeError(
            "host cannot inspect repository paths without following links"
        )
    components = path_components(relative_path)
    descriptor = os.open(
        repository_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        for component in components[:-1]:
            child_descriptor = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child_descriptor
    except OSError:
        os.close(descriptor)
        raise
    return descriptor, components[-1]


def worktree_path_entry(repository_root: Path, relative_path: str) -> PathEntry:
    """Describe a path without following repository or target symlinks."""
    if os.lstat not in os.supports_dir_fd:
        raise RuntimeError(
            "host cannot inspect repository paths without following links"
        )
    try:
        parent_descriptor, filename = nofollow_parent_descriptor(
            repository_root, relative_path
        )
    except (FileNotFoundError, NotADirectoryError):
        return PathEntry(relative_path, "absent")
    try:
        try:
            mode = os.lstat(filename, dir_fd=parent_descriptor).st_mode
        except FileNotFoundError:
            return PathEntry(relative_path, "absent")
        if stat.S_ISLNK(mode):
            if os.readlink not in os.supports_dir_fd:
                raise RuntimeError(
                    "host cannot inspect repository links without following them"
                )
            return PathEntry(
                relative_path,
                "symlink",
                target=os.fsdecode(os.readlink(filename, dir_fd=parent_descriptor)),
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


def index_path_entries(
    paths: Sequence[str], repository_root: Path
) -> tuple[PathEntry, ...]:
    """Return immutable index-object metadata for each selected staged path."""
    if not paths:
        return ()
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
    return tuple(entries.get(path, PathEntry(path, "absent")) for path in paths)


def head_tree_path_entries(
    head: str, paths: Sequence[str], repository_root: Path
) -> tuple[PathEntry, ...]:
    """Return immutable head-tree metadata for each selected range path."""
    if not paths:
        return ()
    arguments = ["ls-tree", "-z", head]
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
    return tuple(entries.get(path, PathEntry(path, "absent")) for path in paths)


def read_regular_file_without_following(
    repository_root: Path, relative_path: str
) -> bytes:
    """Read a regular repository file through no-follow directory descriptors."""
    parent_descriptor, filename = nofollow_parent_descriptor(
        repository_root, relative_path
    )
    try:
        descriptor = os.open(
            filename,
            os.O_RDONLY | os.O_NOFOLLOW,
            dir_fd=parent_descriptor,
        )
    finally:
        os.close(parent_descriptor)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise RuntimeError(f"untracked path is not a regular file: {relative_path}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def untracked_content(repository_root: Path, relative_path: str) -> tuple[bytes, bytes]:
    """Return a non-following content representation for an untracked path."""
    entry = worktree_path_entry(repository_root, relative_path)
    if entry.kind == "symlink":
        if entry.target is None:
            raise RuntimeError(
                f"untracked link changed while resolving scope: {relative_path}"
            )
        return b"symlink", os.fsencode(entry.target)
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
    tracked: bytes,
    repository_root: Path,
    entries: Sequence[PathEntry],
    untracked: Sequence[str],
) -> str:
    """Bind the selected manifest, tracked diff, and untracked contents to SHA-256."""
    digest = sha256()
    add_digest_part(digest, b"schema", b"athena-change-review-scope-v2")
    add_digest_part(digest, b"scope", scope.encode("utf-8"))
    add_digest_part(digest, b"base", base.encode("ascii"))
    add_digest_part(digest, b"head", head.encode("ascii"))
    for path in paths:
        add_digest_part(digest, b"path", os.fsencode(path))
    add_digest_part(digest, b"tracked-diff", tracked)
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
        add_digest_part(digest, b"untracked-content", content)
    return digest.hexdigest()


def capture_scope(
    scope: str,
    base: str,
    head: str,
    paths: Sequence[str],
    repository_root: Path,
) -> ScopeCapture:
    """Capture one complete scope observation for a later stability comparison."""
    selected_tracked_paths = tracked_paths(scope, base, head, paths, repository_root)
    selected_untracked_paths = (
        untracked_paths(paths, repository_root) if scope == "worktree" else []
    )
    all_paths = sorted(set(selected_tracked_paths).union(selected_untracked_paths))
    tracked = tracked_diff(scope, base, head, paths, repository_root)
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
