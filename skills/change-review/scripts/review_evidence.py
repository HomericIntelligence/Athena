#!/usr/bin/env python3
"""Prepare and finalize one change-review requirement-to-evidence result.

This adapter is read-only. It resolves the current scope with ``resolve_scope``,
compares review sections through the shared requirement-evidence module, and
returns a compact result. It does not write a record into the repository,
publish a review, execute reviewed code, or grant authority. The caller retains
the returned record outside the reviewed source and supplies it on the next
invocation.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, cast

sys.dont_write_bytecode = True

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import resolve_scope as scope_resolver


def _load_shared_module() -> Any:
    """Load the shared requirement-evidence module from its canonical location."""
    if "athena_requirement_evidence" in sys.modules:
        return sys.modules["athena_requirement_evidence"]
    path = _HERE.parents[1] / "review-exchange" / "scripts" / "requirement_evidence.py"
    specification = importlib.util.spec_from_file_location(
        "athena_requirement_evidence", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(
            f"The shared requirement-evidence module is unavailable: '{path}'."
        )
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


evidence = _load_shared_module()

if TYPE_CHECKING or __package__ not in {None, ""}:
    from skills._cli import argument_parser
else:
    _cli_path = _HERE.parents[1] / "_cli.py"
    _cli_spec = importlib.util.spec_from_file_location(
        "athena_installed_cli", _cli_path
    )
    if _cli_spec is None or _cli_spec.loader is None:
        raise RuntimeError(
            f"The installed Athena CLI helper is unavailable: '{_cli_path}'."
        )
    _cli = importlib.util.module_from_spec(_cli_spec)
    _cli_spec.loader.exec_module(_cli)
    argument_parser = _cli.argument_parser

Error = evidence.RequirementEvidenceError
PREPARATION_SCHEMA_ID = "athena.change-review.preparation"
RESULT_SCHEMA_ID = "athena.change-review.requirement-evidence"
SCHEMA_VERSION = 1
MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_SECTIONS = evidence.MAX_SECTIONS

PREPARATION_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "requirements_binding",
        "inventory",
        "inventory_sha256",
        "artifact_kind",
        "artifact_binding",
        "scope_selectors",
        "scope",
        "head",
        "base",
        "section_records",
        "retained_sections",
        "retained_rows",
        "sections_to_assess",
        "changed_dependencies",
        "preparation_sha256",
    }
)


def _fail(message: str) -> NoReturn:
    """Reject one request with a bounded diagnostic."""
    raise Error(message)


def _string(value: object, name: str) -> str:
    """Return one bounded non-empty string."""
    if type(value) is not str or not value.strip():
        _fail(f"The {name} must be a non-empty string.")
    if len(value) > evidence.MAX_SUMMARY_LENGTH:
        _fail(f"The {name} is too long.")
    return value


def _object(value: object, name: str, fields: frozenset[str]) -> dict[str, Any]:
    """Return one normalized object with exactly the required fields."""
    if type(value) is not dict or set(value) != fields:
        _fail(f"The {name} must be an object with the required fields.")
    return dict(value)


def _references(value: object, name: str) -> list[str]:
    """Return one bounded list of non-empty references."""
    if type(value) is not list or len(value) > evidence.MAX_REFERENCES:
        _fail(f"The {name} must be a bounded list of references.")
    result = [_string(item, f"{name} item") for item in value]
    if len(set(result)) != len(result):
        _fail(f"The {name} contains a duplicate reference.")
    return result


def _sections(value: object) -> list[dict[str, Any]]:
    """Return the caller-supplied review section assignment."""
    if type(value) is not list or not 1 <= len(value) <= MAX_SECTIONS:
        _fail("The section assignment must hold between one and 200 sections.")
    sections = []
    identifiers = set()
    for item in value:
        section = _object(
            item, "review section", frozenset({"id", "paths", "depends_on"})
        )
        identifier = _string(section["id"], "review section identifier")
        if identifier in identifiers:
            _fail("The section assignment has a duplicate review section identifier.")
        identifiers.add(identifier)
        sections.append(
            {
                "id": identifier,
                "paths": _references(section["paths"], "review section paths"),
                "depends_on": _references(
                    section["depends_on"], "review section dependencies"
                ),
            }
        )
    return sorted(sections, key=lambda item: item["id"])


def _scope_selectors(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return one validated scope selection."""
    scope = _string(value["scope"], "scope")
    if scope not in {"worktree", "staged", "range"}:
        _fail("The scope must be 'worktree', 'staged', or 'range'.")
    range_value = value["range"]
    if range_value is not None:
        range_value = _string(range_value, "range")
    if (scope == "range") != (range_value is not None):
        _fail("Only a range scope names 'BASE..HEAD'.")
    return {
        "scope": scope,
        "range": range_value,
        "paths": _references(value["paths"], "paths"),
    }


