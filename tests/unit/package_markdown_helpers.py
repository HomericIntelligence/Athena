"""Shared Markdown artifact helpers for package unit tests."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def technical_english_targets(markdown: str) -> list[str]:
    """Return local links to the shipped technical-English policy."""
    targets: list[str] = []
    for target in MARKDOWN_LINK.findall(markdown):
        path = target.split("#", 1)[0]
        normalized_name = Path(path).name.lower().replace("-", "_")
        if normalized_name == "technical_english.md":
            targets.append(path)
    return targets


def local_markdown_targets(markdown: str) -> list[tuple[str, str]]:
    """Return paths and fragments from local Markdown links."""
    targets: list[tuple[str, str]] = []
    for target in MARKDOWN_LINK.findall(markdown):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or (not parsed.path and not parsed.fragment):
            continue
        targets.append((unquote(parsed.path), unquote(parsed.fragment)))
    return targets


def markdown_anchors(markdown: str) -> set[str]:
    """Return GitHub-style anchors for the headings in a Markdown document."""
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in markdown.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match is None:
            continue
        heading = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", match.group(1))
        heading = heading.replace("`", "")
        base = re.sub(r"[^\w -]", "", heading.casefold()).replace(" ", "-")
        occurrence = counts.get(base, 0)
        counts[base] = occurrence + 1
        anchors.add(base if occurrence == 0 else f"{base}-{occurrence}")
    return anchors
