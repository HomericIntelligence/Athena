#!/usr/bin/env python3
"""Configurable GitHub CLI fake for executable unit tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


def load_json(name: str, default: object) -> object:
    return json.loads(os.environ.get(name, json.dumps(default)))


def main() -> int:
    arguments = sys.argv[1:]
    if arguments[:2] == ["pr", "view"]:
        if "FAKE_GH_VIEW_RAW" in os.environ:
            print(os.environ["FAKE_GH_VIEW_RAW"])
            return 0
        value = arguments[2]
        number = int(value.rstrip("/").rsplit("/", maxsplit=1)[-1])
        repository = os.environ.get("FAKE_GH_REPOSITORY", "owner/repository")
        default = {
            "number": number,
            "state": "OPEN",
            "url": f"https://github.com/{repository}/pull/{number}",
        }
        configured = load_json("FAKE_GH_VIEW_JSON", {})
        if isinstance(configured, dict):
            default.update(configured)
            configured = default
            requested_fields = arguments[arguments.index("--json") + 1]
            if os.environ.get("FAKE_GH_SIMULATE_COMPLEXITY_DROP") == "1" and any(
                field in requested_fields.split(",") for field in ("commits", "files")
            ):
                configured["title"] = None
                configured["author"] = None
                configured["statusCheckRollup"] = None
            fields_file = os.environ.get("FAKE_GH_VIEW_FIELDS_FILE")
            if fields_file:
                Path(fields_file).write_text(requested_fields, encoding="utf-8")
        print(json.dumps(configured))
        return 0
    if arguments[:2] == ["pr", "list"]:
        print(json.dumps(load_json("FAKE_GH_CANDIDATES_JSON", [])))
        return 0
    if arguments[:2] == ["pr", "diff"]:
        if "FAKE_GH_DIFF_ERROR" in os.environ:
            print(os.environ["FAKE_GH_DIFF_ERROR"], file=sys.stderr)
            return 1
        print(os.environ.get("FAKE_GH_CHANGED_FILES", ""))
        return 0
    if arguments[:2] == ["pr", "checks"]:
        print(os.environ.get("FAKE_GH_CHECKS", "[]"))
        return int(os.environ.get("FAKE_GH_CHECKS_EXIT", "0"))
    if arguments[:2] == ["repo", "view"]:
        print(
            json.dumps(
                {
                    "nameWithOwner": os.environ.get(
                        "FAKE_GH_REPOSITORY", "owner/repository"
                    )
                }
            )
        )
        return 0
    if arguments[:1] == ["api"]:
        files = load_json("FAKE_GH_FILES_JSON", [])
        for item in files if isinstance(files, list) else []:
            if isinstance(item, dict) and isinstance(item.get("filename"), str):
                print(item["filename"])
        return 0
    print(f"unexpected gh invocation: {arguments}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
