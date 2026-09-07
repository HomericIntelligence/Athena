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
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, TypedDict

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.policies.agent_contract_release import (
    AGENT_CONTRACT_TAG,
    agent_contract_release_errors,
    catalog_sha256,
    is_agent_contract_tag,
    live_tag_ruleset_errors,
    principle_detail_paths,
    release_record_errors,
    render_release_record,
    ruleset_sha256,
    tag_ruleset_errors,
)
from scripts.policies.pull_request import evaluate_pull_request, flatten_commit_pages
from scripts.policies.release import evaluate_release, verify_release_assets
from scripts.policies.required_jobs import failed_required_jobs
from scripts.policies.suppressions import find_suppressions
from skills._cli import argument_parser

__all__ = (
    "agent_contract_release_errors",
    "evaluate_pull_request",
    "evaluate_release",
    "failed_required_jobs",
    "find_suppressions",
    "flatten_commit_pages",
    "verify_release_assets",
)


class ManifestPolicyError(ValueError):
    """This error identifies repository manifest content that violates policy."""


class _ReleaseEvidence(TypedDict):
    main_sha: str
    main_commit: object
    pull_requests: list[object]
    workflow_runs: list[object]
    check_runs: list[object]
    tag_ref: object | None
    tag_object: object | None


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise OSError(f"The JSON file cannot be read: '{path}'. {error}") from error
    if not isinstance(value, dict):
        raise TypeError(f"The JSON file must contain an object: '{path}'.")
    return value


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
        relative_path = path.relative_to(repo_root)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise OSError(
                f"The manifest cannot be read: '{relative_path}'. "
                f"The operation returned this diagnostic.\n{error}"
            ) from error
        try:
            manifest = json.loads(text)
        except json.JSONDecodeError as error:
            raise ManifestPolicyError(
                f"The manifest must contain valid JSON: '{relative_path}'. "
                f"The parser returned this diagnostic.\n{error}"
            ) from error
        if not isinstance(manifest, dict) or "version" not in manifest:
            raise ManifestPolicyError(
                "The manifest does not have the required 'version' field: "
                f"'{relative_path}'."
            )
        version = manifest["version"]
        if not isinstance(version, str):
            raise ManifestPolicyError(
                "The manifest does not have the required 'version' field: "
                f"'{relative_path}'."
            )
        versions[name] = version
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


def _release_environment_command() -> int:
    repository = _required_env("GITHUB_REPOSITORY")
    environment = _run_json(["gh", "api", f"repos/{repository}/environments/release"])
    if not isinstance(environment, dict):
        raise TypeError(
            "GitHub returned a release environment response that is invalid."
        )
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


def _tracked_agent_contract_ruleset(repo_root: Path) -> dict[str, Any]:
    path = repo_root / ".github" / "rulesets" / "homeric-agent-contract-tags.json"
    document = _read_json_object(path)
    errors = tag_ruleset_errors(document)
    if errors:
        raise SystemExit("\n".join(errors))
    return document


def _agent_contract_tracked_ruleset_command(repo_root: Path) -> int:
    _tracked_agent_contract_ruleset(repo_root)
    print("The tracked agent-contract tag ruleset passed.")
    return 0


def _live_agent_contract_ruleset(
    repository: str, tracked: dict[str, Any]
) -> dict[str, Any]:
    summaries = _run_json(["gh", "api", f"repos/{repository}/rulesets"])
    if not isinstance(summaries, list):
        raise TypeError("GitHub returned an invalid ruleset list.")
    matches = [
        summary
        for summary in summaries
        if isinstance(summary, dict)
        and summary.get("name") == tracked["name"]
        and summary.get("target") == "tag"
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("id"), int):
        raise SystemExit("The live agent-contract tag ruleset is missing or ambiguous.")
    live = _run_json(["gh", "api", f"repos/{repository}/rulesets/{matches[0]['id']}"])
    if not isinstance(live, dict):
        raise TypeError("GitHub returned an invalid live tag ruleset.")
    if "bypass_actors" not in live:
        raise SystemExit(
            "The GitHub token cannot prove the no-bypass policy because the detailed "
            "live ruleset response omits 'bypass_actors'."
        )
    errors = live_tag_ruleset_errors(tracked, live)
    if errors:
        raise SystemExit("\n".join(errors))
    return live


