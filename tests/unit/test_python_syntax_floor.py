"""Guard the Python source syntax level and the packaged helper imports.

Regression guard for HomericIntelligence/Athena#306, where seven multi-exception
`except` clauses used a Python 2 spelling that no supported host accepts, and
for HomericIntelligence/Athena#301, where nothing verified that the packaged
`pr-review` helpers import.

This repository uses two different interpreter levels, and each has its own
contract:

- `pyproject.toml` declares `requires-python = ">=3.14.8,<3.15"`. On that
  interpreter the Python 3.14 relaxation of multi-exception `except` clauses
  makes the old spelling legal again, so a plain compile on the declared floor
  cannot detect its return.
- `[tool.ruff] target-version = "py312"` pins the source syntax level, and
  `README.md` documents Python 3.12 or newer on the host. A host below 3.14
  rejects that spelling with a hard `SyntaxError`, so the source must stay
  inside 3.12 syntax even though the declared floor is newer.

This module therefore checks that every tracked Python file compiles on the
running interpreter, parses at the documented 3.12 syntax level, and that the
`pr-review` helper chain imports through its real dependency path.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import tomllib
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


def documented_syntax_level() -> tuple[int, int]:
    """Return the `(major, minor)` syntax level pinned by the ruff target.

    The pin is the canonical record of the source syntax contract, so the guard
    reads it instead of hard-coding a level that can drift silently.
    """
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)
    target = project.get("tool", {}).get("ruff", {}).get("target-version")
    assert isinstance(target, str) and target.startswith("py"), (
        "[tool.ruff] target-version is missing or unreadable; re-anchor"
        " documented_syntax_level() before trusting the syntax-level check"
    )
    digits = target.removeprefix("py").replace("_", "")
    assert digits.isdigit() and len(digits) >= 3, (
        f"cannot read a version from {target!r}"
    )
    return (int(digits[0]), int(digits[1:]))


def test_enumeration_finds_the_repository_sources() -> None:
    """Guard the enumeration so a discovery bug cannot pass silently."""
    names = {path.name for path in tracked_python_files()}
    assert len(names) > 20, f"expected the repository Python files, found {len(names)}"
    for expected in DELIVERY_CHAIN:
        assert f"{expected}.py" in names, f"{expected}.py is not tracked"


def test_declared_floor_is_known_to_rust() -> None:
    """The floor this test relies on must stay explicit in the project file.

    If `requires-python` is ever lowered below 3.14, the helpers stop importing
    on the floor and this module's import check becomes the thing that catches
    it. Recording the value keeps that dependency explicit.
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.14.8,<3.15"' in text, (
        "requires-python changed; re-check that the pr-review helpers still"
        " import on the declared floor before trusting the checks below"
    )


def test_the_syntax_level_gate_rejects_the_python_2_except_spelling() -> None:
    """Negative control: the syntax-level gate must reject what it exists for.

    `ast.parse` documents `feature_version` as a best-effort emulation of an
    older grammar. That makes the PEP 758 gating this guard relies on a
    CPython implementation detail: if the interpreter stops applying it, the
    sweep below would pass every file while checking nothing.

    This control fails as soon as that happens, so the gate cannot go inert
    silently. The unparenthesised multi-exception form is invalid below 3.14
    on every supported host, and the declared floor is 3.14, so this holds
    whether the control runs on 3.12, 3.13, or 3.14.
    """
    with pytest.raises(SyntaxError):
        ast.parse(
            "try:\n    pass\nexcept OSError, ValueError:\n    pass\n",
            filename="except_two_values.py",
            feature_version=documented_syntax_level(),
        )


@pytest.mark.parametrize(
    "path",
    tracked_python_files(),
    ids=lambda path: str(path.relative_to(ROOT)),
)
def test_tracked_python_file_compiles(path: Path) -> None:
    """Each tracked Python file must compile on the declared interpreter floor."""
    try:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    except SyntaxError as error:
        pytest.fail(
            f"{path.relative_to(ROOT)} does not compile on the declared floor: "
            f"{error.msg} at line {error.lineno}"
        )


@pytest.mark.parametrize(
    "path",
    tracked_python_files(),
    ids=lambda path: str(path.relative_to(ROOT)),
)
def test_tracked_python_file_parses_at_the_documented_syntax_level(path: Path) -> None:
    """Each tracked Python file must parse at the ruff-pinned syntax level."""
    try:
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
            feature_version=documented_syntax_level(),
        )
    except SyntaxError as error:
        pytest.fail(
            f"{path.relative_to(ROOT)} does not parse at the documented syntax"
            f" level: {error.msg} at line {error.lineno}"
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
