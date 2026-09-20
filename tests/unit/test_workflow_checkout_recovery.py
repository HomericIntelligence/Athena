"""Behavior checks for local worktree and dependency recovery."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from skills.advise.scripts import resolve_knowledge_checkout as resolver
from tests.unit.test_knowledge_checkout_resolution import create_checkout, git

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/git-worktrees/scripts/prepare_worktree.py"


def test_default_worktree_uses_primary_project_and_ignores_directory(
    tmp_path: Path,
) -> None:
    _, primary, _ = create_checkout(tmp_path)
    linked = tmp_path / "existing-elsewhere"
    git(primary, "worktree", "add", "-b", "existing", str(linked))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "new-feature", "--start-point", "HEAD"],
        cwd=linked,
        capture_output=True,
        text=True,
        check=True,
    )
    target = primary / ".worktrees" / "new-feature"
    assert json.loads(result.stdout)["path"] == str(target)
    assert target.is_dir()
    assert git(primary, "check-ignore", str(target)) == str(target)
    assert git(primary, "status", "--porcelain") == ""


def test_default_worktree_dry_run_does_not_change_ignore_file(tmp_path: Path) -> None:
    _, primary, _ = create_checkout(tmp_path)
    exclude = primary / ".git/info/exclude"
    before = exclude.read_bytes()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "planned", "--start-point", "HEAD", "--dry-run"],
        cwd=primary,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["created"] is False
    assert exclude.read_bytes() == before
    assert not (primary / ".worktrees").exists()


def test_signing_and_identity_config_do_not_block_refresh_preparation(
    tmp_path: Path,
) -> None:
    _, checkout, _ = create_checkout(tmp_path)
    for key, value in (
        ("user.name", "Test User"),
        ("user.email", "test@example.invalid"),
        ("user.signingkey", "test-key"),
        ("commit.gpgsign", "true"),
        ("gpg.program", "/nonexistent/signer"),
    ):
        git(checkout, "config", key, value)
    resolver.require_safe_local_git_configuration(checkout)


def test_write_refresh_failure_keeps_local_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, checkout, revision = create_checkout(tmp_path)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = resolver.resolve_knowledge_checkout(checkout, "write")
    assert result["revision"] == revision
    assert result["refresh_state"] == "unavailable"
    assert result["refresh_verified"] is False
    assert result["limitations"]


def test_wrong_origin_is_preserved_while_correct_checkout_is_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, unexpected, _ = create_checkout(tmp_path / "unexpected")
    _, correct, revision = create_checkout(tmp_path / "correct")
    git(
        unexpected,
        "remote",
        "set-url",
        "origin",
        "https://github.com/Other/Mnemosyne.git",
    )
    before = git(unexpected, "rev-parse", "HEAD")
    monkeypatch.setattr(resolver, "prepare_separate_checkout", lambda expected: correct)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = resolver.resolve_knowledge_checkout(unexpected, "write")
    assert result["checkout"] == str(correct)
    assert result["revision"] == revision
    assert git(unexpected, "rev-parse", "HEAD") == before
    assert (
        git(unexpected, "remote", "get-url", "origin")
        == "https://github.com/Other/Mnemosyne.git"
    )


@pytest.mark.parametrize("occupied", [False, True])
def test_separate_dependency_clone_stays_under_primary_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, occupied: bool
) -> None:
    remote, primary, _ = create_checkout(tmp_path)
    linked = tmp_path / "existing"
    git(primary, "worktree", "add", "-b", "existing", str(linked))
    monkeypatch.chdir(linked)
    preferred = primary / ".worktrees" / "HomericIntelligence-Mnemosyne"
    if occupied:
        preferred.mkdir(parents=True)
        (preferred / "existing.txt").write_text("preserve this", encoding="utf-8")
    original_run_git = resolver.run_git

    def local_clone(
        cwd: Path, *arguments: str, timeout: float | None = None
    ) -> subprocess.CompletedProcess[str]:
        if arguments[:1] == ("clone",):
            target = arguments[-1]
            git(cwd, "clone", str(remote), target)
            git(Path(target), "remote", "set-url", "origin", arguments[-2])
            return subprocess.CompletedProcess(arguments, 0, "", "")
        return original_run_git(cwd, *arguments, timeout=timeout)

    monkeypatch.setattr(resolver, "run_git", local_clone)
    target = resolver.prepare_separate_checkout("HomericIntelligence/Mnemosyne")
    if occupied:
        assert target != preferred
        assert target.parent == preferred.parent
        assert (preferred / "existing.txt").read_text(
            encoding="utf-8"
        ) == "preserve this"
    else:
        assert target == preferred
    assert (
        resolver.validate_local_checkout(target).repository
        == "HomericIntelligence/Mnemosyne"
    )
    assert git(primary, "status", "--porcelain") == ""


@pytest.mark.parametrize("dirty_path", ["skill.md", "untracked.md"])
def test_dirty_expected_checkout_is_preserved_during_write_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dirty_path: str
) -> None:
    _, original, original_revision = create_checkout(tmp_path / "original")
    _, separate, separate_revision = create_checkout(tmp_path / "separate")
    dirty_file = original / dirty_path
    dirty_file.write_text("unfinished user work\n", encoding="utf-8")
    original_status = git(original, "status", "--porcelain=v1", "--untracked-files=all")
    monkeypatch.setattr(
        resolver, "prepare_separate_checkout", lambda expected: separate
    )
    monkeypatch.setattr(shutil, "which", lambda _: None)

    result = resolver.resolve_knowledge_checkout(original, "write")

    assert result["checkout"] == str(separate)
    assert result["revision"] == separate_revision
    assert result["refresh_verified"] is False
    assert git(original, "rev-parse", "HEAD") == original_revision
    assert (
        git(original, "status", "--porcelain=v1", "--untracked-files=all")
        == original_status
    )
    assert dirty_file.read_text(encoding="utf-8") == "unfinished user work\n"
    assert any(str(original) in item for item in result["limitations"])
