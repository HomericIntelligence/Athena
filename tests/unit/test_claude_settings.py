"""Unit tests for the Claude host permission settings."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from typing import Any, cast

SETTINGS_PATH = Path(__file__).parents[2] / ".claude" / "settings.json"
HOOK_PATH = SETTINGS_PATH.parent / "hooks" / "deny_unguarded_force_push.py"

HOOK_SPEC = importlib.util.spec_from_file_location(
    "deny_unguarded_force_push", HOOK_PATH
)
assert HOOK_SPEC is not None and HOOK_SPEC.loader is not None
HOOK = importlib.util.module_from_spec(HOOK_SPEC)
HOOK_SPEC.loader.exec_module(HOOK)


def load_settings() -> dict[str, Any]:
    """Load the Claude host settings as JSON."""
    return cast(
        dict[str, Any],
        json.loads(SETTINGS_PATH.read_text(encoding="utf-8")),
    )


class ClaudeSettingsTests(unittest.TestCase):
    def test_force_push_hook_is_configured(self) -> None:
        """The Bash pre-tool hook enforces the force-push policy."""
        settings = load_settings()
        hooks = settings["hooks"]["PreToolUse"]

        self.assertEqual("Bash", hooks[0]["matcher"])
        self.assertIn("deny_unguarded_force_push.py", hooks[0]["hooks"][0]["command"])

    def test_guarded_force_with_lease_push_is_not_denied(self) -> None:
        """Guarded force-with-lease pushes are permitted."""
        command = "git push --force-with-lease --force-if-includes origin feature/x"
        self.assertFalse(HOOK.is_unguarded_force_push(command))

    def test_guarded_force_with_lease_refspec_push_is_not_denied(self) -> None:
        """A leased forced refspec push is permitted."""
        command = "git push --force-with-lease origin +feature:feature"
        self.assertFalse(HOOK.is_unguarded_force_push(command))

    def test_multiline_benign_command_is_not_denied(self) -> None:
        """A harmless multiline Bash command is permitted."""
        command = "echo first line\nprintf second line"
        self.assertFalse(HOOK.is_unguarded_force_push(command))

    def test_shell_control_operators_are_not_denied(self) -> None:
        """Shell control operators do not trigger a force-push denial."""
        for command in (
            "true && echo hi",
            "echo first; echo second",
            "echo left | tr a-z A-Z",
            "sleep 1 &",
        ):
            with self.subTest(command=command):
                self.assertFalse(HOOK.is_unguarded_force_push(command))

    def test_unguarded_force_push_is_denied(self) -> None:
        """Unguarded force pushes remain denied."""
        for command in (
            "git push --force origin feature/x",
            "git push --force origin main",
            "git push -f origin feature/x",
            "git -c user.name=x push -f origin feature/x",
            "git --no-pager push --force origin feature/x",
            "git push --force-with-lease=refs/heads/feature --force origin feature/x",
            "git push --force origin feature/x --force-with-lease=refs/heads/feature",
            "git push --force-with-lease=refs/heads/feature -f origin feature/x",
            "git push -f origin feature/x --force-with-lease=refs/heads/feature",
            "git push origin +feature:feature",
            "git -C /tmp/repo push --force origin feature/x",
            "true && git push -f origin main",
            "git push -f origin main; echo hi",
            "echo ok\ngit push -f origin main",
        ):
            with self.subTest(command=command):
                self.assertTrue(HOOK.is_unguarded_force_push(command))
