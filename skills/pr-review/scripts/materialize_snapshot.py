#!/usr/bin/env python3
"""Materialize one immutable GitHub pull-request snapshot in an isolated repository."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pr_identity import COMMIT_OID, require_commit_oid, require_github_repository
from skills._cli import (
    argument_parser,
    git_read_arguments,
    git_read_environment,
    run_command,
)


SNAPSHOT_COMMAND_TIMEOUT_SECONDS = 30.0
MAX_SNAPSHOT_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class MaterializedSnapshot:
    """A detached source tree bound to one reviewed GitHub pull request."""

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
) -> str:
    """Run a bounded isolated-repository Git command without ambient config."""
    result = run_command(
        ["git", *git_read_arguments(), *arguments],
        cwd=cwd,
        stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=git_read_environment(),
        text=True,
        check=False,
        timeout=SNAPSHOT_COMMAND_TIMEOUT_SECONDS,
    )
    if result.returncode not in accepted_codes:
        raise RuntimeError("cannot materialize the immutable pull-request snapshot")
    return result.stdout.strip() if isinstance(result.stdout, str) else ""


def _require_base_ref(base_ref: str) -> str:
    """Validate the GitHub base branch before it becomes a fetch refspec."""
    if not base_ref or base_ref.startswith("-") or ".." in base_ref:
        raise RuntimeError("GitHub returned an invalid pull-request base ref")
    _git("check-ref-format", "--branch", base_ref)
    return base_ref


def _repository_size(path: Path) -> int:
    """Return the bounded on-disk size of an isolated repository."""
    total = 0
    for entry in path.rglob("*"):
        try:
            details = entry.lstat()
        except OSError as error:
            raise RuntimeError(
                "cannot inspect the immutable pull-request snapshot"
            ) from error
        if stat.S_ISREG(details.st_mode):
            total += details.st_size
            if total > MAX_SNAPSHOT_BYTES:
                raise RuntimeError(
                    "immutable pull-request snapshot exceeds the safe size limit"
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
                "immutable pull-request snapshot must not use partial clone configuration"
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
            "immutable pull-request snapshot must not use promisor configuration"
        )


def _require_commit(repository: Path, revision: str, label: str) -> str:
    """Verify one fetched ref resolves exactly to its captured commit OID."""
    resolved = _git(
        "rev-parse",
        "--verify",
        f"{revision}^{{commit}}",
        cwd=repository,
        capture_output=True,
    )
    return require_commit_oid(resolved, label)


def _make_read_only(root: Path) -> None:
    """Remove write bits from the completed snapshot without following symlinks."""
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
                "cannot make the immutable pull-request snapshot read-only"
            ) from error
    root.chmod(0o555)


def materialize_snapshot(
    *, repository: str, number: int, base_ref: str, base_oid: str, head_oid: str
) -> MaterializedSnapshot:
    """Fetch only a captured base branch and PR head into a fresh repository."""
    canonical_repository = require_github_repository(repository, "GitHub repository")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise RuntimeError("pull-request number must be positive")
    canonical_base = require_commit_oid(base_oid, "captured base OID")
    canonical_head = require_commit_oid(head_oid, "captured head OID")
    canonical_base_ref = _require_base_ref(base_ref)
    root = Path(tempfile.mkdtemp(prefix="athena-pr-review-"))
    source = root / "source"
    template = root / "empty-template"
    hooks = root / "empty-hooks"
    template.mkdir()
    hooks.mkdir()
    try:
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
        )
        base_refspec = f"+refs/heads/{canonical_base_ref}:refs/athena/base"
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
            canonical_repository_url(canonical_repository),
            base_refspec,
            head_refspec,
            cwd=source,
        )
        _repository_size(source / ".git")
        _verify_no_promisor_configuration(source)
        if (
            _git(
                "rev-parse", "--is-shallow-repository", cwd=source, capture_output=True
            )
            != "false"
        ):
            raise RuntimeError(
                "immutable pull-request snapshot requires complete history"
            )
        if (
            _require_commit(source, "refs/athena/base", "fetched base OID")
            != canonical_base
        ):
            raise RuntimeError("fetched base ref does not match the captured base OID")
        if (
            _require_commit(source, f"refs/athena/pr/{number}/head", "fetched head OID")
            != canonical_head
        ):
            raise RuntimeError(
                "fetched pull-request ref does not match the captured head OID"
            )
        merge_bases = _git(
            "merge-base",
            "--all",
            canonical_base,
            canonical_head,
            cwd=source,
            capture_output=True,
        ).splitlines()
        if len(merge_bases) != 1:
            raise RuntimeError(
                "immutable pull-request snapshot requires one unambiguous merge base"
            )
        merge_base = require_commit_oid(merge_bases[0], "immutable merge base")
        tree_oid = _require_commit(source, canonical_head, "fetched head OID")
        tree_oid = _git(
            "rev-parse", f"{tree_oid}^{{tree}}", cwd=source, capture_output=True
        )
        if COMMIT_OID.fullmatch(tree_oid) is None:
            raise RuntimeError("Git returned an invalid immutable head tree")
        _git(
            "-c",
            f"core.hooksPath={hooks}",
            "checkout",
            "--quiet",
            "--detach",
            "--no-recurse-submodules",
            canonical_head,
            cwd=source,
        )
        _make_read_only(root)
    except (OSError, subprocess.TimeoutExpired):
        remove_snapshot(root)
        raise RuntimeError(
            "cannot materialize the immutable pull-request snapshot"
        ) from None
    except BaseException:
        remove_snapshot(root)
        raise
    return MaterializedSnapshot(
        root=root, source_path=source, merge_base=merge_base, tree_oid=tree_oid
    )


def remove_snapshot(root: Path) -> None:
    """Remove a snapshot that this helper created after host inspection ends."""
    resolved = root.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if resolved.parent != temporary_root or not resolved.name.startswith(
        "athena-pr-review-"
    ):
        raise RuntimeError(
            "refusing to remove a snapshot outside the managed temporary directory"
        )

    def make_removable(function: object, path: str, _: object) -> None:
        candidate = Path(path)
        candidate.parent.chmod(0o700)
        if candidate.exists() and not candidate.is_symlink():
            candidate.chmod(0o700)
        if not callable(function):
            raise RuntimeError("cannot remove the immutable pull-request snapshot")
        function(path)

    shutil.rmtree(resolved, onexc=make_removable)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("--repository", required=True, metavar="OWNER/REPOSITORY")
    parser.add_argument("--pr-number", required=True, type=int, metavar="NUMBER")
    parser.add_argument("--base-ref", required=True, metavar="BRANCH")
    parser.add_argument("--base-oid", required=True, metavar="BASE_OID")
    parser.add_argument("--head-oid", required=True, metavar="HEAD_OID")
    arguments = parser.parse_args(argv)
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
    print(__import__("json").dumps(snapshot.as_json(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
