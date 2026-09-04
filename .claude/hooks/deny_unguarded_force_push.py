"""Reject unguarded Git force pushes in Claude Bash tool calls."""

from __future__ import annotations

import json
import shlex
import sys
from typing import Any


def is_unguarded_force_push(command: str) -> bool:
    """Return whether command is a Git push with force but no lease guard."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False

    if not tokens or tokens[0] != "git":
        return False

    index = 1
    while index < len(tokens) and tokens[index] in {"-C", "--git-dir", "--work-tree"}:
        index += 2
    while index < len(tokens) and tokens[index].startswith("--"):
        if tokens[index] == "--" or "=" not in tokens[index]:
            break
        index += 1

    if index >= len(tokens) or tokens[index] != "push":
        return False

    push_tokens = tokens[index + 1 :]
    has_lease = any(
        token == "--force-with-lease" or token.startswith("--force-with-lease=")
        for token in push_tokens
    )
    has_force = any(token in {"--force", "-f"} for token in push_tokens)
    return has_force and not has_lease


def main() -> int:
    """Read a Claude hook request and reject unsafe Bash commands."""
    try:
        request: dict[str, Any] = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return 0

    command = request.get("tool_input", {}).get("command", "")
    if isinstance(command, str) and is_unguarded_force_push(command):
        print(
            "Unguarded Git force push denied; use --force-with-lease.", file=sys.stderr
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
