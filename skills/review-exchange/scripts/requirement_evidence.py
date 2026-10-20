"""Validate and compare one bounded requirement-to-evidence review record.

This module is pure. It does not execute reviewed code, read the network,
publish a review, or grant authority. It validates one independently supplied
expected inventory, compares one assessed row set with that inventory, renders
one compact requirement-to-evidence map, and compares review sections so that a
correction repeats only the affected sections.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any, NoReturn, cast

INVENTORY_SCHEMA_ID = "athena.review-exchange.expected-inventory"
RECORD_SCHEMA_ID = "athena.review-exchange.requirement-evidence"
SCHEMA_VERSION = 1
SURFACES = ("implementation", "tests", "documentation", "operations")
RESULTS = (
    "covered",
    "missing_coverage",
    "incorrect_implementation",
    "not_applicable",
)
MATERIAL_RESULTS = frozenset({"missing_coverage", "incorrect_implementation"})
MAX_REQUIREMENTS = 200
MAX_SECTIONS = 200
MAX_CELLS = 4_000
MAX_REFERENCES = 4_000
MAX_SUMMARY_LENGTH = 4_000
HEX_DIGEST_LENGTH = 64
HEX_DIGEST_CHARACTERS = frozenset("0123456789abcdef")


class RequirementEvidenceError(ValueError):
    """The requirement evidence record or its inputs are not valid."""


def _fail(message: str) -> NoReturn:
    raise RequirementEvidenceError(message)


def canonical_json(value: object) -> str:
    """Return one canonical JSON text for deterministic digests."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_text(value: str) -> str:
    """Return one hexadecimal SHA-256 digest of UTF-8 text."""
    return sha256(value.encode("utf-8")).hexdigest()


def _digest_text(value: object, name: str) -> str:
    """Return one validated lowercase hexadecimal SHA-256 digest."""
    if (
        type(value) is not str
        or len(value) != HEX_DIGEST_LENGTH
        or not set(value) <= HEX_DIGEST_CHARACTERS
    ):
        _fail(f"The {name} must be a lowercase hexadecimal SHA-256 digest.")
    return value


def _object(value: object, name: str, fields: frozenset[str]) -> dict[str, Any]:
    """Return one normalized object with exactly the required fields."""
    if type(value) is not dict or set(value) != fields:
        _fail(f"The {name} must be an object with the required fields.")
    return dict(value)


def _text(value: object, name: str) -> str:
    """Return one bounded non-empty string."""
    if type(value) is not str or not value.strip():
        _fail(f"The {name} must be a non-empty string.")
    if len(value) > MAX_SUMMARY_LENGTH:
        _fail(f"The {name} is too long.")
    return value


def _references(value: object, name: str) -> list[str]:
    """Return one validated list of bounded non-empty references."""
    if type(value) is not list or len(value) > MAX_REFERENCES:
        _fail(f"The {name} must be a bounded list of references.")
    result = [_text(item, f"{name} item") for item in value]
    if len(set(result)) != len(result):
        _fail(f"The {name} contains a duplicate reference.")
    return result


def _binding(value: object, name: str) -> dict[str, str]:
    """Return one validated identity binding."""
    binding = _object(value, name, frozenset({"kind", "identity", "content_sha256"}))
    return {
        "kind": _text(binding["kind"], f"{name}.kind"),
        "identity": _text(binding["identity"], f"{name}.identity"),
        "content_sha256": _digest_text(
            binding["content_sha256"], f"{name}.content_sha256"
        ),
    }


def _dependencies(value: object, name: str) -> dict[str, str]:
    """Return one validated dependency content identity map."""
    if type(value) is not dict or len(value) > MAX_REFERENCES:
        _fail(f"The {name} must be a bounded dependency map.")
    result: dict[str, str] = {}
    for key, item in value.items():
        _text(key, f"{name} name")
        result[key] = _digest_text(item, f"{name} entry")
    return result


def _requirement(value: object) -> dict[str, str]:
    """Return one validated requirement entry."""
    entry = _object(value, "requirement", frozenset({"id", "source"}))
    return {
        "id": _text(entry["id"], "requirement.id"),
        "source": _text(entry["source"], "requirement.source"),
    }


