"""Reject unguarded Git force pushes in Claude Bash tool calls."""

from __future__ import annotations

import json
import shlex
import sys
from typing import Any


_GLOBAL_OPTIONS_WITH_VALUE = {
    "-C",
    "-c",
    "--attr-source",
    "--config-env",
    "--exec-path",
    "--git-dir",
    "--list-cmds",
    "--namespace",
    "--super-prefix",
    "--work-tree",
}

_GLOBAL_FLAGS = {
    "--bare",
    "--glob-pathspecs",
    "--help",
    "--html-path",
    "--icase-pathspecs",
    "--info-path",
    "--literal-pathspecs",
    "--man-path",
    "--no-advice",
    "--no-lazy-fetch",
    "--no-optional-locks",
    "--no-pager",
    "--no-replace-objects",
    "--noglob-pathspecs",
    "--paginate",
    "--version",
    "-P",
    "-h",
    "-p",
    "-v",
}

_SHELL_CONTROL_OPERATORS = {
    "&&",
    "||",
    ";",
    "|",
    "&",
}


def _tokenize_bash_command(command: str) -> list[str] | None:
    """Split a Bash command into tokens with operator tokens preserved."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    except ValueError:
        return None

    lexer.whitespace_split = True
    return list(lexer)


def _consume_git_global_option(tokens: list[str], index: int) -> int | None:
    """Return the next token index after a recognized git global option."""
    token = tokens[index]

    if token in _GLOBAL_FLAGS:
        return index + 1

    if "=" in token:
        option, _, _ = token.partition("=")
        if option in _GLOBAL_OPTIONS_WITH_VALUE:
            return index + 1

    if token in _GLOBAL_OPTIONS_WITH_VALUE:
        if index + 1 >= len(tokens):
            return None
        return index + 2

    return None


def _is_forced_refspec(token: str) -> bool:
    """Return whether a push refspec forces an update."""
    return token.startswith("+")


def _iter_command_segments(command: str) -> list[list[str]]:
    segments: list[list[str]] = []

    for line in command.splitlines():
        tokens = _tokenize_bash_command(line)
        if tokens is None:
            return []

        segment: list[str] = []

        for token in tokens:
            if token in _SHELL_CONTROL_OPERATORS:
                if segment:
                    segments.append(segment)
                    segment = []
                continue

            segment.append(token)

        if segment:
            segments.append(segment)

    return segments


def _is_unguarded_force_push_segment(tokens: list[str]) -> bool:
    """Return whether one command segment is an unguarded Git push."""
    if not tokens or tokens[0] != "git":
        return False

    index = 1
    while index < len(tokens):
        if tokens[index] == "push":
            break

        next_index = _consume_git_global_option(tokens, index)
        if next_index is None:
            return False
        index = next_index

    if index >= len(tokens) or tokens[index] != "push":
        return False

    push_tokens = tokens[index + 1 :]
    has_force = any(token in {"--force", "-f"} for token in push_tokens)
    has_force_with_lease = any(
        token == "--force-with-lease"
        or token.startswith("--force-with-lease=")
        for token in push_tokens
    )
    has_forced_refspec = any(
        _is_forced_refspec(token)
        for token in push_tokens
        if not token.startswith("-")
    )
    return has_force or (has_forced_refspec and not has_force_with_lease)


def is_unguarded_force_push(command: str) -> bool:
    """Return whether command is a Git push with force but no lease guard."""
    for tokens in _iter_command_segments(command):
        if _is_unguarded_force_push_segment(tokens):
            return True
    return False


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
