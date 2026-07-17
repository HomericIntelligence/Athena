#!/usr/bin/env python3
"""Validate Athena's plugin-only distribution using the Python standard library."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.semver import SEMVER_PATTERN  # noqa: E402
from skills._cli import argument_parser  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

ALLOWED_ECOSYSTEM_REPOSITORIES = {"Athena", "Hephaestus", "Mnemosyne"}
ECOSYSTEM_REPOSITORY = re.compile(
    r"\bHomericIntelligence/([A-Za-z0-9_.-]+)\b", re.IGNORECASE
)
ALLOWED_ECOSYSTEM_REPOSITORY_KEYS = {
    repository.casefold() for repository in ALLOWED_ECOSYSTEM_REPOSITORIES
}
REPO_REVIEW_SECTION = re.compile(
    r"^(?P<number>[1-9][0-9]*)\. \*\*(?P<name>[^*:]+):", re.MULTILINE
)
REPO_REVIEW_WEIGHT = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z/ ]*?) (?P<weight>[1-9][0-9]?)%"
)
APPROVED_MERGE_QUEUE_PARAMETERS: dict[str, object] = {
    "check_response_timeout_minutes": 60,
    "grouping_strategy": "ALLGREEN",
    "max_entries_to_build": 10,
    "max_entries_to_merge": 5,
    "merge_method": "SQUASH",
    "min_entries_to_merge": 1,
    "min_entries_to_merge_wait_minutes": 5,
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
        if directory.name == "__pycache__":
            continue
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
    if not isinstance(version, str) or SEMVER_PATTERN.fullmatch(version) is None:
        errors.append(
            ValidationError("version", "Codex manifest version must be valid SemVer")
        )
    return errors


def _validate_layout_and_policy(repo_root: Path = REPO_ROOT) -> list[ValidationError]:
    errors: list[ValidationError] = []
    forbidden_paths = ("athena", "plugins/athena", "CODEOWNERS")
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

    ignored_top_levels = {
        ".git",
        ".mypy_cache",
        ".venv",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
    }
    for path in repo_root.rglob("*"):
        relative_path = path.relative_to(repo_root)
        if (
            not path.is_file()
            or (path.parent == repo_root and path.name.startswith(".coverage"))
            or relative_path.parts[0] in ignored_top_levels
            or "__pycache__" in relative_path.parts
        ):
            continue
        if relative_path.as_posix() == "scripts/validate_skills.py":
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
                    f"cannot inspect {relative_path}: {exc}",
                )
            )
            continue
        for match in ECOSYSTEM_REPOSITORY.finditer(text):
            repository = match.group(1)
            if repository.casefold() not in ALLOWED_ECOSYSTEM_REPOSITORY_KEYS:
                errors.append(
                    ValidationError(
                        "self-contained",
                        f"{relative_path} references forbidden repository '{match.group(0)}'",
                    )
                )
        project_prefix = re.search(r"\bProject[A-Z][A-Za-z0-9_-]*\b", text)
        if project_prefix is not None:
            errors.append(
                ValidationError(
                    "self-contained",
                    f"{relative_path} uses forbidden Project prefix '{project_prefix.group(0)}'",
                )
            )
    return errors


def _validate_cli_conventions(repo_root: Path = REPO_ROOT) -> list[ValidationError]:
    """Require every executable Python helper to use the shared argparse factory."""
    candidates = [
        *(repo_root / "scripts").glob("*.py"),
        *(repo_root / "skills").glob("*/scripts/*.py"),
    ]
    errors: list[ValidationError] = []
    for path in sorted(candidates):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(
                ValidationError(
                    "cli", f"cannot read {path.relative_to(repo_root)}: {exc}"
                )
            )
            continue
        if not text.startswith("#!/usr/bin/env python3\n"):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            errors.append(
                ValidationError(
                    "cli", f"cannot parse {path.relative_to(repo_root)}: {exc}"
                )
            )
            continue
        factory_names = {
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "skills._cli"
            for alias in node.names
            if alias.name == "argument_parser"
        }
        parser_names = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id in factory_names
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        parses_arguments = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "parse_args"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in parser_names
            for node in ast.walk(tree)
        )
        argparse_module_names = {
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
            if alias.name == "argparse"
        }
        argparse_constructor_names = {
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "argparse"
            for alias in node.names
            if alias.name == "ArgumentParser"
        }
        constructs_argparse_directly = any(
            isinstance(node, ast.Call)
            and (
                (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "ArgumentParser"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in argparse_module_names
                )
                or (
                    isinstance(node.func, ast.Name)
                    and node.func.id in argparse_constructor_names
                )
            )
            for node in ast.walk(tree)
        )
        if constructs_argparse_directly:
            errors.append(
                ValidationError(
                    "cli",
                    f"{path.relative_to(repo_root)} must not construct "
                    "argparse.ArgumentParser directly",
                )
            )
        elif not factory_names or not parser_names or not parses_arguments:
            errors.append(
                ValidationError(
                    "cli",
                    f"{path.relative_to(repo_root)} must construct its argparse parser "
                    "with argument_parser()",
                )
            )
    return errors


def _validate_repo_review_scorecard(
    repo_root: Path = REPO_ROOT,
) -> list[ValidationError]:
    """Require the review formula to name and weight each criterion unambiguously."""
    criteria_path = repo_root / "skills" / "repo-review" / "references" / "criteria.md"
    skill_path = repo_root / "skills" / "repo-review" / "SKILL.md"
    try:
        criteria = criteria_path.read_text(encoding="utf-8")
        skill = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [ValidationError("repo-review", f"cannot read scorecard: {error}")]
    sections = [match.group("name") for match in REPO_REVIEW_SECTION.finditer(criteria)]
    expected_numbers = list(range(1, 16))
    numbers = [
        int(match.group("number")) for match in REPO_REVIEW_SECTION.finditer(criteria)
    ]
    if numbers != expected_numbers or len(set(sections)) != len(sections):
        return [
            ValidationError(
                "repo-review",
                "criteria must define each of the 15 uniquely numbered sections",
            )
        ]
    weight_line = re.search(r"^Weights: (?P<weights>.+)$", skill, re.MULTILINE)
    if weight_line is None:
        return [ValidationError("repo-review", "scorecard weights are missing")]
    weights = [
        (match.group("name"), int(match.group("weight")))
        for match in REPO_REVIEW_WEIGHT.finditer(weight_line.group("weights"))
    ]
    errors: list[ValidationError] = []
    if len(weights) != 15 or len({name for name, _ in weights}) != len(weights):
        errors.append(
            ValidationError(
                "repo-review", "scorecard must assign one weight to each of 15 sections"
            )
        )
    for name, _ in weights:
        if name not in sections:
            errors.append(
                ValidationError(
                    "repo-review", f"weight has no matching criteria section: {name}"
                )
            )
    missing_sections = sorted(set(sections).difference(name for name, _ in weights))
    if missing_sections:
        errors.append(
            ValidationError(
                "repo-review",
                f"criteria sections have no weight: {', '.join(missing_sections)}",
            )
        )
    if sum(weight for _, weight in weights) != 100:
        errors.append(ValidationError("repo-review", "weights must total 100%"))
    return errors


def _validate_ruleset_policy(repo_root: Path = REPO_ROOT) -> list[ValidationError]:
    """Require the tracked main ruleset to gate merges on current checks."""
    path = repo_root / ".github" / "rulesets" / "homeric-main-baseline.json"
    document, errors = _read_json(path, "ruleset", repo_root)
    if document is None:
        return errors
    rules = document.get("rules")
    if not isinstance(rules, list):
        return [
            *errors,
            ValidationError("ruleset", "ruleset must contain a rules list"),
        ]
    status_checks = next(
        (
            rule
            for rule in rules
            if isinstance(rule, dict) and rule.get("type") == "required_status_checks"
        ),
        None,
    )
    if not isinstance(status_checks, dict) or not isinstance(
        status_checks.get("parameters"), dict
    ):
        return [
            *errors,
            ValidationError("ruleset", "required status-check policy is missing"),
        ]
    parameters = status_checks["parameters"]
    if parameters.get("strict_required_status_checks_policy") is not True:
        errors.append(
            ValidationError("ruleset", "must require checks current with main")
        )
    checks = parameters.get("required_status_checks")
    if not isinstance(checks, list) or not any(
        isinstance(check, dict) and check.get("context") == "required-checks-gate"
        for check in checks
    ):
        errors.append(ValidationError("ruleset", "must require required-checks-gate"))
    merge_queues = [
        rule
        for rule in rules
        if isinstance(rule, dict) and rule.get("type") == "merge_queue"
    ]
    if not merge_queues:
        errors.append(ValidationError("ruleset", "merge queue policy is missing"))
    elif (
        len(merge_queues) != 1
        or merge_queues[0].get("parameters") != APPROVED_MERGE_QUEUE_PARAMETERS
    ):
        errors.append(
            ValidationError("ruleset", "merge queue policy does not match issue #28")
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
        *_validate_cli_conventions(repo_root),
        *_validate_repo_review_scorecard(repo_root),
        *_validate_ruleset_policy(repo_root),
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
    parser = argument_parser(description="Validate Athena's plugin-only distribution.")
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
