#!/usr/bin/env python3
"""Configurable GitHub CLI fake for executable unit tests."""

from __future__ import annotations

import json
import os
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
        default = {
            "number": int(value),
            "state": "OPEN",
            "url": f"https://example/{value}",
        }
        print(json.dumps(load_json("FAKE_GH_VIEW_JSON", default)))
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
        print(json.dumps({"nameWithOwner": "owner/repository"}))
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
