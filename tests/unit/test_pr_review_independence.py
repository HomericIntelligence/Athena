from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/pr-review/scripts/independence.py"


def load_module() -> ModuleType:
    name = f"test_independence_{id(SCRIPT)}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("The independence helper cannot load.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IndependenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def report(
        self,
        verdict: str,
        *,
        fresh: bool = True,
        authored: bool = False,
        artifact: str = "pr-7",
        instance: str = "r1",
    ) -> dict[str, Any]:
        return {
            "artifact_id": artifact,
            "context_fresh": fresh,
            "authored": authored,
            "verdict": verdict,
            "instance_id": instance,
        }

    def test_multiple_fresh_uninvolved_reports_can_go(self) -> None:
        reports = [self.report("GO", instance=f"r{i}") for i in range(3)]
        result = self.module.assess_batch(reports)
        self.assertEqual("GO", result["status"])
        self.assertEqual(3, result["independent"])

    def test_disagreement_prevents_go(self) -> None:
        reports = [
            self.report("GO", instance="r1"),
            self.report("NO-GO", instance="r2"),
        ]
        self.assertEqual("NO-GO", self.module.assess_batch(reports)["status"])

    def test_mixed_contexts_prevents_go(self) -> None:
        reports = [
            self.report("GO", instance="r1"),
            self.report("GO", fresh=False, instance="r2"),
        ]
        self.assertEqual("NO-GO", self.module.assess_batch(reports)["status"])

    def test_author_response_context_prevents_go(self) -> None:
        reports = [self.report("GO", authored=True)]
        self.assertEqual("NO-GO", self.module.assess_batch(reports)["status"])

    def test_unbound_or_empty_report_prevents_go(self) -> None:
        self.assertEqual("NO-GO", self.module.assess_batch([])["status"])
        self.assertEqual(
            "NO-GO", self.module.assess_batch([{"verdict": "GO"}])["status"]
        )

    def test_empty_artifact_id_prevents_go(self) -> None:
        reports = [self.report("GO", artifact="")]
        self.assertEqual("NO-GO", self.module.assess_batch(reports)["status"])

    def test_duplicate_instance_prevents_go(self) -> None:
        reports = [
            self.report("GO", instance="same"),
            self.report("GO", instance="same"),
        ]
        self.assertEqual("NO-GO", self.module.assess_batch(reports)["status"])

    def test_blank_instance_prevents_go(self) -> None:
        reports = [self.report("GO", instance="   ")]
        self.assertEqual("NO-GO", self.module.assess_batch(reports)["status"])

    def test_non_string_instance_prevents_go(self) -> None:
        report = self.report("GO")
        report["instance_id"] = None
        self.assertEqual("NO-GO", self.module.assess_batch([report])["status"])


if __name__ == "__main__":
    unittest.main()
