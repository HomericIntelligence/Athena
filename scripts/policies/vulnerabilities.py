"""This module defines the vulnerability severity, fix-state, and exception policy."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Final

import yaml

BLOCKING_SEVERITIES: Final = frozenset({"Critical", "High"})
MAX_EXCEPTION_DAYS: Final = {"Critical": 7, "High": 30}
ATHENA_ISSUE_URL: Final = re.compile(
    r"^https://github\.com/HomericIntelligence/Athena/issues/[1-9][0-9]*$"
)


class VulnerabilityPolicyError(ValueError):
    """This error identifies evidence or exception policy that is not valid."""


def _required_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise VulnerabilityPolicyError(
            f"The exception field {key} must contain a nonempty string."
        )
    return value


def load_exceptions(path: Path, *, today: date) -> list[dict[str, str]]:
    """Load narrow, owned, linked, and unexpired vulnerability exceptions."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise VulnerabilityPolicyError(
            "The tool cannot read the exception policy. "
            f"The operation returned this diagnostic.\n{error}"
        ) from error
    if not isinstance(document, dict) or set(document) != {"exceptions"}:
        raise VulnerabilityPolicyError(
            "The exception policy must contain only an exceptions list."
        )
    entries = document["exceptions"]
    if not isinstance(entries, list):
        raise VulnerabilityPolicyError("The exceptions field must be a list.")
    validated: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise VulnerabilityPolicyError("Each exception must be a map.")
        required = {
            "vulnerability",
            "package",
            "version",
            "severity",
            "reason",
            "owner",
            "issue",
            "approved",
            "expires",
        }
        if set(entry) != required:
            raise VulnerabilityPolicyError(
                "The exception fields must be vulnerability, package, version, severity, "
                "reason, owner, issue, approved, and expires."
            )
        normalized = {key: _required_string(entry, key) for key in required}
        severity = normalized["severity"].title()
        if severity not in MAX_EXCEPTION_DAYS:
            raise VulnerabilityPolicyError(
                "Use only High or Critical for the exception severity."
            )
        if ATHENA_ISSUE_URL.fullmatch(normalized["issue"]) is None:
            raise VulnerabilityPolicyError(
                "The exception issue must be an Athena GitHub issue URL."
            )
        try:
            approved = date.fromisoformat(normalized["approved"])
            expiry = date.fromisoformat(normalized["expires"])
        except ValueError as error:
            raise VulnerabilityPolicyError(
                "The exception approved and expires fields must use 'YYYY-MM-DD'."
            ) from error
        if approved > today:
            raise VulnerabilityPolicyError(
                f"The exception approval date '{approved.isoformat()}' is in the future."
            )
        if expiry < today:
            raise VulnerabilityPolicyError(
                f"The exception '{normalized['vulnerability']}' expired on "
                f"'{expiry.isoformat()}'."
            )
        if expiry < approved:
            raise VulnerabilityPolicyError(
                "The exception expiration date is before its approval date."
            )
        if (expiry - approved).days > MAX_EXCEPTION_DAYS[severity]:
            raise VulnerabilityPolicyError(
                f"The {severity} exception is longer than "
                f"{MAX_EXCEPTION_DAYS[severity]} days."
            )
        normalized["severity"] = severity
        validated.append(normalized)
    return validated


def _fix_versions(match: dict[str, Any]) -> list[str]:
    details = match.get("vulnerability")
    if not isinstance(details, dict):
        raise VulnerabilityPolicyError(
            "The Grype match does not contain a vulnerability object."
        )
    fix = details.get("fix")
    if not isinstance(fix, dict):
        return []
    versions = fix.get("versions", [])
    if not isinstance(versions, list) or not all(
        isinstance(item, str) for item in versions
    ):
        raise VulnerabilityPolicyError(
            "The Grype fix versions must be a list of strings."
        )
    return versions


def evaluate_report(
    report: dict[str, Any], exceptions: list[dict[str, str]]
) -> list[str]:
    """Return fixable High and Critical findings that have no exception."""
    matches = report.get("matches")
    if not isinstance(matches, list):
        raise VulnerabilityPolicyError("The Grype report must contain a matches list.")
    blocking: list[str] = []
    for match in matches:
        if not isinstance(match, dict):
            raise VulnerabilityPolicyError("The Grype match must be an object.")
        vulnerability = match.get("vulnerability")
        artifact = match.get("artifact")
        if not isinstance(vulnerability, dict) or not isinstance(artifact, dict):
            raise VulnerabilityPolicyError(
                "The Grype match is missing a vulnerability or an artifact."
            )
        identifier = vulnerability.get("id")
        severity_value = vulnerability.get("severity")
        name = artifact.get("name")
        version = artifact.get("version")
        for value in (identifier, severity_value, name, version):
            if not isinstance(value, str) or not value:
                raise VulnerabilityPolicyError(
                    "The Grype finding identity fields must be strings."
                )
        assert isinstance(identifier, str)
        assert isinstance(severity_value, str)
        assert isinstance(name, str)
        assert isinstance(version, str)
        severity = severity_value.title()
        if severity not in BLOCKING_SEVERITIES or not _fix_versions(match):
            continue
        excepted = any(
            entry["vulnerability"] == identifier
            and entry["package"] == name
            and entry["version"] == version
            and entry["severity"] == severity
            for entry in exceptions
        )
        if not excepted:
            blocking.append(f"{severity} {identifier} in {name}@{version} has a fix.")
    return sorted(blocking)


def load_report(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VulnerabilityPolicyError(
            "The tool cannot read the Grype report. "
            f"The operation returned this diagnostic.\n{error}"
        ) from error
    if not isinstance(report, dict):
        raise VulnerabilityPolicyError("The Grype report must be a JSON object.")
    return report
