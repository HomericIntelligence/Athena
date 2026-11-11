"""Behavior tests for the simple review delivery helper."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/pr-review/scripts/delivery.py"


def load_module() -> ModuleType:
    name = f"test_review_delivery_{id(SCRIPT)}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("The delivery helper cannot load.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeGh:
    def __init__(self, responses: list[tuple[list[str], int, str, str]]) -> None:
        self.responses = responses
        self.calls: list[tuple[tuple[str, ...], str | None]] = []

    def __call__(
        self, arguments: list[str], *, input_text: str | None = None
    ) -> tuple[int, str, str]:
        self.calls.append((tuple(arguments), input_text))
        for match, code, stdout, stderr in self.responses:
            if arguments[: len(match)] == match:
                return code, stdout, stderr
        return 0, "", ""


class ReviewDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = cast(Any, load_module())
        self._original_run = self.module._run

    def tearDown(self) -> None:
        self.module._run = self._original_run

    def test_print_only_does_not_touch_forge(self) -> None:
        code = self.module.main(
            [
                "--print-only",
                "--target",
                "7",
                "--kind",
                "implementation",
                "--decision",
                "go",
            ]
        )
        self.assertEqual(0, code)

    def test_go_sets_go_label_and_requests_auto_merge(self) -> None:
        fake = FakeGh(
            [
                (["pr", "view"], 0, "{}", ""),
                (["pr", "comment"], 0, "{}", ""),
                (
                    ["api", "repos/acme/widget/issues/7/labels"],
                    0,
                    "bug\nstate:implementation-no-go\n",
                    "",
                ),
                (["api", "--method", "PATCH"], 0, "[]", ""),
                (["pr", "merge", "--auto", "--squash"], 0, "{}", ""),
            ]
        )
        self.module._run = fake
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as body:
            body.write("review body\n")
            body.flush()
            code = self.module.main(
                [
                    "--repo",
                    "acme/widget",
                    "--target",
                    "7",
                    "--kind",
                    "implementation",
                    "--decision",
                    "go",
                    "--body",
                    body.name,
                    "--auto-merge",
                ]
            )
        self.assertEqual(0, code)
        patched = next(
            call for call in fake.calls if call[0][:2] == ("api", "--method")
        )
        payload = json.loads(cast(str, patched[1]))
        self.assertIn("state:implementation-go", payload["labels"])
        self.assertNotIn("state:implementation-no-go", payload["labels"])
        self.assertTrue(any(call[0][:2] == ("pr", "merge") for call in fake.calls))

    def test_no_go_removes_go_label_without_auto_merge(self) -> None:
        fake = FakeGh(
            [
                (["pr", "view"], 0, "{}", ""),
                (["pr", "comment"], 0, "{}", ""),
                (
                    ["api", "repos/acme/widget/issues/7/labels"],
                    0,
                    "bug\nstate:implementation-go\n",
                    "",
                ),
                (["api", "--method", "PATCH"], 0, "[]", ""),
            ]
        )
        self.module._run = fake
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as body:
            body.write("review body\n")
            body.flush()
            code = self.module.main(
                [
                    "--repo",
                    "acme/widget",
                    "--target",
                    "7",
                    "--kind",
                    "implementation",
                    "--decision",
                    "no-go",
                    "--body",
                    body.name,
                ]
            )
        self.assertEqual(0, code)
        patched = next(
            call for call in fake.calls if call[0][:2] == ("api", "--method")
        )
        payload = json.loads(cast(str, patched[1]))
        self.assertIn("state:implementation-no-go", payload["labels"])
        self.assertNotIn("state:implementation-go", payload["labels"])
        self.assertFalse(any(call[0][:2] == ("pr", "merge") for call in fake.calls))


if __name__ == "__main__":
    unittest.main()
