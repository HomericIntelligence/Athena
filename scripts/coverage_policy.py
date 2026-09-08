#!/usr/bin/env python3
"""Apply the minimum branch-coverage requirement to each executable Athena Python script."""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills._cli import argument_parser


def coverage_failures(report: object, minimum: float) -> list[str]:
    """Return deterministic per-file coverage failures from coverage.py JSON."""
    if not isinstance(report, dict) or not isinstance(report.get("files"), dict):
        raise TypeError("The coverage report does not contain a file map.")
    meta = report.get("meta")
    if not isinstance(meta, dict) or meta.get("branch_coverage") is not True:
        raise TypeError("The coverage report must contain branch measurements.")
    failures: list[str] = []
    for path, item in sorted(report["files"].items()):
        if not isinstance(path, str) or not isinstance(item, dict):
            raise TypeError(
                "The coverage report contains a file record that is not valid."
            )
        summary = item.get("summary")
        if not isinstance(summary, dict):
            raise TypeError(f"The coverage summary is missing for '{path}'.")
        percent = summary.get("percent_covered")
        if not isinstance(percent, int | float) or isinstance(percent, bool):
            raise TypeError(
                f"The coverage report does not contain a percentage for '{path}'."
            )
        if not math.isfinite(percent) or not 0 <= percent <= 100:
            raise ValueError(f"The coverage percentage is not valid for '{path}'.")
        counts: list[int] = []
        for key in ("num_branches", "covered_branches", "missing_branches"):
            count = summary.get(key)
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise TypeError(f"The branch counts are not valid for '{path}'.")
            counts.append(count)
        total, covered, missing = counts
        if covered + missing != total:
            raise ValueError(f"The branch counts are inconsistent for '{path}'.")
        if total and 100 * covered / total < minimum:
            failures.append(
                f"{path}: Branch coverage is {100 * covered / total:.2f} percent. "
                f"The minimum is {minimum:.2f} percent."
            )
        if float(percent) < minimum:
            failures.append(
                f"{path}: Coverage is {float(percent):.2f} percent. "
                f"The minimum is {minimum:.2f} percent."
            )
    return failures


def expected_scripts(root: Path) -> set[str]:
    """Return every distributable or repository executable Python script."""
    paths = {
        path.relative_to(root).as_posix()
        for path in (root / "scripts").glob("*.py")
        if path.name != "__init__.py"
    }
    paths.update(
        path.relative_to(root).as_posix()
        for path in (root / "skills").glob("*/scripts/*.py")
    )
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--minimum", type=float, default=80.0)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-from", type=Path)
    arguments = parser.parse_args(argv)
    try:
        report: Any = json.loads(arguments.report.read_text(encoding="utf-8"))
        files = report.get("files") if isinstance(report, dict) else None
        if not isinstance(files, dict):
            raise TypeError("The coverage report does not contain a file map.")
        expected = (
            {
                line
                for line in arguments.expected_from.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line
            }
            if arguments.expected_from is not None
            else expected_scripts(arguments.root.resolve())
        )
        missing = sorted(expected.difference(files))
        failures = [
            f"{path}: The coverage report does not contain coverage data."
            for path in missing
        ]
        failures.extend(coverage_failures(report, arguments.minimum))
    except (OSError, TypeError, ValueError) as error:
        print(f"coverage policy error: {error}", file=sys.stderr)
        return 2
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        "Every executable script meets the "
        f"{arguments.minimum:.2f} percent combined and branch coverage requirements."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
