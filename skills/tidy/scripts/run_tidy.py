#!/usr/bin/env python3
"""Replace this process with the dependency-locked Hephaestus tidy command."""

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
    parser = argument_parser(description=__doc__)
    parser.add_argument("automation_checkout", type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(argv)
    command = [
        "uv",
        "run",
        "--project",
        str(parsed.automation_checkout),
        "--locked",
        "hephaestus-tidy",
        *parsed.arguments,
    ]
    try:
        os.execvp(command[0], command)
    except FileNotFoundError as error:
        missing = error.filename or command[0]
        print(f"required command unavailable: {missing}", file=sys.stderr)
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
