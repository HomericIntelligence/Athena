"""Test that local pre-commit hooks delegate to justfile recipes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).parents[2]


def load_precommit_config() -> dict[str, Any]:
    """Load the repository pre-commit configuration."""
    config = yaml.safe_load(
        (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(config, dict)
    return config


def local_hooks(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the hooks from the local pre-commit repository."""
    for repository in config["repos"]:
        if repository["repo"] == "local":
            hooks = repository["hooks"]
            assert isinstance(hooks, list)
            return hooks
    raise AssertionError("the local pre-commit repository is missing")


def justfile_recipes() -> set[str]:
    """Return recipe names defined in the repository justfile."""
    recipe_pattern = re.compile(r"^([a-z][a-z0-9-]*)(?:\s+[^:]+)?\s*:\s*$")
    return {
        match.group(1)
        for line in (ROOT / "justfile").read_text(encoding="utf-8").splitlines()
        if (match := recipe_pattern.match(line))
    }


def test_local_hooks_delegate_to_existing_just_recipes() -> None:
    """Require every local hook to use a recipe defined in the justfile."""
    recipes = justfile_recipes()
    entries = [hook["entry"] for hook in local_hooks(load_precommit_config())]

    assert all(isinstance(entry, str) for entry in entries)
    delegated_recipes = {entry.removeprefix("just ") for entry in entries}
    assert all(entry.startswith("just ") for entry in entries)
    assert delegated_recipes <= recipes


def test_local_hooks_do_not_duplicate_tool_commands() -> None:
    """Prevent local hooks from defining tool commands outside the justfile."""
    entries = [hook["entry"] for hook in local_hooks(load_precommit_config())]
    inline_tools = ("uv run", "ruff", "mypy", "pymarkdown", "coverage")

    assert all(not any(tool in entry for tool in inline_tools) for entry in entries)


def test_precommit_hooks_repo_uses_a_full_commit_pin() -> None:
    """Keep the remote pre-commit hook repository pinned to a commit."""
    repositories = load_precommit_config()["repos"]
    precommit_repository = next(
        repository
        for repository in repositories
        if repository["repo"] == "https://github.com/pre-commit/pre-commit-hooks"
    )

    assert re.fullmatch(r"[0-9a-f]{40}", precommit_repository["rev"])
