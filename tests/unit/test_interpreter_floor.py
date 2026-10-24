"""Helpers must reject an unsupported interpreter with a legible message.

A consumer whose `python3` is older than the declared floor used to meet an
opaque `SyntaxError` from a helper line that is correct for this project. The
shared CLI factory now verifies `sys.version_info` against the declared floor
and exits with a message that names both the required and the detected version.

The floor is stated in `pyproject.toml`. `skills._cli.MINIMUM_SUPPORTED_PYTHON`
is the runtime reference, and the drift test below blocks the two from
disagreeing. Every other test derives its versions from that constant, so a
correct floor bump does not break them.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

import pytest

from skills import _cli

ROOT = Path(__file__).resolve().parents[2]

FLOOR = _cli.MINIMUM_SUPPORTED_PYTHON


def declared_python_floor() -> tuple[int, ...]:
    """Return the `>=` clause of the declared `requires-python` floor."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    clauses = project["project"]["requires-python"].split(",")
    floors = [clause for clause in clauses if clause.startswith(">=")]
    assert len(floors) == 1, f"expected one floor clause, found {floors}"
    return tuple(int(part) for part in floors[0][2:].split("."))


def version_below_floor() -> tuple[int, int, int]:
    """Return a version that sorts strictly below the floor."""
    major, minor, micro = FLOOR
    if micro > 0:
        return (major, minor, micro - 1)
    if minor > 0:
        return (major, minor - 1, 0)
    return (major - 1, 0, 0)


def version_above_floor() -> tuple[int, int, int]:
    """Return a version that sorts strictly above the floor."""
    major, minor, micro = FLOOR
    return (major, minor, micro + 1)


def test_minimum_supported_python_matches_the_declared_floor() -> None:
    """The runtime floor must not drift from the declared floor."""
    assert declared_python_floor() == FLOOR


def test_factory_rejects_an_interpreter_below_the_floor(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unsupported interpreter exits with an actionable message."""
    below_floor = version_below_floor()
    monkeypatch.setattr(sys, "version_info", below_floor)
    with pytest.raises(SystemExit) as error:
        _cli.argument_parser(description="test helper")

    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert _cli._version_text(FLOOR) in captured.err
    assert _cli._version_text(below_floor) in captured.err
    assert "or newer" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("version", [FLOOR, version_above_floor()])
def test_factory_accepts_the_floor_and_newer_interpreters(
    version: tuple[int, int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The floor itself and a newer interpreter both reach the parser."""
    monkeypatch.setattr(sys, "version_info", version)
    parser = _cli.argument_parser(description="test helper")

    assert isinstance(parser, argparse.ArgumentParser)
