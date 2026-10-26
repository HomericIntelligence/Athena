#!/usr/bin/env python3
"""Collect reproducible evidence about recent changes and source patterns."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING or __package__ not in {None, ""}:
    from skills._cli import argument_parser, run_command
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
    run_command = _cli.run_command

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def run(*arguments: str, accepted_codes: tuple[int, ...] = (0,)) -> str:
    result = run_command(arguments, capture_output=True, text=True, check=False)
    if result.returncode not in accepted_codes:
        raise RuntimeError(
            result.stderr.strip()
            or f"The command failed. Command: {' '.join(arguments)}"
        )
    return result.stdout


def main() -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("pattern")
    parser.add_argument("--source-root", default=".")
    arguments = parser.parse_args()
    try:
        try:
            recent_revisions = run(
                "git", "rev-list", "--max-count=10", "HEAD"
            ).splitlines()
        except RuntimeError as error:
            raise RuntimeError(f"The tool cannot resolve HEAD: {error}") from error
        if not recent_revisions:
            raise RuntimeError(
                "The tool cannot resolve HEAD because the repository has no commits."
            )
        recent_commits = run("git", "log", "--oneline", "-10")
        oldest_parent = run(
            "git",
            "rev-parse",
            "--verify",
            f"{recent_revisions[-1]}^",
            accepted_codes=(0, 128),
        ).strip()
        recent_range = f"{oldest_parent or EMPTY_TREE}..HEAD"
        recent_diff = run("git", "diff", "--stat", recent_range)
        pattern_matches = run(
            "git",
            "grep",
            "--line-number",
            "-e",
            arguments.pattern,
            "--",
            arguments.source_root,
            accepted_codes=(0, 1),
        )
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "pattern_matches": pattern_matches,
                "recent_commits": recent_commits,
                "recent_diff": recent_diff,
                "recent_range": recent_range,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
