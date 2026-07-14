#!/usr/bin/env python3
"""Validate Athena's plugin-only distribution using the Python standard library."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent

ALLOWED_ECOSYSTEM_REPOSITORIES = {"Athena", "Hephaestus", "Mnemosyne"}
ECOSYSTEM_REPOSITORY = re.compile(
    r"\bHomericIntelligence/([A-Za-z0-9_.-]+)\b", re.IGNORECASE
)
ALLOWED_ECOSYSTEM_REPOSITORY_KEYS = {
    repository.casefold() for repository in ALLOWED_ECOSYSTEM_REPOSITORIES
}


class ValidationError(NamedTuple):
    """One actionable distribution failure."""

    surface: str
    reason: str


def _read_json(
    path: Path, surface: str, repo_root: Path = REPO_ROOT
) -> tuple[dict[str, object] | None, list[ValidationError]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [
            ValidationError(
                surface, f"cannot read {path.relative_to(repo_root)}: {exc}"
            )
        ]
    if not isinstance(data, dict):
        return None, [
            ValidationError(
                surface, f"{path.relative_to(repo_root)} must be a JSON object"
            )
        ]
    return data, []


def _frontmatter_name(text: str) -> str | None:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.DOTALL)
    if match is None:
        return None
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            return value.strip().strip("\"'") or None
    return None


def _validate_skills(repo_root: Path = REPO_ROOT) -> list[ValidationError]:
    errors: list[ValidationError] = []
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        return [ValidationError("skills", "skills/ directory is missing")]

    seen: set[str] = set()
    skill_dirs = sorted(path for path in skills_dir.iterdir() if path.is_dir())
    if not skill_dirs:
        return [ValidationError("skills", "skills/ contains no discoverable skills")]

    for directory in skill_dirs:
        if directory.name.startswith("_"):
            errors.append(
                ValidationError(
                    "skills", f"private skill directory is forbidden: {directory.name}"
                )
            )
            continue
        skill_file = directory / "SKILL.md"
        try:
            text = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(
                ValidationError(
                    "skills", f"cannot read skills/{directory.name}/SKILL.md: {exc}"
                )
            )
            continue
        name = _frontmatter_name(text)
        if name != directory.name:
            errors.append(
                ValidationError(
                    "skills",
                    f"directory '{directory.name}' does not match frontmatter name '{name}'",
                )
            )
        if name in seen:
            errors.append(ValidationError("skills", f"duplicate skill name: {name}"))
        if name is not None:
            seen.add(name)

    return errors


def _validate_claude(repo_root: Path = REPO_ROOT) -> list[ValidationError]:
    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    manifest_path = repo_root / ".claude-plugin" / "plugin.json"
    marketplace, errors = _read_json(marketplace_path, "claude", repo_root)
    manifest, manifest_errors = _read_json(manifest_path, "claude", repo_root)
    errors.extend(manifest_errors)
    if marketplace is None or manifest is None:
        return errors
    plugins = marketplace.get("plugins")
    if (
        not isinstance(plugins, list)
        or len(plugins) != 1
        or not isinstance(plugins[0], dict)
    ):
        return [
            *errors,
            ValidationError("claude", "marketplace must expose exactly one plugin"),
        ]
    entry = plugins[0]
    if entry.get("name") != "athena" or entry.get("source") != "./":
        errors.append(
            ValidationError("claude", "plugin must be named 'athena' with source './'")
        )
    if manifest.get("name") != "athena" or manifest.get("skills") != "./skills/":
        errors.append(
            ValidationError(
                "claude", "root manifest must name 'athena' and load './skills/'"
            )
        )
    metadata = marketplace.get("metadata")
    marketplace_version = (
        metadata.get("version") if isinstance(metadata, dict) else None
    )
    if marketplace_version != manifest.get("version"):
        errors.append(
            ValidationError(
                "version", "Claude marketplace and manifest versions differ"
            )
        )
    return errors


def _validate_codex(repo_root: Path = REPO_ROOT) -> list[ValidationError]:
    marketplace_path = repo_root / ".agents" / "plugins" / "marketplace.json"
    manifest_path = repo_root / ".codex-plugin" / "plugin.json"
    marketplace, errors = _read_json(marketplace_path, "codex", repo_root)
    manifest, manifest_errors = _read_json(manifest_path, "codex", repo_root)
    errors.extend(manifest_errors)
    if marketplace is None or manifest is None:
        return errors
    plugins = marketplace.get("plugins")
    if (
        not isinstance(plugins, list)
        or len(plugins) != 1
        or not isinstance(plugins[0], dict)
    ):
        return [
            *errors,
            ValidationError("codex", "marketplace must expose exactly one plugin"),
        ]
    entry = plugins[0]
    if entry.get("name") != "athena" or entry.get("source") != {
        "source": "local",
        "path": "./",
    }:
        errors.append(
            ValidationError(
                "codex", "plugin must be named 'athena' with local source './'"
            )
        )
    if manifest.get("name") != "athena" or manifest.get("skills") != "./skills/":
        errors.append(
            ValidationError(
                "codex", "root manifest must name 'athena' and load './skills/'"
            )
        )
    version = manifest.get("version")
    if (
        not isinstance(version, str)
        or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None
    ):
        errors.append(
            ValidationError("version", "Codex manifest version must be semantic X.Y.Z")
        )
    return errors


def _validate_layout_and_policy(repo_root: Path = REPO_ROOT) -> list[ValidationError]:
    errors: list[ValidationError] = []
    forbidden_paths = ("athena", "pyproject.toml", "plugins/athena", "CODEOWNERS")
    for relative in forbidden_paths:
        if (repo_root / relative).exists():
            errors.append(
                ValidationError(
                    "layout", f"obsolete distribution path exists: {relative}"
                )
            )
    required_paths = (
        ".github/CODEOWNERS",
        ".github/workflows/_required.yml",
        ".github/workflows/release.yml",
        "docs/policies/development.md",
        "docs/policies/evidence-integrity.md",
        "docs/policies/required-checks.md",
    )
    for relative in required_paths:
        if not (repo_root / relative).is_file():
            errors.append(
                ValidationError("policy", f"required file is missing: {relative}")
            )

    ignored_parts = {
        ".git",
        ".mypy_cache",
        ".pixi",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "dist",
    }
    for path in repo_root.rglob("*"):
        if (
            not path.is_file()
            or path.name.startswith(".coverage")
            or any(part in ignored_parts for part in path.parts)
        ):
            continue
        if path.relative_to(repo_root).as_posix() == "scripts/validate_skills.py":
            continue
        if path.suffix.lower() in {
            ".gif",
            ".ico",
            ".jpeg",
            ".jpg",
            ".png",
            ".pyc",
            ".webp",
        }:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(
                ValidationError(
                    "self-contained",
                    f"cannot inspect {path.relative_to(repo_root)}: {exc}",
                )
            )
            continue
        for match in ECOSYSTEM_REPOSITORY.finditer(text):
            repository = match.group(1)
            if repository.casefold() not in ALLOWED_ECOSYSTEM_REPOSITORY_KEYS:
                errors.append(
                    ValidationError(
                        "self-contained",
                        f"{path.relative_to(repo_root)} references forbidden repository '{match.group(0)}'",
                    )
                )
        project_prefix = re.search(r"\bProject[A-Z][A-Za-z0-9_-]*\b", text)
        if project_prefix is not None:
            errors.append(
                ValidationError(
                    "self-contained",
                    f"{path.relative_to(repo_root)} uses forbidden Project prefix '{project_prefix.group(0)}'",
                )
            )
    return errors


def validate_repository(repo_root: Path) -> list[ValidationError]:
    """Validate one repository's skills, manifests, layout, and policies."""
    repo_root = repo_root.resolve()
    errors = [
        *_validate_skills(repo_root),
        *_validate_claude(repo_root),
        *_validate_codex(repo_root),
        *_validate_layout_and_policy(repo_root),
    ]
    claude, _ = _read_json(
        repo_root / ".claude-plugin" / "plugin.json", "version", repo_root
    )
    codex, _ = _read_json(
        repo_root / ".codex-plugin" / "plugin.json", "version", repo_root
    )
    if (
        claude is not None
        and codex is not None
        and claude.get("version") != codex.get("version")
    ):
        errors.append(
            ValidationError("version", "Claude and Codex manifest versions differ")
        )
    return errors


def validate() -> list[ValidationError]:
    """Validate the Athena checkout containing this script."""
    return validate_repository(REPO_ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Athena's plugin-only distribution."
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress success output.")
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to validate (defaults to this checkout).",
    )
    args = parser.parse_args(argv)
    errors = validate_repository(args.root)
    if errors:
        print("Athena skill validation FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error.surface}: {error.reason}", file=sys.stderr)
        return 2
    if not args.quiet:
        print("Athena skill validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
