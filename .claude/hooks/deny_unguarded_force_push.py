"""Reject unguarded Git force pushes in Claude Bash tool calls."""

from __future__ import annotations

import json
import re
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

_SHELL_INTERPRETERS = {
    "bash",
    "sh",
}

_UNSUPPORTED_COMMAND_STARTS = {
    "case",
    "do",
    "done",
    "elif",
    "else",
    "esac",
    "fi",
    "for",
    "function",
    "if",
    "select",
    "then",
    "until",
    "while",
}

_ENV_FLAGS = {
    "-i",
    "--ignore-environment",
}

_ENV_OPTIONS_WITH_VALUE = {
    "-u",
    "--unset",
    "-C",
    "--chdir",
    "--default-signal",
    "--block-signal",
}

_TRANSPARENT_WRAPPERS = {
    "builtin",
    "command",
    "exec",
    "sudo",
    "time",
}

_CONTROL_KEYWORDS = {
    "case",
    "do",
    "else",
    "elif",
    "fi",
    "for",
    "function",
    "if",
    "select",
    "then",
    "until",
    "while",
    "esac",
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


def _has_short_option_flag(token: str, flag: str) -> bool:
    """Return whether a short option cluster includes one flag."""
    return token.startswith("-") and not token.startswith("--") and flag in token[1:]


def _push_ref_variants(ref: str) -> set[str]:
    """Return comparable ref names for one push or lease target."""
    variants = {ref}

    if ref.startswith("refs/heads/"):
        variants.add(ref.removeprefix("refs/heads/"))
    elif "/" not in ref:
        variants.add(f"refs/heads/{ref}")

    return variants


def _parse_force_with_lease(token: str) -> tuple[bool, str | None]:
    """Return whether one lease token is scoped and its ref name when present."""
    if token == "--force-with-lease":
        return True, None

    if token.startswith("--force-with-lease="):
        value = token.removeprefix("--force-with-lease=")
        ref, _, _ = value.partition(":")
        return False, ref or None

    return False, None


def _parse_forced_refspec(token: str) -> str | None:
    """Return the pushed destination ref for one forced refspec."""
    if not _is_forced_refspec(token):
        return None

    refspec = token.removeprefix("+")
    _, _, destination = refspec.partition(":")
    return destination or refspec or None


def _is_shell_assignment(token: str) -> bool:
    """Return whether token is a leading shell assignment."""
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token))


def _is_shell_interpreter(token: str) -> bool:
    """Return whether token selects a shell that can run nested commands."""
    return token.rsplit("/", maxsplit=1)[-1] in _SHELL_INTERPRETERS


def _extract_parenthesized_payload(command: str, start: int) -> tuple[str | None, int]:
    """Return the payload inside a balanced parenthesized shell expansion."""
    quote: str | None = None
    escaped = False
    depth = 1
    index = start

    while index < len(command):
        character = command[index]

        if escaped:
            escaped = False
        elif character == "\\" and quote != "'":
            escaped = True
        elif character == "'" and quote != '"':
            quote = None if quote == "'" else "'"
        elif character == '"' and quote != "'":
            quote = None if quote == '"' else '"'
        elif quote != "'":
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    return command[start:index], index + 1

        index += 1

    return None, start


def _extract_backtick_payload(command: str, start: int) -> tuple[str | None, int]:
    """Return the payload inside a backtick shell expansion."""
    escaped = False
    index = start

    while index < len(command):
        character = command[index]

        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "`":
            return command[start:index], index + 1

        index += 1

    return None, start


