"""Exercise invalid evidence at repository validation boundaries."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import ci_policy, generate_sboms, validate_agent_contract
from scripts.policies import agent_contract_release
from skills import _cli


class ValidationFailurePathTests(unittest.TestCase):
    def test_release_rejects_malformed_provider_evidence(self) -> None:
        tag = {"object": {"type": "tag", "sha": "a" * 40}}
        cases = (
            [None],
            [{"object": {"type": "tag", "sha": ""}}],
            [tag, []],
            [tag, {"object": []}],
            [tag, {"object": {}, "verification": []}],
            [{"object": {"type": "commit"}}, []],
        )
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
            "GITHUB_REF_NAME": "v1.2.3",
            "GITHUB_SHA": "b" * 40,
        }
        for responses in cases:
            with (
                self.subTest(responses=responses),
                patch.dict(os.environ, environment),
                patch.object(ci_policy, "_run_json", side_effect=responses) as query,
                self.assertRaises(ValueError),
            ):
                ci_policy._release_command(Path("."))
            self.assertEqual(len(responses), query.call_count)

    def test_json_policy_input_requires_an_object(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(TypeError):
                ci_policy._read_json_object(path)

    def test_tag_ruleset_rejects_missing_or_malformed_rules(self) -> None:
        cases: tuple[object, ...] = (None, {}, [None], [{"type": 1}])
        for rules in cases:
            document = agent_contract_release.expected_tag_ruleset()
            document["rules"] = rules
            with self.subTest(rules=rules):
                self.assertTrue(agent_contract_release.tag_ruleset_errors(document))
        self.assertTrue(agent_contract_release.tag_ruleset_errors([]))

    def test_syft_requires_a_json_object(self) -> None:
        for output in ("[]", "null", "1"):
            result = subprocess.CompletedProcess(["syft"], 0, output, "")
            with (
                self.subTest(output=output),
                patch("scripts.generate_sboms.subprocess.run", return_value=result),
                self.assertRaises(OSError),
            ):
                generate_sboms._run_syft("syft", Path("."), "spdx-json")

    def test_sbom_normalizes_missing_or_invalid_creation_metadata(self) -> None:
        for creation in (None, {"creators": "invalid"}):
            with self.subTest(creation=creation):
                document = generate_sboms._base_document(
                    {"creationInfo": creation},
                    name="fixture",
                    identity="fixture",
                    epoch=0,
                    source_root=Path("."),
                )
                self.assertEqual(
                    ["Tool: Athena SBOM generator"],
                    document["creationInfo"]["creators"],
                )
                self.assertEqual(
                    "1970-01-01T00:00:00Z", document["creationInfo"]["created"]
                )
                json.dumps(document)

    def test_agent_contract_cli_reports_a_missing_contract(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch("sys.stderr", new_callable=io.StringIO) as error,
        ):
            self.assertEqual(1, validate_agent_contract.main(["--root", temporary]))
        self.assertIn("AGENTS.md", error.getvalue())

    def test_empty_command_is_rejected_before_execution(self) -> None:
        with (
            patch("skills._cli.subprocess.run") as run,
            self.assertRaises(RuntimeError),
        ):
            _cli.run_command([])
        run.assert_not_called()

    def test_manifest_version_requires_a_string(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".claude-plugin").mkdir()
            (root / ".claude-plugin/plugin.json").write_text(
                '{"version": 1}', encoding="utf-8"
            )
            with self.assertRaises(ci_policy.ManifestPolicyError):
                ci_policy._manifest_versions(root)

    def test_agent_contract_executable_help_exits_successfully(self) -> None:
        import runpy
        import sys

        with (
            patch.object(sys, "argv", ["validate_agent_contract.py", "--help"]),
            patch("sys.stdout", new_callable=io.StringIO) as output,
            self.assertRaises(SystemExit) as error,
        ):
            runpy.run_path(
                str(Path(validate_agent_contract.__file__)), run_name="__main__"
            )
        self.assertEqual(0, error.exception.code)
        self.assertIn("--catalog-root", output.getvalue())

    def test_git_history_checks_preserve_command_failures(self) -> None:
        cases = (
            (_cli.require_complete_git_history, ()),
            (_cli.require_unambiguous_git_merge_base, ("a" * 40, "b" * 40)),
        )
        for check_history, arguments in cases:
            for diagnostic in ("repository unavailable", ""):
                result = subprocess.CompletedProcess(["git"], 1, "", diagnostic)
                with (
                    self.subTest(check=check_history.__name__, diagnostic=diagnostic),
                    patch("skills._cli.run_command", return_value=result),
                    self.assertRaises(RuntimeError) as error,
                ):
                    check_history(*arguments)
                self.assertIn(diagnostic or "git", str(error.exception))
