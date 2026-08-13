#!/usr/bin/env python3
"""Materialize one immutable GitHub pull-request snapshot in an isolated repository."""

from __future__ import annotations

import json
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

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
BOUNDED_MATERIALIZE_TIMEOUT_SECONDS = 600.0


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
        raise RuntimeError(
            "cannot materialize the immutable pull-request snapshot"
        ) from error
    if result.returncode not in accepted_codes:
        raise RuntimeError("cannot materialize the immutable pull-request snapshot")
    return result.stdout.strip() if isinstance(result.stdout, str) else ""


def _hdiutil(*arguments: str) -> None:
    """Run the macOS disk-image tool or fail closed when it cannot enforce a quota."""
    try:
        result = run_command(
            ["hdiutil", *arguments],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        raise RuntimeError(
            "host cannot enforce the immutable pull-request snapshot size limit"
        ) from error
    if result.returncode != 0:
        raise RuntimeError(
            "host cannot enforce the immutable pull-request snapshot size limit"
        )


def _mount_tmpfs(source: Path, maximum_bytes: int) -> bool:
    """Mount a Linux tmpfs whose total capacity is the snapshot quota.

    Returns True only when the mount is actually enforced; the caller must
    verify ``source.is_mount()`` is not relied on elsewhere. On any failure
    (no ``mount`` binary, no privilege, mount rejection) the caller uses the
    bounded user/mount-namespace fallback or fails closed.
    """
    if sys.platform != "linux" or shutil.which("mount") is None:
        return False
    maximum_kibibytes = maximum_bytes // 1024
    if maximum_kibibytes < 1:
        raise RuntimeError("immutable pull-request snapshot has no usable disk space")
    try:
        source.mkdir()
    except FileExistsError:
        # Directory already exists from a prior materialization; reuse it.
        pass
    except OSError:
        return False
    try:
        result = run_command(
            [
                "mount",
                "-t",
                "tmpfs",
                "-o",
                f"size={maximum_kibibytes}k",
                "tmpfs",
                str(source),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and source.is_mount()


def _create_quota_volume(root: Path, maximum_bytes: int) -> Path | None:
    """Return a bounded source directory, or None for the Linux bounded fallback.

    darwin: attach a sparse HFS+ volume whose total capacity is the quota.
    linux:  mount a tmpfs whose total capacity is the quota when the host is
            privileged; otherwise return None so the caller materializes the
            snapshot inside a bounded user/mount namespace.
    other:  fail closed — the host cannot enforce the snapshot size limit.
    """
    maximum_kibibytes = maximum_bytes // 1024
    if maximum_kibibytes < 1:
        raise RuntimeError("immutable pull-request snapshot has no usable disk space")
    if sys.platform == "darwin":
        image = root / "snapshot.sparseimage"
        source = root / "source"
        source.mkdir()
        _hdiutil(
            "create",
            "-quiet",
            "-type",
            "SPARSE",
            "-size",
            f"{maximum_kibibytes}k",
            "-fs",
            "Case-sensitive HFS+",
            "-volname",
            "Athena PR Review",
            "-nospotlight",
            str(image),
        )
        _hdiutil(
            "attach",
            "-quiet",
            "-nobrowse",
            "-mountpoint",
            str(source),
            str(image),
        )
        if not source.is_mount():
            raise RuntimeError(
                "host cannot enforce the immutable pull-request snapshot size limit"
            )
        return source
    if sys.platform.startswith("linux"):
        source = root / "source"
        if _mount_tmpfs(source, maximum_bytes):
            return source
        try:
            source.rmdir()
        except OSError:
            # The mount may have partially created the directory; a failed
            # rmdir is not fatal - the caller treats None as a fallback.
            pass
        return None
    raise RuntimeError(
        "host cannot enforce the immutable pull-request snapshot size limit"
    )


def _detach_volume(source: Path) -> None:
    """Detach the platform quota volume from its mount point."""
    if sys.platform == "darwin":
        _hdiutil("detach", "-force", "-quiet", str(source))
        return
    if sys.platform.startswith("linux"):
        try:
            result = run_command(
                ["umount", str(source)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                result = run_command(
                    ["umount", "-l", str(source)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    check=False,
                )
            if result.returncode != 0:
                raise RuntimeError("cannot remove the immutable pull-request snapshot")
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            raise RuntimeError(
                "cannot remove the immutable pull-request snapshot"
            ) from error
        return
    raise RuntimeError("cannot remove the immutable pull-request snapshot")


def _detach_best_effort(source: Path) -> None:
    """Detach a quota volume without masking a prior failure."""
    try:
        _detach_volume(source)
    except RuntimeError:
        # Detach is best-effort; a prior failure must not be masked by a
        # secondary cleanup error.
        pass


def _require_base_ref(base_ref: str) -> str:
    """Validate the GitHub base branch before it becomes a fetch refspec."""
    if not base_ref or base_ref.startswith("-") or ".." in base_ref:
        raise RuntimeError("GitHub returned an invalid pull-request base ref")
    _git("check-ref-format", "--branch", base_ref)
    return base_ref


def _repository_size(path: Path, *, maximum_bytes: int | None = None) -> int:
    """Return the size of a repository within 90 percent of free disk space."""
    if maximum_bytes is None:
        try:
            maximum_bytes = (shutil.disk_usage(path).free * 9) // 10
        except OSError as error:
            raise RuntimeError(
                "cannot inspect the immutable pull-request snapshot"
            ) from error
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
            if total > maximum_bytes:
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
    maximum_bytes: int,
) -> tuple[str, str]:
    """Fetch only the captured base branch and PR head into a source directory.

    The source directory is provided by the caller (a quota volume or a
    bounded tmpfs). Returns ``(merge_base, tree_oid)`` after verifying every
    immutable binding against the captured OIDs.
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
    _repository_size(source / ".git", maximum_bytes=maximum_bytes)
    _verify_no_promisor_configuration(source)
    if (
        _git("rev-parse", "--is-shallow-repository", cwd=source, capture_output=True)
        != "false"
    ):
        raise RuntimeError("immutable pull-request snapshot requires complete history")
    if _require_commit(source, "refs/athena/base", "fetched base OID") != base_oid:
        raise RuntimeError("fetched base ref does not match the captured base OID")
    if (
        _require_commit(source, f"refs/athena/pr/{number}/head", "fetched head OID")
        != head_oid
    ):
        raise RuntimeError(
            "fetched pull-request ref does not match the captured head OID"
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
            "immutable pull-request snapshot requires one unambiguous merge base"
        )
    merge_base = require_commit_oid(merge_bases[0], "immutable merge base")
    tree_oid = _require_commit(source, head_oid, "fetched head OID")
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
        head_oid,
        cwd=source,
        temporary_directory=source,
    )
    _repository_size(source, maximum_bytes=maximum_bytes)
    return merge_base, tree_oid


def _bounded_materialize_main(arguments: Sequence[str]) -> int:
    """Materialize inside a bounded user/mount namespace (internal entry).

    This runs as the child of ``unshare -rm`` on Linux. It mounts a tmpfs
    whose total capacity is the snapshot quota, acquires the snapshot inside
    that bound, copies the verified read-only tree to a host-visible path, and
    prints the result as JSON. Exit 2 means the quota boundary itself could
    not be established; exit 1 means materialization failed.
    """
    parser = argument_parser(description="Bounded snapshot materialization.")
    parser.add_argument("--root", required=True, metavar="ROOT")
    parser.add_argument("--repository-url", required=True, metavar="URL")
    parser.add_argument("--pr-number", required=True, type=int, metavar="NUMBER")
    parser.add_argument("--base-ref", required=True, metavar="BRANCH")
    parser.add_argument("--base-oid", required=True, metavar="BASE_OID")
    parser.add_argument("--head-oid", required=True, metavar="HEAD_OID")
    parser.add_argument("--maximum-bytes", required=True, type=int, metavar="BYTES")
    parsed = parser.parse_args(arguments)
    root = Path(parsed.root).resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if root.parent != temporary_root or not root.name.startswith("athena-pr-review-"):
        print(
            "refusing to materialize outside the managed temporary directory",
            file=sys.stderr,
        )
        return 1
    try:
        canonical_base = require_commit_oid(parsed.base_oid, "captured base OID")
        canonical_head = require_commit_oid(parsed.head_oid, "captured head OID")
        canonical_base_ref = _require_base_ref(parsed.base_ref)
        bounded = root / "bounded"
        bounded.mkdir()
        if not _mount_tmpfs(bounded, parsed.maximum_bytes):
            print(
                "host cannot enforce the immutable pull-request snapshot size limit",
                file=sys.stderr,
            )
            return 2
        merge_base, tree_oid = _acquire_into(
            bounded,
            repository_url=parsed.repository_url,
            number=parsed.pr_number,
            base_ref=canonical_base_ref,
            base_oid=canonical_base,
            head_oid=canonical_head,
            hooks=root / "empty-hooks",
            template=root / "empty-template",
            maximum_bytes=parsed.maximum_bytes,
        )
        shutil.copytree(bounded, root / "source", symlinks=True)
        _detach_best_effort(bounded)
        _make_read_only(root)
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        _detach_best_effort(root / "bounded")
        print(str(error), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "source_path": str(root / "source"),
                "merge_base": merge_base,
                "tree_oid": tree_oid,
            },
            sort_keys=True,
        )
    )
    return 0


def _bounded_materialize(
    root: Path,
    maximum_bytes: int,
    *,
    repository: str,
    number: int,
    base_ref: str,
    base_oid: str,
    head_oid: str,
) -> MaterializedSnapshot:
    """Materialize a snapshot inside a bounded Linux user/mount namespace.

    Spawns this helper under ``unshare -rm`` (rootful within the new namespace
    but unprivileged on the host), where the child mounts a tmpfs whose total
    capacity is the snapshot quota. Every fetch/checkout write is bounded by
    that filesystem; the verified tree is copied to a host-visible read-only
    path before the namespace exits. Fails closed when ``unshare`` or a tmpfs
    mount is unavailable.
    """
    unshare = shutil.which("unshare")
    if unshare is None:
        raise RuntimeError(
            "host cannot enforce the immutable pull-request snapshot size limit"
        )
    command = [
        unshare,
        "-rm",
        "--",
        sys.executable,
        str(Path(__file__).resolve()),
        "--bounded-materialize",
        "--root",
        str(root),
        "--repository-url",
        canonical_repository_url(repository),
        "--pr-number",
        str(number),
        "--base-ref",
        base_ref,
        "--base-oid",
        base_oid,
        "--head-oid",
        head_oid,
        "--maximum-bytes",
        str(maximum_bytes),
    ]
    try:
        result = run_command(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=BOUNDED_MATERIALIZE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            "cannot materialize the immutable pull-request snapshot"
        ) from error
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        raise RuntimeError(
            "host cannot enforce the immutable pull-request snapshot size limit"
        ) from error
    if result.returncode == 2:
        raise RuntimeError(
            "host cannot enforce the immutable pull-request snapshot size limit"
        )
    if result.returncode != 0:
        raise RuntimeError("cannot materialize the immutable pull-request snapshot")
    try:
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("cannot materialize the immutable pull-request snapshot")
        record = json.loads(lines[-1])
        if not isinstance(record, dict):
            raise TypeError("cannot materialize the immutable pull-request snapshot")
        source_path = Path(str(record["source_path"]))
        merge_base = require_commit_oid(record["merge_base"], "immutable merge base")
        tree_oid = require_commit_oid(record["tree_oid"], "immutable head tree")
    except (
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        RuntimeError,
    ) as error:
        raise RuntimeError(
            "cannot materialize the immutable pull-request snapshot"
        ) from error
    if source_path != root / "source" or not source_path.is_dir():
        raise RuntimeError("cannot materialize the immutable pull-request snapshot")
    return MaterializedSnapshot(
        root=root, source_path=source_path, merge_base=merge_base, tree_oid=tree_oid
    )


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
    template = root / "empty-template"
    hooks = root / "empty-hooks"
    template.mkdir()
    hooks.mkdir()
    try:
        maximum_snapshot_bytes = (shutil.disk_usage(root).free * 9) // 10
        if maximum_snapshot_bytes < 1:
            raise RuntimeError(
                "immutable pull-request snapshot has no usable disk space"
            )
        source = _create_quota_volume(root, maximum_snapshot_bytes)
        if source is None:
            return _bounded_materialize(
                root,
                maximum_snapshot_bytes,
                repository=canonical_repository,
                number=number,
                base_ref=canonical_base_ref,
                base_oid=canonical_base,
                head_oid=canonical_head,
            )
        merge_base, tree_oid = _acquire_into(
            source,
            repository_url=canonical_repository_url(canonical_repository),
            number=number,
            base_ref=canonical_base_ref,
            base_oid=canonical_base,
            head_oid=canonical_head,
            hooks=hooks,
            template=template,
            maximum_bytes=maximum_snapshot_bytes,
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
    source = resolved / "source"
    if source.is_mount():
        _detach_volume(source)

    def make_removable(function: object, path: str, _: object) -> None:
        candidate = Path(path)
        candidate.parent.chmod(0o700)
        if candidate.exists() and not candidate.is_symlink():
            candidate.chmod(0o700)
        if not callable(function):
            raise TypeError("cannot remove the immutable pull-request snapshot")
        function(path)

    shutil.rmtree(resolved, onexc=make_removable)


def main(argv: Sequence[str] | None = None) -> int:
    command_arguments = list(sys.argv[1:] if argv is None else argv)
    if "--bounded-materialize" in command_arguments:
        child_arguments = [
            argument
            for argument in command_arguments
            if argument != "--bounded-materialize"
        ]
        return _bounded_materialize_main(child_arguments)
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
