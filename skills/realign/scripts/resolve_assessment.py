#!/usr/bin/env python3
"""Bind a realign assessment to one selected commit or worktree overlay."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any, cast

if __package__ not in {None, ""}:
    from skills._cli import (
        argument_parser,
        git_read_arguments,
        git_read_environment,
        run_command,
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
    run_command = _cli.run_command


SELECTOR_FORBIDDEN = ("..", "^@", "^!", "@{", ":")
CANDIDATE_ID = re.compile(r"RLG-[0-9]{3}\Z")


@dataclass(frozen=True)
class SnapshotFileEntry:
    """One regular file read from an explicitly bound source."""

    path: str
    source_kind: str
    content: bytes
    object_id: str | None = None
    mode: str | None = None


def _git_bytes(repository_root: Path, *arguments: str) -> bytes:
    """Run one sanitized read-only Git command and return raw output."""
    result = run_command(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            *git_read_arguments(),
            "-C",
            os.fspath(repository_root),
            *arguments,
        ],
        capture_output=True,
        env=git_read_environment(),
        text=False,
        check=False,
    )
    stdout = cast(bytes, result.stdout)
    stderr = cast(bytes, result.stderr)
    if result.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or "The read-only Git command failed.")
    return stdout


def _git_text(repository_root: Path, *arguments: str) -> str:
    """Run one sanitized Git command and return one textual value."""
    return (
        _git_bytes(repository_root, *arguments)
        .decode("utf-8", errors="surrogateescape")
        .removesuffix("\n")
    )


def _repository_root(repository_root: Path) -> Path:
    """Return and verify the canonical repository root."""
    root = Path(os.path.realpath(os.fspath(repository_root)))
    observed = Path(_git_text(root, "rev-parse", "--show-toplevel"))
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


def _selected_commit(repository_root: Path, selector: str) -> str:
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
    )
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit_oid):
        raise RuntimeError("The selected Git reference did not resolve to one commit.")
    return commit_oid


def _commit_tree(repository_root: Path, commit_oid: str) -> str:
    """Return the immutable tree OID for one already resolved commit."""
    tree_oid = _git_text(
        repository_root,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{commit_oid}^{{tree}}",
    )
    if not re.fullmatch(r"[0-9a-f]{40,64}", tree_oid):
        raise RuntimeError("The selected commit did not resolve to one tree.")
    return tree_oid


def _parse_tree_records(document: bytes) -> list[dict[str, str]]:
    """Parse null-delimited ls-tree records without interpreting path bytes."""
    entries: list[dict[str, str]] = []
    for record in document.split(b"\0"):
        if not record:
            continue
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
    repository_root: Path, commit_oid: str, target: str
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


def _worktree_snapshot_entry(
    repository_root: Path, relative_path: str
) -> SnapshotFileEntry:
    """Read one regular worktree file without following symbolic links."""
    parent, filename = _open_parent(repository_root, relative_path)
    try:
        mode = os.lstat(filename, dir_fd=parent).st_mode
        if stat.S_ISLNK(mode):
            raise RuntimeError(
                f"The source path is a symbolic link: '{relative_path}'."
            )
        if not stat.S_ISREG(mode):
            raise RuntimeError(
                f"The source path is not a regular file: '{relative_path}'."
            )
        descriptor = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            chunks: list[bytes] = []
            while chunk := os.read(descriptor, 1024 * 1024):
                chunks.append(chunk)
        finally:
            os.close(descriptor)
    except FileNotFoundError as error:
        raise RuntimeError(
            f"The source path does not exist: '{relative_path}'."
        ) from error
    finally:
        os.close(parent)
    return SnapshotFileEntry(
        path=relative_path,
        source_kind="worktree_overlay",
        content=b"".join(chunks),
        mode=f"{stat.S_IMODE(mode):04o}",
    )


def _worktree_paths(repository_root: Path, target: str) -> list[str]:
    """Return selected tracked and non-ignored untracked worktree paths."""
    pathspec = _pathspec(target)
    tracked = _git_bytes(repository_root, "ls-files", "-z", "--", *pathspec).split(
        b"\0"
    )
    untracked = _git_bytes(
        repository_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
        *pathspec,
    ).split(b"\0")
    return sorted({os.fsdecode(path) for path in [*tracked, *untracked] if path})


def _worktree_inventory(
    repository_root: Path, head_oid: str, target: str
) -> dict[str, Any]:
    """Return a content-bound worktree overlay inventory."""
    paths = _worktree_paths(repository_root, target)
    entries: list[dict[str, Any]] = []
    for path in paths:
        try:
            snapshot = _worktree_snapshot_entry(repository_root, path)
        except RuntimeError as error:
            message = str(error)
            if "does not exist" in message:
                entries.append(
                    {
                        "path": path,
                        "kind": "absent",
                        "source_kind": "worktree_overlay",
                        "head_oid": head_oid,
                    }
                )
                continue
            if "symbolic link" in message:
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
    status = _git_bytes(
        repository_root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        *_pathspec(target),
    )
    identity = {
        "entries": entries,
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "target": target,
    }
    return {
        **identity,
        "inventory_digest": _canonical_digest(entries),
        "overlay_digest": _canonical_digest(identity),
    }


def resolve_source_binding(
    repository_root: Path, *, reference: str | None = None, target: str | None = "."
) -> dict[str, Any]:
    """Bind one selected commit tree or the current worktree overlay."""
    root = _repository_root(repository_root)
    normalized_target = _target_path(target)
    if reference is not None:
        commit_oid = _selected_commit(root, reference)
        tree_oid = _commit_tree(root, commit_oid)
        entries = _selected_inventory_entries(root, commit_oid, normalized_target)
        inventory_digest = _canonical_digest(entries)
        binding: dict[str, Any] = {
            "repository_root": os.fspath(root),
            "source_kind": "selected_commit_tree",
            "selector": reference,
            "commit_oid": commit_oid,
            "tree_oid": tree_oid,
            "target": normalized_target,
            "inventory_digest": inventory_digest,
        }
        return {**binding, "source_digest": _canonical_digest(binding)}

    head_oid = _selected_commit(root, "HEAD")
    tree_oid = _commit_tree(root, head_oid)
    inventory = _worktree_inventory(root, head_oid, normalized_target)
    binding = {
        "repository_root": os.fspath(root),
        "source_kind": "worktree_overlay",
        "head_oid": head_oid,
        "tree_oid": tree_oid,
        "target": normalized_target,
        "inventory_digest": inventory["inventory_digest"],
        "overlay_digest": inventory["overlay_digest"],
        "overlay_paths": [entry["path"] for entry in inventory["entries"]],
    }
    return {**binding, "source_digest": _canonical_digest(binding)}


def _verify_selected_binding(
    repository_root: Path, binding: Mapping[str, Any]
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
    expected_binding = {
        "repository_root": bound_root,
        "source_kind": "selected_commit_tree",
        "selector": selector,
        "commit_oid": commit_oid,
        "tree_oid": tree_oid,
        "target": target,
        "inventory_digest": inventory_digest,
    }
    if source_digest != _canonical_digest(expected_binding):
        raise RuntimeError("The selected source binding is stale.")
    observed_commit = _selected_commit(repository_root, commit_oid)
    observed_tree = _commit_tree(repository_root, observed_commit)
    if observed_commit != commit_oid or observed_tree != tree_oid:
        raise RuntimeError("The selected source binding is stale.")
    entries = _selected_inventory_entries(repository_root, commit_oid, target)
    if _canonical_digest(entries) != inventory_digest:
        raise RuntimeError("The selected source inventory is stale.")
    return commit_oid, tree_oid


def snapshot_file_entry(
    repository_root: Path, binding: Mapping[str, Any], raw_path: str
) -> SnapshotFileEntry:
    """Read one selected-commit blob without reading checkout bytes."""
    root = _repository_root(repository_root)
    if binding.get("source_kind") != "selected_commit_tree":
        raise RuntimeError("A selected-commit binding is required for this read.")
    commit_oid, _ = _verify_selected_binding(root, binding)
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
    content = _git_bytes(root, "cat-file", "blob", record["object_id"])
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
        head_oid = binding.get("head_oid")
        if not isinstance(head_oid, str):
            raise RuntimeError("The worktree source binding is malformed.")
        return {
            "source_kind": source_kind,
            "target": target,
            **_worktree_inventory(root, head_oid, target),
        }
    raise RuntimeError("The assessment source kind is not valid.")


def guidance_snapshot_manifest(
    repository_root: Path,
    binding: Mapping[str, Any],
    paths: Sequence[str],
) -> list[dict[str, Any]]:
    """Read guidance and architecture files from only the bound source."""
    root = _repository_root(repository_root)
    source_kind = binding.get("source_kind")
    manifest: list[dict[str, Any]] = []
    for raw_path in paths:
        path = normalize_repo_tree_path(raw_path)
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
    return manifest


def validation_manifest(
    *,
    available: bool,
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
            "reason": reason,
            "receipts": [],
            "static_assessment": {"continue": True},
            "repair_eligibility": False,
        }
    successful = bool(copied_receipts) and all(
        receipt.get("status") == "success" for receipt in copied_receipts
    )
    return {
        "status": "available",
        "reason": None,
        "receipts": copied_receipts,
        "static_assessment": {"continue": True},
        "repair_eligibility": successful,
    }


def _selected_candidates(
    report: Mapping[str, Any], candidate_ids: Sequence[str]
) -> tuple[list[str], list[str]]:
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
    candidates: dict[str, list[str]] = {}
    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, Mapping):
            raise TypeError("The assessment report contains a malformed candidate.")
        candidate_id = raw_candidate.get("id")
        raw_paths = raw_candidate.get("paths")
        if (
            not isinstance(candidate_id, str)
            or CANDIDATE_ID.fullmatch(candidate_id) is None
            or candidate_id in candidates
            or not isinstance(raw_paths, list)
            or not raw_paths
            or not all(isinstance(path, str) for path in raw_paths)
        ):
            raise RuntimeError("The assessment report contains a malformed candidate.")
        candidates[candidate_id] = [
            normalize_repo_tree_path(path) for path in raw_paths
        ]
    unknown = [
        candidate_id for candidate_id in candidate_ids if candidate_id not in candidates
    ]
    if unknown:
        raise RuntimeError(f"The repair candidate is unknown: '{unknown[0]}'.")
    paths = sorted(
        {path for candidate_id in candidate_ids for path in candidates[candidate_id]}
    )
    return list(candidate_ids), paths


def _candidate_overlap(repository_root: Path, paths: Sequence[str]) -> bool:
    """Return whether candidate paths overlap mutable checkout state."""
    status = _git_bytes(
        repository_root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        *(f":(top,literal){path}" for path in paths),
    )
    return bool(status)


def repair_preflight(
    repository_root: Path,
    report: Mapping[str, Any],
    candidate_ids: Sequence[str],
) -> dict[str, Any]:
    """Rebind a report and reject stale evidence or overlapping user work."""
    root = _repository_root(repository_root)
    source = report.get("source")
    if not isinstance(source, Mapping):
        raise TypeError("The assessment report source binding is malformed.")
    selected_ids, paths = _selected_candidates(report, candidate_ids)
    source_kind = source.get("source_kind")
    isolated_start: str | None = None
    if source_kind == "selected_commit_tree":
        isolated_start, _ = _verify_selected_binding(root, source)
    elif source_kind == "worktree_overlay":
        current = resolve_source_binding(
            root, target=cast(str | None, source.get("target"))
        )
        for field in (
            "head_oid",
            "tree_oid",
            "target",
            "inventory_digest",
            "overlay_digest",
            "source_digest",
        ):
            if current.get(field) != source.get(field):
                raise RuntimeError("The worktree assessment source is stale.")
    else:
        raise RuntimeError("The assessment report source kind is not valid.")
    if _candidate_overlap(root, paths):
        raise RuntimeError("A repair candidate path overlaps existing work.")
    return {
        "status": "eligible",
        "source_kind": source_kind,
        "candidate_ids": selected_ids,
        "candidate_paths": paths,
        "isolated_worktree_start_oid": isolated_start,
    }


def _read_report(path: Path) -> Mapping[str, Any]:
    """Read one JSON assessment report."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise TypeError("The assessment report must be a JSON object.")
    return document


def main(argv: Sequence[str] | None = None) -> int:
    """Emit one source binding or verify one repair preflight."""
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
    arguments = parser.parse_args(argv)
    try:
        repository_root = Path(_git_text(Path.cwd(), "rev-parse", "--show-toplevel"))
        if arguments.command == "bind":
            source = resolve_source_binding(
                repository_root,
                reference=arguments.reference,
                target=arguments.target,
            )
            result = {
                "schema_version": 1,
                "source": source,
                "inventory": inventory_manifest(repository_root, source),
                "guidance": guidance_snapshot_manifest(
                    repository_root, source, arguments.guidance
                ),
                "validation": validation_manifest(
                    available=False,
                    reason="Validation execution was not requested by this binding command.",
                ),
            }
        else:
            result = repair_preflight(
                repository_root,
                _read_report(arguments.report),
                arguments.candidate_ids,
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
