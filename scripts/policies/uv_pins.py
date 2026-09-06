"""This module defines the uv version consistency policy."""

from __future__ import annotations

import re
from typing import Any

import yaml

_UV_URL = re.compile(
    r"https://github\.com/astral-sh/uv/releases/download/"
    r"(?P<version>\d+\.\d+\.\d+)/uv-x86_64-unknown-linux-gnu\.tar\.gz"
)
_CHECKSUM_ARGUMENT = re.compile(r"(?P<checksum>\S+)[^\S\r\n]+/tmp/uv\.tar\.gz")
_HEX_CHECKSUM = re.compile(r"[0-9a-f]{64}")
_SHELL_CONTINUATION = re.compile(r"\\\r?\n[ \t]*")
_SETUP_UV = "astral-sh/setup-uv@"
_COMMAND_BOUNDARIES = frozenset({"&&", "||", ";", "|", "&"})


def _finish_word(
    tokens: list[tuple[str, bool]], word: list[str], word_started: bool
) -> None:
    if word_started:
        tokens.append(("".join(word), False))
        word.clear()


def _shell_token_lines(container_text: str) -> list[list[tuple[str, bool]]]:
    """Return logical shell lines as word and operator tokens."""
    logical_text = _SHELL_CONTINUATION.sub(" ", container_text)
    token_lines: list[list[tuple[str, bool]]] = []

    for line in logical_text.splitlines():
        tokens: list[tuple[str, bool]] = []
        word: list[str] = []
        word_started = False
        quote: str | None = None
        escaped = False
        index = 0

        while index < len(line):
            character = line[index]
            if escaped:
                word.append(character)
                word_started = True
                escaped = False
            elif character == "\\" and quote != "'":
                word_started = True
                escaped = True
            elif quote is not None:
                if character == quote:
                    quote = None
                else:
                    word.append(character)
            elif character in {"'", '"'}:
                quote = character
                word_started = True
            elif character == "#" and not word_started:
                break
            elif character.isspace():
                _finish_word(tokens, word, word_started)
                word_started = False
            elif character in {"&", "|", ";"}:
                _finish_word(tokens, word, word_started)
                word_started = False
                operator = character
                if (
                    character in {"&", "|"}
                    and index + 1 < len(line)
                    and line[index + 1] == character
                ):
                    operator += character
                    index += 1
                tokens.append((operator, True))
            else:
                word.append(character)
                word_started = True
            index += 1

        if escaped:
            word.append("\\")
        _finish_word(tokens, word, word_started)
        token_lines.append(tokens)

    return token_lines


def _checksum_from_tokens(tokens: list[tuple[str, bool]]) -> str | None:
    if tokens and not tokens[0][1] and tokens[0][0].casefold() == "run":
        tokens = tokens[1:]

    for index, token in enumerate(tokens):
        if token != ("echo", False):
            continue
        if index > 0:
            previous_value, previous_is_operator = tokens[index - 1]
            if not previous_is_operator or previous_value not in _COMMAND_BOUNDARIES:
                continue

        argument_index = index + 1
        if argument_index >= len(tokens) or tokens[argument_index][1]:
            continue
        argument_match = _CHECKSUM_ARGUMENT.fullmatch(tokens[argument_index][0])
        if argument_match is not None:
            pipe_index = argument_index + 1
            checksum = argument_match.group("checksum")
        elif (
            argument_index + 1 < len(tokens)
            and not tokens[argument_index + 1][1]
            and tokens[argument_index + 1][0] == "/tmp/uv.tar.gz"
        ):
            pipe_index = argument_index + 2
            checksum = tokens[argument_index][0]
        else:
            continue

        if tokens[pipe_index : pipe_index + 3] == [
            ("|", True),
            ("sha256sum", False),
            ("--check", False),
        ]:
            return checksum
    return None


def _download_version_from_tokens(tokens: list[tuple[str, bool]]) -> str | None:
    if tokens and not tokens[0][1] and tokens[0][0].casefold() == "run":
        tokens = tokens[1:]

    for index, token in enumerate(tokens):
        if token != ("curl", False):
            continue
        if index > 0:
            previous_value, previous_is_operator = tokens[index - 1]
            if not previous_is_operator or previous_value not in _COMMAND_BOUNDARIES:
                continue

        command_end = next(
            (
                command_index
                for command_index in range(index + 1, len(tokens))
                if tokens[command_index][1]
                and tokens[command_index][0] in _COMMAND_BOUNDARIES
            ),
            len(tokens),
        )
        arguments = tokens[index + 1 : command_end]
        writes_archive = any(
            arguments[argument_index] == ("-o", False)
            and arguments[argument_index + 1] == ("/tmp/uv.tar.gz", False)
            for argument_index in range(len(arguments) - 1)
        )
        if not writes_archive:
            continue
        for value, is_operator in arguments:
            if not is_operator and (match := _UV_URL.search(value)) is not None:
                return match.group("version")
    return None


def _container_pin(container_text: str) -> tuple[str | None, str | None]:
    token_lines = _shell_token_lines(container_text)
    version = next(
        (
            value
            for line in token_lines
            if (value := _download_version_from_tokens(line)) is not None
        ),
        None,
    )
    checksum = next(
        (
            value
            for line in token_lines
            if (value := _checksum_from_tokens(line)) is not None
        ),
        None,
    )
    return (
        version,
        checksum,
    )


def _workflow_versions(value: Any) -> list[str | None]:
    if isinstance(value, dict):
        versions: list[str | None] = []
        uses = value.get("uses")
        if isinstance(uses, str) and uses.casefold().startswith(_SETUP_UV):
            step_with = value.get("with", {})
            versions.append(
                step_with.get("version") if isinstance(step_with, dict) else None
            )
        for child in value.values():
            versions.extend(_workflow_versions(child))
        return versions
    if isinstance(value, list):
        versions = []
        for child in value:
            versions.extend(_workflow_versions(child))
        return versions
    return []


def find_uv_pin_drift(container_text: str, workflow_texts: dict[str, str]) -> list[str]:
    """Return findings when Containerfile and workflow uv pins differ."""
    container_version, checksum = _container_pin(container_text)
    findings: list[str] = []
    if container_version is None:
        findings.append("The Containerfile uv release URL is missing or malformed.")
    if checksum is None:
        findings.append(
            "The Containerfile uv SHA-256 checksum is missing or malformed."
        )
    elif _HEX_CHECKSUM.fullmatch(checksum) is None:
        findings.append(
            "The Containerfile uv SHA-256 checksum must contain 64 lowercase "
            "hexadecimal characters."
        )

    setup_uv_found = False
    for filename, workflow_text in sorted(workflow_texts.items()):
        try:
            workflow = yaml.safe_load(workflow_text)
        except yaml.YAMLError as error:
            findings.append(f"The workflow '{filename}' is not valid YAML: {error}.")
            continue
        versions = _workflow_versions(workflow)
        if not versions:
            continue
        setup_uv_found = True
        for version in versions:
            if not isinstance(version, str):
                findings.append(
                    f"The setup-uv step in '{filename}' has no valid version pin."
                )
            elif container_version is not None and version != container_version:
                findings.append(
                    f"The workflow '{filename}' pins uv '{version}', but the "
                    f"Containerfile pins '{container_version}'."
                )
    if not setup_uv_found:
        findings.append("No astral-sh/setup-uv step has a version pin.")
    return findings
