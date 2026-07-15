#!/usr/bin/env python3
"""Enforce branch-coverage floors for every executable Athena Python script."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Sequence

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills._cli import argument_parser  # noqa: E402


def coverage_failures(report: object, minimum: float) -> list[str]:
    """Return deterministic per-file coverage failures from coverage.py JSON."""
    if not isinstance(report, dict) or not isinstance(report.get("files"), dict):
        raise ValueError("coverage report has no file map")
    failures: list[str] = []
    for path, item in sorted(report["files"].items()):
        if not isinstance(path, str) or not isinstance(item, dict):
            raise ValueError("coverage report contains an invalid file record")
        summary = item.get("summary")
        percent = summary.get("percent_covered") if isinstance(summary, dict) else None
        if not isinstance(percent, int | float):
            raise ValueError(f"coverage report has no percentage for {path}")
        if float(percent) < minimum:
            failures.append(f"{path}: {float(percent):.2f}% < {minimum:.2f}%")
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
            raise ValueError("coverage report has no file map")
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
        failures = [f"{path}: missing coverage" for path in missing]
        failures.extend(coverage_failures(report, arguments.minimum))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"coverage policy error: {error}", file=sys.stderr)
        return 2
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Every executable script meets {arguments.minimum:.2f}% coverage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
