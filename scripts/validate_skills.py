#!/usr/bin/env python3
"""Validate the plugin-only Athena distribution with the Python standard library."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple, cast

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.policies.agent_contract import validate_agent_contract
from scripts.policies.agent_contract_release import tag_ruleset_errors
from scripts.semver import SEMVER_PATTERN
from skills._cli import argument_parser

REPO_ROOT = Path(__file__).resolve().parent.parent

ALLOWED_ECOSYSTEM_REPOSITORIES = {
    "Athena",
    "Hephaestus",
    "Mnemosyne",
    "athena-opencode",
}
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
APPROVED_RULESET_NAME = "homeric-main-baseline"
APPROVED_RULESET_TARGET = "branch"
APPROVED_RULESET_ENFORCEMENT = "active"
APPROVED_RULESET_BYPASS_ACTORS: list[object] = []
APPROVED_RULESET_CONDITIONS: dict[str, object] = {
    "ref_name": {
        "include": ["~DEFAULT_BRANCH"],
        "exclude": [],
    }
}
APPROVED_PULL_REQUEST_PARAMETERS: dict[str, object] = {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews_on_push": False,
    "required_reviewers": [],
    "dismissal_restriction": {"enabled": False, "allowed_actors": []},
    "require_code_owner_review": False,
    "require_last_push_approval": False,
    "required_review_thread_resolution": True,
    "allowed_merge_methods": ["squash"],
    "require_extra_approval_for_unattributed_changes": True,
}
APPROVED_MERGE_QUEUE_PARAMETERS: dict[str, object] = {
    "check_response_timeout_minutes": 180,
    "grouping_strategy": "HEADGREEN",
    "max_entries_to_build": 10,
    "max_entries_to_merge": 5,
    "merge_method": "SQUASH",
    "min_entries_to_merge": 1,
    "min_entries_to_merge_wait_minutes": 5,
}
APPROVED_REQUIRED_STATUS_CHECKS_PARAMETERS: dict[str, object] = {
    "strict_required_status_checks_policy": False,
    "do_not_enforce_on_create": False,
    "required_status_checks": [
        {
            "context": "required-checks-gate",
            "integration_id": 15368,
        }
    ],
}
APPROVED_RULE_TYPES: tuple[str, ...] = (
    "deletion",
    "non_fast_forward",
    "required_linear_history",
    "pull_request",
    "merge_queue",
    "required_status_checks",
    "required_signatures",
)
APPROVED_RULESET_POLICY: dict[str, object] = {
    "name": APPROVED_RULESET_NAME,
    "target": APPROVED_RULESET_TARGET,
    "enforcement": APPROVED_RULESET_ENFORCEMENT,
    "bypass_actors": APPROVED_RULESET_BYPASS_ACTORS,
    "conditions": APPROVED_RULESET_CONDITIONS,
    "rules": [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {"type": "required_linear_history"},
        {
            "type": "pull_request",
            "parameters": APPROVED_PULL_REQUEST_PARAMETERS,
        },
        {
            "type": "merge_queue",
            "parameters": APPROVED_MERGE_QUEUE_PARAMETERS,
        },
        {
            "type": "required_status_checks",
            "parameters": APPROVED_REQUIRED_STATUS_CHECKS_PARAMETERS,
        },
        {"type": "required_signatures"},
    ],
}
PI_PACKAGE_NAME = "@homericintelligence/athena"
PI_SKILL_ROOT = ["./skills"]
OPENCODE_PACKAGE_NAME = "@homericintelligence/athena-opencode"
OPENCODE_MANIFEST_PATH = "npm/athena-opencode/package.json"


class ValidationError(NamedTuple):
    """This record describes one actionable distribution failure."""

    surface: str
    reason: str
    operational: bool = False


def _read_json(
    path: Path, surface: str, repo_root: Path = REPO_ROOT
) -> tuple[dict[str, object] | None, list[ValidationError]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return None, [
            ValidationError(
                surface,
                f"The validator cannot read '{path.relative_to(repo_root)}'. "
                f"The operation returned this diagnostic.\n{exc}",
                True,
            )
        ]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [
            ValidationError(
                surface,
                f"The file '{path.relative_to(repo_root)}' must contain valid JSON. "
                f"The parser returned this diagnostic.\n{exc}",
            )
        ]
    if not isinstance(data, dict):
        return None, [
            ValidationError(
                surface,
                f"The file '{path.relative_to(repo_root)}' must be a JSON object.",
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
        return [ValidationError("skills", "The skills/ directory is missing.")]

    seen: set[str] = set()
    skill_dirs = sorted(path for path in skills_dir.iterdir() if path.is_dir())
    if not skill_dirs:
        return [
            ValidationError(
                "skills", "The skills/ directory does not contain any skills."
            )
        ]

    for directory in skill_dirs:
        if directory.name == "__pycache__":
            continue
        if directory.name.startswith("_"):
            errors.append(
                ValidationError(
                    "skills",
                    f"The validator does not permit this private skill directory: "
                    f"'{directory.name}'.",
                )
            )
            continue
        skill_file = directory / "SKILL.md"
        try:
            text = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(
                ValidationError(
                    "skills",
                    f"The validator cannot read 'skills/{directory.name}/SKILL.md'. "
                    f"The operation returned this diagnostic.\n{exc}",
                    True,
                )
            )
            continue
        name = _frontmatter_name(text)
        if name != directory.name:
            errors.append(
                ValidationError(
                    "skills",
                    f"The directory '{directory.name}' does not match the frontmatter "
                    f"name '{name}'.",
                )
            )
        if name in seen:
            errors.append(
                ValidationError(
                    "skills", f"The validator found a duplicate skill name: '{name}'."
                )
            )
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
            ValidationError(
                "claude", "The marketplace must expose exactly one plugin."
            ),
        ]
    entry = plugins[0]
    if entry.get("name") != "athena" or entry.get("source") != "./":
        errors.append(
            ValidationError(
                "claude", "The plugin must be named 'athena' with source './'."
            )
        )
    if manifest.get("name") != "athena" or manifest.get("skills") != "./skills/":
        errors.append(
            ValidationError(
                "claude",
                "The root manifest must name 'athena' and load './skills/'.",
            )
        )
    metadata = marketplace.get("metadata")
    marketplace_version = (
        metadata.get("version") if isinstance(metadata, dict) else None
    )
    if marketplace_version != manifest.get("version"):
        errors.append(
            ValidationError(
                "version", "The Claude marketplace and manifest versions differ."
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
            ValidationError("codex", "The marketplace must expose exactly one plugin."),
        ]
    entry = plugins[0]
    if entry.get("name") != "athena" or entry.get("source") != {
        "source": "local",
        "path": "./",
    }:
        errors.append(
            ValidationError(
                "codex",
                "The plugin must be named 'athena' with local source './'.",
            )
        )
    if manifest.get("name") != "athena" or manifest.get("skills") != "./skills/":
        errors.append(
            ValidationError(
                "codex",
                "The root manifest must name 'athena' and load './skills/'.",
            )
        )
    version = manifest.get("version")
    if not isinstance(version, str) or SEMVER_PATTERN.fullmatch(version) is None:
        errors.append(
            ValidationError(
                "version",
                "The Codex manifest version must be valid Semantic Versioning (SemVer).",
            )
        )
    return errors


def _validate_pi(repo_root: Path = REPO_ROOT) -> list[ValidationError]:
    """Validate the native Pi package manifest and its canonical skill resource."""
    manifest, errors = _read_json(repo_root / "package.json", "pi", repo_root)
    if manifest is None:
        return errors
    if manifest.get("name") != PI_PACKAGE_NAME:
        errors.append(
            ValidationError("pi", f"The package must be named '{PI_PACKAGE_NAME}'.")
        )
    version = manifest.get("version")
    if not isinstance(version, str) or SEMVER_PATTERN.fullmatch(version) is None:
        errors.append(
            ValidationError(
                "version",
                "The Pi package version must be valid Semantic Versioning (SemVer).",
            )
        )
    keywords = manifest.get("keywords")
    if not isinstance(keywords, list) or "pi-package" not in keywords:
        errors.append(
            ValidationError("pi", "The package must declare the 'pi-package' keyword.")
        )
    pi = manifest.get("pi")
    if (
        not isinstance(pi, dict)
        or pi.get("skills") != PI_SKILL_ROOT
        or set(pi) != {"skills"}
    ):
        errors.append(
            ValidationError(
                "pi",
                "The package must load ['./skills'] and no other Pi resources.",
            )
        )
    return errors


def _validate_opencode(repo_root: Path = REPO_ROOT) -> list[ValidationError]:
    """Validate the opencode npm plugin manifest."""
    manifest, errors = _read_json(
        repo_root / OPENCODE_MANIFEST_PATH, "opencode", repo_root
    )
    if manifest is None:
        return errors
    if manifest.get("name") != OPENCODE_PACKAGE_NAME:
        errors.append(
            ValidationError(
                "opencode", f"The package must be named '{OPENCODE_PACKAGE_NAME}'."
            )
        )
    version = manifest.get("version")
    if not isinstance(version, str) or SEMVER_PATTERN.fullmatch(version) is None:
        errors.append(
            ValidationError(
                "version",
                "The opencode plugin version must be valid Semantic Versioning (SemVer).",
            )
        )
    if manifest.get("main") != "plugin.js":
        errors.append(
            ValidationError("opencode", "The package entry point must be 'plugin.js'.")
        )
    keywords = manifest.get("keywords")
    if not isinstance(keywords, list) or "opencode-plugin" not in keywords:
        errors.append(
            ValidationError(
                "opencode",
                "The package must declare the 'opencode-plugin' keyword.",
            )
        )
    files = manifest.get("files")
    required_files = {"plugin.js", "skills"}
    if not isinstance(files, list) or not required_files.issubset(files):
        errors.append(
            ValidationError(
                "opencode",
                "The package must publish at least the plugin entry and skills corpus.",
            )
        )
    return errors


def _validate_layout_and_policy(repo_root: Path = REPO_ROOT) -> list[ValidationError]:
    errors: list[ValidationError] = []
    forbidden_paths = ("athena", "plugins/athena", "CODEOWNERS")
    for relative in forbidden_paths:
        if (repo_root / relative).exists():
            errors.append(
                ValidationError(
                    "layout", f"An obsolete distribution path exists: '{relative}'."
                )
            )
    required_paths = (
        ".github/CODEOWNERS",
        ".github/rulesets/homeric-agent-contract-tags.json",
        ".github/workflows/_required.yml",
        ".github/workflows/release.yml",
        "docs/policies/development.md",
        "docs/policies/evidence-integrity.md",
        "docs/policies/required-checks.md",
    )
    for relative in required_paths:
        if not (repo_root / relative).is_file():
            errors.append(
                ValidationError(
                    "policy", f"The required file is missing: '{relative}'."
                )
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
                    f"The validator cannot inspect '{relative_path}'. "
                    f"The operation returned this diagnostic.\n{exc}",
                    True,
                )
            )
            continue
        for match in ECOSYSTEM_REPOSITORY.finditer(text):
            repository = match.group(1)
            if repository.casefold() not in ALLOWED_ECOSYSTEM_REPOSITORY_KEYS:
                errors.append(
                    ValidationError(
                        "self-contained",
                        f"The file '{relative_path}' references a forbidden repository: "
                        f"'{match.group(0)}'.",
                    )
                )
        project_prefix = re.search(r"\bProject[A-Z][A-Za-z0-9_-]*\b", text)
        if project_prefix is not None:
            errors.append(
                ValidationError(
                    "self-contained",
                    f"The file '{relative_path}' uses the forbidden Project prefix "
                    f"'{project_prefix.group(0)}'.",
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
                    "cli",
                    f"The validator cannot read '{path.relative_to(repo_root)}'. "
                    f"The operation returned this diagnostic.\n{exc}",
                    True,
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
                    "cli",
                    f"The validator cannot parse '{path.relative_to(repo_root)}'. "
                    f"The operation returned this diagnostic.\n{exc}",
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
                    f"The script '{path.relative_to(repo_root)}' must not construct "
                    "argparse.ArgumentParser directly.",
                )
            )
        elif not factory_names or not parser_names or not parses_arguments:
            errors.append(
                ValidationError(
                    "cli",
                    f"The script '{path.relative_to(repo_root)}' must construct its "
                    "argparse parser "
                    "with argument_parser().",
                )
            )
    return errors


def _validate_repo_review_scorecard(
    repo_root: Path = REPO_ROOT,
) -> list[ValidationError]:
    """Require the review formula to name and weight each criterion unambiguously."""
    criteria_path = repo_root / "docs" / "review" / "repository-scorecard.md"
    skill_path = repo_root / "skills" / "repo-review" / "SKILL.md"
    try:
        criteria = criteria_path.read_text(encoding="utf-8")
        skill = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [
            ValidationError(
                "repo-review",
                "The validator cannot read the scorecard. "
                f"The operation returned this diagnostic.\n{error}",
                True,
            )
        ]
    sections = [match.group("name") for match in REPO_REVIEW_SECTION.finditer(criteria)]
    expected_numbers = list(range(1, 16))
    numbers = [
        int(match.group("number")) for match in REPO_REVIEW_SECTION.finditer(criteria)
    ]
    if numbers != expected_numbers or len(set(sections)) != len(sections):
        return [
            ValidationError(
                "repo-review",
                "The criteria must define each of the 15 uniquely numbered sections.",
            )
        ]
    weight_line = re.search(r"^Weights: (?P<weights>.+)$", skill, re.MULTILINE)
    if weight_line is None:
        return [ValidationError("repo-review", "The scorecard weights are missing.")]
    weights = [
        (match.group("name"), int(match.group("weight")))
        for match in REPO_REVIEW_WEIGHT.finditer(weight_line.group("weights"))
    ]
    errors: list[ValidationError] = []
    if len(weights) != 15 or len({name for name, _ in weights}) != len(weights):
        errors.append(
            ValidationError(
                "repo-review",
                "The scorecard must assign one weight to each of 15 sections.",
            )
        )
    for name, _ in weights:
        if name not in sections:
            errors.append(
                ValidationError(
                    "repo-review",
                    f"The weight has no matching criteria section: '{name}'.",
                )
            )
    missing_sections = sorted(set(sections).difference(name for name, _ in weights))
    if missing_sections:
        errors.append(
            ValidationError(
                "repo-review",
                "The scorecard does not assign a weight to these criteria sections: "
                + ", ".join(f"'{name}'" for name in missing_sections)
                + ".",
            )
        )
    if sum(weight for _, weight in weights) != 100:
        errors.append(
            ValidationError(
                "repo-review", "The scorecard weights must total 100 percent."
            )
        )
    return errors


def _json_type_name(value: object) -> str:
    """Return a stable JSON type name for validator diagnostics."""
    return "null" if value is None else type(value).__name__


def _validate_exact_json(
    actual: object, expected: object, path: str
) -> list[ValidationError]:
    """Require one exact JSON value at the given path."""
    if type(actual) is not type(expected):
        return [
            ValidationError(
                "ruleset",
                "The ruleset must match the approved live baseline from issue #173 "
                f"at {path}. Expected {_json_type_name(expected)} but found "
                f"{_json_type_name(actual)}.",
            )
        ]

    if isinstance(expected, dict):
        actual_dict = cast(dict[str, object], actual)
        expected_dict = cast(dict[str, object], expected)
        actual_keys = set(actual_dict)
        expected_keys = set(expected_dict)
        if actual_keys != expected_keys:
            missing = sorted(expected_keys - actual_keys)
            extra = sorted(actual_keys - expected_keys)
            parts: list[str] = []
            if missing:
                parts.append("missing keys: " + ", ".join(missing))
            if extra:
                parts.append("unexpected keys: " + ", ".join(extra))
            return [
                ValidationError(
                    "ruleset",
                    "The ruleset must match the approved live baseline from issue "
                    f"#173 at {path}. " + "; ".join(parts) + ".",
                )
            ]

        for key in expected_dict:
            nested = _validate_exact_json(
                actual_dict[key], expected_dict[key], f"{path}.{key}"
            )
            if nested:
                return nested
        return []

    if isinstance(expected, list):
        actual_list = cast(list[object], actual)
        expected_list = cast(list[object], expected)
        if len(actual_list) != len(expected_list):
            return [
                ValidationError(
                    "ruleset",
                    "The ruleset must match the approved live baseline from issue "
                    f"#173 at {path}. Expected {len(expected_list)} entries but found "
                    f"{len(actual_list)}.",
                )
            ]
        for index, (actual_item, expected_item) in enumerate(
            zip(actual_list, expected_list)
        ):
            nested = _validate_exact_json(
                actual_item, expected_item, f"{path}[{index}]"
            )
            if nested:
                return nested
        return []

    if actual != expected:
        return [
            ValidationError(
                "ruleset",
                "The ruleset must match the approved live baseline from issue #173 "
                f"at {path}. Expected {expected!r} but found {actual!r}.",
            )
        ]
    return []


def _validate_ruleset_policy(repo_root: Path = REPO_ROOT) -> list[ValidationError]:
    """Require the tracked branch and tag rulesets to enforce current policy."""
    path = repo_root / ".github" / "rulesets" / "homeric-main-baseline.json"
    document, errors = _read_json(path, "ruleset", repo_root)
    if document is not None:
        errors.extend(
            _validate_exact_json(document, APPROVED_RULESET_POLICY, "ruleset")
        )
    tag_path = repo_root / ".github" / "rulesets" / "homeric-agent-contract-tags.json"
    tag_document, tag_read_errors = _read_json(tag_path, "ruleset", repo_root)
    errors.extend(tag_read_errors)
    if tag_document is not None:
        errors.extend(
            ValidationError("ruleset", reason)
            for reason in tag_ruleset_errors(tag_document)
        )
    return errors


def validate_repository(repo_root: Path) -> list[ValidationError]:
    """Validate the skills, manifests, layout, and policies in one repository."""
    repo_root = repo_root.resolve()
    errors = [
        *_validate_skills(repo_root),
        *_validate_claude(repo_root),
        *_validate_codex(repo_root),
        *_validate_pi(repo_root),
        *_validate_opencode(repo_root),
        *_validate_layout_and_policy(repo_root),
        *_validate_cli_conventions(repo_root),
        *_validate_repo_review_scorecard(repo_root),
        *_validate_ruleset_policy(repo_root),
        *(
            ValidationError("agent-contract", error.reason, error.operational)
            for error in validate_agent_contract(repo_root)
        ),
    ]
    claude, _ = _read_json(
        repo_root / ".claude-plugin" / "plugin.json", "version", repo_root
    )
    codex, _ = _read_json(
        repo_root / ".codex-plugin" / "plugin.json", "version", repo_root
    )
    pi, _ = _read_json(repo_root / "package.json", "version", repo_root)
    opencode, _ = _read_json(repo_root / OPENCODE_MANIFEST_PATH, "version", repo_root)
    versions = [
        manifest.get("version")
        for manifest in (claude, codex, pi, opencode)
        if manifest is not None
    ]
    if len(versions) == 4 and len(set(versions)) != 1:
        errors.append(
            ValidationError(
                "version",
                "The Pi, Claude, Codex, and opencode manifest versions differ.",
            )
        )
    return errors


def validate() -> list[ValidationError]:
    """Validate the Athena checkout containing this script."""
    return validate_repository(REPO_ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argument_parser(
        description="Validate the plugin-only Athena distribution."
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress success output.")
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root. By default, use this checkout.",
    )
    args = parser.parse_args(argv)
    errors = validate_repository(args.root)
    if errors:
        print("The Athena skill validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error.surface}: {error.reason}", file=sys.stderr)
        return 2 if any(error.operational for error in errors) else 1
    if not args.quiet:
        print("The Athena skill validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
