#!/usr/bin/env python3
"""Run the dependency-locked Hephaestus tidy command in place of this process."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from skills._cli import argument_parser


def main(argv: Sequence[str] | None = None) -> int:
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argument_parser(description=__doc__)
    parser.add_argument("automation_checkout", type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(raw_arguments)
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
        print(f"required command unavailable: {missing}", file=sys.stderr)
        return 127
    raise RuntimeError("os.execvp returned unexpectedly")


if __name__ == "__main__":
    raise SystemExit(main())
