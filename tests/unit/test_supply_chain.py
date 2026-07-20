"""Behavior tests for deterministic SBOM and vulnerability-policy tooling."""

from __future__ import annotations

from contextlib import redirect_stderr
from datetime import date, timedelta
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
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
            with self.assertRaisesRegex(generate_sboms.SbomError, "no regular files"):
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
            with self.assertRaisesRegex(generate_sboms.SbomError, "not pinned"):
                generate_sboms.build_spdx(RAW_SPDX, environment, workflow, "1.2.3", 0)
            workflow.write_text("jobs: []\n", encoding="utf-8")
            with self.assertRaisesRegex(generate_sboms.SbomError, "no jobs"):
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
            with self.assertRaisesRegex(generate_sboms.SbomError, "one uv version"):
                generate_sboms.build_spdx(RAW_SPDX, environment, workflow, "1.2.3", 0)
            write_workflow(workflow)
            malformed_raw = {**RAW_SPDX, "relationships": {}}
            with self.assertRaisesRegex(generate_sboms.SbomError, "relationships"):
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
            self.assertRaisesRegex(OSError, "invalid json"),
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
            with self.assertRaisesRegex(generate_sboms.SbomError, "non-negative"):
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
            with self.assertRaisesRegex(generate_sboms.SbomError, "requires Linux"):
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
            for change, message in (
                ({"package": ""}, "non-empty"),
                ({"issue": "https://github.com/owner/repo/issues/1"}, "Athena"),
                ({"approved": "2026-01-02"}, "future"),
                ({"expires": "2025-12-31"}, "expired"),
                ({"expires": "2026-01-09"}, "exceeds 7"),
                ({"severity": "Medium"}, "only for High or Critical"),
            ):
                with self.subTest(change=change):
                    entry = {**base, **change}
                    path.write_text(
                        yaml.safe_dump({"exceptions": [entry]}), encoding="utf-8"
                    )
                    with self.assertRaisesRegex(VulnerabilityPolicyError, message):
                        load_exceptions(path, today=date(2026, 1, 1))

            base["severity"] = "High"
            base["expires"] = "2026-01-31"
            path.write_text(yaml.safe_dump({"exceptions": [base]}), encoding="utf-8")
            self.assertEqual(
                "High", load_exceptions(path, today=date(2026, 1, 1))[0]["severity"]
            )
            base["expires"] = "2026-02-01"
            path.write_text(yaml.safe_dump({"exceptions": [base]}), encoding="utf-8")
            with self.assertRaisesRegex(VulnerabilityPolicyError, "exceeds 30"):
                load_exceptions(path, today=date(2026, 1, 15))
            for content, message in (
                ("[]\n", "only an exceptions list"),
                ("exceptions: {}\n", "must be a list"),
                ("exceptions:\n  - bad\n", "must be a mapping"),
                ("exceptions:\n  - vulnerability: CVE-1\n", "exception fields"),
            ):
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(VulnerabilityPolicyError, message):
                        load_exceptions(path, today=date(2026, 1, 1))

    def test_malformed_grype_reports_fail_closed(self) -> None:
        with self.assertRaisesRegex(VulnerabilityPolicyError, "matches list"):
            evaluate_report({}, [])
        with self.assertRaisesRegex(VulnerabilityPolicyError, "identity fields"):
            evaluate_report({"matches": [{"vulnerability": {}, "artifact": {}}]}, [])
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "report.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(VulnerabilityPolicyError, "cannot read"):
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
            "approved": date.today().isoformat(),
            "expires": (date.today() + timedelta(days=1)).isoformat(),
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

            for issue_result, message in (
                (
                    subprocess.CompletedProcess([], 0, stdout='{"state": "closed"}\n'),
                    "not open",
                ),
                (
                    subprocess.CompletedProcess([], 0, stdout="not-json\n"),
                    "malformed issue JSON",
                ),
                (
                    subprocess.CompletedProcess([], 0, stdout="[]\n"),
                    "invalid issue JSON",
                ),
                (
                    subprocess.CompletedProcess(
                        [],
                        0,
                        stdout=(
                            '{"state": "open", "pull_request": '
                            '{"url": "https://api.github.com/repos/'
                            'HomericIntelligence/Athena/pulls/27"}}\n'
                        ),
                    ),
                    "not an issue",
                ),
                (subprocess.CompletedProcess([], 1, stderr="not found"), "not found"),
            ):
                with self.subTest(issue_result=issue_result.returncode):

                    def grype_then_failed_issue(
                        command: list[str], **kwargs: object
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
                        self.assertRaisesRegex(OSError, message),
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
                self.assertRaisesRegex(OSError, "required command unavailable: gh"),
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
                self.assertRaisesRegex(OSError, "exit status 2"),
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
    def test_required_workflow_handles_merge_queue_checks_without_trigger_drift(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        workflow = yaml.safe_load(
            (root / ".github/workflows/_required.yml").read_text(encoding="utf-8")
        )

        self.assertEqual(
            {"workflow_call", "pull_request", "push", "schedule"},
            set(workflow["on"]),
        )
        self.assertEqual({"branches": ["main"]}, workflow["on"]["pull_request"])
        self.assertEqual({"branches": ["main"]}, workflow["on"]["push"])
        self.assertEqual([{"cron": "17 9 * * 2"}], workflow["on"]["schedule"])

    def test_merge_queue_smoke_workflow_owns_the_merge_group_event(self) -> None:
        root = Path(__file__).resolve().parents[2]
        smoke = yaml.safe_load(
            (root / ".github/workflows/merge-queue-smoke.yml").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual({"merge_group"}, set(smoke["on"]))
        self.assertEqual({"types": ["checks_requested"]}, smoke["on"]["merge_group"])
        self.assertEqual(["merge-queue-smoke"], list(smoke["jobs"]))
        job = smoke["jobs"]["merge-queue-smoke"]
        self.assertEqual("merge-queue-smoke", job["name"])
        self.assertEqual(5, job["timeout-minutes"])

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
            if step.get("name")
            == "Build portable plugin archive and deterministic SBOMs"
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

    def test_all_external_actions_are_commit_pinned(self) -> None:
        root = Path(__file__).resolve().parents[2]
        for path in (root / ".github" / "workflows").glob("*.yml"):
            workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
            for job in workflow.get("jobs", {}).values():
                for step in job.get("steps", []):
                    reference = step.get("uses")
                    if reference and not reference.startswith("./"):
                        self.assertRegex(reference, r"^[^@]+@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
