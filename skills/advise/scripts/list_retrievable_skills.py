#!/usr/bin/env python3
"""List the main Mnemosyne skill files that retrieval can use."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING or __package__ not in {None, ""}:
    from skills._cli import argument_parser
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

COMPANION_FILE = re.compile(
    r"(?:.*\.notes(?:-[A-Za-z0-9_-]+)?\.md|.*\.history(?:[-.].*)?)\Z"
)


def retrievable_skill_files(knowledge_root: Path) -> list[Path]:
    """Return the top-level main skill files in sorted order."""
    skills_directory = knowledge_root / "skills"
    if not skills_directory.is_dir():
        raise RuntimeError(
            f"The knowledge skills directory is not available: '{skills_directory}'."
        )
    return sorted(
        path
        for path in skills_directory.glob("*.md")
        if path.is_file() and COMPANION_FILE.fullmatch(path.name) is None
    )


def main() -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("knowledge_root", type=Path)
    arguments = parser.parse_args()
    try:
        paths = retrievable_skill_files(arguments.knowledge_root)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    for path in paths:
        print(path.relative_to(arguments.knowledge_root).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
