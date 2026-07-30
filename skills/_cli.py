"""Shared argparse construction for Athena's executable helpers."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Sequence


PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def run_command(
    arguments: Sequence[str], **kwargs: Any
) -> subprocess.CompletedProcess[str]:
    """Run an external command or identify a missing required capability."""
    if not arguments:
        raise RuntimeError("required command is empty")
    try:
        return subprocess.run(arguments, **kwargs)
    except FileNotFoundError as error:
        command = error.filename or arguments[0]
        raise RuntimeError(f"required command unavailable: {command}") from error


def git_read_environment() -> dict[str, str]:
    """Return a hermetic environment for immutable, non-interactive Git reads."""
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    # `--no-replace-objects` does not disable deprecated graft files. Force Git
    # to read an empty graft source. Strip every inherited GIT_* setting first:
    # location, object, index, config, attribute, pathspec, and transport
    # overrides can otherwise redirect or change a supposedly immutable read.
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


def require_complete_git_history() -> None:
    """Reject shallow history before deriving immutable ancestry evidence."""
    result = run_command(
        ["git", *git_read_arguments(), "rev-parse", "--is-shallow-repository"],
        capture_output=True,
        env=git_read_environment(),
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = (
            result.stderr.strip() or "git rev-parse --is-shallow-repository failed"
        )
        raise RuntimeError(message)
    if result.stdout.strip() != "false":
        raise RuntimeError(
            "immutable review evidence requires a non-shallow repository; "
            "use a complete source snapshot"
        )


def require_unambiguous_git_merge_base(base_oid: str, head_oid: str) -> str:
    """Return the sole immutable merge base or reject ambiguous topology."""
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
        env=git_read_environment(),
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "git merge-base failed"
        raise RuntimeError(message)
    merge_bases = result.stdout.splitlines()
    if len(merge_bases) != 1 or not merge_bases[0]:
        raise RuntimeError(
            "immutable review evidence requires one unambiguous merge base"
        )
    return merge_bases[0]


def plugin_version() -> str:
    """Return the version from the canonical Codex plugin manifest."""
    manifest = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    version = document.get("version") if isinstance(document, dict) else None
    if not isinstance(version, str):
        raise RuntimeError(f"plugin manifest has no string version: {manifest}")
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
        except (OSError, json.JSONDecodeError, RuntimeError) as error:
            parser.exit(
                1, f"{parser.prog}: error: cannot read plugin version: {error}\n"
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
        help="show the Athena plugin version and exit",
    )
    return parser
