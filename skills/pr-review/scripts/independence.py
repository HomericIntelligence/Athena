#!/usr/bin/env python3
"""Evaluate a batch of independent reviews for one artifact."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any, Final, cast

from skills._cli import argument_parser

GO: Final[str] = "GO"
NO_GO: Final[str] = "NO-GO"
VALID_VERDICTS: Final[frozenset[str]] = frozenset({GO, NO_GO})


def assess_batch(reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return the batch decision for one instance.

    Independence is a context property: fresh context, no author or
    author-response for the artifact, and one artifact identity. GO requires
    every submitted report to be independent and GO.
    """
    if not reports:
        return {"status": NO_GO, "reason": "no-independent-reviewer", "independent": 0}
    artifact_id = reports[0].get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return {"status": NO_GO, "reason": "unbound-artifact", "independent": 0}

    independent = 0
    details: list[dict[str, str]] = []
    seen: set[str] = set()
    for report in reports:
        raw_instance = report.get("instance_id")
        if not isinstance(raw_instance, str) or not raw_instance.strip():
            details.append({"instance_id": "missing", "verdict": "rejected"})
            continue
        instance = raw_instance.strip()
        if instance in seen:
            details.append({"instance_id": instance, "verdict": "rejected"})
            continue
        seen.add(instance)
        context_fresh = report.get("context_fresh") is True
        author_restricted = (
            report.get("authored") is True or report.get("author_responded") is True
        )
        same_artifact = report.get("artifact_id") == artifact_id
        verdict = report.get("verdict")
        if (
            context_fresh
            and not author_restricted
            and same_artifact
            and verdict in VALID_VERDICTS
        ):
            independent += 1
            details.append({"instance_id": instance, "verdict": cast(str, verdict)})
        else:
            details.append({"instance_id": instance, "verdict": "rejected"})

    status = (
        GO
        if independent == len(reports)
        and all(item["verdict"] == GO for item in details)
        else NO_GO
    )
    reason = (
        "all-independent-reviews-go"
        if status == GO
        else "split-or-invalid-independence"
    )
    return {
        "status": status,
        "reason": reason,
        "independent": independent,
        "artifact_id": artifact_id,
        "reports": details,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Print the batch result from one JSON document on standard input."""
    parser = argument_parser(description="Evaluate a batch of independent reviews.")
    parser.parse_args(argv)
    reports = json.loads(sys.stdin.read())
    if not isinstance(reports, list):
        print("The input must be one JSON list of reports.", file=sys.stderr)
        return 2
    print(
        json.dumps(assess_batch(cast(list[Mapping[str, Any]], reports)), sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
