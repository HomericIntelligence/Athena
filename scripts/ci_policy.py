#!/usr/bin/env python3
"""Executable CI and release policies for Athena."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


CONVENTIONAL_SUBJECT = re.compile(
    r"^(feat|fix|docs|refactor|test|chore|revert|ci|build|perf)"
    r"(\([a-z0-9._/-]+\))?!?: .+"
)
ISSUE_LINK = re.compile(r"(?m)^Closes #[0-9]+\s*$")
DCO_TRAILER = re.compile(r"(?mi)^Signed-off-by: .+ <.+>$")
SEMVER_TAG = re.compile(r"^v([0-9]+\.[0-9]+\.[0-9]+)$")
SILENT_FAILURE = re.compile(r"\|\|[ \t]*true(?:[ \t]*$|[ \t]+#)", re.MULTILINE)
CONTINUE_ON_ERROR = re.compile(
    r"^[ \t]*continue-on-error:[ \t]*true[ \t]*$", re.MULTILINE
)


def flatten_commit_pages(pages: object) -> list[dict[str, Any]]:
    """Validate GraphQL pagination and return every commit node."""
    if not isinstance(pages, list) or not pages:
        raise ValueError("commit pagination returned no pages")
    commits: list[dict[str, Any]] = []
    total_count: int | None = None
    for page_number, page in enumerate(pages, start=1):
        try:
            connection = page["data"]["repository"]["pullRequest"]["commits"]
            nodes = connection["nodes"]
            page_info = connection["pageInfo"]
        except (KeyError, TypeError) as error:
            raise ValueError(
                f"commit pagination page {page_number} is malformed: {error}"
            ) from error
        if not isinstance(nodes, list):
            raise ValueError(f"commit pagination page {page_number} has invalid nodes")
        page_total = connection.get("totalCount")
        if not isinstance(page_total, int):
            raise ValueError(
                f"commit pagination page {page_number} has invalid totalCount"
            )
        if total_count is None:
            total_count = page_total
        elif page_total != total_count:
            raise ValueError("commit count changed during pagination")
        commits.extend(nodes)
        has_next = page_info.get("hasNextPage")
        if page_number < len(pages) and not has_next:
            raise ValueError("commit pagination returned an unexpected extra page")
        if page_number == len(pages) and has_next:
            raise ValueError("commit pagination stopped before the final page")
    if total_count is None or len(commits) != total_count:
        raise ValueError(
            f"commit pagination incomplete: expected {total_count}, got {len(commits)}"
        )
    return commits


def evaluate_pull_request(
    *, body: str, author: str, commits: list[dict[str, Any]]
) -> list[str]:
    """Return all pull-request policy violations."""
    errors: list[str] = []
    if author != "dependabot[bot]" and ISSUE_LINK.search(body) is None:
        errors.append("PR body must contain a standalone 'Closes #N' line")
    for node in commits:
        commit = node.get("commit", {})
        oid = str(commit.get("oid", "<unknown>"))
        message = str(commit.get("message", ""))
        signature = commit.get("signature") or {}
        if not signature.get("isValid", False):
            errors.append(f"{oid}: commit signature is missing or invalid")
        if (
            author != "dependabot[bot]"
            and CONVENTIONAL_SUBJECT.match(message.splitlines()[0] if message else "")
            is None
        ):
            errors.append(f"{oid}: subject is not Conventional Commits")
        if author != "dependabot[bot]" and DCO_TRAILER.search(message) is None:
            errors.append(f"{oid}: DCO Signed-off-by trailer is missing")
    return errors


def failed_required_jobs(
    event_name: str, results: dict[str, dict[str, str]]
) -> dict[str, str]:
    """Return required jobs whose result is not acceptable for this event."""
    failures: dict[str, str] = {}
    for name, item in results.items():
        result = item.get("result", "missing")
        allowed_skip = name == "pr-policy" and event_name != "pull_request"
        if result != "success" and not (result == "skipped" and allowed_skip):
            failures[name] = result
    return failures


def evaluate_release(
    *,
    tag: str,
    workflow_sha: str,
    tag_commit: str,
    annotated: bool,
    signature_verified: bool,
    main_protected: bool,
    manifest_versions: dict[str, str],
) -> list[str]:
    """Return release-policy violations independent of GitHub transport."""
    errors: list[str] = []
    match = SEMVER_TAG.fullmatch(tag)
    if match is None:
        errors.append("release tag must be an exact vMAJOR.MINOR.PATCH version")
        expected_version = None
    else:
        expected_version = match.group(1)
    if not annotated:
        errors.append("release tag must be annotated")
    if not signature_verified:
        errors.append("GitHub must verify the tag signature")
    if not main_protected:
        errors.append("main must be protected before publishing a release")
    if tag_commit != workflow_sha:
        errors.append("tag target does not match the workflow commit")
    if expected_version is not None:
        for name, version in sorted(manifest_versions.items()):
            if version != expected_version:
                errors.append(
                    f"{name} manifest version {version} does not match tag {expected_version}"
                )
    return errors


def verify_release_assets(directory: Path) -> tuple[str, str]:
    """Verify the single downloaded plugin archive and its checksum file."""
    archives = sorted(directory.glob("athena-plugin-*.tar.gz"))
    checksums = sorted(directory.glob("athena-plugin-*.tar.gz.sha256"))
    if len(archives) != 1 or len(checksums) != 1:
        raise ValueError(
            "release assets must contain exactly one plugin archive and one checksum"
        )
    archive = archives[0]
    checksum = checksums[0]
    fields = checksum.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1] != archive.name:
        raise ValueError("checksum file does not identify the downloaded archive")
    actual = sha256(archive.read_bytes()).hexdigest()
    if fields[0] != actual:
        raise ValueError(f"checksum mismatch for {archive.name}")
    return archive.name, checksum.name


def find_suppressions(files: dict[str, str]) -> list[str]:
    """Return silent-failure policy violations from tracked executable configuration."""
    findings: list[str] = []
    for path, text in sorted(files.items()):
        for pattern, description in (
            (SILENT_FAILURE, "silent `|| true` fallback"),
            (CONTINUE_ON_ERROR, "continue-on-error enabled"),
        ):
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path}:{line}: {description}")
    return findings


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
    results = json.loads(os.environ["RESULTS"])
    failures = failed_required_jobs(os.environ["EVENT_NAME"], results)
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
    archive_name, checksum_name = verify_release_assets(directory)
    subprocess.run(
        [
            "gh",
            "release",
            "create",
            os.environ["GITHUB_REF_NAME"],
            str(directory / archive_name),
            str(directory / checksum_name),
            "--generate-notes",
            "--verify-tag",
            "--repo",
            os.environ["GITHUB_REPOSITORY"],
        ],
        check=True,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
