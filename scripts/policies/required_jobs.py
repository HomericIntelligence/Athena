"""Aggregate required-job policy."""

from __future__ import annotations


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
