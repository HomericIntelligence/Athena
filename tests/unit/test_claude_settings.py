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


class ClaudeSettingsTests(unittest.TestCase):
    def test_force_push_policy_uses_permission_rules_only(self) -> None:
        """The host permission rules are the only force-push policy boundary."""
        self.assertNotIn("hooks", load_settings())

    def test_native_force_push_deny_rules_remain(self) -> None:
        """The settings retain both native force-push deny rules."""
        settings = load_settings()
        rules = cast(list[str], settings["permissions"]["deny"])

        self.assertIn("Bash(git push --force)", rules)
        self.assertIn("Bash(git push --force *)", rules)
