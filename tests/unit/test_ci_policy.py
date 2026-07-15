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


def create_release_assets(directory: Path, version: str = "1.2.3") -> list[str]:
    """Create the exact checksummed archive and SPDX release fixture."""
    archive = directory / f"athena-plugin-{version}.tar.gz"
    archive.write_bytes(b"artifact")
    plugin_name = f"athena-plugin-{version}"
    documents = {
        directory / f"{plugin_name}.spdx.json": {
            "spdxVersion": "SPDX-2.3",
            "name": plugin_name,
            "documentNamespace": f"https://example.invalid/{plugin_name}",
            "packages": [
                {
                    "name": "athena-plugin",
                    "versionInfo": version,
                }
            ],
        },
        directory / f"athena-build-linux-64-{version}.spdx.json": {
            "spdxVersion": "SPDX-2.3",
            "name": "athena-build-linux-64",
            "documentNamespace": "https://example.invalid/athena-build-linux-64",
            "packages": [],
        },
    }
    for path, document in documents.items():
        path.write_text(json.dumps(document) + "\n", encoding="utf-8")
    artifacts = [archive, *documents]
    for artifact in artifacts:
        (directory / f"{artifact.name}.sha256").write_text(
            f"{sha256(artifact.read_bytes()).hexdigest()}  {artifact.name}\n",
            encoding="utf-8",
        )
    return sorted(path.name for path in directory.iterdir())


