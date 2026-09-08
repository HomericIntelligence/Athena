"""Behavior tests for the fast and nightly pytest tiers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

NIGHTLY_MODULES = {
    "tests/unit/test_change_review_scope_hardening.py",
    "tests/unit/test_installed_skill_helpers.py",
    "tests/unit/test_knowledge_checkout_resolution.py",
    "tests/unit/test_package_opencode.py",
    "tests/unit/test_pr_review_contract_hardening.py",
    "tests/unit/test_realign_assessment_manifest.py",
    "tests/unit/test_skill_scripts.py",
}


def collected_modules(marker_expression: str) -> set[str]:
    """Collect test module paths for one marker expression."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--strict-markers",
            "--collect-only",
            "-q",
            "-m",
            marker_expression,
            "tests/unit",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return {
        line.split("::", 1)[0]
        for line in result.stdout.splitlines()
        if line.startswith("tests/unit/")
    }


def test_nightly_marker_selects_only_integration_heavy_modules() -> None:
    """Keep the measured integration-heavy modules in the nightly tier."""
    assert collected_modules("nightly") == NIGHTLY_MODULES


def test_fast_marker_expression_excludes_all_nightly_modules() -> None:
    """Keep each nightly module out of the default fast tier."""
    fast_modules = collected_modules("not nightly")

    assert fast_modules
    assert fast_modules.isdisjoint(NIGHTLY_MODULES)
