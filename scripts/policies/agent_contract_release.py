"""Define the immutable agent-contract release policy."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from scripts.policies.agent_contract import CONTRACT_TAG, parse_principles_catalog
from scripts.semver import SEMVER_PATTERN

AGENT_CONTRACT_TAG = CONTRACT_TAG
AGENT_CONTRACT_REF_PATTERN = "refs/tags/agent-contract-v*"
AGENT_CONTRACT_RULESET_NAME = "homeric-agent-contract-tags"
AGENT_CONTRACT_TAG_PREFIX = "agent-contract-v"


def is_agent_contract_tag(tag: str) -> bool:
    """Return whether a tag is a complete agent-contract release version."""
    return tag.startswith(AGENT_CONTRACT_TAG_PREFIX) and (
        SEMVER_PATTERN.fullmatch(tag.removeprefix(AGENT_CONTRACT_TAG_PREFIX))
        is not None
    )


def expected_tag_ruleset() -> dict[str, Any]:
    """Return the canonical tracked tag-protection policy."""
    return {
        "name": AGENT_CONTRACT_RULESET_NAME,
        "target": "tag",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {
            "ref_name": {
                "include": [AGENT_CONTRACT_REF_PATTERN],
                "exclude": [],
            }
        },
        "rules": [{"type": "update"}, {"type": "deletion"}],
    }


def _rule_types(document: object) -> list[str] | None:
    if not isinstance(document, dict) or not isinstance(document.get("rules"), list):
        return None
    rules = document["rules"]
    if not all(
        isinstance(rule, dict) and isinstance(rule.get("type"), str) for rule in rules
    ):
        return None
    return [rule["type"] for rule in rules]


def tag_ruleset_errors(document: object) -> list[str]:
    """Return violations in one tracked or live agent-contract tag ruleset."""
    if not isinstance(document, dict):
        return ["The agent-contract tag ruleset must be a JSON object."]
    expected = expected_tag_ruleset()
    errors: list[str] = []
    for field in ("name", "target", "enforcement", "conditions"):
        if document.get(field) != expected[field]:
            errors.append(
                f"The agent-contract tag ruleset has an invalid '{field}' field."
            )
    if "bypass_actors" not in document:
        errors.append(
            "The agent-contract tag ruleset is missing the required "
            "'bypass_actors' field."
        )
    elif document["bypass_actors"] != []:
        errors.append("The agent-contract tag ruleset has one or more bypass actors.")
    rule_types = _rule_types(document)
    if rule_types is None:
        errors.append("The agent-contract tag ruleset must contain valid rules.")
    elif sorted(rule_types) != ["deletion", "update"]:
        errors.append(
            "The agent-contract tag ruleset must contain only update and deletion rules."
        )
    return errors


def normalize_tag_ruleset(document: object) -> dict[str, Any]:
    """Remove GitHub readback metadata from one ruleset."""
    errors = tag_ruleset_errors(document)
    if errors:
        raise ValueError("\n".join(errors))
    assert isinstance(document, dict)
    return {
        "name": document["name"],
        "target": document["target"],
        "enforcement": document["enforcement"],
        "bypass_actors": document["bypass_actors"],
        "conditions": document["conditions"],
        "rules": [
            {"type": rule_type} for rule_type in sorted(_rule_types(document) or [])
        ],
    }


def live_tag_ruleset_errors(tracked: object, live: object) -> list[str]:
    """Return violations when live tag protection differs from tracked policy."""
    errors = [*tag_ruleset_errors(tracked), *tag_ruleset_errors(live)]
    if errors:
        return errors
    if normalize_tag_ruleset(tracked) != normalize_tag_ruleset(live):
        return ["The live agent-contract tag ruleset differs from the tracked policy."]
    return []


def _successful_required_run(
    workflow_runs: list[object], *, event: str, revision: str
) -> bool:
    return any(
        isinstance(run, dict)
        and run.get("event") == event
        and run.get("head_sha") == revision
        and run.get("name") == "Required Checks"
        and run.get("conclusion") == "success"
        and isinstance(run.get("html_url"), str)
        and bool(run["html_url"])
        for run in workflow_runs
    )


def agent_contract_release_errors(
    *,
    tag: str,
    commit: str,
    main_sha: str,
    main_commit: object,
    tag_ref: object | None,
    tag_object: object | None,
    pull_requests: list[object],
    workflow_runs: list[object],
    check_runs: list[object],
    pre_tag: bool = False,
) -> list[str]:
    """Return violations in tag identity and required release evidence."""
    errors: list[str] = []
    if not is_agent_contract_tag(tag):
        errors.append(
            "The agent-contract tag must match "
            "'agent-contract-v<major>.<minor>.<patch>'."
        )
    if pre_tag and main_sha != commit:
        errors.append("The agent-contract commit must be the exact main commit.")
    commit_verification = (
        main_commit.get("verification") if isinstance(main_commit, dict) else None
    )
    if (
        not isinstance(main_commit, dict)
        or main_commit.get("sha") != commit
        or not isinstance(commit_verification, dict)
        or commit_verification.get("verified") is not True
    ):
        errors.append("GitHub must verify the exact main commit signature.")
    if not pre_tag:
        ref_object = tag_ref.get("object") if isinstance(tag_ref, dict) else None
        annotated = isinstance(ref_object, dict) and ref_object.get("type") == "tag"
        if not annotated:
            errors.append("The agent-contract tag must be annotated.")
        object_target = (
            tag_object.get("object") if isinstance(tag_object, dict) else None
        )
        verification = (
            tag_object.get("verification") if isinstance(tag_object, dict) else None
        )
        if not isinstance(object_target, dict) or object_target.get("sha") != commit:
            errors.append(
                "The agent-contract tag target must match the release commit."
            )
        if (
            not isinstance(verification, dict)
            or verification.get("verified") is not True
        ):
            errors.append("GitHub must verify the agent-contract tag signature.")

    merged = next(
        (
            pull
            for pull in pull_requests
            if isinstance(pull, dict)
            and pull.get("merged_at")
            and pull.get("merge_commit_sha") == commit
            and isinstance(pull.get("head"), dict)
            and isinstance(pull["head"].get("sha"), str)
        ),
        None,
    )
    if merged is None:
        errors.append("The release commit must have one merged pull-request record.")
        pull_head = ""
    else:
        pull_head = str(merged["head"]["sha"])
    for event, revision in (
        ("pull_request", pull_head),
        ("merge_group", commit),
        ("push", commit),
    ):
        if not revision or not _successful_required_run(
            workflow_runs, event=event, revision=revision
        ):
            errors.append(
                f"The release evidence needs a successful '{event}' Required Checks run."
            )

    successful_checks = {
        str(check["name"])
        for check in check_runs
        if isinstance(check, dict)
        and isinstance(check.get("name"), str)
        and check.get("conclusion") == "success"
    }
    if not any(name.endswith("validate-agent-contract") for name in successful_checks):
        errors.append(
            "The exact main commit needs successful agent-contract validation."
        )
    if "required-checks-gate" not in successful_checks:
        errors.append("The exact main commit needs a successful required-checks gate.")
    return errors


def catalog_sha256(repo_root: Path) -> str:
    """Return the SHA-256 digest of the exact canonical catalog bytes."""
    return sha256(
        (repo_root / "docs" / "principles" / "README.md").read_bytes()
    ).hexdigest()


def principle_detail_paths(repo_root: Path) -> tuple[str, ...]:
    """Return the exact P001-P091 detail paths from the canonical catalog."""
    principles, errors = parse_principles_catalog(repo_root)
    if errors:
        raise ValueError("\n".join(error.reason for error in errors))
    return tuple(f"docs/principles/{principle.detail_path}" for principle in principles)


def _record_values(
    *,
    tag_object_sha: str,
    commit_sha: str,
    catalog_sha256: str,
    workflow_urls: list[str],
    live_ruleset_sha256: str,
    resolved_url_count: int,
    retarget_rejection: str,
    deletion_rejection: str,
) -> dict[str, object]:
    return {
        "tag_object_sha": tag_object_sha,
        "commit_sha": commit_sha,
        "catalog_sha256": catalog_sha256,
        "workflow_urls": workflow_urls,
        "live_ruleset_sha256": live_ruleset_sha256,
        "resolved_url_count": resolved_url_count,
        "retarget_rejection": retarget_rejection,
        "deletion_rejection": deletion_rejection,
    }


def render_release_record(*, tag: str = AGENT_CONTRACT_TAG, **values: Any) -> str:
    """Render a deterministic GitHub Release record from verified readbacks."""
    if not is_agent_contract_tag(tag):
        raise ValueError("The release record needs a valid agent-contract tag.")
    record = _record_values(**values)
    workflow_urls = record["workflow_urls"]
    if not isinstance(workflow_urls, list) or not all(
        isinstance(url, str) for url in workflow_urls
    ):
        raise TypeError("The workflow URL evidence must be a list of strings.")
    workflows = "\n".join(f"- {url}" for url in workflow_urls)
    return (
        f"# {tag} release record\n\n"
        f"- Tag object SHA: `{record['tag_object_sha']}`\n"
        f"- Commit SHA: `{record['commit_sha']}`\n"
        f"- Catalog SHA-256: `{record['catalog_sha256']}`\n"
        f"- Live ruleset SHA-256: `{record['live_ruleset_sha256']}`\n"
        f"- Resolved principle URLs: {record['resolved_url_count']}\n\n"
        f"## Required workflow runs\n\n{workflows}\n\n"
        "## Protected-tag rejection evidence\n\n"
        f"- Retarget: {record['retarget_rejection']}\n"
        f"- Deletion: {record['deletion_rejection']}\n"
    )


def release_record_errors(
    body: str, *, tag: str = AGENT_CONTRACT_TAG, **values: Any
) -> list[str]:
    """Return violations in one published GitHub Release record."""
    expected = render_release_record(tag=tag, **values)
    if body != expected:
        return ["The GitHub Release record does not match the verified evidence."]
    return []


def ruleset_sha256(document: object) -> str:
    """Return a stable digest for a normalized live ruleset."""
    normalized = normalize_tag_ruleset(document)
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    return sha256(payload).hexdigest()
