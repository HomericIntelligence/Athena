"""Unit tests for executable CI and release policy modules."""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stderr
from hashlib import sha256
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import ci_policy
from scripts.policies import agent_contract_release
from scripts.policies.uv_pins import find_uv_pin_drift


def write_checksum(artifact: Path) -> None:
    artifact.with_name(f"{artifact.name}.sha256").write_text(
        f"{sha256(artifact.read_bytes()).hexdigest()}  {artifact.name}\n",
        encoding="utf-8",
    )


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
            "packages": [
                {
                    "name": "athena-build-linux-64",
                    "versionInfo": version,
                }
            ],
        },
    }
    for path, document in documents.items():
        path.write_text(json.dumps(document) + "\n", encoding="utf-8")
    artifacts = [archive, *documents]
    for artifact in artifacts:
        write_checksum(artifact)
    return sorted(path.name for path in directory.iterdir())


class PullRequestPolicyTests(unittest.TestCase):
    def test_required_job_policy_allows_only_non_pr_policy_skip(self) -> None:
        results = {
            "validate": {"result": "success"},
            "pr-policy": {"result": "skipped"},
            "package": {"result": "skipped"},
        }

        self.assertEqual(
            {"package": "skipped"}, ci_policy.failed_required_jobs("push", results)
        )
        self.assertEqual(
            {"package": "skipped", "pr-policy": "skipped"},
            ci_policy.failed_required_jobs("pull_request", results),
        )

    def test_agent_contract_ruleset_policy_is_exact_and_no_bypass(self) -> None:
        document = agent_contract_release.expected_tag_ruleset()

        self.assertEqual([], agent_contract_release.tag_ruleset_errors(document))

        mutations: dict[str, Callable[[dict[str, Any]], None]] = {
            "target": lambda value: value.update(target="branch"),
            "enforcement": lambda value: value.update(enforcement="evaluate"),
            "include": lambda value: value["conditions"]["ref_name"].update(
                include=["refs/tags/*"]
            ),
            "bypass": lambda value: value.update(bypass_actors=[{"actor_id": 1}]),
            "update": lambda value: value.update(
                rules=[rule for rule in value["rules"] if rule["type"] != "update"]
            ),
            "deletion": lambda value: value.update(
                rules=[rule for rule in value["rules"] if rule["type"] != "deletion"]
            ),
            "creation": lambda value: value["rules"].append({"type": "creation"}),
            "status": lambda value: value["rules"].append(
                {"type": "required_status_checks", "parameters": {}}
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                candidate = json.loads(json.dumps(document))
                mutate(candidate)
                self.assertTrue(agent_contract_release.tag_ruleset_errors(candidate))

    def test_live_agent_contract_ruleset_normalizes_provider_metadata(self) -> None:
        tracked = agent_contract_release.expected_tag_ruleset()
        live = json.loads(json.dumps(tracked))
        live.update(id=42, source="HomericIntelligence/Athena", node_id="node")
        live["rules"][0]["ruleset_source_type"] = "Repository"

        self.assertEqual(
            [], agent_contract_release.live_tag_ruleset_errors(tracked, live)
        )

        live["rules"].append({"type": "creation"})
        self.assertTrue(agent_contract_release.live_tag_ruleset_errors(tracked, live))

    def test_agent_contract_release_evidence_requires_every_green_surface(self) -> None:
        commit = "a" * 40
        pull_head = "b" * 40
        tag_ref = {"object": {"type": "tag", "sha": "c" * 40}}
        tag_object = {
            "object": {"type": "commit", "sha": commit},
            "verification": {"verified": True},
        }
        pull_requests = [
            {
                "state": "closed",
                "merged_at": "2026-09-07T00:00:00Z",
                "merge_commit_sha": commit,
                "head": {"sha": pull_head},
            }
        ]
        workflow_runs = [
            {
                "event": event,
                "head_sha": sha,
                "name": "Required Checks",
                "conclusion": "success",
                "html_url": f"https://example.invalid/{event}",
            }
            for event, sha in (
                ("pull_request", pull_head),
                ("merge_group", commit),
                ("push", commit),
            )
        ]
        check_runs = [
            {"name": "validate-agent-contract", "conclusion": "success"},
            {"name": "required-checks-gate", "conclusion": "success"},
        ]

        evidence: dict[str, Any] = {
            "tag": agent_contract_release.AGENT_CONTRACT_TAG,
            "commit": commit,
            "main_sha": commit,
            "main_commit": {
                "sha": commit,
                "verification": {"verified": True},
            },
            "tag_ref": tag_ref,
            "tag_object": tag_object,
            "pull_requests": pull_requests,
            "workflow_runs": workflow_runs,
            "check_runs": check_runs,
        }
        self.assertEqual(
            [], agent_contract_release.agent_contract_release_errors(**evidence)
        )

        recovery_evidence = {**evidence, "tag": "agent-contract-v1.0.1"}
        self.assertEqual(
            [],
            agent_contract_release.agent_contract_release_errors(**recovery_evidence),
        )

        historical_evidence = {**evidence, "main_sha": "d" * 40}
        self.assertEqual(
            [],
            agent_contract_release.agent_contract_release_errors(**historical_evidence),
        )
        self.assertIn(
            "The agent-contract commit must be the exact main commit.",
            agent_contract_release.agent_contract_release_errors(
                **historical_evidence, pre_tag=True
            ),
        )

        for name, replacement in (
            ("wrong-tag", {"tag": "v1.0.1"}),
            ("invalid-semver-tag", {"tag": "agent-contract-v01.0.1"}),
            ("lightweight", {"tag_ref": {"object": {"type": "commit"}}}),
            (
                "unsigned",
                {
                    "tag_object": {
                        "object": {"type": "commit", "sha": commit},
                        "verification": {"verified": False},
                    }
                },
            ),
            (
                "unverified-main",
                {
                    "main_commit": {
                        "sha": commit,
                        "verification": {"verified": False},
                    }
                },
            ),
            ("missing-pr", {"pull_requests": []}),
            (
                "missing-merge-group",
                {
                    "workflow_runs": [
                        run for run in workflow_runs if run["event"] != "merge_group"
                    ]
                },
            ),
            ("missing-provider", {"check_runs": check_runs[1:]}),
        ):
            with self.subTest(name=name):
                candidate: dict[str, Any] = {**evidence, **replacement}
                self.assertTrue(
                    agent_contract_release.agent_contract_release_errors(**candidate)
                )

    def test_agent_contract_release_record_is_complete_and_bound(self) -> None:
        values: dict[str, Any] = {
            "tag_object_sha": "a" * 40,
            "commit_sha": "b" * 40,
            "catalog_sha256": "c" * 64,
            "workflow_urls": [
                "https://github.com/HomericIntelligence/Athena/actions/runs/1",
                "https://github.com/HomericIntelligence/Athena/actions/runs/2",
                "https://github.com/HomericIntelligence/Athena/actions/runs/3",
            ],
            "live_ruleset_sha256": "d" * 64,
            "resolved_url_count": 91,
            "retarget_rejection": "rejected: repository rule violation",
            "deletion_rejection": "rejected: repository rule violation",
        }

        body = agent_contract_release.render_release_record(**values)

        self.assertEqual(
            [], agent_contract_release.release_record_errors(body, **values)
        )
        self.assertTrue(
            agent_contract_release.release_record_errors(
                body.replace(values["commit_sha"], "e" * 40), **values
            )
        )
        recovery_body = agent_contract_release.render_release_record(
            tag="agent-contract-v1.0.1", **values
        )
        self.assertTrue(
            recovery_body.startswith("# agent-contract-v1.0.1 release record")
        )

    def test_agent_contract_ruleset_cli_checks_tracked_and_live_state(self) -> None:
        root = Path(__file__).resolve().parents[2]
        tracked = agent_contract_release.expected_tag_ruleset()
        live = {**tracked, "id": 42}
        environment = {"GITHUB_REPOSITORY": "owner/repository"}

        self.assertEqual(
            0,
            ci_policy.main(["agent-contract-tracked-ruleset", "--root", str(root)]),
        )
        with (
            patch.dict(os.environ, environment, clear=False),
            patch(
                "scripts.ci_policy._run_json",
                side_effect=[
                    [{"id": 42, "name": tracked["name"], "target": "tag"}],
                    live,
                ],
            ),
        ):
            self.assertEqual(
                0,
                ci_policy.main(["agent-contract-live-ruleset", "--root", str(root)]),
            )

    def test_agent_contract_live_ruleset_missing_bypass_actors_reports_authority_gap(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        tracked = agent_contract_release.expected_tag_ruleset()
        live = {**tracked, "id": 42}
        del live["bypass_actors"]

        with (
            patch.dict(
                os.environ, {"GITHUB_REPOSITORY": "owner/repository"}, clear=False
            ),
            patch(
                "scripts.ci_policy._run_json",
                side_effect=[
                    [{"id": 42, "name": tracked["name"], "target": "tag"}],
                    live,
                ],
            ),
            self.assertRaisesRegex(SystemExit, "cannot prove the no-bypass policy"),
        ):
            ci_policy.main(["agent-contract-live-ruleset", "--root", str(root)])

    def test_agent_contract_live_ruleset_distinguishes_authority_gap_from_policy_drift(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        tracked = agent_contract_release.expected_tag_ruleset()
        live = {**tracked, "id": 42, "bypass_actors": [{"actor_id": 1}]}

        with (
            patch.dict(
                os.environ, {"GITHUB_REPOSITORY": "owner/repository"}, clear=False
            ),
            patch(
                "scripts.ci_policy._run_json",
                side_effect=[
                    [{"id": 42, "name": tracked["name"], "target": "tag"}],
                    live,
                ],
            ),
            self.assertRaisesRegex(SystemExit, "has one or more bypass actors"),
        ):
            ci_policy.main(["agent-contract-live-ruleset", "--root", str(root)])

    def test_agent_contract_release_cli_supports_pre_tag_readiness(self) -> None:
        commit = "a" * 40
        evidence = {
            "main_sha": commit,
            "main_commit": {
                "sha": commit,
                "verification": {"verified": True},
            },
            "tag_ref": None,
            "tag_object": None,
            "pull_requests": [
                {
                    "merged_at": "now",
                    "merge_commit_sha": commit,
                    "head": {"sha": "b" * 40},
                }
            ],
            "workflow_runs": [
                {
                    "event": event,
                    "head_sha": revision,
                    "name": "Required Checks",
                    "conclusion": "success",
                    "html_url": f"https://example.invalid/{event}",
                }
                for event, revision in (
                    ("pull_request", "b" * 40),
                    ("merge_group", commit),
                    ("push", commit),
                )
            ],
            "check_runs": [
                {"name": "validate-agent-contract", "conclusion": "success"},
                {"name": "required-checks-gate", "conclusion": "success"},
            ],
        }
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
            "AGENT_CONTRACT_COMMIT": commit,
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch(
                "scripts.ci_policy._collect_agent_contract_release_evidence",
                return_value=evidence,
            ) as collect,
        ):
            self.assertEqual(
                0,
                ci_policy.main(["agent-contract-release", "--pre-tag"]),
            )

        collect.assert_called_once_with("owner/repository", commit, pre_tag=True)

    def test_agent_contract_release_evidence_collection_binds_tag_and_runs(
        self,
    ) -> None:
        commit = "a" * 40
        pull_head = "b" * 40
        tag_sha = "c" * 40
        pull = {
            "merged_at": "now",
            "merge_commit_sha": commit,
            "head": {"sha": pull_head},
        }
        commit_run = {"event": "push", "head_sha": commit}
        pull_run = {"event": "pull_request", "head_sha": pull_head}
        tag_ref = {"object": {"type": "tag", "sha": tag_sha}}
        tag_object = {
            "object": {"type": "commit", "sha": commit},
            "verification": {"verified": True},
        }
        responses = [
            {"object": {"sha": commit}},
            {"sha": commit, "verification": {"verified": True}},
            [pull],
            {"workflow_runs": [commit_run]},
            {"workflow_runs": [pull_run]},
            {"check_runs": [{"name": "required-checks-gate"}]},
            tag_ref,
            tag_object,
        ]
        with (
            patch.dict(
                os.environ,
                {"AGENT_CONTRACT_TAG": agent_contract_release.AGENT_CONTRACT_TAG},
                clear=False,
            ),
            patch("scripts.ci_policy._run_json", side_effect=responses) as run_json,
        ):
            evidence = ci_policy._collect_agent_contract_release_evidence(
                "owner/repository", commit, pre_tag=False
            )

        self.assertEqual(commit, evidence["main_sha"])
        self.assertEqual(
            {"sha": commit, "verification": {"verified": True}},
            evidence["main_commit"],
        )
        self.assertEqual([pull], evidence["pull_requests"])
        self.assertEqual([commit_run, pull_run], evidence["workflow_runs"])
        self.assertEqual(tag_ref, evidence["tag_ref"])
        self.assertEqual(tag_object, evidence["tag_object"])
        self.assertEqual(8, run_json.call_count)

    def test_agent_contract_release_record_cli_writes_and_verifies(self) -> None:
        root = Path(__file__).resolve().parents[2]
        commit = "a" * 40
        pull_head = "b" * 40
        tag_sha = "c" * 40
        workflow_runs = [
            {
                "event": event,
                "head_sha": revision,
                "name": "Required Checks",
                "conclusion": "success",
                "html_url": f"https://example.invalid/{event}",
            }
            for event, revision in (
                ("pull_request", pull_head),
                ("merge_group", commit),
                ("push", commit),
            )
        ]
        evidence = {
            "main_sha": commit,
            "main_commit": {
                "sha": commit,
                "verification": {"verified": True},
            },
            "tag_ref": {"object": {"type": "tag", "sha": tag_sha}},
            "tag_object": {
                "object": {"type": "commit", "sha": commit},
                "verification": {"verified": True},
            },
            "pull_requests": [
                {
                    "merged_at": "now",
                    "merge_commit_sha": commit,
                    "head": {"sha": pull_head},
                }
            ],
            "workflow_runs": workflow_runs,
            "check_runs": [
                {"name": "validate-agent-contract", "conclusion": "success"},
                {"name": "required-checks-gate", "conclusion": "success"},
            ],
        }
        tracked = agent_contract_release.expected_tag_ruleset()
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
            "AGENT_CONTRACT_TAG": agent_contract_release.AGENT_CONTRACT_TAG,
            "AGENT_CONTRACT_COMMIT": commit,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            retarget = temporary / "retarget.txt"
            deletion = temporary / "deletion.txt"
            output = temporary / "release.md"
            rejection = (
                "remote: error: GH013: Repository rule violations found for "
                "refs/tags/agent-contract-v1.0.0.\n"
            )
            retarget.write_text(rejection, encoding="utf-8")
            deletion.write_text(rejection, encoding="utf-8")
            arguments = [
                "agent-contract-release-record",
                "--root",
                str(root),
                "--retarget-rejection-file",
                str(retarget),
                "--deletion-rejection-file",
                str(deletion),
            ]
            with (
                patch.dict(os.environ, environment, clear=True),
                patch(
                    "scripts.ci_policy._collect_agent_contract_release_evidence",
                    return_value=evidence,
                ),
                patch(
                    "scripts.ci_policy._live_agent_contract_ruleset",
                    return_value=tracked,
                ),
                patch(
                    "scripts.ci_policy._resolved_agent_contract_url_count",
                    return_value=91,
                ),
            ):
                self.assertEqual(
                    0, ci_policy.main([*arguments, "--output", str(output)])
                )
                body = output.read_text(encoding="utf-8")
                with patch("scripts.ci_policy._run_json", return_value={"body": body}):
                    self.assertEqual(
                        0, ci_policy.main([*arguments, "--verify-release"])
                    )

        self.assertIn(tag_sha, body)
        self.assertIn(commit, body)
        self.assertIn("Resolved principle URLs: 91", body)

    def test_agent_contract_release_record_rejects_unattributed_push_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            evidence = Path(temporary_directory) / "rejection.txt"
            evidence.write_text("Retarget rejected because the network failed.\n")

            with self.assertRaisesRegex(ValueError, "GitHub ruleset rejection"):
                ci_policy._read_rejection(evidence, "retarget")

    def test_agent_contract_url_and_consumer_cli_checks(self) -> None:
        root = Path(__file__).resolve().parents[2]
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
            "AGENT_CONTRACT_TAG": agent_contract_release.AGENT_CONTRACT_TAG,
        }
        with (
            patch.dict(os.environ, environment, clear=False),
            patch(
                "scripts.ci_policy.principle_detail_paths",
                return_value=(
                    "docs/principles/details/one.md",
                    "docs/principles/details/two.md",
                ),
            ),
            patch(
                "scripts.ci_policy._run_json",
                side_effect=[{"type": "file"}, {"type": "file"}],
            ) as run_json,
        ):
            self.assertEqual(
                0,
                ci_policy.main(["agent-contract-url-resolution", "--root", str(root)]),
            )

        self.assertEqual(2, run_json.call_count)
        self.assertEqual(
            0,
            ci_policy.main(["agent-contract-no-main-consumer", "--root", str(root)]),
        )

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

        with self.assertRaises(ValueError):
            ci_policy.flatten_commit_pages(pages)

    def test_rejects_missing_and_malformed_pagination(self) -> None:
        with self.assertRaises(ValueError):
            ci_policy.flatten_commit_pages([])
        with self.assertRaises(ValueError):
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
        with self.assertRaises(TypeError):
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
        with self.assertRaises(ValueError):
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
        with self.assertRaises(TypeError):
            ci_policy.flatten_commit_pages([malformed_page_info])

        malformed_node = json.loads(json.dumps(base))
        malformed_node["data"]["repository"]["pullRequest"]["commits"]["nodes"] = [
            {"commit": []}
        ]
        with self.assertRaises(ValueError):
            ci_policy.flatten_commit_pages([malformed_node])

    def test_enforces_link_signature_dco_and_subject(self) -> None:
        errors = ci_policy.evaluate_pull_request(
            body="No issue link",
            author="contributor",
            require_issue_link=True,
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
                body="", author="contributor", commits=[commit]
            ),
        )
        self.assertEqual(
            [],
            ci_policy.evaluate_pull_request(
                body="Closes #1\n",
                author="contributor",
                require_issue_link=True,
                commits=[commit],
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

        self.assertEqual(1, len(errors))
        for value in ("codex", "1.0.0", "2.0.0"):
            self.assertIn(value, errors[0])

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

            with self.assertRaises(ValueError):
                ci_policy.verify_release_assets(directory)

    def test_release_assets_require_exact_pair_and_matching_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            with self.assertRaises(ValueError):
                ci_policy.verify_release_assets(directory)
            create_release_assets(directory)
            extra = directory / "unexpected.txt"
            extra.write_text("extra\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                ci_policy.verify_release_assets(directory)
            extra.unlink()
            checksum = directory / "athena-plugin-1.2.3.tar.gz.sha256"
            checksum.write_text(f"{'0' * 64}  different.tar.gz\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                ci_policy.verify_release_assets(directory)

    def test_release_spdx_validation_fails_closed(self) -> None:
        valid_plugin_package = {
            "name": "athena-plugin",
            "versionInfo": "1.2.3",
        }
        cases: tuple[tuple[str, object, type[Exception]], ...] = (
            ("invalid-json", "not-json", ValueError),
            ("non-object-document", [], TypeError),
            (
                "unsupported-spdx-version",
                {
                    "spdxVersion": "SPDX-2.2",
                    "name": "athena-plugin-1.2.3",
                    "documentNamespace": "athena-plugin-1.2.3",
                    "packages": [valid_plugin_package],
                },
                ValueError,
            ),
            (
                "incorrect-document-name",
                {
                    "spdxVersion": "SPDX-2.3",
                    "name": "wrong",
                    "documentNamespace": "athena-plugin-1.2.3",
                    "packages": [valid_plugin_package],
                },
                ValueError,
            ),
            (
                "incorrect-document-namespace",
                {
                    "spdxVersion": "SPDX-2.3",
                    "name": "athena-plugin-1.2.3",
                    "documentNamespace": "wrong",
                    "packages": [valid_plugin_package],
                },
                ValueError,
            ),
            (
                "non-list-packages",
                {
                    "spdxVersion": "SPDX-2.3",
                    "name": "athena-plugin-1.2.3",
                    "documentNamespace": "athena-plugin-1.2.3",
                    "packages": {},
                },
                TypeError,
            ),
            (
                "incorrect-package-version",
                {
                    "spdxVersion": "SPDX-2.3",
                    "name": "athena-plugin-1.2.3",
                    "documentNamespace": "athena-plugin-1.2.3",
                    "packages": [{"name": "athena-plugin", "versionInfo": "9.9.9"}],
                },
                ValueError,
            ),
        )
        for case, content, error_type in cases:
            with (
                self.subTest(case=case),
                tempfile.TemporaryDirectory() as temporary,
            ):
                directory = Path(temporary)
                create_release_assets(directory)
                plugin = directory / "athena-plugin-1.2.3.spdx.json"
                plugin.write_text(
                    content if isinstance(content, str) else json.dumps(content),
                    encoding="utf-8",
                )
                write_checksum(plugin)
                with self.assertRaises(error_type):
                    ci_policy.verify_release_assets(directory)

    def test_release_build_spdx_is_bound_to_release_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            create_release_assets(directory)
            build = directory / "athena-build-linux-64-1.2.3.spdx.json"
            document = json.loads(build.read_text(encoding="utf-8"))
            document["packages"][0]["versionInfo"] = "1.2.2"
            build.write_text(json.dumps(document), encoding="utf-8")
            write_checksum(build)

            with self.assertRaises(ValueError):
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

        self.assertEqual(1, len(findings))
        location, separator, diagnostic = findings[0].partition(": ")
        self.assertEqual("workflow.yml:2", location)
        self.assertEqual(": ", separator)
        self.assertTrue(diagnostic)


class UvPinsPolicyTests(unittest.TestCase):
    CONTAINER = (
        "curl https://github.com/astral-sh/uv/releases/download/0.12.1/"
        "uv-x86_64-unknown-linux-gnu.tar.gz -o /tmp/uv.tar.gz\n"
        'echo "' + "a" * 64 + '  /tmp/uv.tar.gz" | sha256sum --check\n'
    )
    WORKFLOW = """
jobs:
  build:
    steps:
      - uses: astral-sh/setup-uv@abc
        with:
          version: "0.12.1"
"""

    def test_consistent_pins_have_no_findings(self) -> None:
        self.assertEqual(
            [], find_uv_pin_drift(self.CONTAINER, {"workflow.yml": self.WORKFLOW})
        )

    def test_drift_names_workflow_and_both_versions(self) -> None:
        findings = find_uv_pin_drift(
            self.CONTAINER,
            {"workflow.yml": self.WORKFLOW.replace("0.12.1", "0.10.8")},
        )
        self.assertEqual(1, len(findings))
        self.assertIn("workflow.yml", findings[0])
        self.assertIn("0.10.8", findings[0])
        self.assertIn("0.12.1", findings[0])

    def test_multiple_steps_detect_partial_drift(self) -> None:
        workflow = self.WORKFLOW.replace(
            "    steps:",
            '    steps:\n      - uses: astral-sh/setup-uv@def\n        with:\n          version: "0.10.8"',
        )
        findings = find_uv_pin_drift(self.CONTAINER, {"workflow.yml": workflow})
        self.assertEqual(1, len(findings))

    def test_commented_container_url_does_not_override_active_pin(self) -> None:
        container = (
            "# curl https://github.com/astral-sh/uv/releases/download/0.12.1/"
            "uv-x86_64-unknown-linux-gnu.tar.gz -o /tmp/uv.tar.gz\n"
            + self.CONTAINER.replace("0.12.1", "0.13.0")
        )
        workflow = self.WORKFLOW.replace("0.12.1", "0.13.0")

        self.assertEqual([], find_uv_pin_drift(container, {"workflow.yml": workflow}))

    def test_non_download_url_does_not_override_download_pin(self) -> None:
        expected_url = (
            "https://github.com/astral-sh/uv/releases/download/0.12.1/"
            "uv-x86_64-unknown-linux-gnu.tar.gz"
        )
        container = f"RUN echo '{expected_url}'\n" + self.CONTAINER.replace(
            "0.12.1", "0.13.0"
        )

        findings = find_uv_pin_drift(container, {"workflow.yml": self.WORKFLOW})

        self.assertEqual(1, len(findings))
        self.assertIn("0.12.1", findings[0])
        self.assertIn("0.13.0", findings[0])

    def test_malformed_container_pin_fails_closed(self) -> None:
        for container in (
            self.CONTAINER.replace("download/0.12.1", "download/not-a-version"),
            self.CONTAINER.replace("a" * 64, "missing"),
            self.CONTAINER.replace("a" * 64, "g" * 64),
        ):
            with self.subTest(container=container):
                self.assertTrue(
                    find_uv_pin_drift(container, {"workflow.yml": self.WORKFLOW})
                )

    def test_missing_active_checksum_verification_fails_closed(self) -> None:
        cases = {
            "removed": self.CONTAINER.replace(" | sha256sum --check", ""),
            "commented": self.CONTAINER.replace(
                " | sha256sum --check", " # | sha256sum --check"
            ),
        }

        for case, container in cases.items():
            with self.subTest(case=case):
                findings = find_uv_pin_drift(container, {"workflow.yml": self.WORKFLOW})
                self.assertTrue(findings)
                self.assertTrue(
                    any("SHA-256" in finding for finding in findings), findings
                )

    def test_checksum_pipeline_obeys_shell_comments_and_line_continuations(
        self,
    ) -> None:
        download = self.CONTAINER.splitlines()[0]
        checksum_echo = 'echo "' + "a" * 64 + '  /tmp/uv.tar.gz"'
        cases = (
            (
                "inline_comment",
                f"{download}\nRUN true # {checksum_echo} | sha256sum --check\n",
                True,
            ),
            (
                "uncontinued_newline",
                f"{download}\n{checksum_echo}\n  | sha256sum --check\n",
                True,
            ),
            (
                "continued_newline",
                f"{download}\n{checksum_echo} \\\n  | sha256sum --check\n",
                False,
            ),
            (
                "quoted_hash",
                (
                    f"{download}\nRUN printf '%s\\n' '# checksum follows' && \\\n"
                    f"  {checksum_echo} \\\n"
                    "  | sha256sum --check\n"
                ),
                False,
            ),
            (
                "quoted_pipeline",
                (
                    f"{download}\nRUN printf '%s\\n' "
                    f"'{checksum_echo} | sha256sum --check'\n"
                ),
                True,
            ),
            (
                "mid_word_hash",
                (
                    f"{download}\nRUN printf '%s\\n' foo#bar && \\\n"
                    f"  {checksum_echo} \\\n"
                    "  | sha256sum --check\n"
                ),
                False,
            ),
        )

        for case, container, checksum_finding_expected in cases:
            with self.subTest(case=case):
                findings = find_uv_pin_drift(container, {"workflow.yml": self.WORKFLOW})

                self.assertEqual(
                    checksum_finding_expected,
                    any("SHA-256" in finding for finding in findings),
                    findings,
                )

    def test_mixed_case_setup_uv_identity_is_inspected(self) -> None:
        workflow = (
            self.WORKFLOW.rstrip()
            + """
      - uses: Astral-Sh/Setup-UV@def
        with:
          version: "0.10.8"
"""
        )

        findings = find_uv_pin_drift(self.CONTAINER, {"workflow.yml": workflow})

        self.assertEqual(1, len(findings))
        self.assertIn("workflow.yml", findings[0])
        self.assertIn("0.10.8", findings[0])
        self.assertIn("0.12.1", findings[0])

    def test_zero_setup_uv_steps_fails_closed(self) -> None:
        findings = find_uv_pin_drift(self.CONTAINER, {"workflow.yml": "jobs: {}\n"})
        self.assertEqual(1, len(findings))
        self.assertIn("No astral-sh/setup-uv", findings[0])

    def test_repository_pins_are_consistent(self) -> None:
        root = Path(__file__).parents[2]
        container = (root / "ci" / "Containerfile").read_text(encoding="utf-8")
        workflow_root = root / ".github" / "workflows"
        workflows = {
            str(path.relative_to(root)): path.read_text(encoding="utf-8")
            for pattern in ("*.yml", "*.yaml")
            for path in workflow_root.glob(pattern)
        }
        self.assertEqual([], find_uv_pin_drift(container, workflows))


class CommandTests(unittest.TestCase):
    def test_pr_policy_command_wraps_subprocess_failure(self) -> None:
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
            "PR_NUMBER": "9",
            "REPO_OWNER": "owner",
            "REPO_NAME": "repository",
            "PR_AUTHOR": "contributor",
        }
        error = io.StringIO()
        completed = subprocess.CompletedProcess(
            ["gh"], 1, stdout="", stderr="authentication failed"
        )
        with (
            patch.dict(os.environ, environment, clear=False),
            patch("scripts.ci_policy.subprocess.run", return_value=completed),
            redirect_stderr(error),
        ):
            result = ci_policy.main(["pr-policy"])

        self.assertEqual(2, result)
        self.assertIn("error: command failed", error.getvalue())
        self.assertIn("authentication failed", error.getvalue())

    def test_pr_policy_command_rejects_wrong_json_shape(self) -> None:
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
            "PR_NUMBER": "9",
            "REPO_OWNER": "owner",
            "REPO_NAME": "repository",
            "PR_AUTHOR": "contributor",
        }
        error = io.StringIO()
        with (
            patch.dict(os.environ, environment, clear=False),
            patch("scripts.ci_policy._run_json", return_value=[]),
            redirect_stderr(error),
        ):
            result = ci_policy.main(["pr-policy"])

        self.assertEqual(2, result)
        self.assertIn("not an object", error.getvalue())

    def test_release_command_rejects_wrong_json_shape(self) -> None:
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
            "GITHUB_REF_NAME": "v1.2.3",
            "GITHUB_SHA": "a" * 40,
        }
        error = io.StringIO()
        with (
            patch.dict(os.environ, environment, clear=False),
            patch("scripts.ci_policy._run_json", return_value=[]),
            redirect_stderr(error),
        ):
            result = ci_policy.main(["release", "--root", "."])

        self.assertEqual(2, result)
        self.assertIn("invalid tag reference", error.getvalue())

    def test_release_command_reports_invalid_manifest_content_as_policy(self) -> None:
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
            "GITHUB_REF_NAME": "v1.2.3",
            "GITHUB_SHA": "commit",
        }
        for case, content, diagnostic in (
            ("malformed-json", "{\n", "valid JSON"),
            ("missing-version", "{}\n", "version"),
        ):
            with (
                self.subTest(case=case),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                root = Path(temporary_directory)
                manifest = root / ".claude-plugin" / "plugin.json"
                manifest.parent.mkdir()
                manifest.write_text(content, encoding="utf-8")
                responses = [
                    {"object": {"type": "tag", "sha": "tag-object"}},
                    {
                        "object": {"sha": "commit"},
                        "verification": {"verified": True},
                    },
                    {"protected": True},
                ]
                error = io.StringIO()

                with (
                    patch.dict(os.environ, environment, clear=False),
                    patch("scripts.ci_policy._run_json", side_effect=responses),
                    redirect_stderr(error),
                ):
                    result = ci_policy.main(["release", "--root", str(root)])

                self.assertEqual(1, result)
                self.assertIn(diagnostic, error.getvalue())
                self.assertNotIn("Traceback", error.getvalue())

    def test_release_command_reports_unreadable_manifest_as_operational(self) -> None:
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
        error = io.StringIO()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / ".claude-plugin" / "plugin.json").mkdir(parents=True)

            with (
                patch.dict(os.environ, environment, clear=False),
                patch("scripts.ci_policy._run_json", side_effect=responses),
                redirect_stderr(error),
            ):
                result = ci_policy.main(["release", "--root", str(root)])

        self.assertEqual(2, result)
        self.assertIn("error:", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())

    def test_pr_policy_command_reports_missing_environment(self) -> None:
        error = io.StringIO()
        with (
            patch.dict(
                os.environ, {"GITHUB_REPOSITORY": "owner/repository"}, clear=True
            ),
            redirect_stderr(error),
        ):
            result = ci_policy.main(["pr-policy"])

        self.assertEqual(2, result)
        self.assertIn(
            "missing required environment variable: PR_NUMBER", error.getvalue()
        )

    def test_pr_policy_command_reports_malformed_json(self) -> None:
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
            "PR_NUMBER": "9",
            "REPO_OWNER": "owner",
            "REPO_NAME": "repository",
            "PR_AUTHOR": "contributor",
        }
        error = io.StringIO()
        completed = subprocess.CompletedProcess(["gh"], 0, stdout="not json", stderr="")
        with (
            patch.dict(os.environ, environment, clear=False),
            patch("scripts.ci_policy.subprocess.run", return_value=completed),
            redirect_stderr(error),
        ):
            result = ci_policy.main(["pr-policy"])

        self.assertEqual(2, result)
        self.assertIn("error: command produced malformed JSON", error.getvalue())

    def test_uv_pins_command_detects_drift_in_yaml_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "ci").mkdir()
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (root / "ci" / "Containerfile").write_text(
                UvPinsPolicyTests.CONTAINER, encoding="utf-8"
            )
            (workflows / "required.yml").write_text(
                UvPinsPolicyTests.WORKFLOW, encoding="utf-8"
            )
            (workflows / "drift.yaml").write_text(
                UvPinsPolicyTests.WORKFLOW.replace("0.12.1", "0.10.8"),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SystemExit, r"drift\.yaml.*0\.10\.8.*0\.12\.1"):
                ci_policy.main(["uv-pins", "--root", str(root)])

    def test_plain_python_command_does_not_require_pyyaml(self) -> None:
        root = Path(__file__).parents[2]
        script = Path(ci_policy.__file__).resolve()
        program = f"""
import builtins
import runpy
import sys

real_import = builtins.__import__


def reject_yaml(name, *args, **kwargs):
    if name == "yaml":
        raise ModuleNotFoundError("No module named 'yaml'")
    return real_import(name, *args, **kwargs)


builtins.__import__ = reject_yaml
sys.argv = [{str(script)!r}, "suppressions", "--root", {str(root)!r}]
runpy.run_path({str(script)!r}, run_name="__main__")
"""

        result = subprocess.run(
            [sys.executable, "-I", "-c", program],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("no silent-failure suppressions", result.stdout)

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
                side_effect=[
                    {"body": "Closes #1\n", "closingIssuesReferences": [{"number": 1}]},
                    pages,
                ],
            ) as run_json,
        ):
            self.assertEqual(0, ci_policy.main(["pr-policy"]))

        self.assertEqual(2, run_json.call_count)
        self.assertIn("--paginate", run_json.call_args_list[1].args[0])

    def test_release_environment_command_requires_reviewers_and_tag_policies(
        self,
    ) -> None:
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
        }
        responses = [
            {
                "protection_rules": [
                    {
                        "type": "required_reviewers",
                        "reviewers": [{"id": 1, "login": "maintainer"}],
                    }
                ],
                "deployment_branch_policy": {"custom_branch_policies": True},
            },
            [
                {
                    "branch_policies": [
                        {"name": "v*", "type": "tag"},
                        {"name": "agent-contract-v*", "type": "tag"},
                    ]
                }
            ],
        ]
        with (
            patch.dict(os.environ, environment, clear=False),
            patch("scripts.ci_policy._run_json", side_effect=responses) as run_json,
        ):
            self.assertEqual(0, ci_policy.main(["release-environment"]))

        self.assertEqual(2, run_json.call_count)
        self.assertIn(
            "deployment-branch-policies",
            " ".join(run_json.call_args_list[1].args[0]),
        )

    def test_release_environment_command_rejects_missing_or_wrong_tag_policy(
        self,
    ) -> None:
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
        }
        environment_response = {
            "protection_rules": [
                {
                    "type": "required_reviewers",
                    "reviewers": [{"id": 1, "login": "maintainer"}],
                }
            ],
            "deployment_branch_policy": {"custom_branch_policies": True},
        }
        cases = (
            (
                "missing package policy",
                [{"name": "agent-contract-v*", "type": "tag"}],
                "`v*` tag policy",
            ),
            (
                "missing agent-contract policy",
                [{"name": "v*", "type": "tag"}],
                "`agent-contract-v*` tag policy",
            ),
            (
                "package policy has branch type",
                [
                    {"name": "v*", "type": "branch"},
                    {"name": "agent-contract-v*", "type": "tag"},
                ],
                "`v*` tag policy",
            ),
            (
                "agent-contract policy has branch type",
                [
                    {"name": "v*", "type": "tag"},
                    {"name": "agent-contract-v*", "type": "branch"},
                ],
                "`agent-contract-v*` tag policy",
            ),
        )
        for name, policies, expected_error in cases:
            with (
                self.subTest(name),
                patch.dict(os.environ, environment, clear=False),
                patch(
                    "scripts.ci_policy._run_json",
                    side_effect=[
                        environment_response,
                        [{"branch_policies": policies}],
                    ],
                ),
                self.assertRaisesRegex(SystemExit, re.escape(expected_error)),
            ):
                ci_policy.main(["release-environment"])

    def test_release_environment_command_rejects_unprotected_environment(self) -> None:
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
        }
        responses = [
            {
                "protection_rules": [
                    {"type": "required_reviewers", "reviewers": []},
                ],
                "deployment_branch_policy": {"custom_branch_policies": False},
            },
            [
                {
                    "branch_policies": [
                        {"name": "main"},
                    ]
                }
            ],
        ]
        with (
            patch.dict(os.environ, environment, clear=False),
            patch("scripts.ci_policy._run_json", side_effect=responses),
            self.assertRaises(SystemExit) as raised,
        ):
            ci_policy.main(["release-environment"])

        failure = str(raised.exception)
        self.assertIn("reviewer", failure)
        self.assertIn("v*", failure)

    def test_release_environment_command_reports_operational_failures(self) -> None:
        cases: tuple[tuple[str, dict[str, str], list[object] | None, str], ...] = (
            (
                "missing repository",
                {},
                None,
                "missing required environment variable: GITHUB_REPOSITORY",
            ),
            (
                "non-object response",
                {"GITHUB_REPOSITORY": "owner/repository"},
                [],
                "GitHub returned a release environment response that is invalid.",
            ),
        )
        for case, environment, response, diagnostic in cases:
            with self.subTest(case=case):
                error = io.StringIO()
                with (
                    patch.dict(os.environ, environment, clear=True),
                    patch("scripts.ci_policy._run_json", return_value=response),
                    redirect_stderr(error),
                ):
                    result = ci_policy.main(["release-environment"])

                self.assertEqual(2, result)
                self.assertIn(diagnostic, error.getvalue())
                self.assertNotIn("Traceback", error.getvalue())

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
            patch(
                "scripts.ci_policy._run_json",
                side_effect=[
                    {"body": "", "closingIssuesReferences": [{"number": 1}]},
                    pages,
                ],
            ),
            self.assertRaises(SystemExit) as raised,
        ):
            ci_policy.main(["pr-policy"])

        self.assertIsInstance(raised.exception.code, str)

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
            self.assertRaises(SystemExit) as raised,
        ):
            ci_policy.main(["required-jobs"])

        failure = str(raised.exception)
        self.assertIn("validate", failure)
        self.assertIn("failure", failure)

    def test_required_jobs_command_reports_missing_and_malformed_inputs(self) -> None:
        for case, environment in (
            ("missing-event-name", {"RESULTS": "{}"}),
            ("missing-results", {"EVENT_NAME": "push"}),
            ("invalid-json", {"EVENT_NAME": "push", "RESULTS": "not-json"}),
            ("non-object-json", {"EVENT_NAME": "push", "RESULTS": "[]"}),
        ):
            with (
                self.subTest(case=case),
                patch.dict(os.environ, environment, clear=True),
            ):
                self.assertEqual(2, ci_policy.main(["required-jobs"]))

    def test_required_jobs_command_rejects_invalid_job_results(self) -> None:
        for results in ('{"validate": []}', '{"validate": {"result": 1}}'):
            with self.subTest(results=results):
                environment = {"EVENT_NAME": "push", "RESULTS": results}

                with (
                    patch.dict(os.environ, environment, clear=True),
                    self.assertRaises(SystemExit) as raised,
                ):
                    ci_policy.main(["required-jobs"])

                diagnostic = str(raised.exception)
                payload = json.loads(diagnostic[diagnostic.index("{") :])
                self.assertEqual({"validate": "invalid"}, payload)

    def test_manifest_versions_reads_every_supported_host(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for directory in (".claude-plugin", ".codex-plugin"):
                path = root / directory
                path.mkdir()
                (path / "plugin.json").write_text(
                    '{"version": "1.2.3"}\n', encoding="utf-8"
                )
            (root / "package.json").write_text(
                '{"version": "1.2.3"}\n', encoding="utf-8"
            )
            npm = root / "npm" / "athena-opencode"
            npm.mkdir(parents=True)
            (npm / "package.json").write_text(
                '{"version": "1.2.3"}\n', encoding="utf-8"
            )

            versions = ci_policy._manifest_versions(root)

        self.assertEqual(
            {
                "claude": "1.2.3",
                "codex": "1.2.3",
                "pi": "1.2.3",
                "opencode": "1.2.3",
            },
            versions,
        )

    def test_release_command_validates_github_and_git_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for directory in (".claude-plugin", ".codex-plugin"):
                path = root / directory
                path.mkdir()
                (path / "plugin.json").write_text(
                    '{"version": "1.2.3"}\n', encoding="utf-8"
                )
            (root / "package.json").write_text(
                '{"version": "1.2.3"}\n', encoding="utf-8"
            )
            npm = root / "npm" / "athena-opencode"
            npm.mkdir(parents=True)
            (npm / "package.json").write_text(
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
            ["git", "merge-base", "--is-ancestor", "commit", "origin/main"],
            check=False,
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
            (root / "package.json").write_text(
                '{"version": "1.2.3"}\n', encoding="utf-8"
            )
            npm = root / "npm" / "athena-opencode"
            npm.mkdir(parents=True)
            (npm / "package.json").write_text(
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
                self.assertRaises(SystemExit) as raised,
            ):
                ci_policy.main(["release", "--root", str(root)])

            self.assertIsInstance(raised.exception.code, str)

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
            directory = Path(temporary_directory) / "repository" / "dist"
            directory.mkdir(parents=True)
            expected = create_release_assets(directory)
            release_notes = directory.parent / "docs" / "release-notes.md"
            release_notes.parent.mkdir()
            release_notes.write_text("Install from Git.\n", encoding="utf-8")
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
        self.assertIn("--notes-file", run.call_args.args[0])
        self.assertIn(str(release_notes.resolve()), run.call_args.args[0])

    def test_publish_release_command_rejects_missing_release_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory) / "repository" / "dist"
            directory.mkdir(parents=True)
            create_release_assets(directory)
            environment = {
                "GITHUB_REF_NAME": "v1.2.3",
                "GITHUB_REPOSITORY": "owner/repository",
            }
            with (
                patch.dict(os.environ, environment, clear=False),
                patch("scripts.ci_policy.subprocess.run") as run,
                self.assertRaisesRegex(ValueError, "release notes are missing"),
            ):
                ci_policy._publish_release_command(directory)

        run.assert_not_called()

    def test_pr_policy_command_rejects_malformed_closing_issues_references(
        self,
    ) -> None:
        environment = {
            "GITHUB_REPOSITORY": "owner/repository",
            "PR_NUMBER": "9",
            "REPO_OWNER": "owner",
            "REPO_NAME": "repository",
            "PR_AUTHOR": "contributor",
        }
        with (
            patch.dict(os.environ, environment, clear=False),
            patch(
                "scripts.ci_policy._run_json",
                return_value={"body": "Closes #1\n"},
            ) as run_json,
            self.assertRaisesRegex(
                ValueError,
                "GitHub returned a closingIssuesReferences field that is not valid.",
            ),
        ):
            ci_policy._pr_policy_command()

        run_json.assert_called_once()


if __name__ == "__main__":
    unittest.main()
