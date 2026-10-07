#!/usr/bin/env python3
"""Materialize one immutable GitHub pull-request snapshot in an isolated repository."""

from __future__ import annotations

import importlib.util
import inspect
import json
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pr_identity import COMMIT_OID, require_commit_oid, require_github_repository

if TYPE_CHECKING or __package__ not in {None, ""}:
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

SNAPSHOT_COMMAND_TIMEOUT_SECONDS = 30.0
MATERIALIZE_ERROR = "The helper cannot materialize the immutable pull-request snapshot."


@dataclass(frozen=True)
class MaterializedSnapshot:
    """This record binds a detached source tree to one reviewed GitHub pull request."""

    root: Path
    source_path: Path
    merge_base: str
    tree_oid: str

    def as_json(self) -> dict[str, str]:
        """Return the snapshot fields a host needs for immutable inspection."""
        return {
            "merge_base": self.merge_base,
            "root": str(self.root),
            "source_path": str(self.source_path),
            "tree_oid": self.tree_oid,
        }


def canonical_repository_url(repository: str) -> str:
    """Return the sole permitted acquisition endpoint for a GitHub repository."""
    return f"https://github.com/{repository}.git"


def _git(
    *arguments: str,
    cwd: Path | None = None,
    capture_output: bool = False,
    accepted_codes: tuple[int, ...] = (0,),
    temporary_directory: Path | None = None,
) -> str:
    """Run a bounded isolated-repository Git command without ambient config."""
    environment = git_read_environment()
    if temporary_directory is not None:
        environment["TMPDIR"] = str(temporary_directory)
    command_options: dict[str, object] = {
        "cwd": cwd,
        "stdout": subprocess.PIPE if capture_output else subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "env": environment,
        "text": True,
        "check": False,
        "timeout": SNAPSHOT_COMMAND_TIMEOUT_SECONDS,
    }
    try:
        result = run_command(
            ["git", *git_read_arguments(), *arguments], **command_options
        )
    except subprocess.SubprocessError as error:
        raise RuntimeError(MATERIALIZE_ERROR) from error
    if result.returncode not in accepted_codes:
        raise RuntimeError(MATERIALIZE_ERROR)
    return result.stdout.strip() if isinstance(result.stdout, str) else ""

















def _require_base_ref(base_ref: str) -> str:
    """Validate the GitHub base branch before it becomes a fetch refspec."""
    if not base_ref or base_ref.startswith("-") or ".." in base_ref:
        raise RuntimeError("GitHub returned a pull-request base ref that is not valid.")
    _git("check-ref-format", "--branch", base_ref)
    return base_ref


def _repository_size(path: Path, *, maximum_bytes: int | None = None) -> int:
    """Return the repository size and enforce the applicable size limit."""
    if maximum_bytes is None:
        try:
            maximum_bytes = (shutil.disk_usage(path).free * 9) // 10
        except OSError as error:
            raise RuntimeError(
                "The helper cannot inspect the immutable pull-request snapshot."
            ) from error
    total = 0
    for entry in path.rglob("*"):
        try:
            details = entry.lstat()
        except OSError as error:
            raise RuntimeError(
                "The helper cannot inspect the immutable pull-request snapshot."
            ) from error
        if stat.S_ISREG(details.st_mode):
            total += details.st_size
            if total > maximum_bytes:
                raise RuntimeError(
                    "The immutable pull-request snapshot exceeds the safe size limit."
                )
    return total


def _verify_no_promisor_configuration(repository: Path) -> None:
    """Reject partial-clone configuration before any immutable object reads."""
    for key in ("extensions.partialClone",):
        value = _git(
            "config",
            "--local",
            "--get",
            key,
            cwd=repository,
            capture_output=True,
            accepted_codes=(0, 1),
        )
        if value:
            raise RuntimeError(
                "The immutable pull-request snapshot must not use partial-clone configuration."
            )
    promisor = _git(
        "config",
        "--local",
        "--get-regexp",
        r"^remote\..*\.(promisor|partialclonefilter)$",
        cwd=repository,
        capture_output=True,
        accepted_codes=(0, 1),
    )
    if promisor:
        raise RuntimeError(
            "The immutable pull-request snapshot must not use promisor configuration."
        )


def _require_commit(repository: Path, revision: str, label: str) -> str:
    """Verify that one fetched ref resolves to its captured commit object identifier."""
    resolved = _git(
        "rev-parse",
        "--verify",
        f"{revision}^{{commit}}",
        cwd=repository,
        capture_output=True,
    )
    return require_commit_oid(resolved, label)


def _make_read_only(root: Path) -> None:
    """Remove write bits from the completed snapshot without following symbolic links."""
    entries = sorted(root.rglob("*"), key=lambda entry: len(entry.parts), reverse=True)
    for entry in entries:
        if entry.is_symlink():
            continue
        try:
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISDIR(mode):
                entry.chmod(0o555)
            else:
                entry.chmod(0o555 if mode & stat.S_IXUSR else 0o444)
        except OSError as error:
            raise RuntimeError(
                "The helper cannot make the immutable pull-request snapshot read-only."
            ) from error
    root.chmod(0o555)