def _agent_contract_live_ruleset_command(repo_root: Path) -> int:
    repository = _required_env("GITHUB_REPOSITORY")
    tracked = _tracked_agent_contract_ruleset(repo_root)
    live = _live_agent_contract_ruleset(repository, tracked)
    print(
        "The live agent-contract tag ruleset matches the tracked policy at digest "
        f"'{ruleset_sha256(live)}'."
    )
    return 0


def _object_list(value: object, field: str) -> list[object]:
    if not isinstance(value, dict) or not isinstance(value.get(field), list):
        raise TypeError(f"GitHub returned an invalid '{field}' response.")
    return list(value[field])


def _collect_agent_contract_release_evidence(
    repository: str, commit: str, *, pre_tag: bool
) -> _ReleaseEvidence:
    main_ref = _run_json(["gh", "api", f"repos/{repository}/git/ref/heads/main"])
    if not isinstance(main_ref, dict) or not isinstance(main_ref.get("object"), dict):
        raise TypeError("GitHub returned an invalid main reference.")
    main_sha = main_ref["object"].get("sha")
    if not isinstance(main_sha, str):
        raise TypeError("GitHub returned an invalid main revision.")
    main_commit = _run_json(["gh", "api", f"repos/{repository}/git/commits/{commit}"])
    if not isinstance(main_commit, dict):
        raise TypeError("GitHub returned an invalid main commit object.")
    pull_requests = _run_json(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{repository}/commits/{commit}/pulls",
        ]
    )
    if not isinstance(pull_requests, list):
        raise TypeError("GitHub returned an invalid pull-request list.")
    pull_head = next(
        (
            pull.get("head", {}).get("sha")
            for pull in pull_requests
            if isinstance(pull, dict)
            and pull.get("merge_commit_sha") == commit
            and isinstance(pull.get("head"), dict)
            and isinstance(pull["head"].get("sha"), str)
        ),
        None,
    )
    revisions = [commit, *([pull_head] if isinstance(pull_head, str) else [])]
    workflow_runs: list[object] = []
    for revision in dict.fromkeys(revisions):
        response = _run_json(
            [
                "gh",
                "api",
                f"repos/{repository}/actions/runs?head_sha={revision}&per_page=100",
            ]
        )
        workflow_runs.extend(_object_list(response, "workflow_runs"))
    check_response = _run_json(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{repository}/commits/{commit}/check-runs?per_page=100",
        ]
    )
    evidence: _ReleaseEvidence = {
        "main_sha": main_sha,
        "main_commit": main_commit,
        "pull_requests": pull_requests,
        "workflow_runs": workflow_runs,
        "check_runs": _object_list(check_response, "check_runs"),
        "tag_ref": None,
        "tag_object": None,
    }
    if pre_tag:
        return evidence
    tag = _required_env("AGENT_CONTRACT_TAG")
    tag_ref = _run_json(["gh", "api", f"repos/{repository}/git/ref/tags/{tag}"])
    if not isinstance(tag_ref, dict) or not isinstance(tag_ref.get("object"), dict):
        raise TypeError("GitHub returned an invalid agent-contract tag reference.")
    tag_sha = tag_ref["object"].get("sha")
    if not isinstance(tag_sha, str):
        raise TypeError(
            "GitHub returned an invalid agent-contract tag object revision."
        )
    tag_object = _run_json(["gh", "api", f"repos/{repository}/git/tags/{tag_sha}"])
    if not isinstance(tag_object, dict):
        raise TypeError("GitHub returned an invalid agent-contract tag object.")
    evidence["tag_ref"] = tag_ref
    evidence["tag_object"] = tag_object
    return evidence


