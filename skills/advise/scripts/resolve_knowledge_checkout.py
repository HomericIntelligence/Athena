#!/usr/bin/env python3
"""Resolve a trusted Mnemosyne checkout for read-only or write workflows."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from skills._cli import (
    argument_parser,
    git_read_arguments,
    git_read_environment,
    run_command,
)

DEFAULT_KNOWLEDGE_ROOT = Path.home() / ".agent_brain" / "knowledge"
DEFAULT_ORGANIZATION_OWNER = "HomericIntelligence"
REPOSITORY_NAME = "Mnemosyne"
OWNER_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class LocalCheckout:
    """Validated local checkout metadata."""

    root: Path
    repository: str
    origin: str
    branch: str | None
    revision: str


@dataclass(frozen=True)
class RefreshOutcome:
    """Best-effort refresh result."""

    revision: str
    refresh_state: str
    freshness_limit: str
    limitations: list[str]


def validate_owner(owner: str) -> str:
    """Validate a GitHub owner name."""
    if not OWNER_PATTERN.fullmatch(owner):
        raise RuntimeError(f"The knowledge owner is not valid: '{owner}'.")
    return owner


def expected_repository() -> str:
    """Return the expected Mnemosyne repository for the current environment."""
    owner = os.environ.get("HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER")
    if owner is None or not owner:
        owner = DEFAULT_ORGANIZATION_OWNER
    return f"{validate_owner(owner)}/{REPOSITORY_NAME}"


def repository_from_origin(origin: str) -> str:
    """Return the repository identity encoded in a Git origin URL or path."""
    if origin.startswith("git@") and ":" in origin and "://" not in origin:
        candidate = origin.rsplit(":", maxsplit=1)[1]
    else:
        parsed = urlparse(origin)
        candidate = parsed.path if parsed.scheme else origin
    segments = [segment for segment in candidate.replace("\\", "/").split("/") if segment]
    if len(segments) < 2:
        raise RuntimeError(
            f"The origin does not identify an owner and repository: '{origin}'."
        )
    owner = segments[-2]
    repository = segments[-1]
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not OWNER_PATTERN.fullmatch(owner):
        raise RuntimeError(
            f"The origin does not identify a valid repository owner: '{origin}'."
        )
    if repository.casefold() != REPOSITORY_NAME.casefold():
        raise RuntimeError(
            f"The origin does not identify the Mnemosyne repository: '{origin}'."
        )
    return f"{owner}/{repository}"


def run_git(
    cwd: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    """Run Git with the immutable read boundary."""
    return run_command(
        ["git", *git_read_arguments(), *arguments],
        capture_output=True,
        cwd=cwd,
        env=git_read_environment(),
        text=True,
        check=False,
    )


def git_text(cwd: Path, *arguments: str) -> str:
    """Return the trimmed stdout for a successful immutable Git command."""
    result = run_git(cwd, *arguments)
    if result.returncode != 0:
        message = result.stderr.strip() or (
            f"The git {' '.join(arguments)} command failed."
        )
        raise RuntimeError(message)
    return result.stdout.strip()


def validate_local_checkout(knowledge_root: Path) -> LocalCheckout:
    """Validate the local checkout identity and cleanliness."""
    if not knowledge_root.is_dir():
        raise RuntimeError(
            f"The knowledge checkout is not available: '{knowledge_root}'."
        )
    top_level = Path(git_text(knowledge_root, "rev-parse", "--show-toplevel"))
    if top_level.resolve() != knowledge_root.resolve():
        raise RuntimeError(
            f"The knowledge checkout root does not match the requested path: "
            f"'{knowledge_root}'."
        )
    origin = git_text(knowledge_root, "remote", "get-url", "origin")
    repository = repository_from_origin(origin)
    revision = git_text(knowledge_root, "rev-parse", "HEAD")
    if not FULL_SHA_PATTERN.fullmatch(revision):
        raise RuntimeError(
            f"The knowledge checkout revision is not a full commit SHA: '{revision}'."
        )
    status = git_text(
        knowledge_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        raise RuntimeError(
            "The knowledge checkout is dirty:\n" + status
        )
    branch_result = run_git(knowledge_root, "branch", "--show-current")
    if branch_result.returncode != 0:
        message = branch_result.stderr.strip() or "The current branch could not be read."
        raise RuntimeError(message)
    branch = branch_result.stdout.strip() or None
    return LocalCheckout(
        root=knowledge_root,
        repository=repository,
        origin=origin,
        branch=branch,
        revision=revision,
    )


def gh_command(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run `gh` and return the completed process."""
    return run_command(
        ["gh", *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def parse_repo_view(output: str, expected: str) -> str:
    """Return the default branch reported by GitHub."""
    value = json.loads(output)
    if not isinstance(value, dict):
        raise TypeError("GitHub returned repository metadata that is not valid.")
    name_with_owner = value.get("nameWithOwner")
    if isinstance(name_with_owner, str) and name_with_owner.casefold() != expected.casefold():
        raise RuntimeError(
            f"GitHub returned a different repository than expected: '{name_with_owner}'."
        )
    default_branch_ref = value.get("defaultBranchRef")
    if not isinstance(default_branch_ref, dict):
        raise TypeError(
            "GitHub did not return a default branch for the knowledge repository."
        )
    default_branch = default_branch_ref.get("name")
    if not isinstance(default_branch, str) or not default_branch:
        raise TypeError(
            "GitHub did not return a valid default branch for the knowledge repository."
        )
    return default_branch


def refresh_local_checkout(
    checkout: LocalCheckout, expected: str, mode: str
) -> RefreshOutcome:
    """Attempt a best-effort refresh and report the result."""
    limitations: list[str] = []
    if shutil.which("gh") is None:
        reason = "The required command is not available: 'gh'."
        if mode == "write":
            raise RuntimeError(reason)
        limitations.append(reason)
        return RefreshOutcome(
            revision=checkout.revision,
            refresh_state="unavailable",
            freshness_limit="freshness could not be verified or updated",
            limitations=limitations,
        )
    auth_result = gh_command("auth", "status", "--hostname", "github.com")
    if auth_result.returncode != 0:
        reason = (
            auth_result.stderr.strip()
            or auth_result.stdout.strip()
            or "GitHub authentication is unavailable."
        )
        if mode == "write":
            raise RuntimeError(reason)
        limitations.append(reason)
        return RefreshOutcome(
            revision=checkout.revision,
            refresh_state="unavailable",
            freshness_limit="freshness could not be verified or updated",
            limitations=limitations,
        )
    repo_result = gh_command(
        "repo",
        "view",
        "--repo",
        f"github.com/{expected}",
        "--json",
        "nameWithOwner,defaultBranchRef",
    )
    if repo_result.returncode != 0:
        reason = (
            repo_result.stderr.strip()
            or repo_result.stdout.strip()
            or "GitHub repository discovery failed."
        )
        if mode == "write":
            raise RuntimeError(reason)
        limitations.append(reason)
        return RefreshOutcome(
            revision=checkout.revision,
            refresh_state="unavailable",
            freshness_limit="freshness could not be verified or updated",
            limitations=limitations,
        )
    default_branch = parse_repo_view(repo_result.stdout, expected)
    if checkout.branch is None:
        reason = "The knowledge checkout is detached and cannot be refreshed."
        if mode == "write":
            raise RuntimeError(reason)
        limitations.append(reason)
        return RefreshOutcome(
            revision=checkout.revision,
            refresh_state="unavailable",
            freshness_limit="freshness could not be verified or updated",
            limitations=limitations,
        )
    if checkout.branch != default_branch:
        reason = (
            "The knowledge checkout branch does not match the remote default "
            f"branch: '{checkout.branch}' != '{default_branch}'."
        )
        if mode == "write":
            raise RuntimeError(reason)
        limitations.append(reason)
        return RefreshOutcome(
            revision=checkout.revision,
            refresh_state="unavailable",
            freshness_limit="freshness could not be verified or updated",
            limitations=limitations,
        )
    fetch_result = run_git(checkout.root, "fetch", "origin", default_branch)
    if fetch_result.returncode != 0:
        reason = (
            fetch_result.stderr.strip()
            or fetch_result.stdout.strip()
            or f"The knowledge checkout could not fetch origin/{default_branch}."
        )
        if mode == "write":
            raise RuntimeError(reason)
        limitations.append(reason)
        return RefreshOutcome(
            revision=checkout.revision,
            refresh_state="unavailable",
            freshness_limit="freshness could not be verified or updated",
            limitations=limitations,
        )
    merge_result = run_git(checkout.root, "merge", "--ff-only", "FETCH_HEAD")
    if merge_result.returncode != 0:
        reason = (
            merge_result.stderr.strip()
            or merge_result.stdout.strip()
            or "The knowledge checkout could not fast-forward."
        )
        if mode == "write":
            raise RuntimeError(reason)
        limitations.append(reason)
        return RefreshOutcome(
            revision=checkout.revision,
            refresh_state="unavailable",
            freshness_limit="freshness could not be verified or updated",
            limitations=limitations,
        )
    revision = git_text(checkout.root, "rev-parse", "HEAD")
    return RefreshOutcome(
        revision=revision,
        refresh_state="updated",
        freshness_limit="freshness verified by upstream refresh",
        limitations=limitations,
    )


def resolve_knowledge_checkout(knowledge_root: Path, mode: str) -> dict[str, Any]:
    """Resolve the local checkout and report its revision and limits."""
    expected = expected_repository()
    checkout = validate_local_checkout(knowledge_root)
    if checkout.repository.casefold() != expected.casefold():
        raise RuntimeError(
            f"The knowledge checkout origin does not match '{expected}': "
            f"'{checkout.origin}'."
        )
    refresh = refresh_local_checkout(checkout, expected, mode)
    return {
        "branch": checkout.branch,
        "checkout": str(checkout.root),
        "checkout_state": "clean",
        "freshness_limit": refresh.freshness_limit,
        "limitations": refresh.limitations,
        "local_revision": checkout.revision,
        "mode": mode,
        "refresh_state": refresh.refresh_state,
        "repository": checkout.repository,
        "revision": refresh.revision,
        "trust_basis": "validated local checkout",
    }


def main(argv: list[str] | None = None) -> int:
    """Resolve the checkout and print a machine-readable result."""
    parser = argument_parser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("read-only", "write"),
        required=True,
        help="Select the read-only or mutation boundary.",
    )
    parser.add_argument(
        "--knowledge-root",
        type=Path,
        default=DEFAULT_KNOWLEDGE_ROOT,
        help="Use the resolved Mnemosyne checkout path.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON for downstream machine parsing.",
    )
    arguments = parser.parse_args(argv)
    if not arguments.json:
        parser.error("Specify --json.")
    try:
        result = resolve_knowledge_checkout(arguments.knowledge_root, arguments.mode)
    except (json.JSONDecodeError, RuntimeError, TypeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
