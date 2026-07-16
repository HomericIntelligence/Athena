"""Aggregate required-job policy."""

from __future__ import annotations

from collections.abc import Mapping


def failed_required_jobs(
    event_name: str, results: Mapping[str, object]
) -> dict[str, str]:
    """Return required jobs whose result is not acceptable for this event."""
    failures: dict[str, str] = {}
    for name, item in results.items():
        if not isinstance(item, Mapping):
            failures[name] = "invalid"
            continue
        value = item.get("result", "missing")
        result = value if isinstance(value, str) else "invalid"
        allowed_skip = name == "pr-policy" and event_name != "pull_request"
        if result != "success" and not (result == "skipped" and allowed_skip):
            failures[name] = result
    return failures
