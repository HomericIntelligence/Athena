"""Repository-toolchain security contracts."""

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


if __name__ == "__main__":
    unittest.main()
