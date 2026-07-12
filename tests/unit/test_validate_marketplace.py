"""Smoke tests for athena.validate_marketplace.

These tests cover the canonical failure modes the validator claims to detect:
the rename-forget case (marketplace references skills/<name>/ but the
directory is missing), the missing-SKILL.md case, the missing-frontmatter
case, and the duplicate-name case. They use a tmp_path fixture so they
can run without touching the real repo tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from athena.validate_marketplace import validate


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Build a minimal fake repo: marketplace.json + one valid skill."""
    repo = tmp_path

    plugin_dir = repo / ".claude-plugin"
    plugin_dir.mkdir()
    skills_dir = repo / "skills"
    skills_dir.mkdir()

    # Real skill: skills/example/SKILL.md with matching frontmatter name.
    example_dir = skills_dir / "example"
    example_dir.mkdir()
    (example_dir / "SKILL.md").write_text(
        "---\nname: example\ndescription: |\n  Example skill\n---\n# Example\n",
        encoding="utf-8",
    )

    marketplace = {
        "name": "Athena",
        "owner": {"name": "Micah Villmow", "email": "research@villmow.us"},
        "plugins": [
            {"name": "example", "source": "./", "description": "Example skill"},
        ],
    }
    (plugin_dir / "marketplace.json").write_text(
        json.dumps(marketplace), encoding="utf-8"
    )

    # Patch the validator's module-level path constants to point at this
    # fake repo. We mutate the module rather than refactoring for DI so
    # the test stays short.
    import athena.validate_marketplace as vmod

    vmod.MARKETPLACE_PATH = plugin_dir / "marketplace.json"
    vmod.SKILLS_DIR = skills_dir
    return repo


def test_happy_path(fake_repo: Path) -> None:
    """When marketplace matches skills/, validate() returns no errors."""
    assert validate() == []


def test_rename_forget(fake_repo: Path) -> None:
    """Marketplace references a skill folder that does not exist."""
    import athena.validate_marketplace as vmod

    marketplace = json.loads(vmod.MARKETPLACE_PATH.read_text(encoding="utf-8"))
    marketplace["plugins"].append(
        {"name": "ghost-skill", "source": "./", "description": "Does not exist"}
    )
    vmod.MARKETPLACE_PATH.write_text(json.dumps(marketplace), encoding="utf-8")
    errors = validate()
    assert len(errors) == 1
    assert errors[0].plugin_name == "ghost-skill"
    assert "does not exist" in errors[0].reason


def test_missing_skill_md(fake_repo: Path) -> None:
    """skills/<name>/ exists but SKILL.md is missing."""
    import athena.validate_marketplace as vmod

    skills_dir = vmod.SKILLS_DIR
    broken_dir = skills_dir / "broken"
    broken_dir.mkdir()
    # Note: NO SKILL.md inside.
    marketplace = json.loads(vmod.MARKETPLACE_PATH.read_text(encoding="utf-8"))
    marketplace["plugins"].append(
        {"name": "broken", "source": "./", "description": "Missing SKILL.md"}
    )
    vmod.MARKETPLACE_PATH.write_text(json.dumps(marketplace), encoding="utf-8")
    errors = validate()
    assert any(
        e.plugin_name == "broken" and "SKILL.md" in e.reason for e in errors
    )


def test_missing_frontmatter_name(fake_repo: Path) -> None:
    """SKILL.md exists but frontmatter has no `name` field."""
    import athena.validate_marketplace as vmod

    skills_dir = vmod.SKILLS_DIR
    no_name_dir = skills_dir / "no-name"
    no_name_dir.mkdir()
    (no_name_dir / "SKILL.md").write_text(
        "---\ndescription: No name field\n---\n# Body\n",
        encoding="utf-8",
    )
    marketplace = json.loads(vmod.MARKETPLACE_PATH.read_text(encoding="utf-8"))
    marketplace["plugins"].append(
        {"name": "no-name", "source": "./", "description": "No frontmatter name"}
    )
    vmod.MARKETPLACE_PATH.write_text(json.dumps(marketplace), encoding="utf-8")
    errors = validate()
    assert any(
        e.plugin_name == "no-name" and "frontmatter" in e.reason for e in errors
    )


def test_duplicate_plugin_name(fake_repo: Path) -> None:
    """Two marketplace entries with the same name produce a duplicate error."""
    import athena.validate_marketplace as vmod

    marketplace = json.loads(vmod.MARKETPLACE_PATH.read_text(encoding="utf-8"))
    marketplace["plugins"].append(
        {"name": "example", "source": "./", "description": "Duplicate of example"}
    )
    vmod.MARKETPLACE_PATH.write_text(json.dumps(marketplace), encoding="utf-8")
    errors = validate()
    assert any(
        e.plugin_name == "example" and "duplicate" in e.reason for e in errors
    )
