"""Unit tests for the Claude host permission settings."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, cast

SETTINGS_PATH = Path(__file__).parents[2] / ".claude" / "settings.json"


def load_settings() -> dict[str, Any]:
    """Load the Claude host settings as JSON."""
    return cast(
        dict[str, Any],
        json.loads(SETTINGS_PATH.read_text(encoding="utf-8")),
    )


def bash_rule_matches(rule: str, command: str) -> bool:
    """Apply the prefix and exact matching used by Claude Bash rules."""
    prefix = rule.removeprefix("Bash(").removesuffix(")")
    if prefix.endswith("*"):
        return command.startswith(prefix[:-1])
    return command == prefix


class ClaudeSettingsTests(unittest.TestCase):
    def test_guarded_force_with_lease_push_is_not_denied(self) -> None:
        """Guarded force-with-lease pushes are permitted."""
        settings = load_settings()
        command = "git push --force-with-lease --force-if-includes origin feature/x"
        denied = settings["permissions"]["deny"]

        self.assertFalse(
            any(bash_rule_matches(rule, command) for rule in denied),
        )

    def test_unguarded_force_push_is_denied(self) -> None:
        """Unguarded force pushes remain denied."""
        settings = load_settings()
        denied = settings["permissions"]["deny"]

        for command in (
            "git push --force origin feature/x",
            "git push --force origin main",
        ):
            with self.subTest(command=command):
                self.assertTrue(
                    any(bash_rule_matches(rule, command) for rule in denied),
                )