def _resolve(selectors: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve the current review scope through the canonical resolver."""
    manifest = scope_resolver.resolve_scope(
        str(selectors["scope"]),
        None if selectors["range"] is None else str(selectors["range"]),
        list(selectors["paths"]),
    )
    identities = manifest["dependency_identities"]
    if type(identities) is not dict:
        _fail("The resolved scope does not carry dependency content identities.")
    if type(manifest["paths"]) is not list:
        _fail("The resolved scope does not carry its selected path set.")
    return {
        "head": _string(manifest["head"], "resolved head"),
        "base": _string(manifest["base"], "resolved base"),
        "scope_digest": _string(manifest["scope_digest"], "scope digest"),
        "paths": [str(path) for path in manifest["paths"]],
        "identities": {str(key): str(value) for key, value in identities.items()},
    }


def _scope_binding(resolved: Mapping[str, Any]) -> dict[str, Any]:
    """Return the scope binding for one resolved scope."""
    return {"paths": list(resolved["paths"]), "sha256": str(resolved["scope_digest"])}


def _artifact_binding(kind: str, resolved: Mapping[str, Any]) -> dict[str, str]:
    """Return the artifact binding for the resolved head."""
    return {
        "kind": kind,
        "identity": str(resolved["head"]),
        "content_sha256": evidence.sha256_text(
            evidence.canonical_json(
                {
                    "head": str(resolved["head"]),
                    "base": str(resolved["base"]),
                    "scope_digest": str(resolved["scope_digest"]),
                }
            )
        ),
    }


def _section_records(
    sections: Sequence[Mapping[str, Any]],
    identities: Mapping[str, str],
    corrected_findings: Sequence[str],
) -> list[dict[str, Any]]:
    """Bind each review section to the current dependency content identities."""
    records = []
    for section in sections:
        names = sorted({*section["paths"], *section["depends_on"]})
        missing = [name for name in names if name not in identities]
        if missing:
            _fail(f"A review section names a path outside the scope: {missing}.")
        records.append(
            {
                "id": str(section["id"]),
                "paths": list(section["paths"]),
                "depends_on": list(section["depends_on"]),
                "dependencies": {name: identities[name] for name in names},
                "corrected_findings": list(corrected_findings),
            }
        )
    return records


def _rows_with_dependencies(
    rows: object, records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Bind each assessed row to the dependency identities of its section."""
    if type(rows) is not list or len(rows) > evidence.MAX_CELLS:
        _fail("The assessed rows must be a bounded list.")
    dependencies = {
        str(record["id"]): dict(record["dependencies"]) for record in records
    }
    result = []
    for item in rows:
        if type(item) is not dict:
            _fail("Each assessed row must be an object.")
        section = _string(item.get("section"), "assessed row section")
        if section not in dependencies:
            _fail(
                f"The assessment names a review section that is not repeated: "
                f"{section}. A retained section keeps its retained rows."
            )
        result.append(
            {
                "requirement": item.get("requirement"),
                "section": section,
                "surface": item.get("surface"),
                "result": item.get("result"),
                "reason": item.get("reason"),
                "evidence": item.get("evidence"),
                "finding_ids": item.get("finding_ids"),
                "dependencies": dependencies[section],
            }
        )
    return result


def _verified_previous(request: Mapping[str, Any]) -> dict[str, Any] | None:
    """Verify one prior evidence record against the caller-retained digest.

    A digest supplied only inside the record is not provenance. The caller must
    supply the digest it retained with its own review result.
    """
    record = request["previous_record"]
    retained = request["previous_record_sha256"]
    if record is None and retained is None:
        return None
    if record is None or retained is None:
        _fail("A prior evidence record needs the retained record digest.")
    return cast(
        "dict[str, Any] | None",
        evidence.validate_record(record, expected_sha256=retained),
    )


def _preparation_digest(value: Mapping[str, Any]) -> str:
    """Return the canonical digest of one preparation result."""
    body = {key: item for key, item in value.items() if key != "preparation_sha256"}
    return cast(str, evidence.sha256_text(evidence.canonical_json(body)))


def prepare(request: object) -> dict[str, Any]:
    """Bind the current scope, inventory, and reusable sections for one review.

    The returned preparation digest binds the current scope, the frozen
    inventory, the retained sections, and the reason for each repeated section.
    """
    normalized = _object(
        request,
        "preparation request",
        frozenset(
            {
                "scope",
                "range",
                "paths",
                "inventory",
                "artifact_kind",
                "sections",
                "corrected_findings",
                "rows",
                "previous_record",
                "previous_record_sha256",
            }
        ),
    )
    inventory = evidence.validate_inventory(normalized["inventory"])
    artifact_kind = _string(normalized["artifact_kind"], "artifact kind")
    selectors = _scope_selectors(normalized)
    resolved = _resolve(selectors)
    if _scope_binding(resolved) != inventory["scope_binding"]:
        _fail("The frozen inventory scope binding is not the current review scope.")
    records = _section_records(
        _sections(normalized["sections"]),
        resolved["identities"],
        _references(normalized["corrected_findings"], "corrected findings"),
    )
    assigned = {path for record in records for path in record["paths"]}
    unassigned = sorted(set(resolved["paths"]) - assigned)
    if unassigned:
        _fail(
            f"A resolved scope path is not assigned to a review section: {unassigned}."
        )
    previous = _verified_previous(normalized)
    comparison = evidence.compare_sections(previous, records)
    retained = set(comparison["retained"])
    retained_rows: list[dict[str, Any]] = []
    if previous is not None and retained:
        if (
            previous["requirements_sha256"]
            != inventory["requirements_binding"]["content_sha256"]
        ):
            _fail("The retained record does not match the current requirements.")
        retained_rows = [row for row in previous["rows"] if row["section"] in retained]
    result = {
        "schema_id": PREPARATION_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "requirements_binding": inventory["requirements_binding"],
        "inventory": inventory,
        "inventory_sha256": inventory["inventory_sha256"],
        "artifact_kind": artifact_kind,
        "artifact_binding": _artifact_binding(artifact_kind, resolved),
        "scope_selectors": selectors,
        "scope": _scope_binding(resolved),
        "head": resolved["head"],
        "base": resolved["base"],
        "section_records": records,
        "retained_sections": sorted(retained),
        "retained_rows": retained_rows,
        "sections_to_assess": [
            {
                "section": item["section"],
                "cause": item["cause"],
                "dependencies": next(
                    record["dependencies"]
                    for record in records
                    if record["id"] == item["section"]
                ),
            }
            for item in comparison["repeated"]
        ],
        "changed_dependencies": comparison["changed_dependencies"],
    }
    result["preparation_sha256"] = _preparation_digest(result)
    return result


def _validate_preparation(value: object) -> dict[str, Any]:
    """Validate one returned preparation and its digest."""
    preparation = _object(value, "preparation", PREPARATION_FIELDS)
    if preparation["schema_id"] != PREPARATION_SCHEMA_ID:
        _fail("The preparation schema identifier is not supported.")
    if preparation["schema_version"] != SCHEMA_VERSION:
        _fail("The preparation schema version is not supported.")
    if preparation["preparation_sha256"] != _preparation_digest(preparation):
        _fail("The preparation digest does not match its content.")
    evidence.validate_inventory(
        preparation["inventory"], expected_sha256=preparation["inventory_sha256"]
    )
    if type(preparation["sections_to_assess"]) is not list:
        _fail("The preparation must name the sections that need assessment.")
    if type(preparation["retained_rows"]) is not list:
        _fail("The preparation must carry the retained assessed rows.")
    return preparation


def finalize(request: object) -> dict[str, Any]:
    """Merge verified retained rows with new rows for the repeated sections.

    The current scope is resolved again. Source drift after preparation is a
    failure, not a merge. An invalid prior record is rejected with a specific
    diagnostic and no completeness claim.
    """
    normalized = _object(
        request,
        "finalization request",
        frozenset({"preparation", "rows"}),
    )
    preparation = _validate_preparation(normalized["preparation"])
    inventory = preparation["inventory"]
    repeated = {
        str(item["section"]): item for item in preparation["sections_to_assess"]
    }
    records = [
        record for record in preparation["section_records"] if record["id"] in repeated
    ]
    supplied = (
        _rows_with_dependencies(normalized["rows"], records)
        if records
        else (
            []
            if normalized["rows"] == []
            else _fail("The finalization rows must be empty when no section repeats.")
        )
    )
    resolved = _resolve(preparation["scope_selectors"])
    if _scope_binding(resolved) != preparation["scope"]:
        _fail(
            "The reviewed source changed after preparation. Resolve the review again."
        )
    rows = [*preparation["retained_rows"], *supplied]
    record = evidence.build_record(
        inventory=inventory,
        rows=rows,
        expected_sha256=inventory["inventory_sha256"],
        artifact_binding=_artifact_binding(str(preparation["artifact_kind"]), resolved),
    )
    return {
        "schema_id": RESULT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "record": record,
        "record_sha256": record["record_sha256"],
        "findings": evidence.assemble_findings(record),
        "requirement_map": evidence.render_requirement_map(record),
        "retained_sections": list(preparation["retained_sections"]),
        "repeat_causes": [
            {
                "section": item["section"],
                "cause": item["cause"],
                "changed_dependencies": repeated[str(item["section"])]["dependencies"],
            }
            for item in preparation["sections_to_assess"]
        ],
    }


def _read_input(path: str) -> bytes:
    """Return one bounded standard input payload."""
    if path == "-":
        return sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    return Path(path).read_bytes()


def main(argv: Sequence[str] | None = None) -> int:
    """Run one bounded preparation or finalization command."""
    parser = argument_parser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "finalize"))
    parser.add_argument("input", nargs="?", default="-")
    arguments = parser.parse_args(argv)
    try:
        payload = json.loads(_read_input(arguments.input).decode("utf-8"))
        if arguments.command == "prepare":
            result = prepare(payload)
        else:
            result = finalize(payload)
    except (Error, RuntimeError, OSError, ValueError, TypeError, KeyError) as error:
        print(f"The review evidence request failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