def _contains_unguarded_force_push_shell_expansion(command: str) -> bool:
    """Return whether an active shell expansion contains an unsafe push."""
    quote: str | None = None
    escaped = False
    index = 0

    while index < len(command):
        character = command[index]

        if escaped:
            escaped = False
        elif character == "\\" and quote != "'":
            escaped = True
        elif character == "'" and quote != '"':
            quote = None if quote == "'" else "'"
        elif character == '"' and quote != "'":
            quote = None if quote == '"' else '"'
        elif quote != "'":
            if character == "`":
                payload, next_index = _extract_backtick_payload(command, index + 1)
                if payload is None:
                    return False
                if is_unguarded_force_push(payload):
                    return True
                index = next_index - 1
            elif character in {"$", "<", ">"} and command[index + 1 : index + 2] == "(":
                payload, next_index = _extract_parenthesized_payload(command, index + 2)
                if payload is None:
                    return False
                if is_unguarded_force_push(payload):
                    return True
                index = next_index - 1
        index += 1

    return False


def _extract_shell_c_command(tokens: list[str], start: int) -> str | None:
    """Return the command string passed to a shell -c wrapper."""
    index = start + 1

    while index < len(tokens):
        token = tokens[index]

        if token in {"(", ")"}:
            index += 1
            continue
        if token == "-" or (token.startswith("-") and not token.startswith("--")):
            if "c" in token[1:]:
                if index + 1 >= len(tokens):
                    return None
                return tokens[index + 1]
            index += 1
            continue
        break

    return None


def _consume_env_prefix(tokens: list[str], index: int) -> int | None:
    """Return the index of the command after env options."""
    while index < len(tokens):
        token = tokens[index]

        if token in {"(", ")"}:
            return None

        if _is_shell_assignment(token):
            index += 1
            continue

        if token in _ENV_FLAGS or token == "-":
            index += 1
            continue

        if token in _ENV_OPTIONS_WITH_VALUE:
            if index + 1 >= len(tokens):
                return None
            value = tokens[index + 1]
            if (
                value in {"(", ")"}
                or _is_shell_assignment(value)
                or value.startswith("-")
            ):
                return None
            index += 2
            continue

        if any(token.startswith(f"{option}=") for option in _ENV_OPTIONS_WITH_VALUE):
            index += 1
            continue

        if token.startswith("-"):
            return None

        break

    return index


def _consume_command_prefix(tokens: list[str]) -> int | None:
    """Return the index of the actual command token after shell wrappers."""
    index = 0

    while index < len(tokens):
        token = tokens[index]

        if token in {"(", ")"}:
            return None

        if _is_shell_assignment(token):
            index += 1
            continue

        if token in _CONTROL_KEYWORDS or token in _TRANSPARENT_WRAPPERS:
            index += 1
            continue

        if token != "env":
            break

        index += 1
        index = _consume_env_prefix(tokens, index)
        if index is None:
            return None

    return index


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
    if not tokens:
        return False

    if len(tokens) >= 2 and tokens[0] == "(" and tokens[-1] == ")":
        return _is_unguarded_force_push_segment(tokens[1:-1])

    start = _consume_command_prefix(tokens)
    if start is None or start >= len(tokens):
        return False

    tokens = tokens[start:]

    if _is_shell_interpreter(tokens[0]):
        command = _extract_shell_c_command(tokens, 0)
        return bool(command and is_unguarded_force_push(command))

    if tokens[0] != "git":
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
    has_force = any(
        token == "--force" or _has_short_option_flag(token, "f")
        for token in push_tokens
    )
    if has_force:
        return True

    unscoped_leases = 0
    scoped_leases: set[str] = set()
    forced_refspecs: list[str] = []

    for token in push_tokens:
        lease_is_unscoped, lease_ref = _parse_force_with_lease(token)
        if lease_is_unscoped:
            unscoped_leases += 1
        elif lease_ref is not None:
            scoped_leases.update(_push_ref_variants(lease_ref))

        forced_refspec = _parse_forced_refspec(token)
        if forced_refspec is not None:
            forced_refspecs.append(forced_refspec)

    if not forced_refspecs:
        return False

    if unscoped_leases:
        return False

    return any(
        not _push_ref_variants(forced_refspec).intersection(scoped_leases)
        for forced_refspec in forced_refspecs
    )


def is_unguarded_force_push(command: str) -> bool:
    """Return whether command has a Git push with force but no lease guard."""
    if _contains_unguarded_force_push_shell_expansion(command):
        return True

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
