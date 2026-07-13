"""Validate that ``.claude-plugin/marketplace.json`` references real skills.

Why this script exists
----------------------

``marketplace.json`` is the source Claude Code reads to find a plugin
called ``<name>`` inside the Athena marketplace. If the marketplace entry
points at a ``skills/<name>/`` folder that does not exist on disk, the
plugin install fails in the user's session with a confusing path-mismatch
error. Pre-commit + ``just validate-marketplace`` run this validator to
catch the discrepancy before it ships.

The validator is intentionally a *focused script*, not a general schema
checker. The full marketplace schema is documented in the Claude Code
plugin docs; we only assert the contract Athena itself relies on:

1. Every entry under ``plugins`` has a non-empty ``name``.
2. ``name`` matches an existing ``skills/<name>/`` folder.
3. The matching folder contains a ``SKILL.md`` with a parseable
   YAML frontmatter block whose ``name`` matches.
4. Two plugins cannot share a name (idempotency).

Exit codes
----------

- 0 — every entry references a real skill with a parseable ``SKILL.md``.
- 2 — at least one marketplace entry is broken. Errors are printed to
  ``stderr``; a machine-readable summary is printed to ``stdout`` so the
  pre-commit hook can parse it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
SKILLS_DIR = REPO_ROOT / "skills"


class PluginRecord(NamedTuple):
    name: str
    description: str
    source: str


class ValidationError(NamedTuple):
    plugin_name: str
    reason: str


def _load_marketplace(path: Path) -> list[PluginRecord]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    raw_plugins = data.get("plugins", [])
    records: list[PluginRecord] = []
    for entry in raw_plugins:
        # Treat missing fields as ERRORs at the validation step below rather
        # than here, so the validator's error message is always actionable.
        records.append(
            PluginRecord(
                name=entry.get("name", ""),
                description=entry.get("description", ""),
                source=entry.get("source", "./"),
            )
        )
    return records


def _extract_frontmatter_name(skill_md: Path) -> str | None:
    """Parse the first YAML frontmatter block of a SKILL.md file.

    Returns the ``name`` field if present, ``None`` otherwise. The parser
    intentionally avoids a PyYAML dependency: skills may be authored before
    dev tooling is installed, and we want this validator to run on a bare
    install.

    Closing-fence detection looks for ``\\n---`` *followed by a newline* so
    that mid-document horizontal rules or fenced-code fences are not
    mistaken for the explicit frontmatter closer. This still matches the
    canonical frontmatter convention (a blank line after the closing
    fence), at the cost of rejecting the very rare SKILL.md that has no
    blank line between frontmatter and body.
    """
    import re

    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    # Closing fence: newline + --- + newline. The canonical convention is
    # that frontmatter is followed by a blank line; honor that here.
    match = re.search(r"\n---\n", text[3:])
    if match is None:
        return None
    block = text[3 : 3 + match.start()].strip()
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            _, _, value = stripped.partition(":")
            return value.strip().strip('"').strip("'")
    return None


def validate() -> list[ValidationError]:
    """Run the validator and return a list of errors (empty list = OK)."""
    errors: list[ValidationError] = []
    plugins = _load_marketplace(MARKETPLACE_PATH)
    seen_names: set[str] = set()

    for plugin in plugins:
        if not plugin.name:
            errors.append(
                ValidationError(plugin_name="<unnamed>", reason="marketplace entry missing 'name' field")
            )
            continue
        if plugin.name in seen_names:
            errors.append(
                ValidationError(plugin_name=plugin.name, reason="duplicate plugin entry in marketplace.json")
            )
            continue
        seen_names.add(plugin.name)

        skill_dir = SKILLS_DIR / plugin.name
        if not skill_dir.is_dir():
            errors.append(
                ValidationError(
                    plugin_name=plugin.name,
                    reason=f"marketplace references skills/{plugin.name}/ but the directory does not exist",
                )
            )
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            errors.append(
                ValidationError(
                    plugin_name=plugin.name,
                    reason=f"skills/{plugin.name}/ exists but is missing SKILL.md",
                )
            )
            continue

        frontmatter_name = _extract_frontmatter_name(skill_md)
        if frontmatter_name is None:
            errors.append(
                ValidationError(
                    plugin_name=plugin.name,
                    reason=f"skills/{plugin.name}/SKILL.md is missing a YAML frontmatter 'name' field",
                )
            )
            continue
        if frontmatter_name != plugin.name:
            errors.append(
                ValidationError(
                    plugin_name=plugin.name,
                    reason=(
                        f"marketplace name '{plugin.name}' does not match "
                        f"SKILL.md frontmatter name '{frontmatter_name}'"
                    ),
                )
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point.

    Returns 0 on success, 2 on validation errors. Designed to be called
    both by pre-commit (no argv) and ``just validate-marketplace``.
    """
    parser = argparse.ArgumentParser(
        description="Validate Athena .claude-plugin/marketplace.json against the skills/ tree."
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress success output; only print errors.",
    )
    args = parser.parse_args(argv)
    errors = validate()
    if errors:
        print("Athena marketplace validation FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err.plugin_name}: {err.reason}", file=sys.stderr)
        return 2
    if not args.quiet:
        print("Athena marketplace validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
