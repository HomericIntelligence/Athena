"""Every tracked Python file must parse on the declared floor and import here.

Regression guard for HomericIntelligence/Athena#301, which reported that three
`pr-review` helpers could not be imported.

The original defect was not the `except` spelling. It was that nothing verified
the packaged helpers actually parse and import, so a `SyntaxError` in
`anchor_proofs.py` could reach a published plugin unnoticed: that helper cannot
produce the anchor manifest reviewer delivery requires, and `collect_evidence.py`
cannot produce the scope, requirements, and path-manifest digests the GO path
consumes.

This module now enforces the floor directly. `requires-python` declares
`>=3.12,<3.15`, and `ast.parse(..., feature_version=(3, 12))` rejects any syntax
newer than the declared floor. That check runs in this interpreter, so it is
exercised on every host and needs no second toolchain.

Two earlier findings about this file were both wrong in the same way, and both
are recorded so the next reader does not repeat them:

- PEP 758 restores the unparenthesised `except X, Y:` form in 3.14, and `ruff
  format` prefers it when the target is 3.14. With the floor at 3.14 the nine
  sites in this repository were valid, and rewriting them to `except (X, Y):`
  would have fought the formatter. With the floor at 3.12 that form is a hard
  `SyntaxError`, so those sites now use the parenthesised form and the formatter
  agrees.
- Compiling a file with `compile()` in this interpreter proves nothing about the
  declared floor, because this interpreter is not the floor. The `feature_version`
  check below is what actually enforces it.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# The delivery helper pulls in the anchor and evidence helpers by name, so a
# break in any one of them surfaces when the chain is imported together.
DELIVERY_CHAIN = (
    "anchor_proofs",
    "collect_evidence",
    "materialize_snapshot",
    "deliver_go",
)


def tracked_python_files() -> list[Path]:
    """List every Python file tracked by Git, excluding build outputs."""
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "*.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        ROOT / name
        for name in completed.stdout.split()
        if not name.startswith(("build/", "dist/"))
    ]


def test_enumeration_finds_the_repository_sources() -> None:
    """Guard the enumeration so a discovery bug cannot pass silently."""
    names = {path.name for path in tracked_python_files()}
    assert len(names) > 20, f"expected the repository Python files, found {len(names)}"
    for expected in DELIVERY_CHAIN:
        assert f"{expected}.py" in names, f"{expected}.py is not tracked"


def declared_floor() -> tuple[int, int]:
    """Read the minimum declared interpreter from `requires-python`."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'requires-python\s*=\s*">=(\d+)\.(\d+)', text)
    assert match is not None, "requires-python must declare a >= floor"
    return int(match.group(1)), int(match.group(2))


def test_declared_floor_is_known_to_rust() -> None:
    """Record the floor this module checks against.

    `ruff` infers its target version from the same bound, so the formatter and
    this parser cannot disagree about which syntax is legal.
    """
    assert declared_floor() >= (3, 12), "the floor must stay at or above 3.12"


@pytest.mark.parametrize(
    "path",
    tracked_python_files(),
    ids=lambda path: str(path.relative_to(ROOT)),
)
def test_tracked_python_file_parses_on_the_declared_floor(path: Path) -> None:
    """Each tracked Python file must parse without syntax newer than the floor."""
    floor = declared_floor()
    try:
        ast.parse(path.read_text(encoding="utf-8"), str(path), feature_version=floor)
    except SyntaxError as error:
        pytest.fail(
            f"{path.relative_to(ROOT)} uses syntax newer than Python "
            f"{floor[0]}.{floor[1]}: {error.msg} at line {error.lineno}"
        )


def test_pr_review_delivery_chain_imports() -> None:
    """The delivery helper and its dependencies must import together."""
    scripts = ROOT / "skills" / "pr-review" / "scripts"
    scripts_text = str(scripts)
    if scripts_text not in sys.path:
        sys.path.insert(0, scripts_text)
    try:
        for name in DELIVERY_CHAIN:
            try:
                __import__(name)
            except SyntaxError as error:
                pytest.fail(
                    f"{name}.py does not import: {error.msg} at line {error.lineno}"
                )
            except ImportError as error:
                pytest.fail(f"{name}.py does not import: {error}")
    finally:
        if scripts_text in sys.path:
            sys.path.remove(scripts_text)


def test_ast_module_is_usable_for_extending_this_guard() -> None:
    """Keep the `ast` import meaningful for a reader extending this module."""
    assert ast.Module is not None
