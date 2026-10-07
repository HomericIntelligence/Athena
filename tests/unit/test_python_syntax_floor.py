"""Every tracked Python file must compile and import on the declared floor.

Regression guard for HomericIntelligence/Athena#301, which reported that three
`pr-review` helpers could not be imported.

The report was partly mistaken, and this test encodes the corrected
understanding so the next reader does not repeat it:

- `pyproject.toml` declares `requires-python = ">=3.14.7,<3.15"`, and `ruff`
  infers `target-version = 3.14` from that. PEP 758 makes the unparenthesised
  `except X, Y:` form valid again in 3.14, so on the declared floor those
  helpers import and run correctly. `ruff format` actively *prefers* the
  unparenthesised form at that target, so rewriting it to `except (X, Y):`
  fights the formatter and fails the required `format-check` gate.
- The same construct is a hard `SyntaxError` on Python 3.13 and earlier. That
  matters only for a host whose `python3` is older than this repository's
  floor, which is a distribution concern rather than a source defect.

So the defect that is real and source-level is not the `except` spelling. It is
that nothing verifies the packaged helpers actually import, which is why a
`SyntaxError` in `anchor_proofs.py` can reach a published plugin unnoticed:
that helper cannot produce the anchor manifest reviewer delivery requires, and
`collect_evidence.py` cannot produce the scope, requirements, and
path-manifest digests the GO path consumes.

This test therefore checks what holds on the declared floor: every tracked
Python file compiles, and the `pr-review` helper chain imports through its real
dependency path.
"""

from __future__ import annotations

import ast
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


def test_declared_floor_is_known_to_rust() -> None:
    """The floor this test relies on must stay explicit in the project file.

    If `requires-python` is ever lowered below 3.14, the helpers stop importing
    on the floor and this module's import check becomes the thing that catches
    it. Recording the value keeps that dependency explicit.
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.14.7,<3.15"' in text, (
        "requires-python changed; re-check that the pr-review helpers still"
        " import on the declared floor before trusting the checks below"
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
