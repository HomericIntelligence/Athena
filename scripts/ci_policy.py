#!/usr/bin/env python3
"""Apply the Athena continuous integration (CI) and release policies."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.policies.pull_request import evaluate_pull_request, flatten_commit_pages
from scripts.policies.release import evaluate_release, verify_release_assets
from scripts.policies.required_jobs import failed_required_jobs
from scripts.policies.suppressions import find_suppressions
from skills._cli import argument_parser

__all__ = (
    "evaluate_pull_request",
    "evaluate_release",
    "failed_required_jobs",
    "find_suppressions",
    "flatten_commit_pages",
    "verify_release_assets",
)


def _run_json(command: list[str]) -> Any:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def _pr_policy_command() -> int:
    repository = os.environ["GITHUB_REPOSITORY"]
    pr_number = os.environ["PR_NUMBER"]
    owner = os.environ["REPO_OWNER"]
    name = os.environ["REPO_NAME"]
    author = os.environ["PR_AUTHOR"]
    pr = _run_json(
        [
            "gh",
            "pr",
            "view",
            pr_number,
            "--repo",
            repository,
            "--json",
            "body,closingIssuesReferences",
        ]
    )
    closing_issues = pr.get("closingIssuesReferences")
    if not isinstance(closing_issues, list):
        raise TypeError(
            "GitHub returned a closingIssuesReferences field that is not valid."
        )
    query = """query($owner:String!,$name:String!,$pr:Int!,$endCursor:String) {
      repository(owner:$owner,name:$name) { pullRequest(number:$pr) {
        commits(first:100,after:$endCursor) {
          totalCount nodes { commit { oid message signature { isValid } } }
          pageInfo { hasNextPage endCursor }
        }
      } }
    }"""
    pages = _run_json(
        [
            "gh",
            "api",
            "graphql",
            "--paginate",
            "--slurp",
            "-f",
            f"query={query}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"pr={pr_number}",
        ]
    )
    errors = evaluate_pull_request(
        body=str(pr.get("body") or ""),
        author=author,
        commits=flatten_commit_pages(pages),
        require_issue_link=bool(closing_issues),
    )
    if errors:
        raise SystemExit("\n".join(errors))
    print("The pull-request policy passed.")
    return 0


def _required_jobs_command() -> int:
    event_name = os.environ.get("EVENT_NAME")
    results_text = os.environ.get("RESULTS")
    if event_name is None:
        raise SystemExit("The required environment variable EVENT_NAME is missing.")
    if results_text is None:
        raise SystemExit("The required environment variable RESULTS is missing.")
    try:
        results = json.loads(results_text)
    except json.JSONDecodeError as error:
        raise SystemExit(
            "The RESULTS value must contain valid JSON. "
            f"The parser returned this diagnostic.\n{error}"
        ) from error
    if not isinstance(results, dict):
        raise SystemExit("The RESULTS value must be a JSON object.")
    failures = failed_required_jobs(event_name, results)
    if failures:
        raise SystemExit(
            "The required jobs did not pass.\n" + json.dumps(failures, sort_keys=True)
        )
    print(
        "All required job results are acceptable. The workflow skips the "
        "pull-request policy only when that policy does not apply."
    )
    return 0


def _manifest_versions(repo_root: Path) -> dict[str, str]:
    paths = {
        "claude": repo_root / ".claude-plugin" / "plugin.json",
        "codex": repo_root / ".codex-plugin" / "plugin.json",
        "pi": repo_root / "package.json",
        "opencode": repo_root / "npm" / "athena-opencode" / "package.json",
    }
    return {
        name: str(json.loads(path.read_text(encoding="utf-8"))["version"])
        for name, path in paths.items()
    }


def _release_command(repo_root: Path) -> int:
    repository = os.environ["GITHUB_REPOSITORY"]
    tag = os.environ["GITHUB_REF_NAME"]
    workflow_sha = os.environ["GITHUB_SHA"]
    tag_ref = _run_json(["gh", "api", f"repos/{repository}/git/ref/tags/{tag}"])
    annotated = tag_ref.get("object", {}).get("type") == "tag"
    if not annotated:
        tag_object: dict[str, Any] = {}
    else:
        tag_sha = tag_ref["object"]["sha"]
        tag_object = _run_json(["gh", "api", f"repos/{repository}/git/tags/{tag_sha}"])
    branch = _run_json(["gh", "api", f"repos/{repository}/branches/main"])
    tag_commit = str(tag_object.get("object", {}).get("sha", ""))
    errors = evaluate_release(
        tag=tag,
        workflow_sha=workflow_sha,
        tag_commit=tag_commit,
        annotated=annotated,
        signature_verified=bool(tag_object.get("verification", {}).get("verified")),
        main_protected=bool(branch.get("protected")),
        manifest_versions=_manifest_versions(repo_root),
    )
    if (
        not errors
        and subprocess.run(
            ["git", "merge-base", "--is-ancestor", tag_commit, "origin/main"],
            check=False,
        ).returncode
        != 0
    ):
        errors.append("The release tag target must be reachable from protected main.")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"The release policy passed for tag '{tag}' at commit '{tag_commit}'.")
    return 0


def _release_environment_command() -> int:
    repository = os.environ["GITHUB_REPOSITORY"]
    environment = _run_json(["gh", "api", f"repos/{repository}/environments/release"])
    protection_rules = environment.get("protection_rules")
    if not isinstance(protection_rules, list):
        raise TypeError(
            "GitHub returned a release environment protection rule list that is invalid."
        )
    errors: list[str] = []
    required_reviewers = [
        rule
        for rule in protection_rules
        if isinstance(rule, dict)
        and rule.get("type") == "required_reviewers"
        and isinstance(rule.get("reviewers"), list)
        and rule["reviewers"]
    ]
    if not required_reviewers:
        errors.append("The release environment must require at least one reviewer.")
    deployment_branch_policy = environment.get("deployment_branch_policy")
    if not isinstance(
        deployment_branch_policy, dict
    ) or not deployment_branch_policy.get("custom_branch_policies"):
        errors.append(
            "The release environment must use custom deployment branch policies."
        )
    branch_policy_pages = _run_json(
        [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            f"repos/{repository}/environments/release/deployment-branch-policies",
        ]
    )
    if not isinstance(branch_policy_pages, list):
        raise TypeError("GitHub returned a release branch policy list that is invalid.")
    branch_policy_names: list[str] = []
    for page in branch_policy_pages:
        if not isinstance(page, dict):
            raise TypeError(
                "GitHub returned a release branch policy page that is invalid."
            )
        branch_policies = page.get("branch_policies")
        if not isinstance(branch_policies, list):
            raise TypeError(
                "GitHub returned a release branch policy list that is invalid."
            )
        branch_policy_names.extend(
            str(policy["name"])
            for policy in branch_policies
            if isinstance(policy, dict) and isinstance(policy.get("name"), str)
        )
    if "v*" not in branch_policy_names:
        errors.append("The release environment must allow the `v*` tag policy.")
    if errors:
        raise SystemExit("\n".join(errors))
    print("The release environment configuration passed.")
    return 0


def _suppression_command(repo_root: Path) -> int:
    result = subprocess.run(
        ["git", "ls-files", "*.sh", "*.yml", "*.yaml", "justfile"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    files = {
        relative: (repo_root / relative).read_text(encoding="utf-8")
        for relative in result.stdout.splitlines()
    }
    findings = find_suppressions(files)
    if findings:
        raise SystemExit("\n".join(findings))
    print("The check found no silent-failure suppressions.")
    return 0


def _publish_release_command(directory: Path) -> int:
    asset_names = verify_release_assets(directory)
    release_notes = directory.parent / "docs" / "release-notes.md"
    if not release_notes.is_file():
        raise ValueError(f"The release notes are missing: '{release_notes}'.")
    subprocess.run(
        [
            "gh",
            "release",
            "create",
            os.environ["GITHUB_REF_NAME"],
            *(str(directory / name) for name in asset_names),
            "--generate-notes",
            "--notes-file",
            str(release_notes),
            "--verify-tag",
            "--repo",
            os.environ["GITHUB_REPOSITORY"],
        ],
        check=True,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "pr-policy",
            "publish-release",
            "required-jobs",
            "release",
            "release-environment",
            "suppressions",
        ),
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    if args.command == "pr-policy":
        return _pr_policy_command()
    if args.command == "required-jobs":
        return _required_jobs_command()
    if args.command == "release":
        return _release_command(args.root.resolve())
    if args.command == "release-environment":
        return _release_environment_command()
    if args.command == "publish-release":
        return _publish_release_command(args.root.resolve())
    return _suppression_command(args.root.resolve())


if __name__ == "__main__":
    sys.exit(main())
