"""Behavior tests for immutable PR-review evidence binding."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "pr-review" / "scripts" / "collect_evidence.py"
DIFF_CONTEXT_SCRIPT = ROOT / "skills" / "pr-review" / "scripts" / "diff_context.py"
BASE_OID = "a" * 40
HEAD_OID = "b" * 40


def pull_request(
    *,
    state: str = "OPEN",
    base_oid: str = BASE_OID,
    head_oid: str = HEAD_OID,
    base_ref_name: str = "main",
    head_ref_name: str = "feature",
    title: str = "Immutable evidence",
    body: str | None = "",
    is_draft: bool = False,
    closing_issues: list[dict[str, object]] | None = None,
    url: str = "https://github.com/owner/repository/pull/9",
) -> dict[str, object]:
    """Create the minimum complete GitHub pull-request evidence object."""
    return {
        "number": 9,
        "title": title,
        "body": body,
        "state": state,
        "isDraft": is_draft,
        "author": {"login": "reviewer"},
        "baseRefName": base_ref_name,
        "headRefName": head_ref_name,
        "baseRefOid": base_oid,
        "headRefOid": head_oid,
        "statusCheckRollup": [],
        "closingIssuesReferences": closing_issues or [],
        "url": url,
    }


def git(repository: Path, *arguments: str) -> str:
    """Run a deterministic Git setup command for a temporary repository."""
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def initialize_repository(repository: Path, changed_path: str) -> tuple[str, str]:
    """Create a base/head pair with exactly one changed path."""
    git(repository, "init", "--quiet")
    git(repository, "config", "user.name", "Athena Tests")
    git(repository, "config", "user.email", "athena-tests@example.invalid")
    (repository / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(repository, "add", "tracked.txt")
    git(repository, "commit", "--quiet", "-m", "test: base")
    base_oid = git(repository, "rev-parse", "HEAD")
    (repository / changed_path).write_text("changed\n", encoding="utf-8")
    git(repository, "add", "--all")
    git(repository, "commit", "--quiet", "-m", "test: changed path")
    return base_oid, git(repository, "rev-parse", "HEAD")


def initialize_divergent_repository(
    repository: Path, changed_path: str
) -> tuple[str, str]:
    """Create equal base/head trees with a path changed in author intent only."""
    git(repository, "init", "--quiet")
    git(repository, "config", "user.name", "Athena Tests")
    git(repository, "config", "user.email", "athena-tests@example.invalid")
    (repository / changed_path).write_text("base\n", encoding="utf-8")
    git(repository, "add", changed_path)
    git(repository, "commit", "--quiet", "-m", "test: merge base")
    merge_base = git(repository, "rev-parse", "HEAD")
    git(repository, "branch", "-M", "main")
    git(repository, "checkout", "--quiet", "-b", "feature")
    (repository / changed_path).write_text("changed\n", encoding="utf-8")
    git(repository, "commit", "--all", "--quiet", "-m", "test: feature change")
    head_oid = git(repository, "rev-parse", "HEAD")
    git(repository, "checkout", "--quiet", "main")
    (repository / changed_path).write_text("changed\n", encoding="utf-8")
    git(repository, "commit", "--all", "--quiet", "-m", "test: target change")
    base_oid = git(repository, "rev-parse", "HEAD")
    if git(repository, "merge-base", base_oid, head_oid) != merge_base:
        raise AssertionError("divergent test repository lost its merge base")
    return base_oid, head_oid


def initialize_shallow_repository(
    repository: Path, changed_path: str
) -> tuple[str, str]:
    """Create a shallow clone that still contains the requested base and head."""
    with tempfile.TemporaryDirectory() as source_directory:
        source = Path(source_directory)
        initialize_repository(source, changed_path)
        result = subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--no-local",
                "--depth",
                "2",
                str(source),
                str(repository),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
    return git(repository, "rev-parse", "HEAD~1"), git(repository, "rev-parse", "HEAD")


def initialize_ambiguous_merge_base_repository(
    repository: Path, changed_path: str
) -> tuple[str, str]:
    """Create a criss-cross DAG with two equally valid merge bases."""
    git(repository, "init", "--quiet")
    git(repository, "config", "user.name", "Athena Tests")
    git(repository, "config", "user.email", "athena-tests@example.invalid")
    (repository / changed_path).write_text("initial\n", encoding="utf-8")
    git(repository, "add", changed_path)
    git(repository, "commit", "--quiet", "-m", "test: common ancestor")
    common = git(repository, "rev-parse", "HEAD")
    git(repository, "checkout", "--quiet", "-b", "feature")
    (repository / changed_path).write_text("feature\n", encoding="utf-8")
    git(repository, "commit", "--all", "--quiet", "-m", "test: feature parent")
    feature_parent = git(repository, "rev-parse", "HEAD")
    feature_tree = git(repository, "rev-parse", f"{feature_parent}^{{tree}}")
    git(repository, "checkout", "--quiet", "--detach", common)
    (repository / changed_path).write_text("target\n", encoding="utf-8")
    git(repository, "commit", "--all", "--quiet", "-m", "test: target parent")
    target_parent = git(repository, "rev-parse", "HEAD")
    target_tree = git(repository, "rev-parse", f"{target_parent}^{{tree}}")
    head_oid = git(
        repository,
        "commit-tree",
        feature_tree,
        "-p",
        feature_parent,
        "-p",
        target_parent,
        "-m",
        "test: feature merge",
    )
    base_oid = git(
        repository,
        "commit-tree",
        target_tree,
        "-p",
        target_parent,
        "-p",
        feature_parent,
        "-m",
        "test: target merge",
    )
    if set(git(repository, "merge-base", "--all", base_oid, head_oid).splitlines()) != {
        feature_parent,
        target_parent,
    }:
        raise AssertionError("test repository did not create two merge bases")
    return base_oid, head_oid


def bind_repository_identity(
    metadata_sequence: list[dict[str, object]], base_oid: str, head_oid: str
) -> list[dict[str, object]]:
    """Replace test identity sentinels with the temporary repository OIDs."""
    bound: list[dict[str, object]] = []
    for metadata in metadata_sequence:
        copy = metadata.copy()
        if copy.get("baseRefOid") == BASE_OID:
            copy["baseRefOid"] = base_oid
        if copy.get("headRefOid") == HEAD_OID:
            copy["headRefOid"] = head_oid
        bound.append(copy)
    return bound


FAKE_GH = """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

