"""Validate the root agent-contract documents."""

from __future__ import annotations

import os
import re
import stat
import unicodedata
from pathlib import Path
from typing import NamedTuple

AGENTS_START_MARKER = (
    "<!-- BEGIN ATHENA DEVELOPMENT PRINCIPLES: agent-contract-v1.0.0 -->"
)
AGENTS_END_MARKER = "<!-- END ATHENA DEVELOPMENT PRINCIPLES -->"
CLAUDE_POINTER = b"@AGENTS.md\n"
CONTRACT_TAG = "agent-contract-v1.0.0"
DETAIL_URL_PREFIX = (
    "https://github.com/HomericIntelligence/Athena/blob/"
    f"{CONTRACT_TAG}/docs/principles/"
)
EXPECTED_PRINCIPLE_IDENTIFIERS = tuple(f"P{number:03d}" for number in range(1, 92))
MAX_ROOT_DOCUMENT_BYTES = 256 * 1024
MAX_CATALOG_BYTES = 256 * 1024
CATALOG_ENTRY = re.compile(
    r"\A\[(?P<name>[^\]\r\n]+)\]"
    r"\((?P<detail>details/p[0-9]{3}-[a-z0-9-]+\.md)\)"
    r" — (?P<description>.+)\Z"
)
MARKDOWN_HEADING = re.compile(r"^(?P<level>#{1,3}) (?P<title>[^\r\n]+)$")
PRINCIPLE_IDENTIFIER = re.compile(r"P[0-9]{3}")
_NOFOLLOW_SUPPORTED = hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_CLOSE_ON_EXEC = getattr(os, "O_CLOEXEC", 0)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
_BIDI_CONTROL_CLASSES = {
    "LRE",
    "RLE",
    "LRO",
    "RLO",
    "PDF",
    "LRI",
    "RLI",
    "FSI",
    "PDI",
}


class AgentContractError(NamedTuple):
    """This record describes one agent-contract failure."""

    path: str
    reason: str


class Principle(NamedTuple):
    """This record contains one canonical development principle."""

    identifier: str
    name: str
    description: str
    detail_path: str


class _MarkdownHeading(NamedTuple):
    """This record identifies one Markdown heading outside a fenced block."""

    line_index: int
    level: int
    title: str


class _NotRegularFileError(OSError):
    """A selected repository path is not a regular file."""


def _close_descriptor_quietly(descriptor: int) -> None:
    """Close a descriptor without masking an active result or error."""
    try:
        os.close(descriptor)
    except OSError:
        # A failed close leaves descriptor ownership unspecified. Do not retry it.
        return


def _opening_fence(line: str) -> tuple[str, int] | None:
    indentation = len(line) - len(line.lstrip(" "))
    if indentation > 3:
        return None
    candidate = line[indentation:]
    if not candidate or candidate[0] not in {chr(96), "~"}:
        return None
    fence_character = candidate[0]
    fence_length = len(candidate) - len(candidate.lstrip(fence_character))
    if fence_length < 3:
        return None
    information = candidate[fence_length:]
    if fence_character == chr(96) and fence_character in information:
        return None
    return fence_character, fence_length


def _is_closing_fence(line: str, character: str, minimum_length: int) -> bool:
    indentation = len(line) - len(line.lstrip(" "))
    if indentation > 3:
        return False
    candidate = line[indentation:]
    fence_length = len(candidate) - len(candidate.lstrip(character))
    return fence_length >= minimum_length and candidate[fence_length:].strip() == ""


def _outside_fence_mask(lines: list[str]) -> tuple[list[bool], bool]:
    outside: list[bool] = []
    active_fence: tuple[str, int] | None = None
    for line in lines:
        if active_fence is None:
            outside.append(True)
            active_fence = _opening_fence(line)
            continue
        outside.append(False)
        character, minimum_length = active_fence
        if _is_closing_fence(line, character, minimum_length):
            active_fence = None
    return outside, active_fence is not None


