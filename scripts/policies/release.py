"""This module defines the release identity, version, and artifact policy.

The artifact policy validates Software Package Data Exchange (SPDX) documents.
"""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

SEMVER_TAG = re.compile(r"^v([0-9]+\.[0-9]+\.[0-9]+)$")


def evaluate_release(
    *,
    tag: str,
    workflow_sha: str,
    tag_commit: str,
    annotated: bool,
    signature_verified: bool,
    main_protected: bool,
    manifest_versions: dict[str, str],
) -> list[str]:
    """Return release-policy violations independent of GitHub transport."""
    errors: list[str] = []
    match = SEMVER_TAG.fullmatch(tag)
    if match is None:
        errors.append("The release tag must be an exact vMAJOR.MINOR.PATCH version.")
        expected_version = None
    else:
        expected_version = match.group(1)
    if not annotated:
        errors.append("The release tag must be annotated.")
    if not signature_verified:
        errors.append("GitHub must verify the tag signature.")
    if not main_protected:
        errors.append("The main branch must be protected before release publication.")
    if tag_commit != workflow_sha:
        errors.append("The tag target does not match the workflow commit.")
    if expected_version is not None:
        for name, version in sorted(manifest_versions.items()):
            if version != expected_version:
                errors.append(
                    f"The '{name}' manifest version '{version}' does not match tag "
                    f"'{expected_version}'."
                )
    return errors


def _verify_checksum(artifact: Path, checksum: Path) -> None:
    fields = checksum.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1] != artifact.name:
        raise ValueError(f"The checksum file does not identify '{artifact.name}'.")
    actual = sha256(artifact.read_bytes()).hexdigest()
    if fields[0] != actual:
        raise ValueError(f"The checksum does not match '{artifact.name}'.")


def _verify_spdx(path: Path, *, expected_name: str, version: str) -> None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"The tool cannot parse SPDX document '{path.name}'. "
            f"The operation returned this diagnostic.\n{error}"
        ) from error
    if not isinstance(document, dict):
        raise TypeError(f"SPDX document '{path.name}' must be a JSON object.")
    if document.get("spdxVersion") != "SPDX-2.3":
        raise ValueError(f"SPDX document '{path.name}' must use 'SPDX-2.3'.")
    if document.get("name") != expected_name:
        raise ValueError(
            f"SPDX document '{path.name}' does not have the required identity."
        )
    namespace = document.get("documentNamespace")
    if not isinstance(namespace, str) or expected_name not in namespace:
        raise ValueError(
            f"SPDX document '{path.name}' has a namespace that is not valid."
        )
    packages = document.get("packages")
    if not isinstance(packages, list):
        raise TypeError(
            f"SPDX document '{path.name}' does not contain a packages list."
        )
    expected_package = (
        "athena-plugin" if expected_name.startswith("athena-plugin-") else expected_name
    )
    if not any(
        isinstance(package, dict)
        and package.get("name") == expected_package
        and package.get("versionInfo") == version
        for package in packages
    ):
        raise ValueError(
            f"SPDX document '{path.name}' does not contain the required release package."
        )


def verify_release_assets(directory: Path) -> list[str]:
    """Verify the exact release set and all checksum pairs.

    The set contains the archive and software bill of materials (SBOM) files.
    """
    files = sorted(path for path in directory.iterdir() if path.is_file())
    archive_pattern = re.compile(
        r"^athena-plugin-(?P<version>[0-9]+\.[0-9]+\.[0-9]+)\.tar\.gz$"
    )
    archives = [path for path in files if archive_pattern.fullmatch(path.name)]
    if len(archives) != 1:
        raise ValueError("The release assets must contain exactly one plugin archive.")
    archive = archives[0]
    match = archive_pattern.fullmatch(archive.name)
    assert match is not None
    version = match.group("version")
    artifacts = [
        archive,
        directory / f"athena-plugin-{version}.spdx.json",
        directory / f"athena-build-linux-64-{version}.spdx.json",
    ]
    expected = {
        path.name
        for artifact in artifacts
        for path in (artifact, artifact.with_name(f"{artifact.name}.sha256"))
    }
    actual = {path.name for path in files}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            "The release assets do not match the required six-file set. "
            f"The required assets are missing: {missing}. "
            "The release includes these extra assets.\n" + json.dumps(extra)
        )
    for artifact in artifacts:
        _verify_checksum(artifact, artifact.with_name(f"{artifact.name}.sha256"))
    _verify_spdx(
        artifacts[1], expected_name=f"athena-plugin-{version}", version=version
    )
    _verify_spdx(artifacts[2], expected_name="athena-build-linux-64", version=version)
    return sorted(expected)
