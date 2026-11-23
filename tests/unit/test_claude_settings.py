"""Unit tests for the Claude host permission settings.

These tests check configuration invariants. They do not invoke the host matcher.
The exact matching behavior remains host-version specific.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, cast

SETTINGS_PATH = Path(__file__).parents[2] / ".claude" / "settings.json"

PROTECTED_PATHS = (
    "~/.ssh/**",
    "~/.aws/**",
    "~/.kube/**",
    "~/.docker/**",
    "~/.gnupg/**",
    "~/.netrc",
    "~/.npmrc",
    "~/.pypirc",
    "~/.config/gh/**",
    "~/.config/gcloud/**",
    ".env",
    ".env.*",
)


def load_settings() -> dict[str, Any]:
    """Load the Claude host settings as JSON."""
    return cast(
        dict[str, Any],
        json.loads(SETTINGS_PATH.read_text(encoding="utf-8")),
    )


class ClaudeSettingsTests(unittest.TestCase):
    def test_settings_use_permission_rules_not_hooks(self) -> None:
        """The settings use permission rules and not hooks."""
        self.assertNotIn("hooks", load_settings())

    def test_force_push_deny_rules_are_boundary_exact(self) -> None:
        """The force-push deny rules do not use an unbounded force wildcard."""
        settings = load_settings()
        rules = cast(list[str], settings["permissions"]["deny"])

        force_rules = {
            rule for rule in rules if rule.startswith("Bash(git push --force")
        }
        self.assertEqual(
            force_rules,
            {
                "Bash(git push --force)",
                "Bash(git push --force *)",
            },
        )

    def test_file_protection_denies_use_edit_only(self) -> None:
        """The file protections use the Edit tool rule that the host matches."""
        settings = load_settings()
        rules = cast(list[str], settings["permissions"]["deny"])

        self.assertFalse(
            any(rule.startswith("Write(") for rule in rules),
            "Write() file rules are inert on this host; use Edit() rules.",
        )
        for path in PROTECTED_PATHS:
            with self.subTest(path=path):
                self.assertIn(f"Edit({path})", rules)

    def test_admin_merge_is_denied(self) -> None:
        """The merge contract does not permit an admin bypass of branch protection."""
        settings = load_settings()
        rules = cast(list[str], settings["permissions"]["deny"])

        self.assertIn("Bash(gh pr merge --admin*)", rules)
        self.assertIn("Bash(gh pr merge * --admin*)", rules)

    def test_deny_rules_are_unique(self) -> None:
        """The deny list does not contain duplicate rules."""
        settings = load_settings()
        rules = cast(list[str], settings["permissions"]["deny"])

        self.assertEqual(len(rules), len(set(rules)))
