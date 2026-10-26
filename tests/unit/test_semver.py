"""Behavior tests for the shared semantic-version pattern."""

from __future__ import annotations

import unittest

from scripts.semver import SEMVER_PATTERN


class SemverPatternTests(unittest.TestCase):
    def test_accepts_valid_semver_grammar(self) -> None:
        cases = (
            "0.0.0",
            "1.2.3",
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-0.3.7",
            "1.0.0-x.7.z.92",
            "1.2.3+build.5",
            "1.2.3+001",
            "2.0.0-rc.1+build.5",
        )

        for candidate in cases:
            with self.subTest(candidate=candidate):
                self.assertIsNotNone(SEMVER_PATTERN.fullmatch(candidate))

    def test_rejects_invalid_semver_grammar(self) -> None:
        cases = (
            "",
            "1.2",
            "v1.2.3",
            "01.2.3",
            "1.02.3",
            "1.2.3-",
            "1.2.3+",
            "1.2.3-01",
            "1.2.3-..",
            "../escape",
        )

        for candidate in cases:
            with self.subTest(candidate=candidate):
                self.assertIsNone(SEMVER_PATTERN.fullmatch(candidate))


if __name__ == "__main__":
    unittest.main()