class PullRequestPolicyTests(unittest.TestCase):
    def test_policy_rules_are_owned_by_focused_modules(self) -> None:
        owners = {
            "evaluate_pull_request": "scripts.policies.pull_request",
            "failed_required_jobs": "scripts.policies.required_jobs",
            "evaluate_release": "scripts.policies.release",
            "verify_release_assets": "scripts.policies.release",
            "find_suppressions": "scripts.policies.suppressions",
        }

        for function_name, module_name in owners.items():
            with self.subTest(function=function_name):
                function = getattr(ci_policy, function_name)
                self.assertEqual(module_name, function.__module__)

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

    def test_rejects_malformed_page_info_and_commit_nodes(self) -> None:
        base = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "commits": {
                            "totalCount": 1,
                            "nodes": [{"commit": {"oid": "one"}}],
                            "pageInfo": {"hasNextPage": False},
                        }
                    }
                }
            }
        }
        malformed_page_info = json.loads(json.dumps(base))
        malformed_page_info["data"]["repository"]["pullRequest"]["commits"][
            "pageInfo"
        ] = []
        with self.assertRaisesRegex(ValueError, "invalid pageInfo"):
            ci_policy.flatten_commit_pages([malformed_page_info])

        malformed_node = json.loads(json.dumps(base))
        malformed_node["data"]["repository"]["pullRequest"]["commits"]["nodes"] = [
            {"commit": []}
        ]
        with self.assertRaisesRegex(ValueError, "invalid commit node"):
            ci_policy.flatten_commit_pages([malformed_node])

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
            expected = create_release_assets(directory)

            verified = ci_policy.verify_release_assets(directory)

        self.assertEqual(expected, verified)

    def test_release_checksum_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            create_release_assets(directory)
            archive = directory / "athena-plugin-1.2.3.tar.gz"
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
            create_release_assets(directory)
            extra = directory / "unexpected.txt"
            extra.write_text("extra\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exact six-file"):
                ci_policy.verify_release_assets(directory)
            extra.unlink()
            checksum = directory / "athena-plugin-1.2.3.tar.gz.sha256"
            checksum.write_text(f"{'0' * 64}  different.tar.gz\n", encoding="utf-8")
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
    def test_pr_policy_command_collects_paginated_github_evidence(self) -> None:
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
            "PR_NUMBER": "9",
            "REPO_OWNER": "owner",
            "REPO_NAME": "repository",
            "PR_AUTHOR": "contributor",
        }
        pages = [
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "commits": {
                                "totalCount": 1,
                                "nodes": [
                                    {
                                        "commit": {
                                            "oid": "abc",
                                            "message": "fix: valid\n\nSigned-off-by: A <a@example.invalid>",
                                            "signature": {"isValid": True},
                                        }
                                    }
                                ],
                                "pageInfo": {"hasNextPage": False},
                            }
                        }
                    }
                }
            }
        ]
        with (
            patch.dict(os.environ, environment, clear=False),
            patch(
                "scripts.ci_policy._run_json",
                side_effect=[{"body": "Closes #1\n"}, pages],
            ) as run_json,
        ):
            self.assertEqual(0, ci_policy.main(["pr-policy"]))

        self.assertEqual(2, run_json.call_count)
        self.assertIn("--paginate", run_json.call_args_list[1].args[0])

    def test_pr_policy_command_fails_on_policy_violation(self) -> None:
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
            "PR_NUMBER": "9",
            "REPO_OWNER": "owner",
            "REPO_NAME": "repository",
            "PR_AUTHOR": "contributor",
        }
        pages = [
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "commits": {
                                "totalCount": 0,
                                "nodes": [],
                                "pageInfo": {"hasNextPage": False},
                            }
                        }
                    }
                }
            }
        ]
        with (
            patch.dict(os.environ, environment, clear=False),
            patch("scripts.ci_policy._run_json", side_effect=[{"body": ""}, pages]),
            self.assertRaisesRegex(SystemExit, "Closes #N"),
        ):
            ci_policy.main(["pr-policy"])

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

    def test_release_command_validates_github_and_git_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for directory in (".claude-plugin", ".codex-plugin"):
                path = root / directory
                path.mkdir()
                (path / "plugin.json").write_text(
                    '{"version": "1.2.3"}\n', encoding="utf-8"
                )
            environment = {
                "GITHUB_REPOSITORY": "owner/repository",
                "GITHUB_REF_NAME": "v1.2.3",
                "GITHUB_SHA": "commit",
            }
            responses = [
                {"object": {"type": "tag", "sha": "tag-object"}},
                {
                    "object": {"sha": "commit"},
                    "verification": {"verified": True},
                },
                {"protected": True},
            ]
            with (
                patch.dict(os.environ, environment, clear=False),
                patch("scripts.ci_policy._run_json", side_effect=responses),
                patch("scripts.ci_policy.subprocess.run") as run,
            ):
                run.return_value.returncode = 0
                self.assertEqual(0, ci_policy.main(["release", "--root", str(root)]))

        run.assert_called_once_with(
            ["git", "merge-base", "--is-ancestor", "commit", "origin/main"]
        )

    def test_release_command_rejects_lightweight_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for directory in (".claude-plugin", ".codex-plugin"):
                path = root / directory
                path.mkdir()
                (path / "plugin.json").write_text(
                    '{"version": "1.2.3"}\n', encoding="utf-8"
                )
            environment = {
                "GITHUB_REPOSITORY": "owner/repository",
                "GITHUB_REF_NAME": "v1.2.3",
                "GITHUB_SHA": "commit",
            }
            with (
                patch.dict(os.environ, environment, clear=False),
                patch(
                    "scripts.ci_policy._run_json",
                    side_effect=[
                        {"object": {"type": "commit", "sha": "commit"}},
                        {"protected": True},
                    ],
                ),
                self.assertRaisesRegex(SystemExit, "annotated"),
            ):
                ci_policy.main(["release", "--root", str(root)])

    def test_suppression_command_scans_tracked_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            workflow = root / "workflow.yml"
            workflow.write_text("run: safe-command\n", encoding="utf-8")
            with patch("scripts.ci_policy.subprocess.run") as run:
                run.return_value.stdout = "workflow.yml\n"
                self.assertEqual(
                    0, ci_policy.main(["suppressions", "--root", str(root)])
                )

        run.assert_called_once()

    def test_publish_release_verifies_assets_before_gh(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            expected = create_release_assets(directory)
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
        for name in expected:
            self.assertTrue(
                any(argument.endswith(f"/{name}") for argument in run.call_args.args[0])
            )


if __name__ == "__main__":
    unittest.main()
