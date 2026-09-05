#!/usr/bin/env python3
"""Apply Athena continuous integration (CI) and release policies.

Exit codes:
    0: The policy check passed.
    1: A policy violation was found.
    2: The tool could not complete the check.
"""

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
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or "no diagnostic was returned"
        raise OSError(
            f"command failed (exit {result.returncode}): {' '.join(command)}: {detail}"
        )
    try:
        return json.loads(result.stdout)
    except ValueError as error:
        raise ValueError(f"command produced malformed JSON: {error}") from error


def _required_env(name: str) -> str:
    """Return a required environment value or raise an actionable error."""
    value = os.environ.get(name)
    if value is None:
        raise OSError(f"missing required environment variable: {name}")
    return value


def _pr_policy_command() -> int:
    repository = _required_env("GITHUB_REPOSITORY")
    pr_number = _required_env("PR_NUMBER")
    owner = _required_env("REPO_OWNER")
    name = _required_env("REPO_NAME")
    author = _required_env("PR_AUTHOR")
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
    if not isinstance(pr, dict):
        raise ValueError(  # noqa: TRY004 - malformed provider input is operational
            "GitHub returned a pull-request response that is not an object."
        )
    closing_issues = pr.get("closingIssuesReferences")
    if not isinstance(closing_issues, list):
        raise ValueError(  # noqa: TRY004 - malformed provider input is operational
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
        raise ValueError("The required environment variable EVENT_NAME is missing.")
    if results_text is None:
        raise ValueError("The required environment variable RESULTS is missing.")
    try:
        results = json.loads(results_text)
    except ValueError as error:
        raise ValueError(
            "The RESULTS value must contain valid JSON. "
            f"The parser returned this diagnostic.\n{error}"
        ) from error
    if not isinstance(results, dict):
        raise ValueError("The RESULTS value must be a JSON object.")  # noqa: TRY004
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
    versions: dict[str, str] = {}
    for name, path in paths.items():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        try:
            versions[name] = str(manifest["version"])
        except KeyError as error:
            relative_path = path.relative_to(repo_root)
            raise ValueError(
                f"The manifest does not have the required 'version' field: "
                f"'{relative_path}'."
            ) from error
    return versions


def _release_command(repo_root: Path) -> int:
    repository = _required_env("GITHUB_REPOSITORY")
    tag = _required_env("GITHUB_REF_NAME")
    workflow_sha = _required_env("GITHUB_SHA")
    tag_ref = _run_json(["gh", "api", f"repos/{repository}/git/ref/tags/{tag}"])
    if not isinstance(tag_ref, dict) or not isinstance(tag_ref.get("object"), dict):
        raise ValueError(  # noqa: TRY004 - malformed provider input is operational
            "GitHub returned an invalid tag reference response."
        )
    annotated = tag_ref["object"].get("type") == "tag"
    if not annotated:
        tag_object: dict[str, Any] = {}
    else:
        tag_sha = tag_ref["object"].get("sha")
        if not isinstance(tag_sha, str) or not tag_sha:
            raise ValueError("GitHub returned an invalid annotated tag reference.")
        tag_object = _run_json(["gh", "api", f"repos/{repository}/git/tags/{tag_sha}"])
        if not isinstance(tag_object, dict):
            raise ValueError("GitHub returned an invalid annotated tag response.")
        if not isinstance(tag_object.get("object"), dict):
            raise ValueError("GitHub returned an invalid annotated tag object.")
        if not isinstance(tag_object.get("verification"), dict):
            raise ValueError("GitHub returned an invalid tag verification response.")
    branch = _run_json(["gh", "api", f"repos/{repository}/branches/main"])
    if not isinstance(branch, dict):
        raise ValueError(  # noqa: TRY004 - malformed provider input is operational
            "GitHub returned an invalid branch response."
        )
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
            _required_env("GITHUB_REF_NAME"),
            *(str(directory / name) for name in asset_names),
            "--generate-notes",
            "--notes-file",
            str(release_notes),
            "--verify-tag",
            "--repo",
            _required_env("GITHUB_REPOSITORY"),
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
    try:
        if args.command == "pr-policy":
            return _pr_policy_command()
        if args.command == "required-jobs":
            return _required_jobs_command()
        if args.command == "release":
            return _release_command(args.root.resolve())
        if args.command == "publish-release":
            return _publish_release_command(args.root.resolve())
        return _suppression_command(args.root.resolve())
    except (OSError, subprocess.SubprocessError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
