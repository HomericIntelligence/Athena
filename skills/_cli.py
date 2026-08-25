"""This module provides shared command-line support for Athena helpers."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


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


def plugin_version() -> str:
    """Return the version from the canonical Codex plugin manifest."""
    manifest = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    version = document.get("version") if isinstance(document, dict) else None
    if not isinstance(version, str):
        raise TypeError(
            f"The plugin manifest does not contain a string version: '{manifest}'."
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
        except (OSError, TypeError, json.JSONDecodeError) as error:
            parser.exit(
                1,
                f"{parser.prog}: error: The tool cannot read the plugin version: "
                f"{error}\n",
            )
        print(f"{parser.prog} {version}")
        parser.exit(0)


def argument_parser(*, description: str | None = None) -> argparse.ArgumentParser:
    """Create the required parser with a consistent plugin-version action."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--version",
        action=_PluginVersionAction,
        nargs=0,
        help="Show the Athena plugin version and exit.",
    )
    return parser
