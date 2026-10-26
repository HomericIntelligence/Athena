"""This module provides shared command-line support for Athena helpers."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

# `pyproject.toml` states the supported interpreter floor. The packaged archive
# does not carry that file, so this constant is the runtime reference and
# `tests/unit/test_interpreter_floor.py` blocks it from drifting.
MINIMUM_SUPPORTED_PYTHON: Final[tuple[int, int, int]] = (3, 14, 8)


def _version_text(version: tuple[int, ...]) -> str:
    """Return a dotted interpreter version for a failure message."""
    return ".".join(str(part) for part in version)


def _require_supported_interpreter(parser: argparse.ArgumentParser) -> None:
    """Stop with an actionable message when the interpreter is too old."""
    major, minor, micro = sys.version_info[:3]
    if (major, minor, micro) >= MINIMUM_SUPPORTED_PYTHON:
        return
    required = _version_text(MINIMUM_SUPPORTED_PYTHON)
    detected = f"{major}.{minor}.{micro}"
    parser.exit(
        2,
        f"{parser.prog}: error: This helper requires Python {required} or newer. "
        f"This interpreter is {detected}.\n",
    )


def run_command(
    arguments: Sequence[str], **kwargs: Any
) -> subprocess.CompletedProcess[str]:
    """Run an external command and report a missing required capability."""
    if not arguments:
        raise RuntimeError("The required command is empty.")
    try:
        check = kwargs.pop("check", False)
        return subprocess.run(arguments, check=check, **kwargs)
    except FileNotFoundError as error:
        command = error.filename or arguments[0]
        raise RuntimeError(
            f"The required command is not available: '{command}'."
        ) from error


def git_read_environment() -> dict[str, str]:
    """Return an isolated environment for immutable, non-interactive Git reads."""
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    # `--no-replace-objects` does not disable deprecated graft files. Force Git
    # to read an empty graft source. First, remove each inherited `GIT_*`
    # setting. These settings can redirect or change an immutable read. They
    # include location, object, index, configuration, attribute, pathspec, and
    # transport settings.
    environment.update(
        {
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_GRAFT_FILE": os.devnull,
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return environment


def git_read_arguments() -> tuple[str, ...]:
    """Return Git options that disable mutable local object-graph metadata."""
    return ("-c", "core.commitGraph=false", "--no-replace-objects")


def require_complete_git_history(*, cwd: Path | None = None) -> None:
    """Reject shallow history before calculation of immutable ancestry evidence."""
    result = run_command(
        ["git", *git_read_arguments(), "rev-parse", "--is-shallow-repository"],
        capture_output=True,
        cwd=cwd,
        env=git_read_environment(),
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = (
            result.stderr.strip()
            or "The git rev-parse --is-shallow-repository command failed."
        )
        raise RuntimeError(message)
    if result.stdout.strip() != "false":
        raise RuntimeError(
            "The immutable review evidence needs a non-shallow repository. "
            "Use a complete source snapshot."
        )


def require_unambiguous_git_merge_base(
    base_oid: str, head_oid: str, *, cwd: Path | None = None
) -> str:
    """Return the only immutable merge base or reject an ambiguous history."""
    result = run_command(
        [
            "git",
            *git_read_arguments(),
            "merge-base",
            "--all",
            base_oid,
            head_oid,
        ],
        capture_output=True,
        cwd=cwd,
        env=git_read_environment(),
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "The git merge-base command failed."
        raise RuntimeError(message)
    merge_bases = result.stdout.splitlines()
    if len(merge_bases) != 1 or not merge_bases[0]:
        raise RuntimeError(
            "The immutable review evidence requires one unambiguous merge base."
        )
    return merge_bases[0]


def corpus_manifest(module_file: Path) -> Path | None:
    """Return the manifest that declares the corpus version for one helper file."""
    corpus = corpus_root(module_file)
    if corpus is None:
        return None
    manifest = corpus / "_plugin.json"
    if not manifest.exists() and corpus.name == "skills":
        manifest = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
    return manifest


def corpus_root(module_file: Path) -> Path | None:
    """Return the nearest ancestor directory that anchors one Athena corpus.

    The anchor is the presence of the shared ``_cli.py`` helper. Directory
    names are not used, because the installed corpus directory and its parent
    use host-specific names.
    """
    for directory in module_file.resolve().parents:
        if (directory / "_cli.py").is_file():
            return directory
    return None


def corpus_version(module_file: Path) -> str | None:
    """Return the declared corpus version, or None when no manifest is readable."""
    manifest = corpus_manifest(module_file)
    if manifest is None:
        return None
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    version = document.get("version") if isinstance(document, dict) else None
    if not isinstance(version, str) or not version.strip():
        return None
    return version


def corpus_relative_path(module_file: Path) -> str:
    """Return the corpus-root-relative path of one helper file."""
    corpus = corpus_root(module_file)
    if corpus is None:
        return module_file.name
    return module_file.resolve().relative_to(corpus).as_posix()


def plugin_version() -> str:
    """Return this corpus's generated version or its adjacent canonical manifest."""
    version = corpus_version(Path(__file__))
    if version is None:
        manifest = corpus_manifest(Path(__file__))
        raise TypeError(
            "The plugin manifest does not contain a readable string version: "
            f"'{manifest}'."
        )
    return version


class _PluginVersionAction(argparse.Action):
    """Resolve the plugin version only when the option is requested."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        del namespace, values, option_string
        try:
            version = plugin_version()
        except (OSError, TypeError, UnicodeError, json.JSONDecodeError) as error:
            parser.exit(
                1,
                f"{parser.prog}: error: The tool cannot read the plugin version: "
                f"{error}\n",
            )
        print(f"{parser.prog} {version}")
        parser.exit(0)


def argument_parser(
    *, description: str | None = None, enforce_interpreter_floor: bool = True
) -> argparse.ArgumentParser:
    """Create the required parser with a consistent plugin-version action.

    Skill helpers keep the interpreter-floor check. The two repository tools that
    run on the CI runner's system interpreter (`ci_policy.py` and
    `validate_agent_contract.py`) pass `enforce_interpreter_floor=False`. Those
    tools parse on older interpreters, and the floor check would stop them.
    """
    parser = argparse.ArgumentParser(description=description)
    if enforce_interpreter_floor:
        _require_supported_interpreter(parser)
    parser.add_argument(
        "--version",
        action=_PluginVersionAction,
        nargs=0,
        help="Show the Athena plugin version and exit.",
    )
    return parser
