"""Behavior tests for the local CI container orchestrator."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_CI_LOCAL = ROOT / "scripts/run_ci_local.sh"


class LocalCiOrchestratorTests(unittest.TestCase):
    def test_multicommand_subsets_report_an_early_failure(self) -> None:
        cases = (("static", "ruff check"), ("workflow", "yamllint"))

        for subset, failing_command in cases:
            with (
                self.subTest(subset=subset),
                tempfile.TemporaryDirectory() as temporary,
            ):
                fake_engine = Path(temporary) / "fake-container-engine"
                fake_engine.write_text(
                    "#!/bin/sh\n"
                    'case "$*" in\n'
                    '  *"$FAKE_FAILURE"*) exit 23 ;;\n'
                    "  *) exit 0 ;;\n"
                    "esac\n",
                    encoding="utf-8",
                )
                fake_engine.chmod(0o755)
                environment = os.environ.copy()
                environment["CONTAINER_ENGINE"] = str(fake_engine)
                environment["FAKE_FAILURE"] = failing_command

                result = subprocess.run(
                    [str(RUN_CI_LOCAL), subset],
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            self.assertNotEqual(0, result.returncode, result.stdout)
            self.assertIn(f"{subset} FAILED", result.stderr)


if __name__ == "__main__":
    unittest.main()
