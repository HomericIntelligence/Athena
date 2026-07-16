"""Vulnerability severity, fix-state, and exception policy."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
from typing import Any, Final

import yaml


BLOCKING_SEVERITIES: Final = frozenset({"Critical", "High"})
MAX_EXCEPTION_DAYS: Final = {"Critical": 7, "High": 30}
ATHENA_ISSUE_URL: Final = re.compile(
    r"^https://github\.com/HomericIntelligence/Athena/issues/[1-9][0-9]*$"
)


class VulnerabilityPolicyError(ValueError):
    """Raised for malformed evidence or exception policy."""


def _required_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise VulnerabilityPolicyError(f"exception {key} must be a non-empty string")
    return value


def load_exceptions(path: Path, *, today: date) -> list[dict[str, str]]:
    """Load narrow, owned, linked, and unexpired vulnerability exceptions."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise VulnerabilityPolicyError(
            f"cannot read exception policy: {error}"
        ) from error
    if not isinstance(document, dict) or set(document) != {"exceptions"}:
        raise VulnerabilityPolicyError(
            "exception policy must contain only an exceptions list"
        )
    entries = document["exceptions"]
    if not isinstance(entries, list):
        raise VulnerabilityPolicyError("exceptions must be a list")
    validated: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise VulnerabilityPolicyError("each exception must be a mapping")
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
                "exception fields must be vulnerability, package, version, severity, "
                "reason, owner, issue, approved, and expires"
            )
        normalized = {key: _required_string(entry, key) for key in required}
        severity = normalized["severity"].title()
        if severity not in MAX_EXCEPTION_DAYS:
            raise VulnerabilityPolicyError(
                "exceptions are allowed only for High or Critical"
            )
        if ATHENA_ISSUE_URL.fullmatch(normalized["issue"]) is None:
            raise VulnerabilityPolicyError(
                "exception issue must be an Athena GitHub issue URL"
            )
        try:
            approved = date.fromisoformat(normalized["approved"])
            expiry = date.fromisoformat(normalized["expires"])
        except ValueError as error:
            raise VulnerabilityPolicyError(
                "exception approved and expires must be YYYY-MM-DD"
            ) from error
        if approved > today:
            raise VulnerabilityPolicyError(
                f"exception approval date {approved.isoformat()} is in the future"
            )
        if expiry < today:
            raise VulnerabilityPolicyError(
                f"exception {normalized['vulnerability']} expired on {expiry.isoformat()}"
            )
        if expiry < approved:
            raise VulnerabilityPolicyError("exception expires before its approval date")
        if (expiry - approved).days > MAX_EXCEPTION_DAYS[severity]:
            raise VulnerabilityPolicyError(
                f"{severity} exception exceeds {MAX_EXCEPTION_DAYS[severity]} days"
            )
        normalized["severity"] = severity
        validated.append(normalized)
    return validated


def _fix_versions(match: dict[str, Any]) -> list[str]:
    details = match.get("vulnerability")
    if not isinstance(details, dict):
        raise VulnerabilityPolicyError("Grype match has no vulnerability object")
    fix = details.get("fix")
    if not isinstance(fix, dict):
        return []
    versions = fix.get("versions", [])
    if not isinstance(versions, list) or not all(
        isinstance(item, str) for item in versions
    ):
        raise VulnerabilityPolicyError("Grype fix versions must be a string list")
    return versions


def evaluate_report(
    report: dict[str, Any], exceptions: list[dict[str, str]]
) -> list[str]:
    """Return unexcepted fixable High/Critical findings."""
    matches = report.get("matches")
    if not isinstance(matches, list):
        raise VulnerabilityPolicyError("Grype report must contain a matches list")
    blocking: list[str] = []
    for match in matches:
        if not isinstance(match, dict):
            raise VulnerabilityPolicyError("Grype match must be an object")
        vulnerability = match.get("vulnerability")
        artifact = match.get("artifact")
        if not isinstance(vulnerability, dict) or not isinstance(artifact, dict):
            raise VulnerabilityPolicyError(
                "Grype match is missing vulnerability or artifact"
            )
        identifier = vulnerability.get("id")
        severity_value = vulnerability.get("severity")
        name = artifact.get("name")
        version = artifact.get("version")
        for value in (identifier, severity_value, name, version):
            if not isinstance(value, str) or not value:
                raise VulnerabilityPolicyError(
                    "Grype finding identity fields must be strings"
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
            blocking.append(f"{severity} {identifier} in {name}@{version} has a fix")
    return sorted(blocking)


def load_report(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VulnerabilityPolicyError(f"cannot read Grype report: {error}") from error
    if not isinstance(report, dict):
        raise VulnerabilityPolicyError("Grype report must be an object")
    return report
