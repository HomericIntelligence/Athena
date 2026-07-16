#!/usr/bin/env python3
"""Executable CI and release policies for Athena."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.policies.pull_request import (  # noqa: E402
    evaluate_pull_request as evaluate_pull_request,
    flatten_commit_pages as flatten_commit_pages,
)
from scripts.policies.release import (  # noqa: E402
    evaluate_release as evaluate_release,
    verify_release_assets as verify_release_assets,
)
from scripts.policies.required_jobs import (  # noqa: E402
    failed_required_jobs as failed_required_jobs,
)
from scripts.policies.suppressions import (  # noqa: E402
    find_suppressions as find_suppressions,
)
from skills._cli import argument_parser  # noqa: E402


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
        ["gh", "pr", "view", pr_number, "--repo", repository, "--json", "body"]
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
    )
    if errors:
        raise SystemExit("\n".join(errors))
    print("PR policy passed")
    return 0


def _required_jobs_command() -> int:
    event_name = os.environ.get("EVENT_NAME")
    results_text = os.environ.get("RESULTS")
    if event_name is None:
        raise SystemExit("missing required environment variable: EVENT_NAME")
    if results_text is None:
        raise SystemExit("missing required environment variable: RESULTS")
    try:
        results = json.loads(results_text)
    except json.JSONDecodeError as error:
        raise SystemExit(f"RESULTS must contain valid JSON: {error}") from error
    if not isinstance(results, dict):
        raise SystemExit("RESULTS must be a JSON object")
    failures = failed_required_jobs(event_name, results)
    if failures:
        raise SystemExit(
            f"Required jobs not green: {json.dumps(failures, sort_keys=True)}"
        )
    print("All required jobs are green; PR policy was skipped only if inapplicable.")
    return 0


def _manifest_versions(repo_root: Path) -> dict[str, str]:
    paths = {
        "claude": repo_root / ".claude-plugin" / "plugin.json",
        "codex": repo_root / ".codex-plugin" / "plugin.json",
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
            ["git", "merge-base", "--is-ancestor", tag_commit, "origin/main"]
        ).returncode
        != 0
    ):
        errors.append("release tag target must be reachable from protected main")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Release policy passed for {tag} at {tag_commit}")
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
    print("No silent-failure suppressions found.")
    return 0


def _publish_release_command(directory: Path) -> int:
    asset_names = verify_release_assets(directory)
    release_notes = directory.parent / "docs" / "release-notes.md"
    if not release_notes.is_file():
        raise ValueError(f"release notes are missing: {release_notes}")
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
    if args.command == "publish-release":
        return _publish_release_command(args.root.resolve())
    return _suppression_command(args.root.resolve())


if __name__ == "__main__":
    sys.exit(main())
