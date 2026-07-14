"""Unit tests for executable CI and release policy modules."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import ci_policy


class PullRequestPolicyTests(unittest.TestCase):
    def test_flattens_complete_paginated_commit_evidence(self) -> None:
        pages = [
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "commits": {
                                "totalCount": 2,
                                "nodes": [{"commit": {"oid": "one"}}],
                                "pageInfo": {
                                    "hasNextPage": True,
                                    "endCursor": "cursor",
                                },
                            }
                        }
                    }
                }
            },
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "commits": {
                                "totalCount": 2,
                                "nodes": [{"commit": {"oid": "two"}}],
                                "pageInfo": {
                                    "hasNextPage": False,
                                    "endCursor": None,
                                },
                            }
                        }
                    }
                }
            },
        ]

        commits = ci_policy.flatten_commit_pages(pages)

        self.assertEqual(["one", "two"], [node["commit"]["oid"] for node in commits])

    def test_rejects_incomplete_pagination(self) -> None:
        pages = [
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "commits": {
                                "totalCount": 2,
                                "nodes": [{"commit": {"oid": "one"}}],
                                "pageInfo": {
                                    "hasNextPage": True,
                                    "endCursor": "cursor",
                                },
                            }
                        }
                    }
                }
            }
        ]

        with self.assertRaisesRegex(ValueError, "stopped before the final page"):
            ci_policy.flatten_commit_pages(pages)

    def test_rejects_missing_and_malformed_pagination(self) -> None:
        with self.assertRaisesRegex(ValueError, "no pages"):
            ci_policy.flatten_commit_pages([])
        with self.assertRaisesRegex(ValueError, "malformed"):
            ci_policy.flatten_commit_pages([{}])

    def test_rejects_invalid_nodes_and_changing_totals(self) -> None:
        invalid_nodes = [
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "commits": {
                                "totalCount": 1,
                                "nodes": {},
                                "pageInfo": {"hasNextPage": False},
                            }
                        }
                    }
                }
            }
        ]
        with self.assertRaisesRegex(ValueError, "invalid nodes"):
            ci_policy.flatten_commit_pages(invalid_nodes)

        changing_totals = [
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "commits": {
                                "totalCount": 2,
                                "nodes": [{"commit": {"oid": "one"}}],
                                "pageInfo": {"hasNextPage": True},
                            }
                        }
                    }
                }
            },
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "commits": {
                                "totalCount": 3,
                                "nodes": [{"commit": {"oid": "two"}}],
                                "pageInfo": {"hasNextPage": False},
                            }
                        }
                    }
                }
            },
        ]
        with self.assertRaisesRegex(ValueError, "count changed"):
            ci_policy.flatten_commit_pages(changing_totals)

    def test_enforces_link_signature_dco_and_subject(self) -> None:
        errors = ci_policy.evaluate_pull_request(
            body="No issue link",
            author="contributor",
            commits=[
                {
                    "commit": {
                        "oid": "abc",
                        "message": "not conventional",
                        "signature": {"isValid": False},
                    }
                }
            ],
        )

        self.assertEqual(4, len(errors))

    def test_valid_pull_request_and_dependabot_exemption(self) -> None:
        commit = {
            "commit": {
                "oid": "abc",
                "message": "fix: valid\n\nSigned-off-by: A <a@example.invalid>",
                "signature": {"isValid": True},
            }
        }
        self.assertEqual(
            [],
            ci_policy.evaluate_pull_request(
                body="Closes #1\n", author="contributor", commits=[commit]
            ),
        )
        self.assertEqual(
            [],
            ci_policy.evaluate_pull_request(
                body="", author="dependabot[bot]", commits=[commit]
            ),
        )


class RequiredJobsTests(unittest.TestCase):
    def test_allows_only_inapplicable_pr_policy_to_skip(self) -> None:
        results = {
            "validate": {"result": "success"},
            "pr-policy": {"result": "skipped"},
        }

        self.assertEqual({}, ci_policy.failed_required_jobs("push", results))
        self.assertEqual(
            {"pr-policy": "skipped"},
            ci_policy.failed_required_jobs("pull_request", results),
        )


class ReleasePolicyTests(unittest.TestCase):
    def test_release_version_must_match_every_manifest(self) -> None:
        errors = ci_policy.evaluate_release(
            tag="v2.0.0",
            workflow_sha="commit",
            tag_commit="commit",
            annotated=True,
            signature_verified=True,
            main_protected=True,
            manifest_versions={"claude": "2.0.0", "codex": "1.0.0"},
        )

        self.assertIn("codex manifest version 1.0.0 does not match tag 2.0.0", errors)

    def test_valid_release_has_no_policy_errors(self) -> None:
        errors = ci_policy.evaluate_release(
            tag="v1.2.3",
            workflow_sha="commit",
            tag_commit="commit",
            annotated=True,
            signature_verified=True,
            main_protected=True,
            manifest_versions={"claude": "1.2.3", "codex": "1.2.3"},
        )

        self.assertEqual([], errors)

    def test_invalid_release_reports_every_independent_failure(self) -> None:
        errors = ci_policy.evaluate_release(
            tag="latest",
            workflow_sha="workflow",
            tag_commit="tag",
            annotated=False,
            signature_verified=False,
            main_protected=False,
            manifest_versions={"claude": "1.0.0"},
        )

        self.assertEqual(5, len(errors))

    def test_release_checksum_is_verified_after_download(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            archive = directory / "athena-plugin-1.2.3.tar.gz"
            archive.write_bytes(b"artifact")
            checksum = directory / f"{archive.name}.sha256"
            checksum.write_text(
                f"{sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n",
                encoding="utf-8",
            )

            verified = ci_policy.verify_release_assets(directory)

        self.assertEqual((archive.name, checksum.name), verified)

    def test_release_checksum_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            archive = directory / "athena-plugin-1.2.3.tar.gz"
            archive.write_bytes(b"artifact")
            (directory / f"{archive.name}.sha256").write_text(
                f"{'0' * 64}  {archive.name}\n", encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                ci_policy.verify_release_assets(directory)

    def test_release_assets_require_exact_pair_and_matching_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            with self.assertRaisesRegex(ValueError, "exactly one"):
                ci_policy.verify_release_assets(directory)
            archive = directory / "athena-plugin-1.2.3.tar.gz"
            archive.write_bytes(b"artifact")
            (directory / f"{archive.name}.sha256").write_text(
                f"{'0' * 64}  different.tar.gz\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "does not identify"):
                ci_policy.verify_release_assets(directory)


class SuppressionPolicyTests(unittest.TestCase):
    def test_required_workflow_is_not_exempt_from_suppression_scan(self) -> None:
        findings = ci_policy.find_suppressions(
            {".github/workflows/_required.yml": "run: command || true\n"}
        )

        self.assertEqual(1, len(findings))

    def test_detects_continue_on_error_with_line_number(self) -> None:
        findings = ci_policy.find_suppressions(
            {"workflow.yml": "name: test\ncontinue-on-error: true\n"}
        )

        self.assertEqual(["workflow.yml:2: continue-on-error enabled"], findings)


class CommandTests(unittest.TestCase):
    def test_required_jobs_command_reads_environment(self) -> None:
        environment = {
            "EVENT_NAME": "push",
            "RESULTS": json.dumps(
                {
                    "validate": {"result": "success"},
                    "pr-policy": {"result": "skipped"},
                }
            ),
        }
        with patch.dict(os.environ, environment, clear=False):
            self.assertEqual(0, ci_policy.main(["required-jobs"]))

    def test_required_jobs_command_fails_closed(self) -> None:
        environment = {
            "EVENT_NAME": "pull_request",
            "RESULTS": json.dumps({"validate": {"result": "failure"}}),
        }
        with (
            patch.dict(os.environ, environment, clear=False),
            self.assertRaisesRegex(SystemExit, "not green"),
        ):
            ci_policy.main(["required-jobs"])

    def test_manifest_versions_reads_both_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for directory in (".claude-plugin", ".codex-plugin"):
                path = root / directory
                path.mkdir()
                (path / "plugin.json").write_text(
                    '{"version": "1.2.3"}\n', encoding="utf-8"
                )

            versions = ci_policy._manifest_versions(root)

        self.assertEqual({"claude": "1.2.3", "codex": "1.2.3"}, versions)

    def test_publish_release_verifies_assets_before_gh(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            archive = directory / "athena-plugin-1.2.3.tar.gz"
            archive.write_bytes(b"artifact")
            checksum = directory / f"{archive.name}.sha256"
            checksum.write_text(
                f"{sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n",
                encoding="utf-8",
            )
            environment = {
                "GITHUB_REF_NAME": "v1.2.3",
                "GITHUB_REPOSITORY": "owner/repository",
            }
            with (
                patch.dict(os.environ, environment, clear=False),
                patch("scripts.ci_policy.subprocess.run") as run,
            ):
                result = ci_policy.main(["publish-release", "--root", str(directory)])

        self.assertEqual(0, result)
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