def _section(value: object) -> dict[str, Any]:
    """Return one validated review section entry."""
    section = _object(value, "section", frozenset({"id", "paths", "depends_on"}))
    paths = _references(section["paths"], "section.paths")
    depends_on = _references(section["depends_on"], "section.depends_on")
    if len(set(depends_on)) != len(depends_on):
        _fail("A review section contains a duplicate section dependency name.")
    return {
        "id": _text(section["id"], "section.id"),
        "paths": paths,
        "depends_on": depends_on,
    }


def _scope_binding(value: object) -> dict[str, Any]:
    """Return one validated scope binding with its complete selected path set."""
    scope = _object(value, "scope_binding", frozenset({"paths", "sha256"}))
    return {
        "paths": _references(scope["paths"], "scope_binding.paths"),
        "sha256": _digest_text(scope["sha256"], "scope_binding.sha256"),
    }


def inventory_digest(value: Mapping[str, Any]) -> str:
    """Return the canonical digest of one expected inventory without its digest."""
    body = {key: item for key, item in value.items() if key != "inventory_sha256"}
    return sha256_text(canonical_json(body))


def record_digest(value: Mapping[str, Any]) -> str:
    """Return the canonical digest of one evidence record without its digest."""
    body = {key: item for key, item in value.items() if key != "record_sha256"}
    return sha256_text(canonical_json(body))


def expected_cells(value: Mapping[str, Any]) -> list[dict[str, str]]:
    """Return every required requirement, section, and surface combination."""
    cells = [
        {"requirement": requirement["id"], "section": section["id"], "surface": surface}
        for requirement in value["requirements"]
        for section in value["sections"]
        for surface in SURFACES
    ]
    if len(cells) > MAX_CELLS:
        _fail("The expected inventory has too many cells.")
    return sorted(
        cells, key=lambda cell: (cell["requirement"], cell["section"], cell["surface"])
    )


