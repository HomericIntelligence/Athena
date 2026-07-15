"""Shared argparse construction for Athena's executable helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def plugin_version() -> str:
    """Return the version from the canonical Codex plugin manifest."""
    manifest = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    version = document.get("version") if isinstance(document, dict) else None
    if not isinstance(version, str):
        raise RuntimeError(f"plugin manifest has no string version: {manifest}")
    return version


def argument_parser(*, description: str | None = None) -> argparse.ArgumentParser:
    """Create the required parser with a consistent plugin-version action."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {plugin_version()}"
    )
    return parser
