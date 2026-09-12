#!/usr/bin/env python3
"""Prepare and verify immutable source proofs for review publication anchors."""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any

import collect_evidence as evidence
from pr_identity import require_commit_oid

if TYPE_CHECKING:
    from skills._cli import argument_parser, git_read_arguments, git_read_environment
else:
    argument_parser = evidence.argument_parser
    git_read_arguments = evidence.git_read_arguments
    git_read_environment = evidence.git_read_environment

SCHEMA = "athena.pr-review.anchor-manifest"
LEGACY_SCHEMA = "athena.pr-review.historical-anchor-proof"
MARKER = "<!-- HomericIntelligence:review-anchors:v1 -->"
POLICY = "immutable-two-lens-v1"
MAX_BYTES = 2 * 1024 * 1024
MAX_FINDINGS = 100
DIFF_ARGS = (
    "-c",
    "core.quotePath=true",
    "diff",
    "--no-ext-diff",
    "--no-textconv",
    "--text",
    "--no-renames",
    "--no-color",
    "--full-index",
    "--diff-algorithm=myers",
    "--no-indent-heuristic",
    "--unified=3",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "--ignore-submodules=none",
)
HUNK = re.compile(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")


def canonical(value: Any) -> str:
    """Encode one deterministic proof document."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def source_location(location: str) -> tuple[str, int] | None:
    """Parse a factual source location without assigning publication eligibility."""
    path, separator, line = location.rpartition(":")
    if (
        not separator
        or not line.isascii()
        or not line.isdigit()
        or int(line) < 1
        or not path
        or path.startswith("/")
        or ".." in Path(path).parts
        or any(c in path for c in "\n\r")
    ):
        return None
    return path, int(line)


def exact_fields(value: object, fields: set[str], description: str) -> dict[str, Any]:
    """Reject omitted, additional, or ambiguous proof fields."""
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"Invalid {description} fields.")
    return value


class GitSource:
    """Read complete immutable objects with one bounded lifetime and output budget."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.deadline = time.monotonic() + 30.0
        if self.git("rev-parse", "--is-shallow-repository").strip() != b"false":
            raise ValueError("Historical anchor proof requires complete Git history.")
        if self.git("rev-parse", "--show-prefix").strip():
            raise ValueError("The anchor source must be the repository root.")

    def git(self, *arguments: str) -> bytes:
        """Reuse the collector's bounded stream and process cleanup machinery."""
        timeout = self.deadline - time.monotonic()
        if timeout <= 0:
            raise ValueError("The anchor source proof exceeded its deadline.")
        command = [
            "git",
            *git_read_arguments(),
            "--literal-pathspecs",
            *arguments,
        ]
        process = subprocess.Popen(
            command,
            cwd=self.root,
            env=git_read_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.stdout, process.stderr
        if stdout is None or stderr is None:
            process.kill()
            process.wait()
            raise ValueError("The anchor source proof has no output streams.")
        captures = (
            evidence.ProviderStream(MAX_BYTES),
            evidence.ProviderStream(16 * 1024),
        )
        readers = tuple(
            threading.Thread(
                target=evidence.drain_provider_stream,
                args=(stream, capture),
                daemon=True,
            )
            for stream, capture in zip((stdout, stderr), captures, strict=True)
        )
        for reader in readers:
            reader.start()
        try:
            code = evidence.provider_return_code(
                process,
                *captures,
                "The anchor source exceeds its byte limit.",
                timeout_seconds=timeout,
                coverage_gap=RuntimeError,
                stderr_limit_error="The anchor source diagnostic exceeds its byte limit.",
                deadline_error="The anchor source proof exceeded its deadline.",
                output_error="The anchor source output is incomplete.",
            )
        except BaseException:
            evidence.reap_provider(process, (stdout, stderr), readers)
            raise
        for reader in readers:
            reader.join(evidence.PROVIDER_READER_JOIN_SECONDS)
        if code != 0:
            raise ValueError("An immutable anchor source Git query failed.")
        return bytes(captures[0].output)

    def ranges(
        self, base: str, head: str, merge: str | None = None
    ) -> tuple[str, dict[str, str]]:
        """Bind both original diff lenses; a current branch is never a substitute."""
        for oid in (base, head):
            require_commit_oid(oid, "anchor source commit")
            if self.git("cat-file", "-t", oid).strip() != b"commit":
                raise ValueError("The anchor source is not a commit.")
        bases = self.git("merge-base", "--all", base, head).decode("ascii").splitlines()
        if len(bases) != 1 or (merge is not None and bases[0] != merge):
            raise ValueError("The anchor source merge base is missing or ambiguous.")
        merged = require_commit_oid(bases[0], "anchor merge base")
        hashes = {
            name: sha256(self.git(*DIFF_ARGS, old, head, "--")).hexdigest()
            for name, old in (("author_intent", merged), ("current_target", base))
        }
        return merged, hashes

    def classify(
        self, base: str, head: str, merge: str, path: str, side: str, line: int
    ) -> bool:
        """Classify a head RIGHT or unambiguous merge-base LEFT coordinate."""
        if side not in {"LEFT", "RIGHT"}:
            raise ValueError("Invalid publication anchor side.")
        revision = head if side == "RIGHT" else merge
        blob = self.git("cat-file", "blob", f"{revision}:{path}")
        blob.decode("utf-8")
        physical_lines = blob.count(b"\n") + bool(blob and not blob.endswith(b"\n"))
        if b"\x00" in blob or line > physical_lines:
            raise ValueError("The factual source location is unavailable.")
        if side == "LEFT" and self.git("cat-file", "blob", f"{base}:{path}") != blob:
            raise ValueError(
                "LEFT anchors require identical merge-base and base file content."
            )
        eligible = False
        for old in (merge, base):
            patch = self.git(*DIFF_ARGS, old, head, "--", path)
            for row in patch.split(b"\n"):
                if not row.startswith(b"@@"):
                    continue
                match = HUNK.fullmatch(row)
                if match is None:
                    raise ValueError("The immutable diff hunk is invalid.")
                old_start, old_count, new_start, new_count = match.groups()
                start, count = (
                    (old_start, old_count) if side == "LEFT" else (new_start, new_count)
                )
                if (
                    int(start)
                    <= line
                    < int(start) + (int(count) if count is not None else 1)
                ):
                    eligible = True
        return eligible


def prepare_manifest(
    source: Path, base: str, head: str, findings: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Derive a publication manifest from real Git source and factual locations."""
    if len(findings) > MAX_FINDINGS:
        raise ValueError("Too many publication findings.")
    git = GitSource(source)
    merge, hashes = git.ranges(base, head)
    entries: list[dict[str, Any]] = []
    for finding in findings:
        finding_id = finding["id"]
        if (
            not isinstance(finding_id, str)
            or re.fullmatch(r"F-(?:00[1-9]|0[1-9][0-9]|100)", finding_id) is None
        ):
            raise ValueError("Invalid ordinary publication finding ID.")
        location = finding["location"]
        if not isinstance(location, str):
            raise TypeError("Invalid factual publication location.")
        anchor = source_location(location)
        entry: dict[str, Any] = {"id": finding_id}
        if anchor is None:
            entry.update(publication="summary", reason="non_source_location")
        else:
            path, line = anchor
            side = finding.get("side", "RIGHT")
            eligible = git.classify(base, head, merge, path, side, line)
            entry.update(
                path=path,
                side=side,
                line=line,
                publication="inline" if eligible else "summary",
            )
            if not eligible:
                entry["reason"] = "outside_bound_hunks"
        entries.append(entry)
    entries.sort(key=lambda entry: entry["id"])
    if len({entry["id"] for entry in entries}) != len(entries):
        raise ValueError("Duplicate publication finding ID.")
    return {
        "schema_id": SCHEMA,
        "schema_version": 1,
        "base_oid": base,
        "head_oid": head,
        "merge_base_oid": merge,
        "diff_policy": POLICY,
        "hunks_sha256": hashes,
        "findings": entries,
    }


def visible_manifest(visible: str) -> dict[str, Any] | None:
    """Read the unique canonical annex whose bytes the existing carrier hashes."""
    if "HomericIntelligence:review-anchors:" not in visible:
        return None
    if visible.count(MARKER) != 1:
        raise ValueError("The publication anchor annex is missing or ambiguous.")
    prefix, tail = visible.split(MARKER)
    if prefix and not prefix.endswith("\n\n"):
        raise ValueError("The publication anchor annex is not a separate section.")
    if not tail.startswith("\n```json\n") or not tail.endswith("\n```"):
        raise ValueError(
            "The publication anchor annex is not the final visible section."
        )
    encoded = tail[len("\n```json\n") : -len("\n```")]
    value = json.loads(encoded)
    if canonical(value) != encoded:
        raise ValueError("The publication anchor annex is not canonical JSON.")
    return exact_fields(
        value,
        {
            "schema_id",
            "schema_version",
            "base_oid",
            "head_oid",
            "merge_base_oid",
            "diff_policy",
            "hunks_sha256",
            "findings",
        },
        "anchor manifest",
    )


def expected_anchors(
    *,
    source: Path | None,
    target: Mapping[str, Any],
    envelope: Mapping[str, Any],
    visible: str,
    findings: Sequence[Mapping[str, Any]],
    review_id: str | None,
    legacy_proofs: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[str, str | None, int]]:
    """Verify publication geometry without changing a finding or granting authority."""
    manifest = visible_manifest(visible)
    legacy = [
        p for p in legacy_proofs if p.get("state_sha256") == envelope["state_sha256"]
    ]
    if len(legacy) > 1 or (legacy and manifest is not None):
        raise ValueError("The historical publication proof is ambiguous.")
    ordinary = [f for f in findings if not f["id"].startswith("native:")]
    fallback: dict[str, tuple[str, str | None, int]] = {
        f["id"]: (anchor[0], None, anchor[1])
        for f in ordinary
        if (anchor := source_location(f["location"])) is not None
    }
    if manifest is None and not legacy:
        return fallback
    if source is None:
        raise ValueError("Publication anchor verification requires immutable source.")
    state = envelope["state"]
    if manifest is not None:
        if (
            manifest["schema_id"] != SCHEMA
            or type(manifest["schema_version"]) is not int
            or manifest["schema_version"] != 1
            or manifest["diff_policy"] != POLICY
        ):
            raise ValueError("Unsupported publication anchor manifest.")
        if manifest["head_oid"] != state["artifact_binding"]["revision"]:
            raise ValueError("The publication anchor head differs from its carrier.")
        entries = manifest["findings"]
        if not isinstance(entries, list) or len(entries) > MAX_FINDINGS:
            raise ValueError("Invalid publication finding list.")
        by_id = {
            entry["id"]: entry
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        }
        requested = [
            {
                "id": f["id"],
                "location": f["location"],
                "side": by_id.get(f["id"], {}).get("side", "RIGHT"),
            }
            for f in ordinary
        ]
        expected = prepare_manifest(
            source, manifest["base_oid"], manifest["head_oid"], requested
        )
        if canonical(manifest) != canonical(expected):
            raise ValueError(
                "The publication anchor manifest does not match immutable source."
            )
        return {
            entry["id"]: (entry["path"], entry["side"], entry["line"])
            for entry in entries
            if entry["publication"] == "inline"
        }
    proof = exact_fields(
        legacy[0],
        {
            "schema_id",
            "schema_version",
            "target",
            "review_id",
            "state_sha256",
            "visible_content_sha256",
            "base_oid",
            "head_oid",
            "merge_base_oid",
            "finding_ids",
            "witness",
        },
        "historical anchor proof",
    )
    if (
        proof["schema_id"] != LEGACY_SCHEMA
        or type(proof["schema_version"]) is not int
        or proof["schema_version"] != 1
        or canonical(proof["target"]) != canonical(target)
        or review_id is None
        or proof["review_id"] != review_id
        or proof["head_oid"] != state["artifact_binding"]["revision"]
        or proof["visible_content_sha256"] != sha256(visible.encode()).hexdigest()
    ):
        raise ValueError(
            "The historical source proof does not bind its original carrier."
        )
    # This narrow legacy grammar is an existing published assertion, not new authority.
    base, head = proof["base_oid"], proof["head_oid"]
    require_commit_oid(base, "historical base")
    require_commit_oid(head, "historical head")
    witness = (
        f"Reviewed {target['repository'].rsplit('/', 1)[-1]} #{target['number']} "
        f"at `{head}`, against base/merge-base `{base}` (zero commits behind)."
    )
    if (
        proof["witness"] != witness
        or not (
            visible == witness or visible.startswith((witness + "\n", witness + " "))
        )
        or visible.count("against base/merge-base") != 1
        or proof["merge_base_oid"] != base
    ):
        raise ValueError(
            "The original published source witness is unavailable or ambiguous."
        )
    computed = prepare_manifest(source, base, head, ordinary)
    if computed["merge_base_oid"] != base:
        raise ValueError("The historical source witness has an incorrect merge base.")
    summaries = [
        entry["id"]
        for entry in computed["findings"]
        if entry.get("reason") == "outside_bound_hunks"
    ]
    if not summaries or proof["finding_ids"] != summaries:
        raise ValueError("The historical summary classification is incorrect.")
    return {key: value for key, value in fallback.items() if key not in summaries}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--base-oid", required=True)
    parser.add_argument("--head-oid", required=True)
    parser.add_argument("--findings", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with args.findings.open("rb") as stream:
            encoded = stream.read(MAX_BYTES + 1)
        if len(encoded) > MAX_BYTES:
            raise ValueError("The publication findings exceed the input limit.")
        findings = json.loads(encoded)
        if not isinstance(findings, list):
            raise TypeError("Publication findings must be a list.")
        print(
            canonical(
                prepare_manifest(args.source, args.base_oid, args.head_oid, findings)
            )
        )
    except (OSError, RuntimeError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