arguments = sys.argv[1:]


def option_value(name):
    for index, argument in enumerate(arguments[:-1]):
        if argument == name:
            return arguments[index + 1]
    return None


if arguments[:2] == ["pr", "view"]:
    if (
        os.environ.get("ATHENA_TEST_FORBID_AMBIENT_TARGET") == "1"
        and option_value("--repo") != "github.com/owner/repository"
    ):
        print("strict review must use the retained GitHub target", file=sys.stderr)
        raise SystemExit(9)
    state_path = Path(os.environ["ATHENA_TEST_GH_STATE"])
    count = int(state_path.read_text(encoding="utf-8")) if state_path.exists() else 0
    state_path.write_text(str(count + 1), encoding="utf-8")
    sequence = json.loads(os.environ["ATHENA_TEST_GH_PR_SEQUENCE"])
    print(json.dumps(sequence[min(count, len(sequence) - 1)]))
elif arguments[:2] == ["repo", "view"]:
    if os.environ.get("ATHENA_TEST_FORBID_AMBIENT_TARGET") == "1":
        print("strict review must not query an ambient repository", file=sys.stderr)
        raise SystemExit(10)
    print(json.dumps({"nameWithOwner": "owner/repository"}))
elif arguments[:2] == ["issue", "view"]:
    if (
        os.environ.get("ATHENA_TEST_FORBID_AMBIENT_TARGET") == "1"
        and option_value("--repo") != "github.com/owner/requirements"
    ):
        print("linked issue reads must use the canonical GitHub target", file=sys.stderr)
        raise SystemExit(11)
    state_path = Path(os.environ["ATHENA_TEST_GH_ISSUE_STATE"])
    count = int(state_path.read_text(encoding="utf-8")) if state_path.exists() else 0
    state_path.write_text(str(count + 1), encoding="utf-8")
    sequence = json.loads(os.environ["ATHENA_TEST_GH_ISSUE_SEQUENCE"])
    print(json.dumps(sequence[min(count, len(sequence) - 1)]))
elif arguments[:1] == ["api"]:
    if any("/issues/" in argument and argument.endswith("/comments") for argument in arguments):
        if ["--hostname", "github.com"] not in [arguments[index:index + 2] for index in range(len(arguments) - 1)]:
            print("linked issue comments must use the canonical GitHub host", file=sys.stderr)
            raise SystemExit(8)
        state_path = os.environ.get("ATHENA_TEST_GH_COMMENT_STATE")
        sequence_raw = os.environ.get("ATHENA_TEST_GH_COMMENT_SEQUENCE")
        if state_path is None or sequence_raw is None:
            print("[]")
        else:
            path = Path(state_path)
            count = int(path.read_text(encoding="utf-8")) if path.exists() else 0
            path.write_text(str(count + 1), encoding="utf-8")
            sequence = json.loads(sequence_raw)
            print(json.dumps([sequence[min(count, len(sequence) - 1)]]))
    elif os.environ.get("ATHENA_TEST_FORBID_GH_API") == "1":
        print("strict review must not query the provider file list", file=sys.stderr)
        raise SystemExit(7)