def _acquire_into(
    source: Path,
    *,
    repository_url: str,
    number: int,
    base_ref: str,
    base_oid: str,
    head_oid: str,
    hooks: Path,
    template: Path,
) -> tuple[str, str]:
    """Fetch only the captured base branch and pull-request head.

    Verify each immutable binding against the captured object identifiers.
    Then, return ``(merge_base, tree_oid)``.
    """
    _git(
        "-c",
        f"core.hooksPath={hooks}",
        "-c",
        "init.defaultBranch=athena-review",
        "init",
        "--quiet",
        f"--template={template}",
        "--initial-branch=athena-review",
        str(source),
        temporary_directory=source,
    )
    base_refspec = f"+refs/heads/{base_ref}:refs/athena/base"
    head_refspec = f"+refs/pull/{number}/head:refs/athena/pr/{number}/head"
    _git(
        "-c",
        f"core.hooksPath={hooks}",
        "-c",
        "remote.origin.fetch=",
        "-c",
        "fetch.writeCommitGraph=false",
        "-c",
        "fetch.fsckObjects=true",
        "-c",
        "transfer.fsckObjects=true",
        "fetch",
        "--quiet",
        "--no-tags",
        "--no-write-fetch-head",
        "--no-recurse-submodules",
        "--refmap=",
        repository_url,
        base_refspec,
        head_refspec,
        cwd=source,
        temporary_directory=source,
    )
    if (
        _git("rev-parse", "--is-shallow-repository", cwd=source, capture_output=True)
        != "false"
    ):
        raise RuntimeError(
            "The immutable pull-request snapshot requires complete history."
        )
    if (
        _require_commit(source, "refs/athena/base", "fetched base object identifier")
        != base_oid
    ):
        raise RuntimeError(
            "The fetched base ref does not match the captured base object identifier."
        )
    if (
        _require_commit(
            source,
            f"refs/athena/pr/{number}/head",
            "fetched head object identifier",
        )
        != head_oid
    ):
        raise RuntimeError(
            "The fetched pull-request ref does not match the captured head object identifier."
        )
    merge_bases = _git(
        "merge-base",
        "--all",
        base_oid,
        head_oid,
        cwd=source,
        capture_output=True,
    ).splitlines()
    if len(merge_bases) != 1:
        raise RuntimeError(
            "The immutable pull-request snapshot requires one unambiguous merge base."
        )
    merge_base = require_commit_oid(merge_bases[0], "immutable merge base")
    tree_oid = _require_commit(source, head_oid, "fetched head object identifier")
    tree_oid = _git(
        "rev-parse", f"{tree_oid}^{{tree}}", cwd=source, capture_output=True
    )
    if COMMIT_OID.fullmatch(tree_oid) is None:
        raise RuntimeError("Git returned an immutable head tree that is not valid.")
    _git(
        "-c",
        f"core.hooksPath={hooks}",
        "checkout",
        "--quiet",
        "--detach",
        "--no-recurse-submodules",
        head_oid,
        cwd=source,
        temporary_directory=source,
    )
    return merge_base, tree_oid


def materialize_snapshot(
    *, repository: str, number: int, base_ref: str, base_oid: str, head_oid: str
) -> MaterializedSnapshot:
    """Materialize a captured base branch and pull-request head in a new repository."""
    canonical_repository = require_github_repository(repository, "GitHub repository")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise RuntimeError("The pull-request number must be positive.")
    canonical_base = require_commit_oid(base_oid, "captured base object identifier")
    canonical_head = require_commit_oid(head_oid, "captured head object identifier")
    canonical_base_ref = _require_base_ref(base_ref)
    root = Path(tempfile.mkdtemp(prefix="athena-pr-review-"))
    template = root / "empty-template"
    hooks = root / "empty-hooks"
    template.mkdir()
    hooks.mkdir()
    try:
        source = root / "source"
        source.mkdir()
        merge_base, tree_oid = _acquire_into(
            source,
            repository_url=canonical_repository_url(canonical_repository),
            number=number,
            base_ref=canonical_base_ref,
            base_oid=canonical_base,
            head_oid=canonical_head,
            hooks=hooks,
            template=template,
        )
        _make_read_only(root)
    except (OSError, RuntimeError) as error:
        shutil.rmtree(root, ignore_errors=True)
        raise RuntimeError(MATERIALIZE_ERROR) from None
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    return MaterializedSnapshot(
        root=root, source_path=root / "source", merge_base=merge_base, tree_oid=tree_oid
    )


def remove_snapshot(root: Path) -> None:
    """After host inspection ends, remove a snapshot that this helper materialized."""
    resolved = root.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if resolved.parent != temporary_root or not resolved.name.startswith(
        "athena-pr-review-"
    ):
        raise RuntimeError("The helper cannot remove the snapshot outside the managed temporary directory.")
    source = resolved / "source"
    def make_removable(function: object, path: str, _: object) -> None:
        candidate = Path(path)
        candidate.parent.chmod(0o700)
        if candidate.exists() and not candidate.is_symlink():
            candidate.chmod(0o700)
        if not callable(function):
            raise TypeError("The helper cannot remove the snapshot.")
        function(path)

    if "onexc" in inspect.signature(shutil.rmtree).parameters:
        shutil.rmtree(resolved, onexc=make_removable)
        return
    shutil.rmtree(resolved, onerror=make_removable)


def main(argv: Sequence[str] | None = None) -> int:
    command_arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argument_parser(description=__doc__)
    parser.add_argument("--repository", required=True, metavar="OWNER/REPOSITORY")
    parser.add_argument("--pr-number", required=True, type=int, metavar="NUMBER")
    parser.add_argument("--base-ref", required=True, metavar="BRANCH")
    parser.add_argument("--base-oid", required=True, metavar="BASE_OID")
    parser.add_argument("--head-oid", required=True, metavar="HEAD_OID")
    arguments = parser.parse_args(command_arguments)
    try:
        snapshot = materialize_snapshot(
            repository=arguments.repository,
            number=arguments.pr_number,
            base_ref=arguments.base_ref,
            base_oid=arguments.base_oid,
            head_oid=arguments.head_oid,
        )
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    print(json.dumps(snapshot.as_json(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
