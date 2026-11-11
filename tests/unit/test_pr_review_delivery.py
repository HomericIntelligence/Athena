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

    def test_failed_label_read_skips_label_write(self) -> None:
        module = cast(Any, load_module())
        fake = FakeGh(
            [
                (["pr", "view"], 0, "{}", ""),
                (["pr", "comment"], 0, "{}", ""),
                (["api", "repos/acme/widget/issues/7/labels"], 1, "", "failed"),
            ]
        )
        module._run = fake
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as body:
            body.write("review body\n")
            body.flush()
            self.assertEqual(
                1,
                module.main(
                    [
                        "--repo",
                        "acme/widget",
                        "--target",
                        "7",
                        "--body",
                        body.name,
                        "--decision",
                        "no-go",
                    ]
                ),
            )
        self.assertFalse(any(call[0][:2] == ("api", "--method") for call in fake.calls))

    def test_implementation_decision_preserves_plan_pair(self) -> None:
        module = cast(Any, load_module())
        fake = FakeGh(
            [
                (["pr", "view"], 0, "{}", ""),
                (["pr", "comment"], 0, "{}", ""),
                (
                    ["api", "repos/acme/widget/issues/7/labels"],
                    0,
                    "bug\nstate:implementation-no-go\nstate:plan-go\n",
                    "",
                ),
                (["api", "--method", "PATCH"], 0, "[]", ""),
            ]
        )
        module._run = fake
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as body:
            body.write("review body\n")
            body.flush()
            self.assertEqual(
                0,
                module.main(
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
                    ]
                ),
            )
        patched = next(
            call for call in fake.calls if call[0][:2] == ("api", "--method")
        )
        payload = json.loads(cast(str, patched[1]))
        self.assertIn("state:plan-go", payload["labels"])
        self.assertIn("state:implementation-go", payload["labels"])
        self.assertNotIn("state:implementation-no-go", payload["labels"])

    def test_comment_failure_stops_label_and_auto_merge(self) -> None:
        module = cast(Any, load_module())
        fake = FakeGh(
            [
                (["pr", "view"], 0, "{}", ""),
                (["pr", "comment"], 1, "", "failed"),
            ]
        )
        module._run = fake
        self.assertEqual(
            1,
            module.main(
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
                    "/dev/null",
                    "--auto-merge",
                ]
            ),
        )
        self.assertEqual(2, len(fake.calls))

    def test_plan_decision_preserves_implementation_pair(self) -> None:
        module = cast(Any, load_module())
        fake = FakeGh(
            [
                (["pr", "view"], 0, "{}", ""),
                (["pr", "comment"], 0, "{}", ""),
                (
                    ["api", "repos/acme/widget/issues/7/labels"],
                    0,
                    "bug\nstate:implementation-go\nstate:plan-no-go\n",
                    "",
                ),
                (["api", "--method", "PATCH"], 0, "[]", ""),
            ]
        )
        module._run = fake
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as body:
            body.write("review body\n")
            body.flush()
            self.assertEqual(
                0,
                module.main(
                    [
                        "--repo",
                        "acme/widget",
                        "--target",
                        "7",
                        "--kind",
                        "plan",
                        "--decision",
                        "go",
                        "--body",
                        body.name,
                    ]
                ),
            )
        patched = next(
            call for call in fake.calls if call[0][:2] == ("api", "--method")
        )
        payload = json.loads(cast(str, patched[1]))
        self.assertIn("state:implementation-go", payload["labels"])
        self.assertIn("state:plan-go", payload["labels"])
        self.assertNotIn("state:plan-no-go", payload["labels"])

    def test_label_patch_failure_exits_nonzero(self) -> None:
        module = cast(Any, load_module())
        fake = FakeGh(
            [
                (["pr", "view"], 0, "{}", ""),
                (["pr", "comment"], 0, "{}", ""),
                (
                    ["api", "repos/acme/widget/issues/7/labels"],
                    0,
                    "state:implementation-go\n",
                    "",
                ),
                (["api", "--method", "PATCH"], 1, "", "failed"),
            ]
        )
        module._run = fake
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as body:
            body.write("review body\n")
            body.flush()
            self.assertEqual(
                1,
                module.main(
                    [
                        "--repo",
                        "acme/widget",
                        "--target",
                        "7",
                        "--body",
                        body.name,
                        "--decision",
                        "no-go",
                    ]
                ),
            )

    def test_auto_merge_failure_exits_nonzero(self) -> None:
        module = cast(Any, load_module())
        fake = FakeGh(
            [
                (["pr", "view"], 0, "{}", ""),
                (["pr", "comment"], 0, "{}", ""),
                (
                    ["api", "repos/acme/widget/issues/7/labels"],
                    0,
                    "state:implementation-no-go\n",
                    "",
                ),
                (["api", "--method", "PATCH"], 0, "[]", ""),
                (["pr", "merge", "--auto"], 1, "", "failed"),
            ]
        )
        module._run = fake
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as body:
            body.write("review body\n")
            body.flush()
            self.assertEqual(
                1,
                module.main(
                    [
                        "--repo",
                        "acme/widget",
                        "--target",
                        "7",
                        "--body",
                        body.name,
                        "--decision",
                        "go",
                        "--auto-merge",
                    ]
                ),
            )


if __name__ == "__main__":
    unittest.main()
