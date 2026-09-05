"""Repository-toolchain security contracts."""

import re
import unittest
from pathlib import Path


class ToolchainPolicyTests(unittest.TestCase):
    """Verify the repository-tooling interpreter contract."""

    def test_default_python_pin_is_a_remediated_supported_release(self) -> None:
        """Require the pinned interpreter to stay in the fixed 3.13 line."""
        root = Path(__file__).resolve().parents[2]
        parts = (
            (root / ".python-version").read_text(encoding="utf-8").strip().split(".")
        )

        self.assertEqual(3, len(parts))
        version = tuple(int(part) for part in parts)
        self.assertGreaterEqual(version, (3, 13, 15))
        self.assertLess(version, (3, 14, 0))

    def test_container_stages_use_the_pinned_python_version(self) -> None:
        """Require every CI image stage to use the pinned Python version."""
        root = Path(__file__).resolve().parents[2]
        version = (root / ".python-version").read_text(encoding="utf-8").strip()
        containerfile = (root / "ci" / "Containerfile").read_text(encoding="utf-8")
        stages = re.findall(
            r"^FROM python:(\d+\.\d+\.\d+)-slim@sha256:[0-9a-f]{64}",
            containerfile,
            re.MULTILINE,
        )

        self.assertEqual(3, len(stages))
        self.assertTrue(all(stage == version for stage in stages))


if __name__ == "__main__":
    unittest.main()