def _agent_contract_release_command(repo_root: Path, *, pre_tag: bool) -> int:
    del repo_root
    repository = _required_env("GITHUB_REPOSITORY")
    tag = os.environ.get("AGENT_CONTRACT_TAG", AGENT_CONTRACT_TAG)
    commit = _required_env("AGENT_CONTRACT_COMMIT")
    evidence = _collect_agent_contract_release_evidence(
        repository, commit, pre_tag=pre_tag
    )
    errors = agent_contract_release_errors(
        tag=tag,
        commit=commit,
        pre_tag=pre_tag,
        **evidence,
    )
    if errors:
        raise SystemExit("\n".join(errors))
    phase = "pre-tag readiness" if pre_tag else "signed tag"
    print(f"The agent-contract {phase} policy passed for commit '{commit}'.")
    return 0


def _resolved_agent_contract_url_count(
    repo_root: Path, repository: str, tag: str
) -> int:
    if not is_agent_contract_tag(tag):
        raise SystemExit(
            "The agent-contract tag must match "
            "'agent-contract-v<major>.<minor>.<patch>'."
        )
    paths = principle_detail_paths(repo_root)
    for path in paths:
        result = _run_json(
            ["gh", "api", f"repos/{repository}/contents/{path}?ref={tag}"]
        )
        if not isinstance(result, dict) or result.get("type") != "file":
            raise SystemExit(f"The tagged principle URL does not resolve: '{path}'.")
    return len(paths)


def _agent_contract_url_resolution_command(repo_root: Path) -> int:
    repository = _required_env("GITHUB_REPOSITORY")
    tag = _required_env("AGENT_CONTRACT_TAG")
    count = _resolved_agent_contract_url_count(repo_root, repository, tag)
    print(f"All {count} tagged principle URLs resolve.")
    return 0


