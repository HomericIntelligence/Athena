#!/usr/bin/env python3
"""Deliver a review verdict as a comment and apply its state label."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from skills._cli import argument_parser, run_command

GO: Final[str] = "GO"
NO_GO: Final[str] = "NO-GO"
IMPLEMENTATION: Final[str] = "implementation"
PLAN: Final[str] = "plan"
LABELS: Final[dict[tuple[str, str], str]] = {
    (IMPLEMENTATION, GO): "state:implementation-go",
    (IMPLEMENTATION, NO_GO): "state:implementation-no-go",
    (PLAN, GO): "state:plan-go",
    (PLAN, NO_GO): "state:plan-no-go",
}
SIBLING: Final[dict[str, str]] = {
    "state:implementation-go": "state:implementation-no-go",
    "state:implementation-no-go": "state:implementation-go",
    "state:plan-go": "state:plan-no-go",
    "state:plan-no-go": "state:plan-go",
}


def _run(
    arguments: Sequence[str], *, input_text: str | None = None
) -> tuple[int, str, str]:
    completed = run_command(
        ["gh", *arguments],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _labels(repo: str, number: int) -> list[str] | None:
    code, out, _ = _run(
        [
            "api",
            f"repos/{repo}/issues/{number}/labels",
            "--paginate",
            "--jq",
            ".[].name",
        ]
    )
    if code != 0:
        return None
    return [line for line in out.splitlines() if line]


def _result(status: str, detail: dict[str, Any], exit_code: int = 0) -> int:
    print(json.dumps({"status": status, **detail}, sort_keys=True))
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description="Deliver a review result to GitHub.")
    parser.add_argument(
        "--repo", help="OWNER/REPOSITORY. Preferably resolved by the caller."
    )
    parser.add_argument(
        "--target", required=True, type=int, help="Issue or pull-request number."
    )
    parser.add_argument(
        "--kind", choices=(IMPLEMENTATION, PLAN), default=IMPLEMENTATION
    )
    parser.add_argument(
        "--decision", choices=("GO", "NO-GO", "go", "no-go"), required=True
    )
    parser.add_argument(
        "--body",
        help="Review body path. Standard input is used when omitted.",
    )
    parser.add_argument(
        "--auto-merge",
        action="store_true",
        help="Enable auto-merge for a GO implementation review.",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Emit the delivery plan without forge writes.",
    )
    args = parser.parse_args(argv)
    args.decision = args.decision.upper()
    label = LABELS[(args.kind, args.decision)]
    detail = {
        "repo": args.repo,
        "target": args.target,
        "kind": args.kind,
        "decision": args.decision,
        "label": label,
    }
    if args.print_only:
        return _result("planned", detail)
    repo = args.repo
    if repo is None:
        code, out, _ = _run(
            ["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]
        )
        repo = out.strip() if code == 0 else ""
    body = (
        Path(args.body).read_text(encoding="utf-8") if args.body else sys.stdin.read()
    )
    detail = {
        "repo": repo,
        "target": args.target,
        "kind": args.kind,
        "decision": args.decision,
        "label": label,
    }
    if not repo:
        return _result("unresolvable", detail)
    status: list[str] = []
    code, out, err = _run(
        ["pr", "view", str(args.target), "--repo", repo, "--json", "number"]
    )
    is_pr = code == 0 and bool(out.strip())
    code, out, err = (
        _run(
            ["pr", "comment", str(args.target), "--repo", repo, "--body", body],
        )
        if is_pr
        else _run(
            ["issue", "comment", str(args.target), "--repo", repo, "--body", body]
        )
    )
    if code == 0:
        status.append("commented")
    else:
        detail["comment_error"] = err.strip()
    if "commented" not in status:
        detail["label_error"] = "comment write failed; label write skipped"
        detail["applied"] = status
        return _result("delivery_failed", detail, 1)
    existing = _labels(repo, args.target)
    if existing is None:
        detail["label_error"] = "label read failed; label write skipped"
    else:
        sibling = SIBLING[label]
        desired = [name for name in existing if name != sibling]
        if label not in desired:
            desired.append(label)
        payload = json.dumps({"labels": desired}, separators=(",", ":"))
        code, out, err = _run(
            [
                "api",
                "--method",
                "PATCH",
                f"repos/{repo}/issues/{args.target}/labels",
                "--input",
                "-",
            ],
            input_text=payload,
        )
        if code == 0:
            status.append("labelled")
        else:
            detail["label_error"] = err.strip()
    if (
        args.auto_merge
        and args.kind == IMPLEMENTATION
        and args.decision == GO
        and is_pr
    ):
        code, out, err = _run(
            ["pr", "merge", "--auto", "--squash", "--repo", repo, str(args.target)]
        )
        if code == 0:
            status.append("auto-merge")
        else:
            detail["auto_merge_error"] = err.strip()
    detail["applied"] = status
    if not status:
        return _result("delivery_failed", detail, 1)
    print(json.dumps({"status": "delivered", **detail}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
