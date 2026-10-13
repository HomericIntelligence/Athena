#!/usr/bin/env python3
"""Classify a test file as behavior evidence or as a fixed-source-position layout test.

The tool reads one test file and prints one JSON verdict. A `reject` verdict names
the fixed source positions, citation offsets, or source-file length checks that tie
the test to source layout. The remediation text offers a behavior-level test or the
removal of the invalid test. The tool never asks for citation-offset maintenance.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING or __package__ not in {None, ""}:
    from skills._cli import argument_parser
else:
    _cli_path = Path(__file__).resolve().parents[2] / "_cli.py"
    _cli_spec = importlib.util.spec_from_file_location(
        "athena_installed_cli", _cli_path
    )
    if _cli_spec is None or _cli_spec.loader is None:
        raise RuntimeError(
            f"The installed Athena CLI helper is unavailable: '{_cli_path}'."
        )
    _cli = importlib.util.module_from_spec(_cli_spec)
    _cli_spec.loader.exec_module(_cli)
    argument_parser = _cli.argument_parser

REASON_FIXED_POSITION = "fixed-source-position"
REASON_CITATION_OFFSET = "citation-offset"
REASON_FILE_LENGTH = "source-file-length"
REASON_TEXT_SEARCH = "equivalent-source-text-search"

REMEDIATION = (
    "Assert the observable contract of this behavior through its public interface, or "
    "remove the test when it protects no required behavior. Do not keep a source "
    "position as a test invariant."
)

LOOP_TARGET = re.compile(r"\bfor\s+(?P<targets>[^:\n]+?)\s+in\s+(?:enumerate|range)\(")
SOURCE_LINES_INDEX = re.compile(
    r"\b(?:[A-Za-z_]*_)?"
    r"(?:source_?lines|lines|file_lines|all_lines|text_lines)"
    r"\s*\[\s*(?P<index>[^\[\]:]+?)\s*\]"
)
CITATION_LINE_NUMBER = re.compile(
    r"""(?:\br?split\(\s*["']:\s*["']\s*\)|:\(\?P<[\w]+>\\d\+\)|:\\d\+)"""
)
SOURCE_LENGTH = re.compile(r"\blen\([^)]*(?:splitlines|lines|source|_text)[^)]*\)")
LINE_NAME = re.compile(
    r"\b(?![A-Za-z_]*lines\b)[A-Za-z_]*line(?:_[A-Za-z_]+)*\b", re.IGNORECASE
)
SOURCE_TEXT_NAME = re.compile(
    r"\b(?:source|src|writer|registry|module|code)(?:_text)?\b|\btext_lines\b"
)
STRING_LITERAL = re.compile(r"""^(?:[rubf]*)(?:'[^']*'|"[^"]*")$""")
BOUNDARY_INDEX = frozenset({"0", "-1"})
SUBSCRIPT_ASSIGNMENT = re.compile(r"\s*=[^=]")
ASSERT_KEYWORD = re.compile(r"\bassert\b")
TEXT_SEARCH = re.compile(r"\s(?:in|re\.search\()\s")


@dataclass(frozen=True)
class Finding:
    """One layout-dependent construct and the line that contains it."""

    reason: str
    line_number: int

    def describe(self) -> str:
        """Return a stable review annotation for the finding."""
        return f"{self.reason} at line {self.line_number}"


def numbered_lines(text: str) -> Iterator[tuple[int, str]]:
    """Yield each source line with its one-based line number."""
    yield from enumerate(text.splitlines(), start=1)


def loop_index_names(text: str) -> set[str]:
    """Return the loop variables that count lines, not stored source positions."""
    names: set[str] = set()
    for match in LOOP_TARGET.finditer(text):
        targets = [part.strip() for part in match.group("targets").split(",")]
        names.update(target for target in targets if target)
    return names


def writes_to_subscript(line: str) -> bool:
    """Return whether the line writes into a subscript, such as a fixture edit."""
    bracket = line.find("[")
    if bracket < 0:
        return False
    return SUBSCRIPT_ASSIGNMENT.search(line[bracket:]) is not None


def fixed_position_findings(text: str) -> list[Finding]:
    """Return findings for source collections indexed by a stored position.

    A first-line or last-line index and a write into a fixture line are not stored
    product positions. Skip them.
    """
    counters = loop_index_names(text)
    findings: list[Finding] = []
    for number, line in numbered_lines(text):
        if writes_to_subscript(line):
            continue
        for match in SOURCE_LINES_INDEX.finditer(line):
            index = match.group("index").strip()
            if STRING_LITERAL.match(index) or index in counters:
                continue
            if index in BOUNDARY_INDEX:
                continue
            findings.append(Finding(REASON_FIXED_POSITION, number))
    return findings


def parses_citation_line(text: str) -> bool:
    """Return whether the file reads a line number from a `path:line` citation."""
    return CITATION_LINE_NUMBER.search(text) is not None


def file_length_findings(text: str) -> list[Finding]:
    """Return findings for a stored citation that a source length constrains."""
    if not parses_citation_line(text):
        return []
    findings: list[Finding] = []
    for number, line in numbered_lines(text):
        if SOURCE_LENGTH.search(line) is None:
            continue
        if LINE_NAME.search(line) is None and ASSERT_KEYWORD.search(line) is None:
            continue
        findings.append(Finding(REASON_FILE_LENGTH, number))
    return findings


def citation_offset_findings(text: str) -> list[Finding]:
    """Return findings for each citation line that a stored offset selects."""
    if not parses_citation_line(text):
        return []
    return [
        Finding(REASON_CITATION_OFFSET, number)
        for number, line in numbered_lines(text)
        if SOURCE_LENGTH.search(line) is not None
    ]


def text_search_findings(text: str) -> list[Finding]:
    """Return findings for source-text searches that substitute for behavior."""
    findings: list[Finding] = []
    for number, line in numbered_lines(text):
        if ASSERT_KEYWORD.search(line) is None:
            continue
        if TEXT_SEARCH.search(line) is None:
            continue
        if SOURCE_TEXT_NAME.search(line) is None:
            continue
        findings.append(Finding(REASON_TEXT_SEARCH, number))
    return findings


def classify_text(text: str) -> dict[str, object]:
    """Return the JSON verdict contract for one test file."""
    findings = [
        *fixed_position_findings(text),
        *citation_offset_findings(text),
        *file_length_findings(text),
        *text_search_findings(text),
    ]
    ordered = sorted(dict.fromkeys(findings), key=lambda item: item.line_number)
    reasons = [finding.describe() for finding in ordered]
    return {
        "verdict": "reject" if reasons else "accept",
        "reasons": reasons,
        "remediation": REMEDIATION if reasons else "",
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Classify one test file and print its JSON verdict."""
    parser = argument_parser(description=__doc__)
    parser.add_argument(
        "test_file", metavar="TEST_FILE", help="The test file to classify."
    )
    arguments = parser.parse_args(argv)
    path = Path(arguments.test_file)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        print(f"The tool cannot read '{path}': {error}", file=sys.stderr)
        return 1
    print(json.dumps(classify_text(text), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
