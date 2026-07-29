#!/usr/bin/env python3
"""Resolve a change-review scope without changing repository or Git state."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Protocol, Sequence, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from skills._cli import argument_parser, run_command


def git_bytes(*arguments: str) -> bytes:
    """Run Git and return its raw stdout or raise a concise error."""
    result = run_command(
        ["git", *arguments], capture_output=True, text=False, check=False
    )
    stdout = cast(bytes, result.stdout)
    stderr = cast(bytes, result.stderr)
    if result.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"git {' '.join(arguments)} failed")
    return stdout


def git_text(*arguments: str) -> str:
    """Run Git and decode a single-line textual response."""
    return git_bytes(*arguments).decode("utf-8", errors="surrogateescape").strip()


def path_list(document: bytes) -> list[str]:
    """Return sorted Git NUL-delimited paths without lossy shell parsing."""
    return sorted(os.fsdecode(path) for path in document.split(b"\0") if path)


def pathspec_arguments(arguments: list[str], paths: Sequence[str]) -> list[str]:
    """Append a safe Git pathspec separator and normalized selected paths."""
    literal_paths = [] if "." in paths else [f":(literal){path}" for path in paths]
    return [*arguments, "--", *literal_paths]


def normalized_paths(repository_root: Path, paths: Sequence[str]) -> list[str]:
    """Require requested path filters to remain inside the repository root."""
    root = repository_root.resolve()
    normalized: list[str] = []
    for raw_path in paths:
        candidate = Path(raw_path)
        resolved = (
            candidate if candidate.is_absolute() else repository_root / candidate
        ).resolve(strict=False)
        try:
            relative = resolved.relative_to(root)
        except ValueError as error:
            raise RuntimeError(f"path outside repository: {raw_path!r}") from error
        normalized.append(relative.as_posix())
    return sorted(set(normalized))


def verified_commit(reference: str) -> str:
    """Resolve one non-option Git reference to an immutable commit OID."""
    if not reference or reference.startswith("-"):
        raise RuntimeError(f"invalid Git reference: {reference!r}")
    return git_text("rev-parse", "--verify", f"{reference}^{{commit}}")


def range_revisions(value: str) -> tuple[str, str]:
    """Resolve the required BASE..HEAD notation to immutable commit OIDs."""
    if value.count("..") != 1:
        raise RuntimeError("range must use exactly one BASE..HEAD separator")
    base_reference, head_reference = value.split("..", maxsplit=1)
    return verified_commit(base_reference), verified_commit(head_reference)


def tracked_paths(scope: str, base: str, head: str, paths: Sequence[str]) -> list[str]:
    """Return the tracked paths selected by the requested scope."""
    if scope == "worktree":
        arguments = ["diff", "--name-only", "-z", "--no-renames", "HEAD"]
    elif scope == "staged":
        arguments = [
            "diff",
            "--cached",
            "--name-only",
            "-z",
            "--no-renames",
            "HEAD",
        ]
    else:
        arguments = [
            "diff",
            "--name-only",
            "-z",
            "--no-renames",
            f"{base}..{head}",
        ]
    return path_list(git_bytes(*pathspec_arguments(arguments, paths)))


def tracked_diff(scope: str, base: str, head: str, paths: Sequence[str]) -> bytes:
    """Return the exact binary-safe tracked diff selected by the scope."""
    if scope == "worktree":
        arguments = ["diff", "--binary", "--no-ext-diff", "HEAD"]
    elif scope == "staged":
        arguments = ["diff", "--cached", "--binary", "--no-ext-diff", "HEAD"]
    else:
        arguments = ["diff", "--binary", "--no-ext-diff", f"{base}..{head}"]
    return git_bytes(*pathspec_arguments(arguments, paths))


def untracked_paths(paths: Sequence[str]) -> list[str]:
    """Return non-ignored untracked paths selected by the default scope."""
    arguments = ["ls-files", "--others", "--exclude-standard", "-z"]
    return path_list(git_bytes(*pathspec_arguments(arguments, paths)))


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


def untracked_content(repository_root: Path, relative_path: str) -> tuple[bytes, bytes]:
    """Return a non-following content representation for an untracked path."""
    path = repository_root / relative_path
    if path.is_symlink():
        return b"symlink", os.fsencode(os.readlink(path))
    if path.is_file():
        return b"file", path.read_bytes()
    raise RuntimeError(f"untracked path changed while resolving scope: {relative_path}")


def scope_digest(
    scope: str,
    base: str,
    head: str,
    paths: Sequence[str],
    tracked: bytes,
    repository_root: Path,
    untracked: Sequence[str],
) -> str:
    """Bind the selected manifest, tracked diff, and untracked contents to SHA-256."""
    digest = sha256()
    add_digest_part(digest, b"schema", b"athena-change-review-scope-v1")
    add_digest_part(digest, b"scope", scope.encode("utf-8"))
    add_digest_part(digest, b"base", base.encode("ascii"))
    add_digest_part(digest, b"head", head.encode("ascii"))
    for path in paths:
        add_digest_part(digest, b"path", os.fsencode(path))
    add_digest_part(digest, b"tracked-diff", tracked)
    for path in untracked:
        kind, content = untracked_content(repository_root, path)
        add_digest_part(digest, b"untracked-path", os.fsencode(path))
        add_digest_part(digest, b"untracked-kind", kind)
        add_digest_part(digest, b"untracked-content", content)
    return digest.hexdigest()


def resolve_scope(
    scope: str, range_value: str | None, selected_paths: Sequence[str]
) -> dict[str, object]:
    """Resolve the selected paths and content identity for one review scope."""
    repository_root = Path(git_text("rev-parse", "--show-toplevel")).resolve()
    paths = normalized_paths(repository_root, selected_paths)
    if scope == "range":
        if range_value is None:
            raise RuntimeError("range scope requires BASE..HEAD")
        base, head = range_revisions(range_value)
    else:
        head = verified_commit("HEAD")
        base = head

    selected_tracked_paths = tracked_paths(scope, base, head, paths)
    selected_untracked_paths = untracked_paths(paths) if scope == "worktree" else []
    all_paths = sorted(set(selected_tracked_paths).union(selected_untracked_paths))
    digest = scope_digest(
        scope,
        base,
        head,
        all_paths,
        tracked_diff(scope, base, head, paths),
        repository_root,
        selected_untracked_paths,
    )
    return {
        "base": base,
        "head": head,
        "paths": all_paths,
        "scope": scope,
        "scope_digest": digest,
        "tracked_paths": selected_tracked_paths,
        "untracked_paths": selected_untracked_paths,
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
