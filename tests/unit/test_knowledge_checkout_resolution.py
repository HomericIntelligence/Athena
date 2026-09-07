from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/advise/scripts/resolve_knowledge_checkout.py"
FAKE_GH = ROOT / "tests/fixtures/fake_gh.py"
GIT = shutil.which("git")
if GIT is None:
    raise RuntimeError("The test suite needs git.")


def git(cwd: Path, *arguments: str) -> str:
    """Run Git and return trimmed stdout."""
    result = subprocess.run(
        [GIT, *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def create_checkout(root: Path) -> tuple[Path, Path, str]:
    """Create a local checkout that tracks a bare Mnemosyne remote."""
    remote_root = root / "HomericIntelligence"
    remote_root.mkdir(parents=True)
    remote = remote_root / "Mnemosyne.git"
    git(root, "init", "--bare", "--quiet", "--initial-branch=main", str(remote))

    seed = root / "seed"
    git(root, "clone", "--quiet", str(remote), str(seed))
    git(seed, "config", "user.name", "Athena Tests")
    git(seed, "config", "user.email", "athena-tests@example.invalid")
    (seed / "skill.md").write_text("base\n", encoding="utf-8")
    git(seed, "add", "skill.md")
    git(seed, "commit", "--quiet", "-m", "test: seed")
    git(seed, "push", "--quiet", "origin", "main")

    knowledge_root = root / "knowledge"
    git(root, "clone", "--quiet", str(remote), str(knowledge_root))
    return remote, knowledge_root, git(knowledge_root, "rev-parse", "HEAD")


def push_followup_commit(root: Path, remote: Path) -> str:
    """Push a new commit to the remote repository and return its SHA."""
    update = root / "update"
    git(root, "clone", "--quiet", str(remote), str(update))
    git(update, "config", "user.name", "Athena Tests")
    git(update, "config", "user.email", "athena-tests@example.invalid")
    (update / "skill.md").write_text("base\nrefreshed\n", encoding="utf-8")
    git(update, "commit", "--quiet", "-am", "test: refresh")
    git(update, "push", "--quiet", "origin", "main")
    return git(update, "rev-parse", "HEAD")


def delete_remote_branch(remote: Path, branch: str = "main") -> None:
    """Delete a remote branch so fetch can fail against a valid repository."""
    subprocess.run(
        [GIT, "--git-dir", str(remote), "update-ref", "-d", f"refs/heads/{branch}"],
        capture_output=True,
        check=True,
        text=True,
    )


def build_env(
    root: Path,
    *,
    include_gh: bool,
    repository: str = "HomericIntelligence/Mnemosyne",
    auth_exit: int = 0,
    repo_view_exit: int = 0,
    repo_view_json: dict[str, object] | None = None,
    default_branch: str = "main",
    repo_view_stderr: str = "",
    auth_stderr: str = "",
) -> dict[str, str]:
    """Return an isolated tool path and fake `gh` environment."""
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python3").symlink_to(sys.executable)
    (bin_dir / "git").symlink_to(GIT)
    if include_gh:
        (bin_dir / "gh").symlink_to(FAKE_GH)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir)
    if include_gh:
        env["FAKE_GH_REQUIRE_REPOSITORY"] = repository
        env["FAKE_GH_REPOSITORY"] = repository
        env["FAKE_GH_AUTH_STATUS_EXIT"] = str(auth_exit)
        env["FAKE_GH_AUTH_STATUS_STDERR"] = auth_stderr
        env["FAKE_GH_REPO_VIEW_EXIT"] = str(repo_view_exit)
        env["FAKE_GH_DEFAULT_BRANCH"] = default_branch
        env["FAKE_GH_REPO_VIEW_STDERR"] = repo_view_stderr
        if repo_view_json is not None:
            env["FAKE_GH_REPO_VIEW_JSON"] = json.dumps(repo_view_json)
    return env


def run_resolver(
    cwd: Path,
    *arguments: str,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run the knowledge resolver helper."""
    return subprocess.run(
        [str(SCRIPT), *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def resolver_json(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """Parse a JSON result from the resolver."""
    return json.loads(result.stdout)


def assert_failure(result: subprocess.CompletedProcess[str], *expected: str) -> None:
    """Assert a nonzero, actionable failure."""
    assert result.returncode == 1
    assert result.stderr.strip()
    assert "Traceback" not in result.stderr
    for literal in expected:
        assert literal in result.stderr


def test_read_only_uses_local_checkout_when_gh_is_missing(tmp_path: Path) -> None:
    remote, knowledge_root, revision = create_checkout(tmp_path)
    del remote
    result = run_resolver(
        knowledge_root,
        "--mode",
        "read-only",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=build_env(tmp_path / "missing-gh", include_gh=False),
    )

    assert result.returncode == 0, result.stderr
    payload = resolver_json(result)
    assert payload["revision"] == revision
    assert payload["local_revision"] == revision
    assert payload["refresh_state"] == "unavailable"
    assert payload["freshness_limit"] == "freshness could not be verified or updated"
    assert "gh" in payload["limitations"][0]


def test_read_only_uses_local_checkout_when_gh_is_unauthenticated(
    tmp_path: Path,
) -> None:
    _remote, knowledge_root, revision = create_checkout(tmp_path)
    env = build_env(
        tmp_path / "unauthenticated-gh",
        include_gh=True,
        auth_exit=1,
        auth_stderr="authentication failed",
    )
    result = run_resolver(
        knowledge_root,
        "--mode",
        "read-only",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = resolver_json(result)
    assert payload["revision"] == revision
    assert payload["refresh_state"] == "unavailable"
    assert payload["freshness_limit"] == "freshness could not be verified or updated"
    assert payload["limitations"] == ["authentication failed"]


def test_read_only_uses_local_checkout_when_upstream_discovery_fails(
    tmp_path: Path,
) -> None:
    _remote, knowledge_root, revision = create_checkout(tmp_path)
    env = build_env(
        tmp_path / "discovery-fails",
        include_gh=True,
        repo_view_exit=2,
        repo_view_stderr="repository lookup failed",
    )
    result = run_resolver(
        knowledge_root,
        "--mode",
        "read-only",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = resolver_json(result)
    assert payload["revision"] == revision
    assert payload["refresh_state"] == "unavailable"
    assert payload["freshness_limit"] == "freshness could not be verified or updated"
    assert payload["limitations"] == ["repository lookup failed"]


def test_read_only_uses_local_checkout_when_fetch_fails(tmp_path: Path) -> None:
    remote, knowledge_root, revision = create_checkout(tmp_path)
    delete_remote_branch(remote)
    env = build_env(
        tmp_path / "fetch-fails",
        include_gh=True,
        repo_view_json={
            "defaultBranchRef": {"name": "main"},
            "nameWithOwner": "HomericIntelligence/Mnemosyne",
        },
    )
    result = run_resolver(
        knowledge_root,
        "--mode",
        "read-only",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = resolver_json(result)
    assert payload["revision"] == revision
    assert payload["refresh_state"] == "unavailable"
    assert payload["freshness_limit"] == "freshness could not be verified or updated"
    assert payload["limitations"]


def test_successful_refresh_reports_the_updated_revision(tmp_path: Path) -> None:
    remote, knowledge_root, revision = create_checkout(tmp_path)
    updated_revision = push_followup_commit(tmp_path, remote)
    env = build_env(tmp_path / "refresh-success", include_gh=True)
    result = run_resolver(
        knowledge_root,
        "--mode",
        "read-only",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = resolver_json(result)
    assert payload["revision"] == updated_revision
    assert payload["local_revision"] == revision
    assert payload["refresh_state"] == "updated"
    assert payload["freshness_limit"] == "freshness verified by upstream refresh"


def test_write_mode_requires_refresh_and_fails_closed_on_missing_gh(
    tmp_path: Path,
) -> None:
    _remote, knowledge_root, _revision = create_checkout(tmp_path)
    result = run_resolver(
        knowledge_root,
        "--mode",
        "write",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=build_env(tmp_path / "write-missing-gh", include_gh=False),
    )

    assert_failure(result, "gh")


def test_write_mode_requires_refresh_and_fails_on_unauthenticated_gh(
    tmp_path: Path,
) -> None:
    _remote, knowledge_root, _revision = create_checkout(tmp_path)
    env = build_env(
        tmp_path / "write-unauthenticated-gh",
        include_gh=True,
        auth_exit=1,
        auth_stderr="authentication failed",
    )
    result = run_resolver(
        knowledge_root,
        "--mode",
        "write",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=env,
    )

    assert_failure(result, "authentication failed")


def test_write_mode_requires_refresh_and_uses_the_updated_revision(
    tmp_path: Path,
) -> None:
    remote, knowledge_root, revision = create_checkout(tmp_path)
    updated_revision = push_followup_commit(tmp_path, remote)
    env = build_env(tmp_path / "write-refresh-success", include_gh=True)
    result = run_resolver(
        knowledge_root,
        "--mode",
        "write",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = resolver_json(result)
    assert payload["revision"] == updated_revision
    assert payload["local_revision"] == revision
    assert payload["refresh_state"] == "updated"


def test_mismatched_origin_fails(tmp_path: Path) -> None:
    _remote, knowledge_root, _revision = create_checkout(tmp_path)
    other_remote_root = tmp_path / "OtherOrg"
    other_remote_root.mkdir()
    other_remote = other_remote_root / "Mnemosyne.git"
    git(tmp_path, "init", "--bare", "--quiet", "--initial-branch=main", str(other_remote))
    git(
        knowledge_root,
        "remote",
        "set-url",
        "origin",
        str(other_remote),
    )
    result = run_resolver(
        knowledge_root,
        "--mode",
        "read-only",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=build_env(tmp_path / "origin-mismatch", include_gh=False),
    )

    assert_failure(result, "does not match")


def test_dirty_checkout_fails(tmp_path: Path) -> None:
    _remote, knowledge_root, _revision = create_checkout(tmp_path)
    (knowledge_root / "skill.md").write_text("dirty\n", encoding="utf-8")
    result = run_resolver(
        knowledge_root,
        "--mode",
        "read-only",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=build_env(tmp_path / "dirty-checkout", include_gh=False),
    )

    assert_failure(result, "dirty")
