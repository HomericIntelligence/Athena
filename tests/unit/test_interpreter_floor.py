"""Helpers must reject an unsupported interpreter with a legible message.

A consumer whose `python3` is older than the declared floor used to meet an
opaque `SyntaxError` from a helper line that is correct for this project. The
shared CLI factory now verifies `sys.version_info` against the declared floor
and exits with a message that names both the required and the detected version.

The floor is stated in `pyproject.toml`. `skills._cli.MINIMUM_SUPPORTED_PYTHON`
is the runtime reference, and the drift test below blocks the two from
disagreeing.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

import pytest

from skills import _cli

ROOT = Path(__file__).resolve().parents[2]


def declared_python_floor() -> tuple[int, ...]:
    """Return the `>=` clause of the declared `requires-python` floor."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    clauses = project["project"]["requires-python"].split(",")
    floors = [clause for clause in clauses if clause.startswith(">=")]
    assert len(floors) == 1, f"expected one floor clause, found {floors}"
    return tuple(int(part) for part in floors[0][2:].split("."))


def test_minimum_supported_python_matches_the_declared_floor() -> None:
    """The runtime floor must not drift from the declared floor."""
    assert declared_python_floor() == _cli.MINIMUM_SUPPORTED_PYTHON


def test_factory_rejects_an_interpreter_below_the_floor(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unsupported interpreter exits with an actionable message."""
    monkeypatch.setattr(sys, "version_info", (3, 13, 2))
    with pytest.raises(SystemExit) as error:
        _cli.argument_parser(description="test helper")

    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "3.14.8" in captured.err
    assert "3.13.2" in captured.err
    assert "or newer" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("version", [(3, 14, 8), (3, 15, 1)])
def test_factory_accepts_the_floor_and_newer_interpreters(
    version: tuple[int, int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The floor itself and a newer interpreter both reach the parser."""
    monkeypatch.setattr(sys, "version_info", version)
    parser = _cli.argument_parser(description="test helper")

    assert isinstance(parser, argparse.ArgumentParser)
