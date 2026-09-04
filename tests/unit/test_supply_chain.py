"""Test deterministic software bills of materials (SBOMs) and vulnerability policy."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import UTC, date, datetime, timedelta
from fnmatch import fnmatchcase
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts import generate_sboms, scan_vulnerabilities
from scripts.policies.vulnerabilities import (
    VulnerabilityPolicyError,
    evaluate_report,
    load_exceptions,
    load_report,
)

RAW_SPDX = {
    "spdxVersion": "SPDX-2.3",
    "SPDXID": "SPDXRef-DOCUMENT",
    "name": "volatile",
    "documentNamespace": "https://example.invalid/random",
    "creationInfo": {
        "created": "2020-01-01T00:00:00Z",
        "creators": ["Tool: syft-1.46.0", "Organization: Anchore, Inc"],
    },
    "packages": [
        {
            "SPDXID": "SPDXRef-Package-conda",
            "name": "python",
            "versionInfo": "3.13",
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
        },
        {
            "SPDXID": "SPDXRef-Package-libffi",
            "name": "libffi",
            "versionInfo": "3.4",
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": True,
        },
    ],
    "files": [
        {
            "SPDXID": "SPDXRef-File-libffi",
            "fileName": "/volatile/environment/lib/libffi.so",
        }
    ],
    "relationships": [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-Package-conda",
        },
        {
            "spdxElementId": "SPDXRef-Package-libffi",
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": "SPDXRef-File-libffi",
        },
        {
            "spdxElementId": "SPDXRef-Package-libffi",
            "relationshipType": "DEPENDENCY_OF",
            "relatedSpdxElement": "SPDXRef-Package-conda",
        },
    ],
}

WORKFLOW_CLASSIFICATIONS = {
    "_agent-contract.yml": "provider-only",
    "_required.yml": "protected-events",
    "release.yml": "publishing",
}
WORKFLOW_CLASSIFICATION_VALUES = {"provider-only", "protected-events", "publishing"}
AGENT_CONTRACT_WORKFLOW = "$/.github/workflows/_agent-contract.yml"


def _workflow_triggers(
    workflow: dict[object, object], filename: str, errors: list[str]
) -> dict[str, object] | None:
    """Normalize valid GitHub event syntax, including PyYAML's YAML 1.1 `on`."""
    has_string_key = "on" in workflow
    has_boolean_key = True in workflow
    if has_string_key and has_boolean_key:
        errors.append(f"{filename}: workflow has ambiguous string and boolean on keys")
        return None
    if not has_string_key and not has_boolean_key:
        errors.append(f"{filename}: workflow is missing its on trigger")
        return None

    raw_triggers = workflow["on" if has_string_key else True]
    if isinstance(raw_triggers, str):
        return {raw_triggers: None}
    if isinstance(raw_triggers, list) and all(
        isinstance(event, str) for event in raw_triggers
    ):
        return {event: None for event in raw_triggers}
    if isinstance(raw_triggers, dict) and all(
        isinstance(event, str) for event in raw_triggers
    ):
        return raw_triggers
    errors.append(f"{filename}: on trigger must be an event or event mapping")
    return None


def _branch_patterns(
    value: object, filename: str, field: str, errors: list[str]
) -> list[str] | None:
    if isinstance(value, str):
        return [value]
    if (
        isinstance(value, list)
        and value
        and all(isinstance(pattern, str) and pattern for pattern in value)
    ):
        return value
    errors.append(f"{filename}: push.{field} must contain branch glob patterns")
    return None


def _patterns_select_main(patterns: list[str]) -> bool:
    selected = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        candidate = pattern[1:] if negated else pattern
        if candidate and fnmatchcase("main", candidate):
            selected = not negated
    return selected


def _pushes_protected_main(
    triggers: dict[str, object], filename: str, errors: list[str]
) -> bool:
    if "push" not in triggers:
        return False
    push = triggers["push"]
    if push is None:
        return True
    if not isinstance(push, dict):
        errors.append(f"{filename}: push trigger must be null or a mapping")
        return False
    if not push:
        return True

    branches_present = "branches" in push
    ignored_present = "branches-ignore" in push
    if branches_present and ignored_present:
        errors.append(f"{filename}: push cannot combine branches and branches-ignore")
        return False
    if branches_present:
        patterns = _branch_patterns(push["branches"], filename, "branches", errors)
        return patterns is not None and _patterns_select_main(patterns)
    if ignored_present:
        patterns = _branch_patterns(
            push["branches-ignore"], filename, "branches-ignore", errors
        )
        return patterns is not None and not any(
            fnmatchcase("main", pattern) for pattern in patterns
        )

    # A tags-only filter suppresses all branch pushes. Every other mapping without a
    # branch filter (for example, paths-only) includes pushes to protected main.
    return not ({"tags", "tags-ignore"} & set(push))


def workflow_inventory_errors(
    workflow_directory: Path,
    classifications: dict[str, str] | None = None,
) -> list[str]:
    """Return fail-closed errors for the complete, explicit workflow inventory."""
    if classifications is None:
        classifications = WORKFLOW_CLASSIFICATIONS
    workflows: dict[str, dict[object, object]] = {}
    errors: list[str] = []
    for path in sorted(workflow_directory.iterdir()):
        if path.suffix not in {".yml", ".yaml"}:
            continue
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            errors.append(f"{path.name}: workflow must be a mapping")
            continue
        workflows[path.name] = document

    actual = set(workflows)
    declared = set(classifications)
    for filename in sorted(actual - declared):
        errors.append(f"{filename}: workflow is not classified")
    for filename in sorted(declared - actual):
        errors.append(f"{filename}: classified workflow is missing")

    providers = [
        filename
        for filename, classification in classifications.items()
        if classification == "provider-only"
    ]
    if providers != ["_agent-contract.yml"]:
        errors.append(
            "_agent-contract.yml must be the sole provider-only workflow exception"
        )

    for filename in sorted(actual & declared):
        workflow = workflows[filename]
        classification = classifications[filename]
        if classification not in WORKFLOW_CLASSIFICATION_VALUES:
            errors.append(
                f"{filename}: unknown workflow classification {classification!r}"
            )
            continue
        triggers = _workflow_triggers(workflow, filename, errors)
        jobs = workflow.get("jobs", {})
        if not isinstance(jobs, dict):
            errors.append(f"{filename}: jobs must be a mapping")
            continue

        if classification == "provider-only":
            if triggers is not None and set(triggers) != {"workflow_call"}:
                errors.append(
                    f"{filename}: provider-only workflow must use workflow_call only"
                )
            continue

        if classification == "protected-events" and triggers is not None:
            protected_event = (
                "pull_request" in triggers
                or "merge_group" in triggers
                or _pushes_protected_main(triggers, filename, errors)
            )
            if not protected_event:
                errors.append(f"{filename}: does not run for protected main")

        call = jobs.get("agent-contract")
        if not isinstance(call, dict) or call.get("uses") != AGENT_CONTRACT_WORKFLOW:
            errors.append(f"{filename}: must directly self-call the agent contract")
            continue
        if call.get("permissions") != {"contents": "read"}:
            errors.append(
                f"{filename}: agent-contract permissions must be contents: read"
            )
        if "secrets" in call:
            errors.append(f"{filename}: agent-contract must not receive secrets")

    return errors


