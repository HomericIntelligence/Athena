"""Shared argparse construction for Athena's executable helpers."""

from __future__ import annotations

import argparse
import json
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
