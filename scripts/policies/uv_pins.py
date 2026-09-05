"""This module defines the uv version consistency policy."""

from __future__ import annotations

import re
from typing import Any

import yaml

_UV_URL = re.compile(
    r"https://github\.com/astral-sh/uv/releases/download/"
    r"(?P<version>\d+\.\d+\.\d+)/uv-x86_64-unknown-linux-gnu\.tar\.gz"
)
_UV_CHECKSUM = re.compile(r"echo\s+[\"']?(?P<checksum>\S+)\s+/tmp/uv\.tar\.gz")
_HEX_CHECKSUM = re.compile(r"[0-9a-f]{64}")
_SETUP_UV = "astral-sh/setup-uv@"


def _container_pin(container_text: str) -> tuple[str | None, str | None]:
    active_text = "\n".join(
        line
        for line in container_text.splitlines()
        if not line.lstrip().startswith("#")
    )
    url_match = _UV_URL.search(active_text)
    checksum_match = _UV_CHECKSUM.search(active_text)
    return (
        url_match.group("version") if url_match else None,
        checksum_match.group("checksum") if checksum_match else None,
    )


def _workflow_versions(value: Any) -> list[str | None]:
    if isinstance(value, dict):
        versions: list[str | None] = []
        uses = value.get("uses")
        if isinstance(uses, str) and uses.startswith(_SETUP_UV):
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