def build_inventory(
    *,
    requirements_binding: Mapping[str, Any],
    artifact_binding: Mapping[str, Any],
    scope_binding: Mapping[str, Any],
    requirements: Sequence[Mapping[str, Any]],
    sections: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one frozen expected inventory before any assessment.

    The inventory is an independent input. An assessment cannot replace it or
    shrink it. Every selected scope path must be assigned to one section.
    """
    if not 1 <= len(requirements) <= MAX_REQUIREMENTS:
        _fail("The expected inventory needs between one and 200 requirements.")
    if not 1 <= len(sections) <= MAX_SECTIONS:
        _fail("The expected inventory needs between one and 200 sections.")
    normalized_requirements = [_requirement(item) for item in requirements]
    identifiers = [item["id"] for item in normalized_requirements]
    if len(set(identifiers)) != len(identifiers):
        _fail("The expected inventory has a duplicate requirement identifier.")
    normalized_sections = [_section(item) for item in sections]
    section_identifiers = [item["id"] for item in normalized_sections]
    if len(set(section_identifiers)) != len(section_identifiers):
        _fail("The expected inventory has a duplicate review section identifier.")
    scope = _scope_binding(scope_binding)
    assigned: set[str] = set()
    for section in normalized_sections:
        assigned.update(section["paths"])
    unassigned = sorted(set(scope["paths"]) - assigned)
    if unassigned:
        _fail(f"The scope binding path is not assigned to a section: {unassigned}.")
    inventory = {
        "schema_id": INVENTORY_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "requirements_binding": _binding(requirements_binding, "requirements_binding"),
        "artifact_binding": _binding(artifact_binding, "artifact_binding"),
        "scope_binding": scope,
        "requirements": sorted(normalized_requirements, key=lambda item: item["id"]),
        "sections": sorted(normalized_sections, key=lambda item: item["id"]),
        "expected_cells": [],
    }
    cells = expected_cells(inventory)
    inventory["expected_cells"] = cells
    inventory["inventory_sha256"] = inventory_digest(inventory)
    return validate_inventory(inventory)


def validate_inventory(
    value: object, *, expected_sha256: str | None = None
) -> dict[str, Any]:
    """Validate one expected inventory and its frozen digest.

    Callers that freeze the inventory before assessment pass the digest they
    retained. A changed inventory must then be an explicit update with the old
    and new digests and a change cause.
    """
    inventory = _object(
        value,
        "expected inventory",
        frozenset(
            {
                "schema_id",
                "schema_version",
                "requirements_binding",
                "artifact_binding",
                "scope_binding",
                "requirements",
                "sections",
                "expected_cells",
                "inventory_sha256",
            }
        ),
    )
    if inventory["schema_id"] != INVENTORY_SCHEMA_ID:
        _fail("The expected inventory schema identifier is not supported.")
    if inventory["schema_version"] != SCHEMA_VERSION:
        _fail("The expected inventory schema version is not supported.")
    body = {key: item for key, item in inventory.items() if key != "inventory_sha256"}
    normalized: dict[str, Any] = {
        "schema_id": INVENTORY_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "requirements_binding": _binding(
            body["requirements_binding"], "requirements_binding"
        ),
        "artifact_binding": _binding(body["artifact_binding"], "artifact_binding"),
        "scope_binding": _scope_binding(body["scope_binding"]),
        "requirements": [_requirement(item) for item in body["requirements"]],
        "sections": [_section(item) for item in body["sections"]],
        "expected_cells": expected_cells(body),
    }
    identifiers = [cast(dict[str, str], item)["id"] for item in normalized["requirements"]]
    if len(set(identifiers)) != len(identifiers):
        _fail("The expected inventory has a duplicate requirement identifier.")
    sections = [cast(dict[str, Any], item)["id"] for item in normalized["sections"]]
    if len(set(sections)) != len(sections):
        _fail("The expected inventory has a duplicate review section identifier.")
    supplied = _digest_text(inventory["inventory_sha256"], "expected inventory digest")
    if supplied != inventory_digest(normalized):
        _fail("The expected inventory digest does not match its content.")
    if (
        expected_sha256 is not None
        and _digest_text(expected_sha256, "frozen inventory digest") != supplied
    ):
        _fail("The expected inventory digest is not the frozen inventory digest.")
    return {**normalized, "inventory_sha256": supplied}


def _row(value: object, name: str) -> dict[str, Any]:
    """Return one validated assessed row."""
    row = _object(
        value,
        name,
        frozenset(
            {
                "requirement",
                "section",
                "surface",
                "result",
                "reason",
                "evidence",
                "finding_ids",
                "dependencies",
            }
        ),
    )
    result = _text(row["result"], f"{name}.result")
    if result not in RESULTS:
        _fail(f"The {name}.result is not a supported assessment result.")
    reason = row["reason"]
    if result == "not_applicable" and reason is None:
        _fail(f"A {name} that is not applicable needs a reason.")
    if result != "not_applicable" and reason is not None:
        _fail(f"A {name} keeps its reason only for a not-applicable result.")
    finding_ids = _references(row["finding_ids"], f"{name}.finding_ids")
    if result in MATERIAL_RESULTS and not finding_ids:
        _fail(f"A {name} with a material result needs a finding identifier.")
    if result not in MATERIAL_RESULTS and finding_ids:
        _fail(f"A {name} without a material result keeps no finding identifier.")
    references = _references(row["evidence"], f"{name}.evidence")
    if result != "not_applicable" and not references:
        _fail(f"A {name} that applies needs at least one evidence reference.")
    return {
        "requirement": _text(row["requirement"], f"{name}.requirement"),
        "section": _text(row["section"], f"{name}.section"),
        "surface": _text(row["surface"], f"{name}.surface"),
        "result": result,
        "reason": None if reason is None else _text(reason, f"{name}.reason"),
        "evidence": references,
        "finding_ids": finding_ids,
        "dependencies": _dependencies(row["dependencies"], f"{name}.dependencies"),
    }


def validate_assessment(
    inventory: object,
    rows: object,
    *,
    expected_inventory: object | None = None,
    expected_sha256: str | None = None,
) -> list[dict[str, Any]]:
    """Validate assessed rows against one independently supplied inventory.

    The submitted row keys and the expected cells must be equal as exact sets.
    Missing, extra, and duplicate rows are rejected. An assessment cannot
    replace or shrink the expected inventory.
    """
    frozen = validate_inventory(inventory)
    reference_sha256 = expected_sha256
    if expected_inventory is not None:
        reference = validate_inventory(expected_inventory)
        if reference["inventory_sha256"] != frozen["inventory_sha256"]:
            _fail(
                "The submitted expected inventory does not match the expected "
                "inventory. Record an inventory update with the old and new "
                "digests and a change cause."
            )
        frozen = reference
        if expected_sha256 is not None and (
            _digest_text(expected_sha256, "frozen inventory digest")
            != frozen["inventory_sha256"]
        ):
            _fail("The expected inventory digest is not the frozen inventory digest.")
    elif reference_sha256 is not None and (
        _digest_text(reference_sha256, "frozen inventory digest")
        != frozen["inventory_sha256"]
    ):
        _fail("The expected inventory digest is not the frozen inventory digest.")
    if type(rows) is not list:
        _fail("The assessed rows must be a list.")
    if len(rows) > MAX_CELLS:
        _fail("The assessment has too many rows.")
    validated = [_row(row, "assessed row") for row in rows]
    cells = frozen["expected_cells"]
    known = {(item["requirement"], item["section"], item["surface"]) for item in cells}
    identifiers = {item["id"] for item in frozen["requirements"]}
    sections = {item["id"] for item in frozen["sections"]}
    seen: set[tuple[str, str, str]] = set()
    for row in validated:
        key = (row["requirement"], row["section"], row["surface"])
        if key in seen:
            _fail(f"The assessment has a duplicate assessed cell: {key}.")
        seen.add(key)
        if row["requirement"] not in identifiers:
            _fail(f"The assessment names an unknown requirement: {row['requirement']}.")
        if row["section"] not in sections:
            _fail(f"The assessment names an unknown review section: {row['section']}.")
        if row["surface"] not in SURFACES:
            _fail(
                f"The assessment names an unknown evidence surface: {row['surface']}."
            )
    missing = sorted(known - seen)
    if missing:
        _fail(f"The assessment is missing expected cells: {missing}.")
    extra = sorted(seen - known)
    if extra:
        _fail(f"The assessment adds cells outside the inventory: {extra}.")
    return sorted(
        validated,
        key=lambda row: (row["requirement"], row["section"], row["surface"]),
    )


def build_record(
    *,
    inventory: object,
    rows: object,
    artifact_binding: object | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Build one validated evidence record from a complete assessment.

    Callers cannot assemble a findings batch from a partial assessment.
    """
    validated_rows = validate_assessment(
        inventory, rows, expected_sha256=expected_sha256
    )
    frozen = validate_inventory(inventory, expected_sha256=expected_sha256)
    record = {
        "schema_id": RECORD_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "requirements_binding": frozen["requirements_binding"],
        "requirements_sha256": frozen["requirements_binding"]["content_sha256"],
        "artifact_binding": (
            frozen["artifact_binding"]
            if artifact_binding is None
            else _binding(artifact_binding, "artifact_binding")
        ),
        "inventory": frozen,
        "inventory_sha256": frozen["inventory_sha256"],
        "rows": validated_rows,
    }
    record["record_sha256"] = record_digest(record)
    return validate_record(record)


def validate_record(
    value: object, *, expected_sha256: str | None = None
) -> dict[str, Any]:
    """Validate one evidence record and its digest."""
    record = _object(
        value,
        "requirement evidence record",
        frozenset(
            {
                "schema_id",
                "schema_version",
                "requirements_binding",
                "requirements_sha256",
                "artifact_binding",
                "inventory",
                "inventory_sha256",
                "rows",
                "record_sha256",
            }
        ),
    )
    if record["schema_id"] != RECORD_SCHEMA_ID:
        _fail("The requirement evidence schema identifier is not supported.")
    if record["schema_version"] != SCHEMA_VERSION:
        _fail("The requirement evidence schema version is not supported.")
    frozen = validate_inventory(
        record["inventory"], expected_sha256=record["inventory_sha256"]
    )
    validated_rows = validate_assessment(
        frozen,
        record["rows"],
        expected_inventory=frozen,
        expected_sha256=frozen["inventory_sha256"],
    )
    normalized = {
        "schema_id": RECORD_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "requirements_binding": _binding(
            record["requirements_binding"], "requirements_binding"
        ),
        "requirements_sha256": _digest_text(
            record["requirements_sha256"], "requirements_sha256"
        ),
        "artifact_binding": _binding(record["artifact_binding"], "artifact_binding"),
        "inventory": frozen,
        "inventory_sha256": frozen["inventory_sha256"],
        "rows": validated_rows,
    }
    if (
        normalized["requirements_sha256"]
        != frozen["requirements_binding"]["content_sha256"]
    ):
        _fail("The evidence record requirements digest does not match its inventory.")
    supplied = _digest_text(record["record_sha256"], "evidence record digest")
    if supplied != record_digest(normalized):
        _fail("The evidence record digest does not match its content.")
    if (
        expected_sha256 is not None
        and _digest_text(expected_sha256, "expected record digest") != supplied
    ):
        _fail("The evidence record digest is not the expected record digest.")
    return {**normalized, "record_sha256": supplied}


def assemble_findings(record: object) -> list[dict[str, Any]]:
    """Return the complete findings batch for one validated record."""
    validated = validate_record(record)
    findings: list[dict[str, Any]] = []
    for row in validated["rows"]:
        for finding_id in row["finding_ids"]:
            findings.append(
                {
                    "id": finding_id,
                    "result": row["result"],
                    "requirement": row["requirement"],
                    "section": row["section"],
                    "surface": row["surface"],
                    "evidence": list(row["evidence"]),
                }
            )
    findings.sort(
        key=lambda item: (
            item["id"],
            item["requirement"],
            item["section"],
            item["surface"],
        )
    )
    if len(findings) > MAX_REFERENCES:
        _fail("The findings batch is too large to deliver.")
    return findings


def render_requirement_map(record: object) -> str:
    """Render one compact requirement-to-evidence map for one record."""
    validated = validate_record(record)
    lines = [
        "| Requirement | Section | Surface | Result | Evidence | Findings | Reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in validated["rows"]:
        lines.append(
            "| {requirement} | {section} | {surface} | {result} | {evidence} | "
            "{findings} | {reason} |".format(
                requirement=row["requirement"],
                section=row["section"],
                surface=row["surface"],
                result=row["result"],
                evidence=", ".join(row["evidence"]) or "-",
                findings=", ".join(row["finding_ids"]) or "-",
                reason=row["reason"] or "-",
            )
        )
    return "\n".join(lines)


def _current_sections(value: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return one validated current section dependency record."""
    if not 1 <= len(value) <= MAX_SECTIONS:
        _fail("The current section record needs between one and 200 sections.")
    result = []
    identifiers = []
    for section in value:
        entry = _object(
            section,
            "current review section",
            frozenset(
                {"id", "paths", "depends_on", "dependencies", "corrected_findings"}
            ),
        )
        identifiers.append(_text(entry["id"], "current review section identifier"))
        result.append(
            {
                "id": identifiers[-1],
                "paths": _references(entry["paths"], "current review section paths"),
                "depends_on": _references(
                    entry["depends_on"], "current review section dependencies"
                ),
                "dependencies": _dependencies(
                    entry["dependencies"], "current review section identities"
                ),
                "corrected_findings": _references(
                    entry["corrected_findings"], "current review section corrections"
                ),
            }
        )
    if len(set(identifiers)) != len(identifiers):
        _fail("The current section record has a duplicate review section identifier.")
    return result


def _prior_rows(prior: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return prior assessed rows grouped by review section."""
    rows = prior.get("rows")
    if type(rows) is not list:
        _fail("The prior record has no assessed rows.")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            _fail("A prior assessed row must be an object.")
        section = row.get("section")
        if not isinstance(section, str) or "dependencies" not in row:
            continue
        grouped.setdefault(section, []).append(dict(row))
    return grouped


def compare_sections(
    prior: Mapping[str, Any] | None, current: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Compare prior sections with current dependencies.

    A section is retained when its requirements, section dependencies, source
    content, and applicable scope remain equivalent. Each repeated section
    names the finding or source change that caused the repeat. A prior record
    without dependency evidence cannot authorize any reuse.
    """
    sections = _current_sections(current)
    repeated: list[dict[str, Any]] = []
    retained: list[str] = []
    if prior is None:
        return {
            "retained": retained,
            "repeated": [
                {
                    "section": section["id"],
                    "cause": {"kind": "first_review"},
                    "changed_dependencies": [],
                }
                for section in sections
            ],
            "changed_dependencies": [],
        }
    prior_requirements = prior.get("requirements_sha256")
    current_requirements = _current_requirements(prior, sections)
    if (
        prior_requirements is not None
        and current_requirements is not None
        and prior_requirements != current_requirements
    ):
        return {
            "retained": retained,
            "repeated": [
                {
                    "section": section["id"],
                    "cause": {"kind": "requirements_changed"},
                    "changed_dependencies": [],
                }
                for section in sections
            ],
            "changed_dependencies": [],
        }
    grouped = _prior_rows(prior)
    changed_dependencies: list[dict[str, str]] = []
    changed_names: set[str] = set()
    for section in sections:
        prior_rows = grouped.get(section["id"], [])
        prior_identities: dict[str, str] = {}
        for row in prior_rows:
            dependencies = row.get("dependencies")
            if type(dependencies) is not dict or not dependencies:
                continue
            for name, value in dependencies.items():
                if not (type(value) is str and len(value) == HEX_DIGEST_LENGTH):
                    _fail("A prior dependency identity is not a content digest.")
                prior_identities[name] = value
        if not prior_identities:
            repeated.append(
                {
                    "section": section["id"],
                    "cause": {"kind": "no_verified_dependency_evidence"},
                    "changed_dependencies": [],
                }
            )
            continue
        local_changes = [
            {
                "name": name,
                "old": prior_identities[name],
                "new": value,
            }
            for name, value in sorted(section["dependencies"].items())
            if name in prior_identities and prior_identities[name] != value
        ]
        local_changes.extend(
            {
                "name": name,
                "old": "",
                "new": section["dependencies"][name],
            }
            for name in sorted(section["dependencies"])
            if name not in prior_identities
        )
        if local_changes:
            changed_dependencies.extend(local_changes)
            changed_names.update(item["name"] for item in local_changes)
            repeated.append(
                {
                    "section": section["id"],
                    "cause": {
                        "kind": "dependency_changed",
                        "changed": [item["name"] for item in local_changes],
                    },
                    "changed_dependencies": local_changes,
                }
            )
            continue
        dependent = sorted(
            name for name in section["depends_on"] if name in changed_names
        )
        corrected = sorted(
            {
                finding_id
                for row in prior_rows
                for finding_id in row.get("finding_ids", [])
                if finding_id in section["corrected_findings"]
            }
        )
        if dependent:
            repeated.append(
                {
                    "section": section["id"],
                    "cause": {"kind": "dependency_changed", "changed": dependent},
                    "changed_dependencies": [],
                }
            )
            continue
        if corrected:
            repeated.append(
                {
                    "section": section["id"],
                    "cause": {"kind": "finding_corrected", "finding_id": corrected[0]},
                    "changed_dependencies": [],
                }
            )
            continue
        retained.append(section["id"])
    unique_changes = {item["name"]: item for item in changed_dependencies}
    return {
        "retained": sorted(retained),
        "repeated": sorted(repeated, key=lambda item: item["section"]),
        "changed_dependencies": [
            unique_changes[name] for name in sorted(unique_changes)
        ],
    }


def _current_requirements(
    prior: Mapping[str, Any], sections: Sequence[Mapping[str, Any]]
) -> str | None:
    """Return the requirements identity that a prior record or caller supplied."""
    value = prior.get("requirements_binding")
    if isinstance(value, Mapping) and "content_sha256" in value:
        digest_value = value["content_sha256"]
        if type(digest_value) is str and len(digest_value) == HEX_DIGEST_LENGTH:
            return digest_value
    del sections
    return None
