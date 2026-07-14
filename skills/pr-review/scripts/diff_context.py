#!/usr/bin/env python3
"""Compute the two required pull-request diff lenses."""

from __future__ import annotations

import json
import subprocess
import sys


def git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(arguments)} failed")
    return result.stdout.strip()


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: diff_context.py BASE_REF HEAD_REF", file=sys.stderr)
        return 64
    base_ref, head_ref = sys.argv[1:]
    try:
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