def write_archive(path: Path) -> None:
    with tarfile.open(path, mode="w:gz") as archive:
        for name, content in (
            ("README.md", b"readme\n"),
            ("skills/a/SKILL.md", b"skill\n"),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))


def write_workflow(path: Path, action: str = "actions/checkout@" + "a" * 40) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "jobs": {
                    "package": {
                        "steps": [
                            {"uses": action},
                            {
                                "uses": "astral-sh/setup-uv@" + "b" * 40,
                                "with": {"version": "0.10.8"},
                            },
                        ]
                    },
                    "unrelated": {
                        "steps": [{"uses": "actions/download-artifact@" + "c" * 40}]
                    },
                }
            }
        ),
        encoding="utf-8",
    )


def finding(
    *, severity: str = "High", fixes: list[str] | None = None, version: str = "1.0"
) -> dict[str, object]:
    return {
        "vulnerability": {
            "id": "CVE-2026-0001",
            "severity": severity,
            "fix": {"versions": ["2.0"] if fixes is None else fixes},
        },
        "artifact": {"name": "example", "version": version},
    }


class SbomTests(unittest.TestCase):
    def test_plugin_spdx_is_reproducible_and_covers_archive_and_dependencies(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive = Path(temporary_directory) / "plugin.tar.gz"
            write_archive(archive)

            first = generate_sboms.plugin_spdx(
                RAW_SPDX, archive, "1.2.3", 1_700_000_000
            )
            second = generate_sboms.plugin_spdx(
                RAW_SPDX, archive, "1.2.3", 1_700_000_000
            )

        self.assertEqual(first, second)
        self.assertEqual(
            {"./README.md", "./skills/a/SKILL.md"},
            {item["fileName"] for item in first["files"]},
        )
        package_names = {item["name"] for item in first["packages"]}
        self.assertTrue(
            {"python", "git", "gh", "Mnemosyne", "Hephaestus"} <= package_names
        )
        self.assertEqual("2023-11-14T22:13:20Z", first["creationInfo"]["created"])
        self.assertNotIn("syft-1.46.0", json.dumps(first))

    def test_plugin_spdx_rejects_empty_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive = Path(temporary_directory) / "empty.tar.gz"
            with tarfile.open(archive, mode="w:gz"):
                pass
            with self.assertRaises(generate_sboms.SbomError):
                generate_sboms.plugin_spdx(RAW_SPDX, archive, "1.0.0", 0)

    def test_build_spdx_includes_environment_uv_and_pinned_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            environment = root / "environment"
            environment.mkdir()
            workflow = root / "workflow.yml"
            write_workflow(workflow)

            document = generate_sboms.build_spdx(
                RAW_SPDX, environment, workflow, "1.2.3", 0
            )

        package_names = {item["name"] for item in document["packages"]}
        self.assertTrue(
            {"python", "uv", "actions/checkout", "athena-build-linux-64"}
            <= package_names
        )
        self.assertNotIn("actions/download-artifact", package_names)
        self.assertEqual(1, len(document["documentDescribes"]))
        packages = {item["name"]: item for item in document["packages"]}
        self.assertEqual("0.10.8", packages["uv"]["versionInfo"])
        self.assertEqual("1.2.3", packages["athena-build-linux-64"]["versionInfo"])
        relationship_types = {
            item["relationshipType"] for item in document["relationships"]
        }
        self.assertTrue(
            {"CONTAINS", "DEPENDENCY_OF", "DEPENDS_ON"} <= relationship_types
        )
        self.assertFalse(
            any(
                item.get("spdxElementId") == "SPDXRef-DOCUMENT"
                or item.get("relatedSpdxElement") == "SPDXRef-DOCUMENT"
                for item in document["relationships"]
            )
        )

    def test_build_spdx_rejects_unpinned_action_and_bad_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            environment = root / "environment"
            environment.mkdir()
            workflow = root / "workflow.yml"
            write_workflow(workflow, "actions/checkout@v4")
            with self.assertRaises(generate_sboms.SbomError):
                generate_sboms.build_spdx(RAW_SPDX, environment, workflow, "1.2.3", 0)
            workflow.write_text("jobs: []\n", encoding="utf-8")
            with self.assertRaises(generate_sboms.SbomError):
                generate_sboms.build_spdx(RAW_SPDX, environment, workflow, "1.2.3", 0)
            workflow.write_text(
                yaml.safe_dump(
                    {
                        "jobs": {
                            "package": {
                                "steps": [{"uses": "actions/checkout@" + "a" * 40}]
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(generate_sboms.SbomError):
                generate_sboms.build_spdx(RAW_SPDX, environment, workflow, "1.2.3", 0)
            write_workflow(workflow)
            malformed_raw = {**RAW_SPDX, "relationships": {}}
            with self.assertRaises(generate_sboms.SbomError):
                generate_sboms.build_spdx(
                    malformed_raw, environment, workflow, "1.2.3", 0
                )

    def test_syft_transport_fails_closed_on_exit_and_invalid_json(self) -> None:
        completed = subprocess.CompletedProcess([], 1, stdout="", stderr="broken")
        with (
            patch("scripts.generate_sboms.subprocess.run", return_value=completed),
            self.assertRaisesRegex(OSError, "broken"),
        ):
            generate_sboms._run_syft("syft", Path("source"), "json")
        completed = subprocess.CompletedProcess([], 0, stdout="not-json", stderr="")
        with (
            patch("scripts.generate_sboms.subprocess.run", return_value=completed),
            self.assertRaises(OSError),
        ):
            generate_sboms._run_syft("syft", Path("source"), "json")

    def test_generate_writes_two_checksummed_sboms_and_native_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / ".codex-plugin").mkdir()
            (root / ".codex-plugin" / "plugin.json").write_text(
                '{"version":"1.2.3"}\n', encoding="utf-8"
            )
            archive = root / "athena-plugin-1.2.3.tar.gz"
            write_archive(archive)
            environment = root / "environment"
            environment.mkdir()
            workflow = root / "workflow.yml"
            write_workflow(workflow)
            output = root / "dist"
            native = root / "internal" / "inventory.json"
            with patch(
                "scripts.generate_sboms._run_syft",
                side_effect=[RAW_SPDX, RAW_SPDX, {"artifacts": []}],
            ):
                plugin, build = generate_sboms.generate(
                    archive_path=archive,
                    environment_path=environment,
                    workflow_path=workflow,
                    output_directory=output,
                    native_output=native,
                    epoch=0,
                    syft="syft",
                    repo_root=root,
                    platform_name="linux",
                )

            self.assertTrue(plugin.is_file() and build.is_file() and native.is_file())
            self.assertTrue(Path(f"{plugin}.sha256").is_file())
            self.assertTrue(Path(f"{build}.sha256").is_file())
            with self.assertRaises(generate_sboms.SbomError):
                generate_sboms.generate(
                    archive_path=archive,
                    environment_path=environment,
                    workflow_path=workflow,
                    output_directory=output,
                    native_output=native,
                    epoch=-1,
                    syft="syft",
                    repo_root=root,
                    platform_name="linux",
                )
            with self.assertRaises(generate_sboms.SbomError):
                generate_sboms.generate(
                    archive_path=archive,
                    environment_path=environment,
                    workflow_path=workflow,
                    output_directory=output,
                    native_output=native,
                    epoch=0,
                    syft="syft",
                    repo_root=root,
                    platform_name="darwin",
                )

    def test_generate_normalizes_volatile_syft_output_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / ".codex-plugin").mkdir()
            (root / ".codex-plugin" / "plugin.json").write_text(
                '{"version":"1.2.3"}\n', encoding="utf-8"
            )
            archive = root / "athena-plugin-1.2.3.tar.gz"
            write_archive(archive)
            workflow = root / "workflow.yml"
            write_workflow(workflow)
            environment_one = root / "environment-one"
            environment_two = root / "environment-two"
            environment_one.mkdir()
            environment_two.mkdir()

            first_raw = json.loads(json.dumps(RAW_SPDX))
            second_raw = json.loads(json.dumps(RAW_SPDX))
            ambiguous_packages = [
                {
                    "SPDXID": f"SPDXRef-Package-importlib-{version}",
                    "name": "importlib-metadata",
                    "versionInfo": version,
                    "downloadLocation": "NOASSERTION",
                    "filesAnalyzed": False,
                }
                for version in ("8", "9")
            ]
            for raw in (first_raw, second_raw):
                raw["packages"].extend(json.loads(json.dumps(ambiguous_packages)))
            first_raw["relationships"].append(
                {
                    "spdxElementId": "SPDXRef-Package-libffi",
                    "relationshipType": "DEPENDENCY_OF",
                    "relatedSpdxElement": "SPDXRef-Package-importlib-8",
                }
            )
            second_raw["relationships"].append(
                {
                    "spdxElementId": "SPDXRef-Package-libffi",
                    "relationshipType": "DEPENDENCY_OF",
                    "relatedSpdxElement": "SPDXRef-Package-importlib-9",
                }
            )
            first_raw["files"][0]["fileName"] = str(
                environment_one / "lib" / "libffi.so"
            )
            second_raw["files"][0]["fileName"] = str(
                environment_two / "lib" / "libffi.so"
            )
            second_raw["documentNamespace"] = "https://example.invalid/other"
            second_raw["creationInfo"]["created"] = "2030-01-01T00:00:00Z"
            second_raw["creationInfo"]["creators"] = [
                "Organization: Anchore, Inc",
                "Tool: syft-99.0.0",
            ]
            for key in ("packages", "files", "relationships"):
                second_raw[key].reverse()

            generated: list[tuple[Path, Path]] = []
            for index, (environment, raw) in enumerate(
                ((environment_one, first_raw), (environment_two, second_raw)), start=1
            ):
                with patch(
                    "scripts.generate_sboms._run_syft",
                    side_effect=[raw, raw, {"artifacts": [index]}],
                ):
                    generated.append(
                        generate_sboms.generate(
                            archive_path=archive,
                            environment_path=environment,
                            workflow_path=workflow,
                            output_directory=root / f"dist-{index}",
                            native_output=root / f"internal-{index}.json",
                            epoch=1_700_000_000,
                            syft="syft",
                            repo_root=root,
                            platform_name="linux",
                        )
                    )

            for first, second in zip(*generated, strict=True):
                self.assertEqual(first.read_bytes(), second.read_bytes())
                self.assertEqual(
                    Path(f"{first}.sha256").read_text(encoding="utf-8"),
                    Path(f"{second}.sha256").read_text(encoding="utf-8"),
                )

    def test_cli_dist_discovery_and_error_exit_classes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "dist").mkdir()
            errors = io.StringIO()
            with redirect_stderr(errors):
                self.assertEqual(1, generate_sboms.main(["--root", str(root)]))
            with patch(
                "scripts.generate_sboms.generate", side_effect=OSError("tool failed")
            ):
                archive = root / "dist" / "athena-plugin-1.0.0.tar.gz"
                archive.touch()
                with redirect_stderr(errors):
                    self.assertEqual(
                        2,
                        generate_sboms.main(
                            [
                                "--root",
                                str(root),
                                "--archive",
                                str(archive),
                                "--source-date-epoch",
                                "0",
                            ]
                        ),
                    )


class VulnerabilityPolicyTests(unittest.TestCase):
    def test_fixable_high_and_critical_block_but_unfixed_and_lower_do_not(self) -> None:
        report = {
            "matches": [
                finding(severity="Critical"),
                finding(severity="High", version="1.1"),
                finding(severity="High", fixes=[]),
                finding(severity="Medium"),
            ]
        }
        blocking = evaluate_report(report, [])
        self.assertEqual(2, len(blocking))

    def test_exact_exception_suppresses_only_matching_finding(self) -> None:
        exception = {
            "vulnerability": "CVE-2026-0001",
            "package": "example",
            "version": "1.0",
            "severity": "High",
            "reason": "fixture",
            "owner": "security",
            "issue": "https://github.com/HomericIntelligence/Athena/issues/1",
            "approved": "2026-01-01",
            "expires": "2026-01-02",
        }
        self.assertEqual([], evaluate_report({"matches": [finding()]}, [exception]))
        self.assertEqual(
            1, len(evaluate_report({"matches": [finding(version="1.1")]}, [exception]))
        )

    def test_exception_schema_expiry_and_maximum_duration_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "exceptions.yml"
            path.write_text("exceptions: []\n", encoding="utf-8")
            self.assertEqual([], load_exceptions(path, today=date(2026, 1, 1)))
            base = {
                "vulnerability": "CVE-1",
                "package": "package",
                "version": "1",
                "severity": "Critical",
                "reason": "reason",
                "owner": "owner",
                "issue": "https://github.com/HomericIntelligence/Athena/issues/1",
                "approved": "2026-01-01",
                "expires": "2026-01-02",
            }
            path.write_text(yaml.safe_dump({"exceptions": [base]}), encoding="utf-8")
            self.assertEqual(
                "Critical",
                load_exceptions(path, today=date(2026, 1, 1))[0]["severity"],
            )
            for change in (
                {"package": ""},
                {"issue": "https://github.com/owner/repo/issues/1"},
                {"approved": "2026-01-02"},
                {"approved": "2025-12-30", "expires": "2025-12-31"},
                {"expires": "2026-01-09"},
                {"severity": "Medium"},
            ):
                with self.subTest(change=change):
                    entry = {**base, **change}
                    path.write_text(
                        yaml.safe_dump({"exceptions": [entry]}), encoding="utf-8"
                    )
                    with self.assertRaises(VulnerabilityPolicyError):
                        load_exceptions(path, today=date(2026, 1, 1))

            base["severity"] = "High"
            base["expires"] = "2026-01-31"
            path.write_text(yaml.safe_dump({"exceptions": [base]}), encoding="utf-8")
            self.assertEqual(
                "High", load_exceptions(path, today=date(2026, 1, 1))[0]["severity"]
            )
            base["expires"] = "2026-02-01"
            path.write_text(yaml.safe_dump({"exceptions": [base]}), encoding="utf-8")
            with self.assertRaises(VulnerabilityPolicyError):
                load_exceptions(path, today=date(2026, 1, 15))
            for content in (
                "[]\n",
                "exceptions: {}\n",
                "exceptions:\n  - bad\n",
                "exceptions:\n  - vulnerability: CVE-1\n",
            ):
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(VulnerabilityPolicyError):
                        load_exceptions(path, today=date(2026, 1, 1))

    def test_malformed_grype_reports_fail_closed(self) -> None:
        with self.assertRaises(VulnerabilityPolicyError):
            evaluate_report({}, [])
        with self.assertRaises(VulnerabilityPolicyError):
            evaluate_report({"matches": [{"vulnerability": {}, "artifact": {}}]}, [])
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "report.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(VulnerabilityPolicyError):
                load_report(path)

    def test_scan_requires_each_exception_to_reference_an_open_athena_issue(
        self,
    ) -> None:
        exception = {
            "vulnerability": "CVE-2026-0001",
            "package": "example",
            "version": "1.0",
            "severity": "High",
            "reason": "fixture",
            "owner": "security",
            "issue": "https://github.com/HomericIntelligence/Athena/issues/1",
            "approved": datetime.now(UTC).date().isoformat(),
            "expires": (datetime.now(UTC).date() + timedelta(days=1)).isoformat(),
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            exceptions = root / "exceptions.yml"
            exceptions.write_text(
                yaml.safe_dump({"exceptions": [exception]}), encoding="utf-8"
            )
            report = root / "report.json"

            def grype_then_issue(
                command: list[str], **kwargs: object
            ) -> subprocess.CompletedProcess[str]:
                del kwargs
                if command[0] == "grype":
                    report.write_text('{"matches": []}\n', encoding="utf-8")
                    return subprocess.CompletedProcess(command, 0)
                return subprocess.CompletedProcess(
                    command, 0, stdout='{"state": "open"}\n'
                )

            with patch(
                "scripts.scan_vulnerabilities.subprocess.run",
                side_effect=grype_then_issue,
            ):
                self.assertEqual(
                    [],
                    scan_vulnerabilities.scan(
                        inventory=root / "inventory.json",
                        config=root / "grype.yml",
                        exceptions_path=exceptions,
                        report_path=report,
                        grype="grype",
                    ),
                )

            for issue_result in (
                subprocess.CompletedProcess([], 0, stdout='{"state": "closed"}\n'),
                subprocess.CompletedProcess([], 0, stdout="not-json\n"),
                subprocess.CompletedProcess([], 0, stdout="[]\n"),
                subprocess.CompletedProcess(
                    [],
                    0,
                    stdout=(
                        '{"state": "open", "pull_request": '
                        '{"url": "https://api.github.com/repos/'
                        'HomericIntelligence/Athena/pulls/27"}}\n'
                    ),
                ),
                subprocess.CompletedProcess([], 1, stderr="not found"),
            ):
                with self.subTest(issue_result=issue_result.returncode):

                    def grype_then_failed_issue(
                        command: list[str],
                        issue_result: subprocess.CompletedProcess[str] = issue_result,
                        **kwargs: object,
                    ) -> subprocess.CompletedProcess[str]:
                        del kwargs
                        if command[0] == "grype":
                            report.write_text('{"matches": []}\n', encoding="utf-8")
                            return subprocess.CompletedProcess(command, 0)
                        return issue_result

                    with (
                        patch(
                            "scripts.scan_vulnerabilities.subprocess.run",
                            side_effect=grype_then_failed_issue,
                        ),
                        self.assertRaises(OSError),
                    ):
                        scan_vulnerabilities.scan(
                            inventory=root / "inventory.json",
                            config=root / "grype.yml",
                            exceptions_path=exceptions,
                            report_path=report,
                            grype="grype",
                        )

            def grype_then_missing_gh(
                command: list[str], **kwargs: object
            ) -> subprocess.CompletedProcess[str]:
                del kwargs
                if command[0] == "grype":
                    report.write_text('{"matches": []}\n', encoding="utf-8")
                    return subprocess.CompletedProcess(command, 0)
                raise FileNotFoundError(2, "No such file or directory", "gh")

            with (
                patch(
                    "scripts.scan_vulnerabilities.subprocess.run",
                    side_effect=grype_then_missing_gh,
                ),
                self.assertRaises(OSError),
            ):
                scan_vulnerabilities.scan(
                    inventory=root / "inventory.json",
                    config=root / "grype.yml",
                    exceptions_path=exceptions,
                    report_path=report,
                    grype="grype",
                )

    def test_scan_invokes_grype_and_enforces_generated_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            exceptions = root / "exceptions.yml"
            exceptions.write_text("exceptions: []\n", encoding="utf-8")
            report = root / "report.json"

            def write_report(
                *args: object, **kwargs: object
            ) -> subprocess.CompletedProcess[bytes]:
                del args, kwargs
                report.write_text('{"matches": []}\n', encoding="utf-8")
                return subprocess.CompletedProcess([], 0)

            with patch(
                "scripts.scan_vulnerabilities.subprocess.run", side_effect=write_report
            ) as run:
                blocking = scan_vulnerabilities.scan(
                    inventory=root / "inventory.json",
                    config=root / "grype.yml",
                    exceptions_path=exceptions,
                    report_path=report,
                    grype="grype",
                )
            self.assertEqual([], blocking)
            self.assertIn("sbom:", run.call_args.args[0][1])
            with (
                patch(
                    "scripts.scan_vulnerabilities.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 2),
                ),
                self.assertRaises(OSError),
            ):
                scan_vulnerabilities.scan(
                    inventory=root / "inventory.json",
                    config=root / "grype.yml",
                    exceptions_path=exceptions,
                    report_path=report,
                    grype="grype",
                )

    def test_scan_cli_distinguishes_policy_and_operational_failures(self) -> None:
        errors = io.StringIO()
        with (
            patch("scripts.scan_vulnerabilities.scan", return_value=["High CVE"]),
            redirect_stderr(errors),
        ):
            self.assertEqual(
                1, scan_vulnerabilities.main(["--inventory", "inventory.json"])
            )
        with patch("scripts.scan_vulnerabilities.scan", return_value=[]):
            self.assertEqual(
                0, scan_vulnerabilities.main(["--inventory", "inventory.json"])
            )
        with (
            patch(
                "scripts.scan_vulnerabilities.scan",
                side_effect=VulnerabilityPolicyError("bad report"),
            ),
            redirect_stderr(errors),
        ):
            self.assertEqual(
                1, scan_vulnerabilities.main(["--inventory", "inventory.json"])
            )
        with (
            patch(
                "scripts.scan_vulnerabilities.scan",
                side_effect=OSError("scanner failed"),
            ),
            redirect_stderr(errors),
        ):
            self.assertEqual(
                2, scan_vulnerabilities.main(["--inventory", "inventory.json"])
            )


class WorkflowContractTests(unittest.TestCase):
    @staticmethod
    def _fixture_inventory_errors(
        filename: str,
        source: str,
        classification: str | None,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workflow_directory = Path(temporary_directory)
            (workflow_directory / "_agent-contract.yml").write_text(
                """name: Agent Contract
"on":
  workflow_call:
permissions:
  contents: read
jobs:
  validate-agent-contract:
    runs-on: ubuntu-24.04
    steps: []
""",
                encoding="utf-8",
            )
            (workflow_directory / filename).write_text(source, encoding="utf-8")
            classifications = {"_agent-contract.yml": "provider-only"}
            if classification is not None:
                classifications[filename] = classification
            return workflow_inventory_errors(workflow_directory, classifications)

    @staticmethod
    def _needs(job: dict[str, object]) -> set[str]:
        value = job.get("needs", [])
        if isinstance(value, str):
            return {value}
        if isinstance(value, list):
            return {item for item in value if isinstance(item, str)}
        return set()

    def _depends_on(
        self,
        jobs: dict[str, dict[str, object]],
        job_name: str,
        dependency: str,
        visited: set[str] | None = None,
    ) -> bool:
        if job_name == dependency:
            return True
        if visited is None:
            visited = set()
        if job_name in visited:
            return False
        visited.add(job_name)
        return any(
            self._depends_on(jobs, required, dependency, visited)
            for required in self._needs(jobs[job_name])
            if required in jobs
        )

    def _required_concurrency_key(
        self,
        *,
        workflow: str,
        event_name: str,
        event: dict[str, object],
        sha: str,
    ) -> str:
        root = Path(__file__).resolve().parents[2]
        required = yaml.safe_load(
            (root / ".github" / "workflows" / "_required.yml").read_text(
                encoding="utf-8"
            )
        )
        group = required["concurrency"]["group"]
        self.assertEqual(
            (
                "${{ format('required-{0}-{1}-{2}', github.workflow, "
                "github.event_name, github.event.pull_request.number || github.sha) }}"
            ),
            group,
        )
        pull_request = event.get("pull_request")
        number = pull_request.get("number") if isinstance(pull_request, dict) else None
        identity = number or sha
        return f"required-{workflow}-{event_name}-{identity}"

    def test_reusable_agent_contract_is_hermetic_and_required(self) -> None:
        root = Path(__file__).resolve().parents[2]
        provider_path = root / ".github" / "workflows" / "_agent-contract.yml"
        action_path = (
            root / ".github" / "actions" / "validate-agent-contract" / "action.yml"
        )
        self.assertTrue(provider_path.is_file(), provider_path)
        self.assertTrue(action_path.is_file(), action_path)

        provider = yaml.safe_load(provider_path.read_text(encoding="utf-8"))
        self.assertEqual({"name", "on", "permissions", "jobs"}, set(provider))
        self.assertEqual({"workflow_call"}, set(provider["on"]))
        self.assertIsNone(provider["on"]["workflow_call"])
        self.assertEqual({"contents": "read"}, provider["permissions"])
        self.assertNotIn("concurrency", provider)
        self.assertEqual({"validate-agent-contract"}, set(provider["jobs"]))
        job = provider["jobs"]["validate-agent-contract"]
        self.assertEqual(
            {"name", "runs-on", "timeout-minutes", "steps"},
            set(job),
        )
        self.assertEqual("validate-agent-contract", job["name"])
        self.assertEqual("ubuntu-24.04", job["runs-on"])
        self.assertEqual(5, job["timeout-minutes"])
        self.assertEqual(2, len(job["steps"]))
        checkout, validate = job["steps"]
        self.assertEqual(
            {
                "name": "Check out the caller revision",
                "uses": ("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"),
                "with": {"persist-credentials": False},
            },
            checkout,
        )
        self.assertEqual(
            {
                "name": "Validate the root agent contract",
                "uses": "$/.github/actions/validate-agent-contract",
            },
            validate,
        )

        action = yaml.safe_load(action_path.read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "name": "Validate agent contract",
                "description": (
                    "Validate root agent instructions against the canonical Athena "
                    "catalog."
                ),
                "runs": {
                    "using": "composite",
                    "steps": [
                        {
                            "name": "Validate the caller checkout",
                            "shell": "bash",
                            "run": (
                                'python3 -I -S "${{ github.action_path }}/../../../scripts/'
                                'validate_agent_contract.py" --root "${{ github.workspace }}" '
                                '--catalog-root "${{ github.action_path }}/../../.."'
                            ),
                        }
                    ],
                },
            },
            action,
        )

        required = yaml.safe_load(
            (root / ".github" / "workflows" / "_required.yml").read_text(
                encoding="utf-8"
            )
        )
        call = required["jobs"]["agent-contract"]
        self.assertEqual("agent-contract", call["name"])
        self.assertEqual({"contents": "read"}, call["permissions"])
        self.assertEqual("$/.github/workflows/_agent-contract.yml", call["uses"])
        self.assertNotIn("secrets", call)
        self.assertIn(
            "agent-contract", required["jobs"]["required-checks-gate"]["needs"]
        )

    def test_agent_contract_action_executes_only_the_provider_validator(self) -> None:
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            provider = fixture_root / "provider"
            caller = fixture_root / "caller"
            action_path = provider / ".github" / "actions" / "validate-agent-contract"
            action_path.mkdir(parents=True)
            caller.mkdir()
            shutil.copy2(
                root / ".github" / "actions" / "validate-agent-contract" / "action.yml",
                action_path / "action.yml",
            )
            shutil.copytree(root / "scripts", provider / "scripts")
            (provider / "skills").mkdir()
            shutil.copy2(root / "skills" / "_cli.py", provider / "skills" / "_cli.py")
            shutil.copytree(
                root / "docs" / "principles", provider / "docs" / "principles"
            )
            shutil.copy2(root / "AGENTS.md", caller / "AGENTS.md")
            shutil.copy2(root / "CLAUDE.md", caller / "CLAUDE.md")
            sentinel = fixture_root / "caller-code-ran"
            (caller / "sitecustomize.py").write_text(
                f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n",
                encoding="utf-8",
            )
            (caller / "skills").mkdir()
            (caller / "skills" / "__init__.py").write_text(
                f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n",
                encoding="utf-8",
            )

            action = yaml.safe_load((action_path / "action.yml").read_text("utf-8"))
            command = action["runs"]["steps"][0]["run"]
            command = command.replace("${{ github.action_path }}", str(action_path))
            command = command.replace("${{ github.workspace }}", str(caller))
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-euo", "pipefail", "-c", command],
                cwd=caller,
                env={"PATH": os.environ["PATH"]},
                capture_output=True,
                check=False,
                text=True,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse(sentinel.exists())

            audit_runner = fixture_root / "audit_runner.py"
            audit_runner.write_text(
                """from __future__ import annotations

import runpy
import sys


def deny_external_capability(event: str, _arguments: tuple[object, ...]) -> None:
    if event.startswith("socket.") or event in {
        "os.posix_spawn",
        "os.spawn",
        "os.system",
        "subprocess.Popen",
    }:
        raise RuntimeError(f"The validator used a denied capability: {event}")


sys.addaudithook(deny_external_capability)
script = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
""",
                encoding="utf-8",
            )
            audited_command = command.replace(
                "python3 -I -S ",
                f'python3 -I -S "{audit_runner}" ',
                1,
            )
            audited_result = subprocess.run(
                [
                    "bash",
                    "--noprofile",
                    "--norc",
                    "-euo",
                    "pipefail",
                    "-c",
                    audited_command,
                ],
                cwd=caller,
                env={"PATH": os.environ["PATH"]},
                capture_output=True,
                check=False,
                text=True,
            )

            self.assertEqual(0, audited_result.returncode, audited_result.stderr)
            self.assertFalse(sentinel.exists())

    def test_protected_and_publishing_workflows_directly_self_call(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(
            [],
            workflow_inventory_errors(root / ".github" / "workflows"),
        )

    def test_protected_main_trigger_forms_cannot_silently_skip_the_contract(
        self,
    ) -> None:
        trigger_sources = {
            "unquoted on": """on:
  pull_request:
""",
            "push null": """on:
  push:
""",
            "push empty mapping": """on:
  push: {}
""",
            "push without branch filters": """on:
  push:
    paths: ["src/**"]
""",
            "push branches-ignore permits main": """on:
  push:
    branches-ignore: ["release/**"]
""",
            "push glob matches main": """on:
  push:
    branches: ["**"]
""",
        }
        for scenario, triggers in trigger_sources.items():
            with self.subTest(scenario=scenario):
                errors = self._fixture_inventory_errors(
                    "ordinary.yml",
                    f"""name: Ordinary automation
{triggers}jobs:
  build:
    runs-on: ubuntu-24.04
    steps: []
""",
                    "protected-events",
                )
                self.assertTrue(
                    any("must directly self-call" in error for error in errors),
                    errors,
                )
                self.assertFalse(
                    any("does not run for protected main" in error for error in errors),
                    errors,
                )

    def test_publishing_classification_does_not_depend_on_workflow_names(self) -> None:
        errors = self._fixture_inventory_errors(
            "artifact-integrity.yml",
            """name: Artifact integrity
on:
  push:
    tags: ["v*"]
jobs:
  deliver:
    runs-on: ubuntu-24.04
    steps: []
""",
            "publishing",
        )

        self.assertTrue(
            any("must directly self-call" in error for error in errors),
            errors,
        )

    def test_non_main_push_filters_do_not_claim_protected_main_coverage(self) -> None:
        trigger_sources = {
            "main is ignored": """on:
  push:
    branches-ignore: ["m*"]
""",
            "main does not match": """on:
  push:
    branches: ["release/**"]
""",
            "ordered negation removes main": """on:
  push:
    branches: ["**", "!main"]
""",
            "tag filters suppress branch pushes": """on:
  push:
    tags: ["v*"]
""",
        }
        for scenario, triggers in trigger_sources.items():
            with self.subTest(scenario=scenario):
                errors = self._fixture_inventory_errors(
                    "ordinary.yml",
                    f"""name: Ordinary automation
{triggers}jobs:
  build:
    runs-on: ubuntu-24.04
    steps: []
""",
                    "protected-events",
                )
                self.assertTrue(
                    any("does not run for protected main" in error for error in errors),
                    errors,
                )

    def test_unknown_workflow_fails_the_explicit_inventory(self) -> None:
        errors = self._fixture_inventory_errors(
            "maintenance.yml",
            """name: Weekly maintenance
on:
  schedule:
    - cron: "17 9 * * 2"
jobs:
  report:
    runs-on: ubuntu-24.04
    steps: []
""",
            None,
        )

        self.assertTrue(any("is not classified" in error for error in errors), errors)

    def test_workflow_dependency_graphs_fail_closed_on_agent_contract(self) -> None:
        root = Path(__file__).resolve().parents[2]
        required = yaml.safe_load(
            (root / ".github" / "workflows" / "_required.yml").read_text(
                encoding="utf-8"
            )
        )
        release = yaml.safe_load(
            (root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        )
        required_jobs = required["jobs"]
        release_jobs = release["jobs"]
        self.assertEqual(
            set(required_jobs) - {"required-checks-gate"},
            set(required_jobs["required-checks-gate"]["needs"]),
        )
        for name in set(required_jobs) - {"agent-contract"}:
            with self.subTest(workflow="required", job=name):
                self.assertTrue(
                    self._depends_on(required_jobs, name, "agent-contract"),
                    name,
                )
        for name in set(release_jobs) - {"agent-contract"}:
            with self.subTest(workflow="release", job=name):
                self.assertTrue(
                    self._depends_on(release_jobs, name, "agent-contract"),
                    name,
                )

    def test_required_concurrency_does_not_use_a_fork_branch_name(self) -> None:
        root = Path(__file__).resolve().parents[2]
        required = yaml.safe_load(
            (root / ".github" / "workflows" / "_required.yml").read_text(
                encoding="utf-8"
            )
        )
        group = required["concurrency"]["group"]
        self.assertNotIn("github.head_ref", group)
        self.assertNotIn("github.ref", group)
        self.assertIs(required["concurrency"]["cancel-in-progress"], True)

    def test_same_name_fork_pull_requests_have_isolated_concurrency_keys(self) -> None:
        first = self._required_concurrency_key(
            workflow="Required Checks",
            event_name="pull_request",
            event={"pull_request": {"number": 101, "head": {"ref": "feature"}}},
            sha="first-head",
        )
        second = self._required_concurrency_key(
            workflow="Required Checks",
            event_name="pull_request",
            event={"pull_request": {"number": 102, "head": {"ref": "feature"}}},
            sha="second-head",
        )

        self.assertNotEqual(first, second)

    def test_new_commit_for_the_same_pull_request_cancels_the_stale_run(self) -> None:
        stale = self._required_concurrency_key(
            workflow="Required Checks",
            event_name="pull_request",
            event={"pull_request": {"number": 101}},
            sha="stale-head",
        )
        current = self._required_concurrency_key(
            workflow="Required Checks",
            event_name="pull_request",
            event={"pull_request": {"number": 101}},
            sha="current-head",
        )

        self.assertEqual(stale, current)

    def test_pull_request_and_non_pull_request_runs_cannot_cancel_each_other(
        self,
    ) -> None:
        pull_request = self._required_concurrency_key(
            workflow="Required Checks",
            event_name="pull_request",
            event={"pull_request": {"number": 101}},
            sha="shared-sha",
        )
        push = self._required_concurrency_key(
            workflow="Required Checks",
            event_name="push",
            event={},
            sha="shared-sha",
        )

        self.assertNotEqual(pull_request, push)

    def test_required_workflow_handles_merge_queue_checks_without_trigger_drift(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        workflow = yaml.safe_load(
            (root / ".github/workflows/_required.yml").read_text(encoding="utf-8")
        )

        self.assertEqual(
            {"workflow_call", "pull_request", "push", "merge_group", "schedule"},
            set(workflow["on"]),
        )
        self.assertEqual({"branches": ["main"]}, workflow["on"]["pull_request"])
        self.assertEqual({"branches": ["main"]}, workflow["on"]["push"])
        self.assertEqual({"types": ["checks_requested"]}, workflow["on"]["merge_group"])
        self.assertEqual([{"cron": "17 9 * * 2"}], workflow["on"]["schedule"])

    def test_required_and_release_workflows_consume_gated_sboms(self) -> None:
        root = Path(__file__).resolve().parents[2]
        required = yaml.safe_load(
            (root / ".github/workflows/_required.yml").read_text(encoding="utf-8")
        )
        release = yaml.safe_load(
            (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
        )
        jobs = required["jobs"]
        self.assertEqual("package", jobs["security-dependency-scan"]["needs"])
        self.assertIn("security-dependency-scan", jobs["required-checks-gate"]["needs"])
        package_text = json.dumps(jobs["package"])
        self.assertIn("*.spdx.json", package_text)
        self.assertIn("athena-sca-input", package_text)
        self.assertNotIn("pixi", package_text)
        build_run = next(
            step["run"]
            for step in jobs["package"]["steps"]
            if "scripts/generate_sboms.py" in step.get("run", "")
        )
        self.assertEqual(2, build_run.count("uv run python scripts/generate_sboms.py"))
        self.assertEqual(4, build_run.count("cmp dist/"))
        self.assertEqual(
            "read", release["jobs"]["required"]["permissions"]["pull-requests"]
        )
        self.assertEqual(
            "read", release["jobs"]["required"]["permissions"].get("issues")
        )
        self.assertEqual(
            "athena-plugin", release["jobs"]["release"]["steps"][1]["with"]["name"]
        )
        npm_job = release["jobs"]["publish-npm"]
        self.assertIn("required", npm_job["needs"])
        self.assertEqual("write", npm_job["permissions"]["id-token"])
        publish_step = next(
            step
            for step in npm_job["steps"]
            if step.get("name") == "Publish npm package"
        )
        self.assertIn("--provenance", publish_step["run"])
        self.assertNotIn("env", publish_step)

    def test_pi_runtime_is_locked_updated_and_scanned_before_ci_executes_it(
        self,
    ) -> None:
        """The gate must scan the real Pi and npm dependency tree in continuous integration."""
        root = Path(__file__).resolve().parents[2]
        runtime_root = root / "ci" / "pi-runtime"
        manifest = json.loads(
            (runtime_root / "package.json").read_text(encoding="utf-8")
        )
        lock = json.loads(
            (runtime_root / "package-lock.json").read_text(encoding="utf-8")
        )
        dependabot = yaml.safe_load(
            (root / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        )
        required = yaml.safe_load(
            (root / ".github" / "workflows" / "_required.yml").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            {
                "pi-subagents": "0.51.0",
                "@earendil-works/pi-coding-agent": "0.84.2",
            },
            manifest["dependencies"],
        )
        self.assertEqual(3, lock["lockfileVersion"])
        for package in manifest["dependencies"]:
            resolved = lock["packages"][f"node_modules/{package}"]
            self.assertIn("integrity", resolved)
            self.assertEqual(manifest["dependencies"][package], resolved["version"])
        self.assertIn(
            {
                "package-ecosystem": "npm",
                "directory": "/ci/pi-runtime",
                "schedule": {"interval": "monthly"},
                "cooldown": {"default-days": 7},
                "open-pull-requests-limit": 5,
                "labels": ["dependencies", "npm"],
                "commit-message": {"prefix": "chore(deps)"},
                "groups": {
                    "minor-patch": {
                        "patterns": ["*"],
                        "update-types": ["minor", "patch"],
                    },
                    "major": {
                        "patterns": ["*"],
                        "update-types": ["major"],
                    },
                },
            },
            dependabot["updates"],
        )

        package_job = required["jobs"]["package"]
        node_setup = next(
            (
                step
                for step in package_job["steps"]
                if step.get("uses")
                == "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020"
            ),
            None,
        )
        self.assertIsNotNone(node_setup)
        assert node_setup is not None
        self.assertEqual("24", node_setup["with"]["node-version"])
        pi_step = next(
            step
            for step in package_job["steps"]
            if "find_pi_package_root.mjs" in step.get("run", "")
        )
        self.assertNotIn("PI_RUNTIME_REF", pi_step["env"])
        self.assertNotIn("earendil-works/pi.git", pi_step["run"])
        self.assertNotIn("hydrate:model-data", pi_step["run"])
        self.assertNotIn("build:offline", pi_step["run"])
        self.assertIn("pi() {", pi_step["run"])
        self.assertIn(
            "node_modules/@earendil-works/pi-coding-agent/dist/cli.js",
            pi_step["run"],
        )
        self.assertIn('npm ci --prefix "$PI_RUNTIME_ROOT"', pi_step["run"])
        self.assertIn("--ignore-scripts --engine-strict", pi_step["run"])
        self.assertIn("find_pi_package_root.mjs", pi_step["run"])
        self.assertIn(
            '"$PI_RUNTIME_ROOT/node_modules/@earendil-works/pi-coding-agent/npm-shrinkwrap.json"',
            pi_step["run"],
        )
        self.assertIn('scan "$PI_RUNTIME_ROOT" -o json', pi_step["run"])
        self.assertIn("syft-pi-source.json", json.dumps(package_job))
        self.assertIn("syft-pi-subagents.json", json.dumps(package_job))

        scan_job = required["jobs"]["security-dependency-scan"]
        scan_step = next(
            step
            for step in scan_job["steps"]
            if "scripts/scan_vulnerabilities.py" in step.get("run", "")
        )
        self.assertIn("syft-environment.json", scan_step["run"])
        self.assertIn("syft-pi-source.json", scan_step["run"])
        self.assertIn("syft-pi-subagents.json", scan_step["run"])

    def test_all_external_actions_are_commit_pinned(self) -> None:
        root = Path(__file__).resolve().parents[2]
        for path in (root / ".github" / "workflows").glob("*.yml"):
            workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
            for job in workflow.get("jobs", {}).values():
                for step in job.get("steps", []):
                    reference = step.get("uses")
                    if reference and not reference.startswith(("./", "$/")):
                        self.assertRegex(reference, r"^[^@]+@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