def _agent_contract_no_main_consumer_command(repo_root: Path) -> int:
    result = subprocess.run(
        ["git", "ls-files", "README.md", "AGENTS.md", "docs", ".github"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    forbidden = re.compile(
        r"HomericIntelligence/Athena/\.github/workflows/_agent-contract\.yml@(?:main|master)"
    )
    violations = [
        relative
        for relative in result.stdout.splitlines()
        if forbidden.search((repo_root / relative).read_text(encoding="utf-8"))
    ]
    if violations:
        raise SystemExit(
            "Agent-contract consumers must not pin a mutable branch: "
            + ", ".join(violations)
        )
    print("No agent-contract consumer pins a mutable main branch.")
    return 0


def _read_rejection(path: Path | None, name: str, tag: str = AGENT_CONTRACT_TAG) -> str:
    if path is None:
        raise OSError(f"The {name} rejection evidence file is required.")
    text = path.read_text(encoding="utf-8").strip()
    required_markers = ("GH013", f"refs/tags/{tag}")
    if not text or any(marker not in text for marker in required_markers):
        raise ValueError(
            f"The {name} evidence does not record a GitHub ruleset rejection."
        )
    return text


def _agent_contract_release_record_command(
    repo_root: Path,
    *,
    output: Path | None,
    verify_release: bool,
    retarget_rejection_file: Path | None,
    deletion_rejection_file: Path | None,
) -> int:
    repository = _required_env("GITHUB_REPOSITORY")
    tag = _required_env("AGENT_CONTRACT_TAG")
    commit = _required_env("AGENT_CONTRACT_COMMIT")
    evidence = _collect_agent_contract_release_evidence(
        repository, commit, pre_tag=False
    )
    errors = agent_contract_release_errors(
        tag=tag,
        commit=commit,
        pre_tag=False,
        **evidence,
    )
    if errors:
        raise SystemExit("\n".join(errors))
    tracked = _tracked_agent_contract_ruleset(repo_root)
    live = _live_agent_contract_ruleset(repository, tracked)
    tag_ref = evidence["tag_ref"]
    assert isinstance(tag_ref, dict) and isinstance(tag_ref.get("object"), dict)
    workflow_runs = evidence["workflow_runs"]
    assert isinstance(workflow_runs, list)
    workflow_urls = sorted(
        {
            str(run["html_url"])
            for run in workflow_runs
            if isinstance(run, dict)
            and run.get("name") == "Required Checks"
            and run.get("conclusion") == "success"
            and run.get("event") in {"pull_request", "merge_group", "push"}
            and isinstance(run.get("html_url"), str)
        }
    )
    values = {
        "tag_object_sha": str(tag_ref["object"]["sha"]),
        "commit_sha": commit,
        "catalog_sha256": catalog_sha256(repo_root),
        "workflow_urls": workflow_urls,
        "live_ruleset_sha256": ruleset_sha256(live),
        "resolved_url_count": _resolved_agent_contract_url_count(
            repo_root, repository, tag
        ),
        "retarget_rejection": _read_rejection(retarget_rejection_file, "retarget", tag),
        "deletion_rejection": _read_rejection(deletion_rejection_file, "deletion", tag),
    }
    body = render_release_record(tag=tag, **values)
    if output is not None:
        output.write_text(body, encoding="utf-8")
    if verify_release:
        release = _run_json(["gh", "api", f"repos/{repository}/releases/tags/{tag}"])
        if not isinstance(release, dict) or not isinstance(release.get("body"), str):
            raise TypeError("GitHub returned an invalid release record.")
        errors = release_record_errors(release["body"], tag=tag, **values)
        if errors:
            raise SystemExit("\n".join(errors))
    if output is None and not verify_release:
        print(body, end="")
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


def _uv_pins_command(repo_root: Path) -> int:
    """Validate that all workflow uv pins match the Containerfile pin."""
    import re

    from scripts.policies.uv_pins import find_uv_pin_drift

    container_path = repo_root / "ci" / "Containerfile"
    workflow_root = repo_root / ".github" / "workflows"
    workflow_paths = sorted(
        {
            path
            for pattern in ("*.yml", "*.yaml")
            for path in workflow_root.glob(pattern)
        }
    )
    workflow_texts = {
        str(path.relative_to(repo_root)): path.read_text(encoding="utf-8")
        for path in workflow_paths
    }
    findings = find_uv_pin_drift(
        container_path.read_text(encoding="utf-8"), workflow_texts
    )
    if findings:
        raise SystemExit("\n".join(findings))
    version_match = re.search(
        r"releases/download/(?P<version>\d+\.\d+\.\d+)/uv-",
        container_path.read_text(encoding="utf-8"),
    )
    version = version_match.group("version") if version_match else "unknown"
    print(f"uv pins are in sync ({version}).")
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
            "agent-contract-live-ruleset",
            "agent-contract-no-main-consumer",
            "agent-contract-release",
            "agent-contract-release-record",
            "agent-contract-tracked-ruleset",
            "agent-contract-url-resolution",
            "pr-policy",
            "publish-release",
            "required-jobs",
            "release",
            "release-environment",
            "suppressions",
            "uv-pins",
        ),
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--pre-tag", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-release", action="store_true")
    parser.add_argument("--retarget-rejection-file", type=Path)
    parser.add_argument("--deletion-rejection-file", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "agent-contract-tracked-ruleset":
            return _agent_contract_tracked_ruleset_command(args.root.resolve())
        if args.command == "agent-contract-live-ruleset":
            return _agent_contract_live_ruleset_command(args.root.resolve())
        if args.command == "agent-contract-release":
            return _agent_contract_release_command(
                args.root.resolve(), pre_tag=args.pre_tag
            )
        if args.command == "agent-contract-url-resolution":
            return _agent_contract_url_resolution_command(args.root.resolve())
        if args.command == "agent-contract-no-main-consumer":
            return _agent_contract_no_main_consumer_command(args.root.resolve())
        if args.command == "agent-contract-release-record":
            return _agent_contract_release_record_command(
                args.root.resolve(),
                output=args.output,
                verify_release=args.verify_release,
                retarget_rejection_file=args.retarget_rejection_file,
                deletion_rejection_file=args.deletion_rejection_file,
            )
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
        if args.command == "uv-pins":
            return _uv_pins_command(args.root.resolve())
        return _suppression_command(args.root.resolve())
    except ManifestPolicyError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