def _open_relative_regular(
    root: Path, relative_path: Path
) -> tuple[int, os.stat_result]:
    if not _NOFOLLOW_SUPPORTED:
        raise OSError("This platform cannot open repository paths without links.")
    if (
        relative_path.is_absolute()
        or not relative_path.parts
        or any(part in {"", ".", ".."} for part in relative_path.parts)
    ):
        raise OSError(f"The relative path is invalid: '{relative_path}'.")

    directory_flags = os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOSE_ON_EXEC
    file_flags = os.O_RDONLY | _NOFOLLOW | _CLOSE_ON_EXEC | _NONBLOCK
    directory_descriptor: int | None = os.open(root, directory_flags)
    file_descriptor: int | None = None
    try:
        for component in relative_path.parts[:-1]:
            assert directory_descriptor is not None
            child_descriptor = os.open(
                component,
                directory_flags,
                dir_fd=directory_descriptor,
            )
            try:
                os.close(directory_descriptor)
            except OSError:
                # A failed close leaves ownership unspecified. Close the child once.
                directory_descriptor = None
                _close_descriptor_quietly(child_descriptor)
                raise
            directory_descriptor = child_descriptor
        assert directory_descriptor is not None
        file_descriptor = os.open(
            relative_path.parts[-1],
            file_flags,
            dir_fd=directory_descriptor,
        )
        metadata = os.fstat(file_descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise _NotRegularFileError("The selected path is not a regular file.")
        return file_descriptor, metadata
    except BaseException:
        if file_descriptor is not None:
            _close_descriptor_quietly(file_descriptor)
        raise
    finally:
        if directory_descriptor is not None:
            _close_descriptor_quietly(directory_descriptor)


def _read_bounded_regular_utf8(
    root: Path, relative_path: Path, maximum_bytes: int
) -> tuple[str | None, str | None]:
    try:
        file_descriptor, metadata = _open_relative_regular(root, relative_path)
    except OSError as error:
        return (
            None,
            (
                "is missing or unreadable and must be a regular file without symbolic "
                f"links. {error}"
            ),
        )

    try:
        if metadata.st_size > maximum_bytes:
            return None, f"exceeds {maximum_bytes} bytes."
        content = bytearray()
        while len(content) <= maximum_bytes:
            remaining = maximum_bytes + 1 - len(content)
            chunk = os.read(file_descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            content.extend(chunk)
        if len(content) > maximum_bytes:
            return None, f"exceeds {maximum_bytes} bytes."
        try:
            return bytes(content).decode("utf-8"), None
        except UnicodeError as error:
            return None, f"must be readable UTF-8. {error}"
    except OSError as error:
        return None, f"is missing or unreadable. {error}"
    finally:
        os.close(file_descriptor)


def _read_root_document(
    repo_root: Path, filename: str
) -> tuple[str | None, list[AgentContractError]]:
    text, failure = _read_bounded_regular_utf8(
        repo_root, Path(filename), MAX_ROOT_DOCUMENT_BYTES
    )
    if failure is None:
        return text, []
    return None, [AgentContractError(filename, f"The root '{filename}' {failure}")]


def _catalog_error(reason: str) -> AgentContractError:
    return AgentContractError("docs/principles/README.md", reason)


def _unsafe_character(text: str) -> str | None:
    for character in text:
        if character == "\n":
            continue
        if (
            unicodedata.category(character).startswith("C")
            or unicodedata.bidirectional(character) in _BIDI_CONTROL_CLASSES
        ):
            return f"U+{ord(character):04X}"
    return None


def _normalize_catalog_entry(lines: list[str]) -> str | None:
    if not lines or lines[0] != "":
        return None
    content = lines[1:]
    while content and content[-1] == "":
        content.pop()
    if not content:
        return None
    if any(line == "" or line != line.strip() for line in content):
        return None
    return " ".join(content)


def _regular_relative_failure(root: Path, relative_path: Path) -> str | None:
    try:
        file_descriptor, _ = _open_relative_regular(root, relative_path)
    except OSError as error:
        return str(error)
    os.close(file_descriptor)
    return None


def parse_principles_catalog(
    catalog_root: Path,
) -> tuple[tuple[Principle, ...], list[AgentContractError]]:
    """Parse and validate the canonical Athena principles catalog."""
    catalog_relative_path = Path("docs") / "principles" / "README.md"
    text, failure = _read_bounded_regular_utf8(
        catalog_root, catalog_relative_path, MAX_CATALOG_BYTES
    )
    if failure is not None:
        return (), [_catalog_error(f"The principles catalog {failure}")]
    assert text is not None

    unsafe_character = _unsafe_character(text)
    if unsafe_character is not None:
        return (), [
            _catalog_error(
                "The principles catalog contains an unsafe control or bidirectional "
                f"character: {unsafe_character}."
            )
        ]

    errors: list[AgentContractError] = []
    principles: list[Principle] = []
    seen_identifiers: set[str] = set()
    seen_detail_paths: set[str] = set()
    lines = text.split("\n")
    outside_fence, unterminated_fence = _outside_fence_mask(lines)
    if unterminated_fence:
        errors.append(
            _catalog_error("The principles catalog has an unterminated fenced block.")
        )
    headings: list[_MarkdownHeading] = []
    for line_index, line in enumerate(lines):
        if not outside_fence[line_index]:
            continue
        heading_match = MARKDOWN_HEADING.fullmatch(line)
        if heading_match is not None:
            headings.append(
                _MarkdownHeading(
                    line_index,
                    len(heading_match.group("level")),
                    heading_match.group("title"),
                )
            )

    for index, catalog_heading in enumerate(headings):
        if catalog_heading.level != 3:
            continue
        identifier = catalog_heading.title
        if PRINCIPLE_IDENTIFIER.fullmatch(identifier) is None:
            errors.append(
                _catalog_error(
                    f"The heading '{identifier}' does not match the required catalog structure."
                )
            )
            continue
        end_line = (
            headings[index + 1].line_index if index + 1 < len(headings) else len(lines)
        )
        normalized_entry = _normalize_catalog_entry(
            lines[catalog_heading.line_index + 1 : end_line]
        )
        entry = (
            CATALOG_ENTRY.fullmatch(normalized_entry)
            if normalized_entry is not None
            else None
        )
        if entry is None:
            errors.append(
                _catalog_error(
                    f"The '{identifier}' entry does not match the required catalog structure."
                )
            )
            continue

        detail_path = entry.group("detail")
        name = entry.group("name")
        description = entry.group("description")
        if identifier in seen_identifiers:
            errors.append(
                _catalog_error(
                    f"The catalog has duplicate principle identifier '{identifier}'."
                )
            )
        seen_identifiers.add(identifier)
        if detail_path in seen_detail_paths:
            errors.append(
                _catalog_error(
                    f"The catalog has duplicate detail link '{detail_path}'."
                )
            )
        seen_detail_paths.add(detail_path)
        if not detail_path.startswith(f"details/{identifier.casefold()}-"):
            errors.append(
                _catalog_error(
                    f"The '{identifier}' detail link does not match its identifier."
                )
            )
        detail_relative_path = Path("docs") / "principles" / Path(detail_path)
        detail_failure = _regular_relative_failure(catalog_root, detail_relative_path)
        if detail_failure is not None:
            errors.append(
                _catalog_error(
                    f"The '{identifier}' detail file is missing or is not regular: "
                    f"'{detail_path}'. {detail_failure}"
                )
            )
        principles.append(Principle(identifier, name, description, detail_path))

    actual_identifiers = {principle.identifier for principle in principles}
    expected_identifiers = set(EXPECTED_PRINCIPLE_IDENTIFIERS)
    for identifier in sorted(expected_identifiers - actual_identifiers):
        errors.append(
            _catalog_error(
                f"The catalog is missing principle identifier '{identifier}'."
            )
        )
    for identifier in sorted(actual_identifiers - expected_identifiers):
        errors.append(
            _catalog_error(
                f"The catalog has unexpected principle identifier '{identifier}'."
            )
        )
    source_identifier_order = tuple(principle.identifier for principle in principles)
    if source_identifier_order != EXPECTED_PRINCIPLE_IDENTIFIERS:
        errors.append(
            _catalog_error(
                "The catalog projection must be exactly P001 through P091 in order."
            )
        )
    return tuple(principles), errors


def render_principles_block(principles: tuple[Principle, ...]) -> str:
    """Render the deterministic AGENTS.md catalog mirror."""
    ordered = tuple(sorted(principles, key=lambda principle: principle.identifier))
    identifiers = tuple(principle.identifier for principle in ordered)
    if identifiers != EXPECTED_PRINCIPLE_IDENTIFIERS:
        raise ValueError("The rendered catalog must contain exactly P001 through P091.")
    rows = [
        f"- [{principle.identifier} — {principle.name}]"
        f"({DETAIL_URL_PREFIX}{principle.detail_path}) — {principle.description}"
        for principle in ordered
    ]
    return "\n".join((AGENTS_START_MARKER, *rows, AGENTS_END_MARKER))


def _standalone_marker_positions(text: str, marker: str) -> list[int]:
    lines = text.split("\n")
    outside_fence, _ = _outside_fence_mask(lines)
    positions: list[int] = []
    offset = 0
    for line_index, line in enumerate(lines):
        if outside_fence[line_index] and line == marker:
            positions.append(offset)
        offset += len(line)
        if line_index + 1 < len(lines):
            offset += 1
    return positions


def validate_agent_contract(
    repo_root: Path, *, catalog_root: Path | None = None
) -> list[AgentContractError]:
    """Return all root agent-contract violations."""
    if catalog_root is None:
        catalog_root = repo_root
    errors: list[AgentContractError] = []
    principles, catalog_errors = parse_principles_catalog(catalog_root)
    errors.extend(catalog_errors)
    agents, agents_errors = _read_root_document(repo_root, "AGENTS.md")
    claude, claude_errors = _read_root_document(repo_root, "CLAUDE.md")
    errors.extend(agents_errors)
    errors.extend(claude_errors)
    if claude is not None and claude.encode("utf-8") != CLAUDE_POINTER:
        errors.append(
            AgentContractError(
                "CLAUDE.md",
                "The root 'CLAUDE.md' bytes must equal '@AGENTS.md\\n'.",
            )
        )
    if agents is not None:
        start_positions = _standalone_marker_positions(agents, AGENTS_START_MARKER)
        end_positions = _standalone_marker_positions(agents, AGENTS_END_MARKER)
        markers_valid = (
            agents.count(AGENTS_START_MARKER) == 1
            and agents.count(AGENTS_END_MARKER) == 1
            and len(start_positions) == 1
            and len(end_positions) == 1
            and start_positions[0] < end_positions[0]
        )
        if not markers_valid:
            errors.append(
                AgentContractError(
                    "AGENTS.md",
                    "The root 'AGENTS.md' must contain one generated "
                    "development-principles block.",
                )
            )
        elif not catalog_errors:
            start = start_positions[0]
            end = end_positions[0] + len(AGENTS_END_MARKER)
            if agents[start:end] != render_principles_block(principles):
                errors.append(
                    AgentContractError(
                        "AGENTS.md",
                        "The generated development-principles block does not match "
                        "the canonical Athena catalog.",
                    )
                )
    return errors
