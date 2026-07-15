"""Release identity, version, and artifact policy."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re


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
        errors.append("release tag must be an exact vMAJOR.MINOR.PATCH version")
        expected_version = None
    else:
        expected_version = match.group(1)
    if not annotated:
        errors.append("release tag must be annotated")
    if not signature_verified:
        errors.append("GitHub must verify the tag signature")
    if not main_protected:
        errors.append("main must be protected before publishing a release")
    if tag_commit != workflow_sha:
        errors.append("tag target does not match the workflow commit")
    if expected_version is not None:
        for name, version in sorted(manifest_versions.items()):
            if version != expected_version:
                errors.append(
                    f"{name} manifest version {version} does not match tag {expected_version}"
                )
    return errors


def verify_release_assets(directory: Path) -> tuple[str, str]:
    """Verify the single downloaded plugin archive and its checksum file."""
    archives = sorted(directory.glob("athena-plugin-*.tar.gz"))
    checksums = sorted(directory.glob("athena-plugin-*.tar.gz.sha256"))
    if len(archives) != 1 or len(checksums) != 1:
        raise ValueError(
            "release assets must contain exactly one plugin archive and one checksum"
        )
    archive = archives[0]
    checksum = checksums[0]
    fields = checksum.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1] != archive.name:
        raise ValueError("checksum file does not identify the downloaded archive")
    actual = sha256(archive.read_bytes()).hexdigest()
    if fields[0] != actual:
        raise ValueError(f"checksum mismatch for {archive.name}")
    return archive.name, checksum.name
