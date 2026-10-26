#!/usr/bin/env python3
"""Validate a repository's root agent contract against the Athena catalog."""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.policies.agent_contract import validate_agent_contract
from skills._cli import argument_parser

REPO_ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    """Run the reusable agent-contract validator."""
    parser = argument_parser(
        description="Validate root agent instructions against the Athena catalog."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to validate. By default, use the Athena checkout.",
    )
    parser.add_argument(
        "--catalog-root",
        type=Path,
        default=REPO_ROOT,
        help="Athena catalog root. By default, use the validator checkout.",
    )
    args = parser.parse_args(argv)
    errors = validate_agent_contract(
        args.root.resolve(), catalog_root=args.catalog_root.resolve()
    )
    if errors:
        print("The agent-contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error.path}: {error.reason}", file=sys.stderr)
        return 1
    print("The agent-contract validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
