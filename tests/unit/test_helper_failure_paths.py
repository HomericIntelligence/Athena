"""Exercise imported helper interfaces and command failure boundaries."""

from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load_helper(skill: str, name: str) -> Any:
    """Load a helper through its import interface without invoking its CLI."""
    path = ROOT / "skills" / skill / "scripts" / f"{name}.py"
    module_name = f"skills.test_{skill.replace('-', '_')}_{name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with (
        patch.dict(sys.modules, {module_name: module}),
        patch.object(sys, "path", [str(path.parent), *sys.path]),
    ):
        spec.loader.exec_module(module)
    return module


class HelperFailurePathTests(unittest.TestCase):
    def test_imported_selector_returns_only_main_skill_files(self) -> None:
        module = load_helper("advise", "list_retrievable_skills")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "skills").mkdir()
            for name in ("z.md", "a.md", "a.notes.md", "a.history.md"):
                (root / "skills" / name).touch()
            self.assertEqual(
                [root / "skills/a.md", root / "skills/z.md"],
                module.retrievable_skill_files(root),
            )

    def test_imported_tidy_stops_before_execution_when_revision_is_stale(self) -> None:
        module = load_helper("tidy", "run_tidy")
        with (
            patch.object(
                module.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(["git"], 1),
            ),
            patch("sys.stderr"),
            patch.object(module.os, "execvp") as execute,
        ):
            self.assertEqual(1, module.main(["/unavailable"]))
        execute.assert_not_called()

    def test_repository_evidence_rejects_empty_revision_output(self) -> None:
        module = load_helper("systematic-debugging", "repository_evidence")
        with (
            patch.object(sys, "argv", ["helper", "pattern"]),
            patch.object(module, "run", return_value="") as run,
            patch("sys.stderr", new_callable=io.StringIO) as error,
        ):
            self.assertEqual(1, module.main())
        run.assert_called_once()
        self.assertIn("no commits", error.getvalue())
