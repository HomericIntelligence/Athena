from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from skills.advise.scripts import resolve_knowledge_checkout as resolver

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/advise/scripts/resolve_knowledge_checkout.py"
FAKE_GH = ROOT / "tests/fixtures/fake_gh.py"
GIT = shutil.which("git")
if GIT is None:
    raise RuntimeError("The test suite needs git.")
GIT_PATH: str = GIT


def git(cwd: Path, *arguments: str) -> str:
    """Run Git and return trimmed stdout."""
    result = subprocess.run(
        [GIT_PATH, *arguments],
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
    origin_url = "https://github.com/" + "HomericIntelligence/" + "Mnemosyne.git"
    git(knowledge_root, "remote", "set-url", "origin", origin_url)
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
        [
            GIT_PATH,
            "--git-dir",
            str(remote),
            "update-ref",
            "-d",
            f"refs/heads/{branch}",
        ],
        capture_output=True,
        check=True,
        text=True,
    )


def build_env(
    root: Path,
    *,
    include_gh: bool,
    repository: str = "HomericIntelligence/" + "Mnemosyne",
    auth_exit: int = 0,
    auth_sleep_seconds: float = 0,
    repo_view_exit: int = 0,
    repo_view_sleep_seconds: float = 0,
    repo_view_json: dict[str, object] | None = None,
    default_branch: str = "main",
    repo_view_stderr: str = "",
    auth_stderr: str = "",
    git_fetch_sleep_seconds: float = 0,
    git_fetch_remote: Path | None = None,
) -> dict[str, str]:
    """Return an isolated tool path and fake `gh` environment."""
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python3").symlink_to(sys.executable)
    if git_fetch_sleep_seconds > 0 or git_fetch_remote is not None:
        git_wrapper = bin_dir / "git"
        trusted_url = f"https://github.com/{repository}.git"
        replacement = str(git_fetch_remote) if git_fetch_remote else trusted_url
        git_wrapper.write_text(
            "\n".join(
                [
                    f"#!{sys.executable}",
                    "import os",
                    "import sys",
                    "import time",
                    "arguments = sys.argv[1:]",
                    "if 'fetch' in arguments:",
                    f"    time.sleep({git_fetch_sleep_seconds})",
                    (
                        "    arguments = ["
                        f"{replacement!r} if value == {trusted_url!r} else value "
                        "for value in arguments]"
                    ),
                    f"os.execv({GIT_PATH!r}, [{GIT_PATH!r}, *arguments])",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        git_wrapper.chmod(0o755)
    else:
        (bin_dir / "git").symlink_to(GIT_PATH)
    if include_gh:
        (bin_dir / "gh").symlink_to(FAKE_GH)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir)
    if include_gh:
        env["FAKE_GH_REQUIRE_REPOSITORY"] = repository
        env["FAKE_GH_REPOSITORY"] = repository
        env["FAKE_GH_AUTH_STATUS_EXIT"] = str(auth_exit)
        env["FAKE_GH_AUTH_STATUS_SLEEP_SECONDS"] = str(auth_sleep_seconds)
        env["FAKE_GH_AUTH_STATUS_STDERR"] = auth_stderr
        env["FAKE_GH_REPO_VIEW_EXIT"] = str(repo_view_exit)
        env["FAKE_GH_REPO_VIEW_SLEEP_SECONDS"] = str(repo_view_sleep_seconds)
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
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise TypeError("The resolver did not return a JSON object.")
    return payload


def test_repository_identity_helpers() -> None:
    """Exercise the resolver module directly for coverage."""
    assert (
        resolver.repository_from_origin(
            "https://github.com/" + "HomericIntelligence/" + "Mnemosyne.git"
        )
        == "HomericIntelligence/Mnemosyne"
    )
    with pytest.raises(RuntimeError):
        resolver.repository_from_origin(
            "file:///tmp/" + "HomericIntelligence/" + "Mnemosyne.git"
        )


def test_resolver_module_coverage_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exercise the resolver control flow in process for coverage."""
    cli_module = resolver._load_installed_cli_module()
    assert cli_module.git_read_arguments()
    _remote, knowledge_root, revision = create_checkout(tmp_path)
    checkout = resolver.validate_local_checkout(knowledge_root)
    assert checkout.revision == revision
    assert resolver.validate_owner("HomericIntelligence") == "HomericIntelligence"
    with pytest.raises(RuntimeError):
        resolver.validate_owner("bad owner")
    assert (
        resolver.repository_from_origin(
            "https://github.com/" + "HomericIntelligence/" + "Mnemosyne.git"
        )
        == "HomericIntelligence/Mnemosyne"
    )
    assert (
        resolver.repository_from_origin(
            "git@github.com:" + "HomericIntelligence/" + "Mnemosyne.git"
        )
        == "HomericIntelligence/Mnemosyne"
    )
    with pytest.raises(RuntimeError):
        resolver.repository_from_origin(
            "file:///tmp/" + "HomericIntelligence/" + "Mnemosyne.git"
        )

    monkeypatch.setattr(
        resolver,
        "resolve_knowledge_checkout",
        lambda *_args, **_kwargs: {
            "checkout": str(knowledge_root),
            "revision": revision,
        },
    )
    assert (
        resolver.main(
            [
                "--mode",
                "read-only",
                "--knowledge-root",
                str(knowledge_root),
                "--json",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out

    monkeypatch.setattr(
        "skills.advise.scripts.resolve_knowledge_checkout.shutil.which",
        lambda _name: None,
    )
    outcome = resolver.refresh_local_checkout(
        checkout, "HomericIntelligence/Mnemosyne", "read-only"
    )
    assert outcome.refresh_state == "unavailable"
    with pytest.raises(RuntimeError):
        resolver.refresh_local_checkout(
            checkout, "HomericIntelligence/Mnemosyne", "write"
        )

    monkeypatch.setattr(
        "skills.advise.scripts.resolve_knowledge_checkout.shutil.which",
        lambda _name: "/usr/bin/gh",
    )
    monkeypatch.setattr(
        resolver,
        "gh_command",
        lambda *arguments: subprocess.CompletedProcess[str](
            args=["gh", *arguments],
            returncode=1,
            stdout="",
            stderr="authentication failed",
        ),
    )
    outcome = resolver.refresh_local_checkout(
        checkout, "HomericIntelligence/Mnemosyne", "read-only"
    )
    assert outcome.refresh_state == "unavailable"
    with pytest.raises(RuntimeError):
        resolver.refresh_local_checkout(
            checkout, "HomericIntelligence/Mnemosyne", "write"
        )

    responses = iter(
        [
            subprocess.CompletedProcess[str](
                args=["gh", "auth", "status"],
                returncode=0,
                stdout="github.com\n  ✓ Logged in to github.com as fake-user",
                stderr="",
            ),
            subprocess.CompletedProcess[str](
                args=["gh", "repo", "view"],
                returncode=2,
                stdout="",
                stderr="repository lookup failed",
            ),
        ]
    )
    monkeypatch.setattr(resolver, "gh_command", lambda *arguments: next(responses))
    outcome = resolver.refresh_local_checkout(
        checkout, "HomericIntelligence/Mnemosyne", "read-only"
    )
    assert outcome.refresh_state == "unavailable"

    updates = {
        "fetch": subprocess.CompletedProcess[str](
            args=["git", "fetch"],
            returncode=0,
            stdout="",
            stderr="",
        ),
        "merge": subprocess.CompletedProcess[str](
            args=["git", "merge"],
            returncode=0,
            stdout="",
            stderr="",
        ),
        "rev-parse": subprocess.CompletedProcess[str](
            args=["git", "rev-parse", "HEAD"],
            returncode=0,
            stdout=revision,
            stderr="",
        ),
    }
    monkeypatch.setattr(
        resolver,
        "gh_command",
        lambda *arguments: subprocess.CompletedProcess[str](
            args=["gh", *arguments],
            returncode=0,
            stdout=json.dumps(
                {
                    "defaultBranchRef": {"name": "main"},
                    "nameWithOwner": "HomericIntelligence/Mnemosyne",
                }
            ),
            stderr="",
        ),
    )
    monkeypatch.setattr(
        resolver,
        "parse_repo_view",
        lambda _output, _expected: "main",
    )

    def fake_run_git(
        cwd: Path, *arguments: str, timeout: float | None = None
    ) -> subprocess.CompletedProcess[str]:
        del cwd, timeout
        if arguments[:1] == ("fetch",):
            return updates["fetch"]
        if arguments[:2] == ("merge", "--ff-only"):
            return updates["merge"]
        if arguments[:2] == ("rev-parse", "HEAD"):
            return updates["rev-parse"]
        if arguments[:2] == ("rev-parse", "FETCH_HEAD"):
            return subprocess.CompletedProcess[str](
                args=["git", "rev-parse", "FETCH_HEAD"],
                returncode=0,
                stdout=revision,
                stderr="",
            )
        if arguments[:2] == ("branch", "--show-current"):
            return subprocess.CompletedProcess[str](
                args=["git", "branch", "--show-current"],
                returncode=0,
                stdout="main",
                stderr="",
            )
        if arguments[:1] == ("status",):
            return subprocess.CompletedProcess[str](
                args=["git", *arguments],
                returncode=0,
                stdout="",
                stderr="",
            )
        return subprocess.CompletedProcess[str](
            args=["git", *arguments],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(resolver, "run_git", fake_run_git)
    outcome = resolver.refresh_local_checkout(
        checkout, "HomericIntelligence/Mnemosyne", "read-only"
    )
    assert outcome.refresh_state == "updated"
    assert outcome.revision == revision


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


def test_read_only_uses_local_checkout_when_gh_auth_times_out(
    tmp_path: Path,
) -> None:
    _remote, knowledge_root, revision = create_checkout(tmp_path)
    env = build_env(
        tmp_path / "auth-timeout",
        include_gh=True,
        auth_sleep_seconds=4,
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
    assert "timed out" in payload["limitations"][0]


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


def test_read_only_uses_local_checkout_when_gh_repo_view_times_out(
    tmp_path: Path,
) -> None:
    _remote, knowledge_root, revision = create_checkout(tmp_path)
    env = build_env(
        tmp_path / "repo-view-timeout",
        include_gh=True,
        repo_view_sleep_seconds=4,
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
    assert "timed out" in payload["limitations"][0]


def test_read_only_uses_local_checkout_when_fetch_fails(tmp_path: Path) -> None:
    remote, knowledge_root, revision = create_checkout(tmp_path)
    delete_remote_branch(remote)
    env = build_env(
        tmp_path / "fetch-fails",
        include_gh=True,
        git_fetch_remote=remote,
        repo_view_json={
            "defaultBranchRef": {"name": "main"},
            "nameWithOwner": "HomericIntelligence/" + "Mnemosyne",
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


def test_read_only_uses_local_checkout_when_fetch_times_out(
    tmp_path: Path,
) -> None:
    remote, knowledge_root, revision = create_checkout(tmp_path)
    push_followup_commit(tmp_path, remote)
    env = build_env(
        tmp_path / "fetch-timeout",
        include_gh=True,
        git_fetch_sleep_seconds=4,
        git_fetch_remote=remote,
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
    assert "timed out" in payload["limitations"][0]


def test_successful_refresh_reports_the_updated_revision(tmp_path: Path) -> None:
    remote, knowledge_root, revision = create_checkout(tmp_path)
    updated_revision = push_followup_commit(tmp_path, remote)
    env = build_env(
        tmp_path / "refresh-success",
        include_gh=True,
        git_fetch_remote=remote,
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
    assert payload["revision"] == updated_revision
    assert payload["local_revision"] == revision
    assert payload["refresh_state"] == "updated"
    assert payload["freshness_limit"] == "freshness verified by upstream refresh"


def test_refresh_rejects_local_url_rewrite_configuration(tmp_path: Path) -> None:
    remote, knowledge_root, revision = create_checkout(tmp_path)
    origin_url = git(knowledge_root, "config", "--get", "remote.origin.url")
    git(
        knowledge_root,
        "config",
        "--add",
        f"url.{remote.as_posix()}.insteadOf",
        origin_url,
    )
    result = run_resolver(
        knowledge_root,
        "--mode",
        "read-only",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=build_env(tmp_path / "unsafe-local-config", include_gh=True),
    )

    assert result.returncode == 0, result.stderr
    payload = resolver_json(result)
    assert payload["revision"] == revision
    assert payload["refresh_state"] == "unavailable"
    assert "unsafe local Git configuration" in payload["limitations"][0]
    write_result = run_resolver(
        knowledge_root,
        "--mode",
        "write",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=build_env(tmp_path / "unsafe-write-config", include_gh=True),
    )
    assert_failure(write_result, "unsafe local Git configuration")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("core.fsmonitor", "true"),
        ("core.hooksPath", "hooks"),
        ("credential.helper", "!true"),
        ("filter.untrusted.clean", "true"),
    ],
)
def test_refresh_rejects_local_configuration_with_execution_effects(
    tmp_path: Path,
    key: str,
    value: str,
) -> None:
    _remote, knowledge_root, _revision = create_checkout(tmp_path)
    git(knowledge_root, "config", key, value)

    with pytest.raises(RuntimeError, match="unsafe local Git configuration"):
        resolver.require_safe_local_git_configuration(knowledge_root)


def test_write_mode_rejects_a_local_revision_ahead_of_upstream(
    tmp_path: Path,
) -> None:
    remote, knowledge_root, _revision = create_checkout(tmp_path)
    (knowledge_root / "skill.md").write_text("base\nlocal\n", encoding="utf-8")
    git(
        knowledge_root,
        "-c",
        "user.name=Athena Tests",
        "-c",
        "user.email=athena-tests@example.invalid",
        "commit",
        "--quiet",
        "-am",
        "test: local ahead",
    )
    local_revision = git(knowledge_root, "rev-parse", "HEAD")
    result = run_resolver(
        knowledge_root,
        "--mode",
        "write",
        "--knowledge-root",
        str(knowledge_root),
        "--json",
        env=build_env(
            tmp_path / "local-ahead",
            include_gh=True,
            git_fetch_remote=remote,
        ),
    )

    assert_failure(result, "not an ancestor of the upstream revision")
    assert git(knowledge_root, "rev-parse", "HEAD") == local_revision


def test_direct_script_bootstraps_from_an_opencode_skill_layout(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "skills" / "athena"
    staged_script = skill_root / "advise" / "scripts" / SCRIPT.name
    staged_script.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "skills" / "_cli.py", skill_root / "_cli.py")
    shutil.copy2(SCRIPT, staged_script)

    result = subprocess.run(
        [sys.executable, str(staged_script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Resolve a trusted Mnemosyne checkout" in result.stdout


def test_skill_commands_use_the_installed_resolver_path() -> None:
    repo_relative = "skills/advise/scripts/resolve_knowledge_checkout.py"
    installed = (
        "<installed-advise-skill-directory>/scripts/resolve_knowledge_checkout.py"
    )
    for relative_path in ("skills/advise/SKILL.md", "skills/learn/SKILL.md"):
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert repo_relative not in content
        assert installed in content


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


def test_write_mode_requires_refresh_and_fails_on_gh_timeout(
    tmp_path: Path,
) -> None:
    _remote, knowledge_root, _revision = create_checkout(tmp_path)
    env = build_env(
        tmp_path / "write-gh-timeout",
        include_gh=True,
        auth_sleep_seconds=4,
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

    assert_failure(result, "timed out")


def test_write_mode_requires_refresh_and_uses_the_updated_revision(
    tmp_path: Path,
) -> None:
    remote, knowledge_root, revision = create_checkout(tmp_path)
    updated_revision = push_followup_commit(tmp_path, remote)
    env = build_env(
        tmp_path / "write-refresh-success",
        include_gh=True,
        git_fetch_remote=remote,
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

    assert result.returncode == 0, result.stderr
    payload = resolver_json(result)
    assert payload["revision"] == updated_revision
    assert payload["local_revision"] == revision
    assert payload["refresh_state"] == "updated"


def test_local_filesystem_origin_fails(tmp_path: Path) -> None:
    _remote, knowledge_root, _revision = create_checkout(tmp_path)
    git(
        knowledge_root,
        "remote",
        "set-url",
        "origin",
        str(tmp_path / "HomericIntelligence" / ("Mnemosyne" + ".git")),
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

    assert_failure(result, "trusted GitHub repository URL")


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


def test_resolver_module_defensive_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover defensive branches that the process tests do not reach."""
    monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *_: None)
    with pytest.raises(RuntimeError, match="CLI helper is unavailable"):
        resolver._load_installed_cli_module()
    remote, knowledge_root, revision = create_checkout(tmp_path)
    checkout = resolver.validate_local_checkout(knowledge_root)
    assert checkout.revision == revision

    monkeypatch.delenv("HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER", raising=False)
    assert resolver.expected_repository() == "HomericIntelligence/Mnemosyne"
    monkeypatch.setenv("HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER", "HomericIntelligence")
    assert resolver.expected_repository() == "HomericIntelligence/Mnemosyne"
    monkeypatch.setenv("HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER", "bad owner")
    with pytest.raises(RuntimeError):
        resolver.expected_repository()
    monkeypatch.delenv("HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER", raising=False)

    for origin in [
        "http://github.com/" + "HomericIntelligence/" + "Mnemosyne.git",
        "https://example.com/" + "HomericIntelligence/" + "Mnemosyne.git",
        "git@github.com:" + "HomericIntelligence/" + "Other.git",
        "git@github.com:" + "bad owner/" + "Mnemosyne.git",
    ]:
        with pytest.raises(RuntimeError):
            resolver.repository_from_origin(origin)

    assert (
        resolver.repository_from_origin(
            "ssh://git@github.com/" + "HomericIntelligence/" + "Mnemosyne.git"
        )
        == "HomericIntelligence/Mnemosyne"
    )

    assert (
        resolver.parse_repo_view(
            json.dumps(
                {
                    "defaultBranchRef": {"name": "main"},
                    "nameWithOwner": "HomericIntelligence/" + "Mnemosyne",
                }
            ),
            "HomericIntelligence/Mnemosyne",
        )
        == "main"
    )
    with pytest.raises(json.JSONDecodeError):
        resolver.parse_repo_view("{", "HomericIntelligence/Mnemosyne")
    with pytest.raises(TypeError):
        resolver.parse_repo_view(json.dumps([]), "HomericIntelligence/Mnemosyne")
    with pytest.raises(TypeError):
        resolver.parse_repo_view(
            json.dumps({"nameWithOwner": "HomericIntelligence/" + "Mnemosyne"}),
            "HomericIntelligence/Mnemosyne",
        )
    with pytest.raises(TypeError):
        resolver.parse_repo_view(
            json.dumps({"defaultBranchRef": {}}),
            "HomericIntelligence/Mnemosyne",
        )

    missing_root = tmp_path / "missing"
    with pytest.raises(RuntimeError):
        resolver.validate_local_checkout(missing_root)

    nested_root = knowledge_root / "nested"
    nested_root.mkdir()
    with pytest.raises(RuntimeError):
        resolver.validate_local_checkout(nested_root)

    dirty_root = tmp_path / "dirty"
    git(tmp_path, "clone", "--quiet", str(remote), str(dirty_root))
    (dirty_root / "skill.md").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        resolver.validate_local_checkout(dirty_root)

    fake_root = tmp_path / "fake-root"
    fake_root.mkdir()

    def fake_git_text(_cwd: Path, *arguments: str) -> str:
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(fake_root)
        if arguments == ("config", "--get", "remote.origin.url"):
            return "https://github.com/" + "HomericIntelligence/" + "Mnemosyne.git"
        if arguments == ("rev-parse", "HEAD"):
            return "not-a-sha"
        if arguments == (
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ):
            return ""
        raise AssertionError(arguments)

    monkeypatch.setattr(resolver, "git_text", fake_git_text)
    monkeypatch.setattr(
        resolver,
        "run_git",
        lambda _cwd, *arguments, timeout=None: subprocess.CompletedProcess[str](
            args=["git", *arguments],
            returncode=0,
            stdout="main" if arguments[:1] == ("branch",) else "",
            stderr="",
        ),
    )
    with pytest.raises(RuntimeError):
        resolver.validate_local_checkout(fake_root)

    checkout = resolver.LocalCheckout(
        root=knowledge_root,
        repository="HomericIntelligence/Mnemosyne",
        origin="https://github.com/" + "HomericIntelligence/" + "Mnemosyne.git",
        branch=None,
        revision="a" * 40,
    )
    monkeypatch.setattr(
        "skills.advise.scripts.resolve_knowledge_checkout.shutil.which",
        lambda _name: "/usr/bin/gh",
    )
    monkeypatch.setattr(
        resolver,
        "gh_command",
        lambda *arguments: subprocess.CompletedProcess[str](
            args=["gh", *arguments],
            returncode=0,
            stdout=json.dumps(
                {
                    "defaultBranchRef": {"name": "main"},
                    "nameWithOwner": "HomericIntelligence/Mnemosyne",
                }
            ),
            stderr="",
        ),
    )
    outcome = resolver.refresh_local_checkout(
        checkout, "HomericIntelligence/Mnemosyne", "read-only"
    )
    assert outcome.refresh_state == "unavailable"


def test_resolver_module_error_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover the remaining resolver error branches directly."""
    fake_root = tmp_path / "fake-root"
    fake_root.mkdir()
    original_run_git = resolver.run_git
    original_git_text = resolver.git_text

    def dirty_git_text(_cwd: Path, *arguments: str) -> str:
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(fake_root)
        if arguments == ("config", "--get", "remote.origin.url"):
            return "https://github.com/" + "HomericIntelligence/" + "Mnemosyne.git"
        if arguments == ("rev-parse", "HEAD"):
            return "c" * 40
        if arguments == (
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ):
            return " M skill.md"
        raise AssertionError(arguments)

    monkeypatch.setattr(resolver, "git_text", dirty_git_text)
    monkeypatch.setattr(
        resolver,
        "run_git",
        lambda _cwd, *arguments, timeout=None: subprocess.CompletedProcess[str](
            args=["git", *arguments],
            returncode=0,
            stdout="main" if arguments[:1] == ("branch",) else "",
            stderr="",
        ),
    )
    with pytest.raises(RuntimeError, match="dirty"):
        resolver.validate_local_checkout(fake_root)

    def branch_failure_run_git(
        _cwd: Path, *arguments: str, timeout: float | None = None
    ) -> subprocess.CompletedProcess[str]:
        del timeout
        if arguments[:2] == ("branch", "--show-current"):
            return subprocess.CompletedProcess[str](
                args=["git", *arguments],
                returncode=1,
                stdout="",
                stderr="branch unavailable",
            )
        return subprocess.CompletedProcess[str](
            args=["git", *arguments],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        resolver,
        "git_text",
        lambda _cwd, *arguments: {
            ("rev-parse", "--show-toplevel"): str(fake_root),
            ("config", "--get", "remote.origin.url"): (
                "https://github.com/" + "HomericIntelligence/" + "Mnemosyne.git"
            ),
            ("rev-parse", "HEAD"): "d" * 40,
            ("status", "--porcelain=v1", "--untracked-files=all"): "",
        }[arguments],
    )
    monkeypatch.setattr(resolver, "run_git", branch_failure_run_git)
    with pytest.raises(RuntimeError, match="branch unavailable"):
        resolver.validate_local_checkout(fake_root)

    def timeout_run_command(
        *_arguments: object, timeout: float | None = None, **_kwargs: object
    ) -> None:
        raise subprocess.TimeoutExpired(
            cmd=["tool"], timeout=timeout if timeout is not None else 0.0
        )

    monkeypatch.setattr(resolver, "run_git", original_run_git)
    monkeypatch.setattr(resolver, "run_command", timeout_run_command)
    with pytest.raises(RuntimeError, match="timed out"):
        resolver.gh_command("auth", "status")
    with pytest.raises(RuntimeError, match="timed out"):
        resolver.run_git(fake_root, "fetch", "origin", "main", timeout=1.5)

    monkeypatch.setattr(
        resolver,
        "run_git",
        lambda _cwd, *arguments, timeout=None: subprocess.CompletedProcess[str](
            args=["git", *arguments],
            returncode=1,
            stdout="",
            stderr="git failed",
        ),
    )
    monkeypatch.setattr(resolver, "git_text", original_git_text)
    with pytest.raises(RuntimeError, match="git failed"):
        resolver.git_text(fake_root, "rev-parse", "HEAD")

    with pytest.raises(RuntimeError, match="different repository"):
        resolver.parse_repo_view(
            json.dumps(
                {
                    "defaultBranchRef": {"name": "main"},
                    "nameWithOwner": "Other/Repo",
                }
            ),
            "HomericIntelligence/Mnemosyne",
        )

    checkout = resolver.LocalCheckout(
        root=fake_root,
        repository="HomericIntelligence/Mnemosyne",
        origin="https://github.com/" + "HomericIntelligence/" + "Mnemosyne.git",
        branch="main",
        revision="e" * 40,
    )

    def auth_timeout(*_arguments: str) -> subprocess.CompletedProcess[str]:
        raise RuntimeError("auth timed out")

    monkeypatch.setattr(
        "skills.advise.scripts.resolve_knowledge_checkout.shutil.which",
        lambda _name: "/usr/bin/gh",
    )
    monkeypatch.setattr(resolver, "gh_command", auth_timeout)
    outcome = resolver.refresh_local_checkout(
        checkout, "HomericIntelligence/Mnemosyne", "read-only"
    )
    assert outcome.refresh_state == "unavailable"

    responses: Iterator[subprocess.CompletedProcess[str] | RuntimeError] = iter(
        [
            subprocess.CompletedProcess[str](
                args=["gh", "auth", "status"],
                returncode=0,
                stdout="github.com\n  ✓ Logged in to github.com as fake-user",
                stderr="",
            ),
            RuntimeError("repository lookup timed out"),
        ]
    )

    def discovery_timeout(*_arguments: str) -> subprocess.CompletedProcess[str]:
        value = next(responses)
        if isinstance(value, RuntimeError):
            raise value
        return value

    monkeypatch.setattr(resolver, "gh_command", discovery_timeout)
    outcome = resolver.refresh_local_checkout(
        checkout, "HomericIntelligence/Mnemosyne", "read-only"
    )
    assert outcome.refresh_state == "unavailable"

    monkeypatch.setattr(
        resolver,
        "gh_command",
        lambda *arguments: subprocess.CompletedProcess[str](
            args=["gh", *arguments],
            returncode=0,
            stdout=json.dumps(
                {
                    "defaultBranchRef": {"name": "main"},
                    "nameWithOwner": "HomericIntelligence/Mnemosyne",
                }
            ),
            stderr="",
        ),
    )
    monkeypatch.setattr(
        resolver,
        "parse_repo_view",
        lambda _output, _expected: (_ for _ in ()).throw(
            json.JSONDecodeError("bad", "", 0)
        ),
    )
    outcome = resolver.refresh_local_checkout(
        checkout, "HomericIntelligence/Mnemosyne", "read-only"
    )
    assert outcome.refresh_state == "unavailable"

    monkeypatch.setattr(resolver, "parse_repo_view", lambda _output, _expected: "main")
    monkeypatch.setattr(
        resolver,
        "run_git",
        lambda _cwd, *arguments, timeout=None: (
            subprocess.CompletedProcess[str](
                args=["git", *arguments],
                returncode=0,
                stdout="main" if arguments[:1] == ("branch",) else "",
                stderr="",
            )
            if arguments[:1] != ("fetch",)
            else subprocess.CompletedProcess[str](
                args=["git", *arguments],
                returncode=1,
                stdout="",
                stderr="fetch failed",
            )
        ),
    )
    outcome = resolver.refresh_local_checkout(
        checkout, "HomericIntelligence/Mnemosyne", "read-only"
    )
    assert outcome.refresh_state == "unavailable"

    monkeypatch.setattr(
        resolver,
        "run_git",
        lambda _cwd, *arguments, timeout=None: (
            subprocess.CompletedProcess[str](
                args=["git", *arguments],
                returncode=0,
                stdout="main" if arguments[:1] == ("branch",) else "",
                stderr="",
            )
            if arguments[:1] not in {("fetch",), ("merge",)}
            else subprocess.CompletedProcess[str](
                args=["git", *arguments],
                returncode=1,
                stdout="",
                stderr="merge failed",
            )
        ),
    )
    outcome = resolver.refresh_local_checkout(
        checkout, "HomericIntelligence/Mnemosyne", "read-only"
    )
    assert outcome.refresh_state == "unavailable"

    monkeypatch.setattr(
        resolver,
        "expected_repository",
        lambda: "Other/Mnemosyne",
    )
    with pytest.raises(RuntimeError, match="does not match"):
        resolver.resolve_knowledge_checkout(fake_root, "read-only")

    monkeypatch.setattr(
        resolver,
        "resolve_knowledge_checkout",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(SystemExit):
        resolver.main(["--mode", "read-only", "--knowledge-root", str(fake_root)])
    assert (
        resolver.main(
            [
                "--mode",
                "read-only",
                "--knowledge-root",
                str(fake_root),
                "--json",
            ]
        )
        == 1
    )
