"""Silent-failure suppression policy."""

from __future__ import annotations

import re


SILENT_FAILURE = re.compile(r"\|\|[ \t]*true(?:[ \t]*$|[ \t]+#)", re.MULTILINE)
CONTINUE_ON_ERROR = re.compile(
    r"^[ \t]*continue-on-error:[ \t]*true[ \t]*$", re.MULTILINE
)


def find_suppressions(files: dict[str, str]) -> list[str]:
    """Return silent-failure policy violations from tracked executable configuration."""
    findings: list[str] = []
    for path, text in sorted(files.items()):
        for pattern, description in (
            (SILENT_FAILURE, "silent `|| true` fallback"),
            (CONTINUE_ON_ERROR, "continue-on-error enabled"),
        ):
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path}:{line}: {description}")
    return findings