elif arguments[:2] == ["pr", "checks"]:
    print("[]")
else:
    print(f"unexpected gh invocation: {arguments}", file=sys.stderr)
    raise SystemExit(2)
"""


class ImmutableEvidenceTests(unittest.TestCase):
    def run_collector(
        self,
        metadata_sequence: list[dict[str, object]],
        *,
        changed_path: str = "changed.txt",
        repository_initializer: Callable[[Path, str], tuple[str, str]] = (
            initialize_repository
        ),
        replace_head_with_base: bool = False,
        linked_issue_sequence: list[dict[str, object]] | None = None,
        linked_comment_sequence: list[list[dict[str, object]]] | None = None,
        expected_target: bool = True,
        hostile_target_environment: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], int, str, str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            base_oid, head_oid = repository_initializer(root, changed_path)
            if replace_head_with_base:
                git(root, "replace", head_oid, base_oid)
            bin_directory = root / "bin"
            bin_directory.mkdir()
            gh_path = bin_directory / "gh"
            gh_path.write_text(FAKE_GH, encoding="utf-8")
            gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)
            environment = os.environ.copy()
            environment["PATH"] = f"{bin_directory}{os.pathsep}{environment['PATH']}"
            state_path = root / "gh-state"
            environment["ATHENA_TEST_GH_STATE"] = str(state_path)
            environment["ATHENA_TEST_GH_PR_SEQUENCE"] = json.dumps(
                bind_repository_identity(metadata_sequence, base_oid, head_oid)
            )
            if linked_issue_sequence is not None:
                issue_state_path = root / "gh-issue-state"
                environment["ATHENA_TEST_GH_ISSUE_STATE"] = str(issue_state_path)
                environment["ATHENA_TEST_GH_ISSUE_SEQUENCE"] = json.dumps(
                    linked_issue_sequence
                )
            if linked_comment_sequence is not None:
                comment_state_path = root / "gh-comment-state"
                environment["ATHENA_TEST_GH_COMMENT_STATE"] = str(comment_state_path)
                environment["ATHENA_TEST_GH_COMMENT_SEQUENCE"] = json.dumps(
                    linked_comment_sequence
                )
            environment["ATHENA_TEST_FORBID_GH_API"] = "1"
            if hostile_target_environment:
                environment["GH_HOST"] = "attacker.invalid"
                environment["GH_REPO"] = "attacker/repository"
                environment["ATHENA_TEST_FORBID_AMBIENT_TARGET"] = "1"
            expected_arguments = [
                "--expected-base-oid",
                base_oid,
                "--expected-head-oid",
                head_oid,
            ]
            if expected_target:
                expected_arguments.extend(
                    (
                        "--expected-host",
                        "github.com",
                        "--expected-repository",
                        "owner/repository",
                        "--expected-pr-number",
                        "9",
                        "--expected-pr-url",
                        "https://github.com/owner/repository/pull/9",
                    )
                )
            command = [
                sys.executable,
                str(SCRIPT),
                *expected_arguments,
                "9",
            ]
            if os.environ.get("ATHENA_COVERAGE") == "1":
                command = [
                    sys.executable,
                    "-m",
                    "coverage",
                    "run",
                    "--branch",
                    "--parallel-mode",
                    str(SCRIPT),
                    *expected_arguments,
                    "9",
                ]
                environment["COVERAGE_FILE"] = str(ROOT / ".coverage")
            result = subprocess.run(
                command,
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            call_count = (
                int(state_path.read_text(encoding="utf-8"))
                if state_path.exists()
                else 0
            )
            return result, call_count, base_oid, head_oid

    def test_emits_stably_revalidated_immutable_identity(self) -> None:
        result, call_count, base_oid, head_oid = self.run_collector(
            [pull_request(), pull_request()]
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, call_count)
        evidence = json.loads(result.stdout)
        identity = evidence["reviewed_identity"]
        self.assertEqual("github.com", identity["forge_host"])
        self.assertEqual(base_oid, identity["base_oid"])
        self.assertEqual(head_oid, identity["head_oid"])
        self.assertEqual(["changed.txt"], evidence["changed_files"])
        self.assertEqual(
            "Immutable evidence", evidence["reviewed_scope"]["fields"]["title"]
        )
        self.assertEqual("main", evidence["reviewed_scope"]["fields"]["baseRefName"])
        self.assertEqual("feature", evidence["reviewed_scope"]["fields"]["headRefName"])
        self.assertEqual(0, evidence["reviewed_linked_requirements"]["count"])
        self.assertEqual("coverage_gap", evidence["check_evidence"]["status"])

    def test_requires_an_explicit_review_target_for_strict_evidence(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request()], expected_target=False
        )

        self.assertEqual(2, result.returncode)
        self.assertEqual(0, call_count)

    def test_uses_the_retained_target_despite_hostile_gh_environment(self) -> None:
        reference = {
            "id": "I_1",
            "number": 10,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/10",
        }
        requirement = {
            "id": "I_1",
            "number": 10,
            "url": "https://github.com/owner/requirements/issues/10",
            "title": "Requirements",
            "body": "Acceptance criterion",
            "state": "OPEN",
        }
        result, call_count, _, _ = self.run_collector(
            [
                pull_request(closing_issues=[reference]),
                pull_request(closing_issues=[reference]),
            ],
            linked_issue_sequence=[requirement, requirement],
            linked_comment_sequence=[[], []],
            expected_target=True,
            hostile_target_environment=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, call_count)

    def test_rejects_a_noncanonical_provider_url_in_strict_mode(self) -> None:
        noncanonical = "https://github.com/owner/repository/pull/9?source=attacker"
        result, call_count, _, _ = self.run_collector([pull_request(url=noncanonical)])

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_missing_immutable_identity(self) -> None:
        metadata = pull_request()
        metadata.pop("headRefOid")

        result, call_count, _, _ = self.run_collector([metadata])

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_non_open_pull_request(self) -> None:
        result, call_count, _, _ = self.run_collector([pull_request(state="CLOSED")])

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_missing_open_state(self) -> None:
        metadata = pull_request()
        metadata.pop("state")

        result, call_count, _, _ = self.run_collector([metadata])

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_missing_review_scope_fields(self) -> None:
        for field in ("body", "isDraft", "closingIssuesReferences"):
            with self.subTest(field=field):
                metadata = pull_request()
                metadata.pop(field)

                result, call_count, _, _ = self.run_collector([metadata])

                self.assertEqual(1, result.returncode)
                self.assertEqual(1, call_count)

    def test_rejects_identity_that_differs_from_resolved_revisions(self) -> None:
        result, call_count, _, _ = self.run_collector([pull_request(head_oid="c" * 40)])

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_identity_that_changes_while_collecting_evidence(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request(head_oid="c" * 40)]
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)

    def test_rejects_scope_that_changes_while_collecting_evidence(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request(title="Changed review scope")]
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)

    def test_rejects_branch_scope_that_changes_while_collecting_evidence(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request(base_ref_name="release")]
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)

    def test_rejects_source_branch_scope_that_changes_while_collecting_evidence(
        self,
    ) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request(head_ref_name="renamed-feature")]
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)

    def test_rejects_linked_requirement_content_that_changes_while_collecting(
        self,
    ) -> None:
        reference = {
            "id": "I_1",
            "number": 10,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/10",
        }
        initial_requirement = {
            "id": "I_1",
            "number": 10,
            "url": "https://github.com/owner/requirements/issues/10",
            "title": "Requirements",
            "body": "Initial acceptance criterion",
            "state": "OPEN",
            "comments": [],
        }
        changed_requirement = initial_requirement | {
            "body": "Changed acceptance criterion"
        }

        result, call_count, _, _ = self.run_collector(
            [
                pull_request(closing_issues=[reference]),
                pull_request(closing_issues=[reference]),
            ],
            linked_issue_sequence=[initial_requirement, changed_requirement],
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)

    def test_rejects_an_incomplete_linked_issue_reference(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request(closing_issues=[{"number": 10}])]
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_a_noncanonical_linked_issue_url(self) -> None:
        reference = {
            "id": "I_1",
            "number": 10,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/10?source=attacker",
        }
        result, call_count, _, _ = self.run_collector(
            [pull_request(closing_issues=[reference])]
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_a_boolean_linked_issue_number(self) -> None:
        reference = {
            "id": "I_1",
            "number": True,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/True",
        }
        requirement = {
            "id": "I_1",
            "number": True,
            "url": "https://github.com/owner/requirements/issues/True",
            "title": "Requirements",
            "body": "Acceptance criterion",
            "state": "OPEN",
        }
        result, call_count, _, _ = self.run_collector(
            [
                pull_request(closing_issues=[reference]),
                pull_request(closing_issues=[reference]),
            ],
            linked_issue_sequence=[requirement, requirement],
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_a_linked_issue_response_with_a_different_id(self) -> None:
        reference = {
            "id": "I_linked",
            "number": 10,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/10",
        }
        mismatched_requirement = {
            "id": "I_different",
            "number": 10,
            "url": "https://github.com/owner/requirements/issues/10",
            "title": "Requirements",
            "body": "Acceptance criterion",
            "state": "OPEN",
        }
        result, call_count, _, _ = self.run_collector(
            [pull_request(closing_issues=[reference])],
            linked_issue_sequence=[mismatched_requirement],
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_emits_a_stable_linked_requirements_binding(self) -> None:
        reference = {
            "id": "I_1",
            "number": 10,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/10",
        }
        requirement = {
            "id": "I_1",
            "number": 10,
            "url": "https://github.com/owner/requirements/issues/10",
            "title": "Requirements",
            "body": "Acceptance criterion",
            "state": "OPEN",
        }
        comments = [{"id": 1, "body": "Canonical plan"}]

        result, call_count, _, _ = self.run_collector(
            [
                pull_request(closing_issues=[reference]),
                pull_request(closing_issues=[reference]),
            ],
            linked_issue_sequence=[requirement, requirement],
            linked_comment_sequence=[comments, comments],
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, call_count)
        binding = json.loads(result.stdout)["reviewed_linked_requirements"]
        self.assertEqual(1, binding["count"])
        self.assertRegex(binding["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            {
                "content_sha256": binding["items"][0]["content_sha256"],
                "id": "I_1",
                "number": 10,
                "repository": "owner/requirements",
                "url": "https://github.com/owner/requirements/issues/10",
            },
            binding["items"][0],
        )
        self.assertRegex(binding["items"][0]["content_sha256"], r"^[0-9a-f]{64}$")

    def test_rejects_linked_requirement_comments_that_change_while_collecting(
        self,
    ) -> None:
        reference = {
            "id": "I_1",
            "number": 10,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/10",
        }
        requirement = {
            "id": "I_1",
            "number": 10,
            "url": "https://github.com/owner/requirements/issues/10",
            "title": "Requirements",
            "body": "Acceptance criterion",
            "state": "OPEN",
        }

        result, call_count, _, _ = self.run_collector(
            [
                pull_request(closing_issues=[reference]),
                pull_request(closing_issues=[reference]),
            ],
            linked_issue_sequence=[requirement, requirement],
            linked_comment_sequence=[[], [{"id": 1, "body": "Changed plan"}]],
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)

    def test_emits_final_revalidated_metadata(self) -> None:
        initial = pull_request()
        initial["reviews"] = [{"id": "initial"}]
        final = pull_request()
        final["reviews"] = [{"id": "final"}]

        result, _, _, _ = self.run_collector([initial, final])

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            [{"id": "final"}], json.loads(result.stdout)["pull_request"]["reviews"]
        )

    def test_immutable_changed_paths_ignore_replacement_refs(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request()],
            changed_path="replacement.txt",
            replace_head_with_base=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, call_count)
        self.assertEqual(
            ["replacement.txt"], json.loads(result.stdout)["changed_files"]
        )

    def test_binds_the_union_of_author_intent_and_current_target_paths(self) -> None:
        """A target-equivalent tree must not hide a feature's changed path."""
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request()],
            repository_initializer=initialize_divergent_repository,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, call_count)
        self.assertEqual(["changed.txt"], json.loads(result.stdout)["changed_files"])

    def test_rejects_shallow_history_before_binding_changed_paths(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request()],
            repository_initializer=initialize_shallow_repository,
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)
        self.assertIn("non-shallow", result.stderr)

    def test_rejects_an_ambiguous_merge_base_before_binding_paths(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request()],
            repository_initializer=initialize_ambiguous_merge_base_repository,
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)
        self.assertIn("unambiguous merge base", result.stderr)

    def test_diff_context_rejects_an_ambiguous_merge_base(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            base_oid, head_oid = initialize_ambiguous_merge_base_repository(
                repository, "changed.txt"
            )
            result = subprocess.run(
                [sys.executable, str(DIFF_CONTEXT_SCRIPT), base_oid, head_oid],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("unambiguous merge base", result.stderr)

    def test_binds_a_newline_path_without_querying_provider_file_metadata(self) -> None:
        path = "line\nbreak.py"
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request()], changed_path=path
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, call_count)
        evidence = json.loads(result.stdout)
        self.assertEqual([path], evidence["changed_files"])
        self.assertEqual(
            sha256(path.encode("utf-8") + b"\0").hexdigest(),
            evidence["changed_path_manifest"]["sha256"],
        )


if __name__ == "__main__":
    unittest.main()
