#!/usr/bin/env python3
"""Emit a read-only, machine-readable inventory of registered worktrees."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


def git(cwd: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(arguments)} failed")
    return result.stdout


def parse_porcelain(output: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in output.splitlines() + [""]:
        if not line:
            if current:
                records.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value if value else True
    return records


def main() -> int:
    try:
        root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
        records = parse_porcelain(git(root, "worktree", "list", "--porcelain"))
        for record in records:
            path = Path(str(record["worktree"]))
            record["path"] = str(path)
            record["exists"] = path.is_dir()
            porcelain_head = str(record.pop("HEAD", ""))
            record.pop("worktree", None)
            if not record["exists"]:
                record["clean"] = False
                record["status"] = []
                record["recent_commits"] = []
                record["head"] = porcelain_head
                continue
            status = git(path, "status", "--short")
            record["clean"] = not bool(status.strip())
            record["status"] = status.splitlines()
            record["recent_commits"] = git(
                path, "log", "--oneline", "--decorate", "-5"
            ).splitlines()
            record["head"] = git(path, "rev-parse", "--verify", "HEAD").strip()
    except (KeyError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    print(json.dumps(records, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
