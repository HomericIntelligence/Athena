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
SKILLS_DIR = REPO_ROOT / "skills"
CLAUDE_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CLAUDE_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
CODEX_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CODEX_MANIFEST = REPO_ROOT / ".codex-plugin" / "plugin.json"

KNOWLEDGE_SKILLS = {"advise", "learn"}
AUTOMATION_SKILLS = {
    "create-reusable-utilities",
    "finish-branch",
    "github-actions-python-cicd",
    "python-repo-modernization",
    "tidy",
}
FORBIDDEN_ECOSYSTEM_REFERENCES = {
    "Odysseus",
    "Scylla",
    "Charybdis",
    "Keystone",
    "Telemachy",
    "Agamemnon",
    "Nestor",
    "Proteus",
    "Argus",
    "Hermes",
    "AchaeanFleet",
    "Odyssey",
}


class ValidationError(NamedTuple):
    """One actionable distribution failure."""

    surface: str
    reason: str


def _read_json(path: Path, surface: str) -> tuple[dict[str, object] | None, list[ValidationError]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [ValidationError(surface, f"cannot read {path.relative_to(REPO_ROOT)}: {exc}")]
    if not isinstance(data, dict):
        return None, [ValidationError(surface, f"{path.relative_to(REPO_ROOT)} must be a JSON object")]
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


def _validate_skills() -> list[ValidationError]:
    errors: list[ValidationError] = []
    if not SKILLS_DIR.is_dir():
        return [ValidationError("skills", "skills/ directory is missing")]

    seen: set[str] = set()
    skill_dirs = sorted(path for path in SKILLS_DIR.iterdir() if path.is_dir())
    if not skill_dirs:
        return [ValidationError("skills", "skills/ contains no discoverable skills")]

    for directory in skill_dirs:
        if directory.name.startswith("_"):
            errors.append(ValidationError("skills", f"private skill directory is forbidden: {directory.name}"))
            continue
        skill_file = directory / "SKILL.md"
        try:
            text = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(ValidationError("skills", f"cannot read skills/{directory.name}/SKILL.md: {exc}"))
            continue
        name = _frontmatter_name(text)
        if name != directory.name:
            errors.append(ValidationError("skills", f"directory '{directory.name}' does not match frontmatter name '{name}'"))
        if name in seen:
            errors.append(ValidationError("skills", f"duplicate skill name: {name}"))
        if name is not None:
            seen.add(name)

        if directory.name in KNOWLEDGE_SKILLS:
            for required in ("HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER", ".agent_brain/knowledge"):
                if required not in text:
                    errors.append(ValidationError("knowledge", f"{directory.name} is missing required contract '{required}'"))
        if directory.name in AUTOMATION_SKILLS:
            for required in ("HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER", ".agent_brain/automation"):
                if required not in text:
                    errors.append(ValidationError("automation", f"{directory.name} is missing required contract '{required}'"))

    return errors


def _validate_claude() -> list[ValidationError]:
    marketplace, errors = _read_json(CLAUDE_MARKETPLACE, "claude")
    manifest, manifest_errors = _read_json(CLAUDE_MANIFEST, "claude")
    errors.extend(manifest_errors)
    if marketplace is None or manifest is None:
        return errors
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        return [*errors, ValidationError("claude", "marketplace must expose exactly one plugin")]
    entry = plugins[0]
    if entry.get("name") != "athena" or entry.get("source") != "./":
        errors.append(ValidationError("claude", "plugin must be named 'athena' with source './'"))
    if manifest.get("name") != "athena" or manifest.get("skills") != "./skills/":
        errors.append(ValidationError("claude", "root manifest must name 'athena' and load './skills/'"))
    metadata = marketplace.get("metadata")
    marketplace_version = metadata.get("version") if isinstance(metadata, dict) else None
    if marketplace_version != manifest.get("version"):
        errors.append(ValidationError("version", "Claude marketplace and manifest versions differ"))
    return errors


def _validate_codex() -> list[ValidationError]:
    marketplace, errors = _read_json(CODEX_MARKETPLACE, "codex")
    manifest, manifest_errors = _read_json(CODEX_MANIFEST, "codex")
    errors.extend(manifest_errors)
    if marketplace is None or manifest is None:
        return errors
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        return [*errors, ValidationError("codex", "marketplace must expose exactly one plugin")]
    entry = plugins[0]
    if entry.get("name") != "athena" or entry.get("source") != {"source": "local", "path": "./"}:
        errors.append(ValidationError("codex", "plugin must be named 'athena' with local source './'"))
    if manifest.get("name") != "athena" or manifest.get("skills") != "./skills/":
        errors.append(ValidationError("codex", "root manifest must name 'athena' and load './skills/'"))
    version = manifest.get("version")
    if not isinstance(version, str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
        errors.append(ValidationError("version", "Codex manifest version must be semantic X.Y.Z"))
    return errors


def _validate_layout_and_policy() -> list[ValidationError]:
    errors: list[ValidationError] = []
    forbidden_paths = ("athena", "pyproject.toml", "plugins/athena", "CODEOWNERS")
    for relative in forbidden_paths:
        if (REPO_ROOT / relative).exists():
            errors.append(ValidationError("layout", f"obsolete distribution path exists: {relative}"))
    required_paths = (
        ".github/CODEOWNERS",
        ".github/workflows/_required.yml",
        ".github/workflows/release.yml",
        "docs/policies/development.md",
        "docs/policies/evidence-integrity.md",
        "docs/policies/required-checks.md",
    )
    for relative in required_paths:
        if not (REPO_ROOT / relative).is_file():
            errors.append(ValidationError("policy", f"required file is missing: {relative}"))

    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", ".pixi", "dist", "build"} for part in path.parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for name in FORBIDDEN_ECOSYSTEM_REFERENCES:
            if name in text:
                errors.append(ValidationError("self-contained", f"{path.relative_to(REPO_ROOT)} references forbidden repository '{name}'"))
    return errors


def validate() -> list[ValidationError]:
    """Validate skills, host manifests, layout, and self-contained policy."""
    errors = [*_validate_skills(), *_validate_claude(), *_validate_codex(), *_validate_layout_and_policy()]
    claude, _ = _read_json(CLAUDE_MANIFEST, "version")
    codex, _ = _read_json(CODEX_MANIFEST, "version")
    if claude is not None and codex is not None and claude.get("version") != codex.get("version"):
        errors.append(ValidationError("version", "Claude and Codex manifest versions differ"))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Athena's plugin-only distribution.")
    parser.add_argument("--quiet", action="store_true", help="Suppress success output.")
    args = parser.parse_args(argv)
    errors = validate()
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
