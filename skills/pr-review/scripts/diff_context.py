#!/usr/bin/env python3
"""Compute the two required pull-request diff lenses."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from skills._cli import argument_parser


def git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(arguments)} failed")
    return result.stdout.strip()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("base_ref", metavar="BASE_REF")
    parser.add_argument("head_ref", metavar="HEAD_REF")
    arguments = parser.parse_args(argv)
    base_ref, head_ref = arguments.base_ref, arguments.head_ref
    try:
        for label, value in (("base ref", base_ref), ("head ref", head_ref)):
            if value.startswith("-"):
                raise RuntimeError(f"{label} must not begin with '-': {value!r}")
        git("rev-parse", "--verify", f"{base_ref}^{{commit}}")
        git("rev-parse", "--verify", f"{head_ref}^{{commit}}")
        merge_base = git("merge-base", base_ref, head_ref)
        behind_count = int(git("rev-list", "--count", f"{head_ref}..{base_ref}"))
    except (RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "base_ref": base_ref,
                "head_ref": head_ref,
                "merge_base": merge_base,
                "behind_count": behind_count,
                "author_intent_range": f"{merge_base}...{head_ref}",
                "current_base_range": f"{base_ref}..{head_ref}",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
