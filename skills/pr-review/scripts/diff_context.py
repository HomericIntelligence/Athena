#!/usr/bin/env python3
"""Compute the two required pull-request diff lenses."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pr_identity import require_commit_oid

from skills._cli import (
    argument_parser,
    git_read_arguments,
    git_read_environment,
    require_complete_git_history,
    require_unambiguous_git_merge_base,
    run_command,
)


def git(*arguments: str) -> str:
    result = run_command(
        ["git", *git_read_arguments(), *arguments],
        capture_output=True,
        env=git_read_environment(),
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(arguments)} failed")
    return result.stdout.strip()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("base_ref", metavar="BASE_OID")
    parser.add_argument("head_ref", metavar="HEAD_OID")
    arguments = parser.parse_args(argv)
    try:
        base_ref = require_commit_oid(arguments.base_ref, "base OID")
        head_ref = require_commit_oid(arguments.head_ref, "head OID")
        require_complete_git_history()
        git("rev-parse", "--verify", f"{base_ref}^{{commit}}")
        git("rev-parse", "--verify", f"{head_ref}^{{commit}}")
        merge_base = require_commit_oid(
            require_unambiguous_git_merge_base(base_ref, head_ref), "merge base"
        )
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
