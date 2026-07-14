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
        print(os.environ.get("FAKE_GH_CHANGED_FILES", ""))
        return 0
    if arguments[:2] == ["pr", "checks"]:
        print(os.environ.get("FAKE_GH_CHECKS", ""))
        return 0
    print(f"unexpected gh invocation: {arguments}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
