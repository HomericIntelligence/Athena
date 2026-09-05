#!/usr/bin/env python3
"""Run the dependency-locked Hephaestus tidy command in place of this process."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from skills._cli import argument_parser

_REQUIRED_HEPHAESTUS_TIDY_REVISION = "aa357098e5d72178d248e4188e7f5e5f843cdd3f"


def _validate_hephaestus_revision(automation_checkout: Path) -> int:
    """Fail closed when the resolved Hephaestus checkout is older than the fix."""
    command = [
        "git",
        "-C",
        str(automation_checkout),
        "merge-base",
        "--is-ancestor",
        _REQUIRED_HEPHAESTUS_TIDY_REVISION,
        "HEAD",
    ]
    try:
        result = subprocess.run(command, check=False)
    except FileNotFoundError as error:
        missing = error.filename or command[0]
        print(f"The required command is not available: '{missing}'.", file=sys.stderr)
        return 127
    if result.returncode != 0:
        print(
            "The resolved Hephaestus checkout is stale; it must include "
            f"commit {_REQUIRED_HEPHAESTUS_TIDY_REVISION}.",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argument_parser(description=__doc__)
    parser.add_argument("automation_checkout", type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(raw_arguments)
    validation_status = _validate_hephaestus_revision(parsed.automation_checkout)
    if validation_status != 0:
        return validation_status
    command = [
        "uv",
        "run",
        "--project",
        str(parsed.automation_checkout),
        "--locked",
        "hephaestus-tidy",
        *raw_arguments[1:],
    ]
    try:
        os.execvp(command[0], command)
    except FileNotFoundError as error:
        missing = error.filename or command[0]
        print(f"The required command is not available: '{missing}'.", file=sys.stderr)
        return 127
    raise RuntimeError("The os.execvp call returned control unexpectedly.")


if __name__ == "__main__":
    raise SystemExit(main())
