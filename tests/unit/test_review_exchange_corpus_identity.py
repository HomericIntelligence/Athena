"""Behavior tests for corpus identity and the mixed-corpus guard.

The reported failure in issue #334 is a mixed install: the invoked helper
carries the current corpus and its sibling is stale. These tests build one
temporary corpus with a rewritten declared version, which is the reported
shape.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest

from skills import _cli

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "skills/_cli.py"
REVIEW_SCRIPT = ROOT / "skills/review-exchange/scripts/review_exchange.py"
ISSUE_SCRIPT = ROOT / "skills/review-exchange/scripts/issue_exchange.py"
DECLARED_PATTERN = re.compile(
    r'^CORPUS_VERSION: Final\[str\] = "([^"]+)"$', re.MULTILINE
)
HEX = "a" * 40
REVIEW_MARKER = "<!-- HomericIntelligence:issue-review -->"
REMEDY = "Re-sync the installed helper corpus to one version."


def load_module(path: Path, name: str) -> ModuleType:
    """Load one executable helper as a test module."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"The helper cannot be loaded: '{path}'.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_cli(root: Path) -> Path:
    """Write one shared CLI anchor file into a temporary corpus root."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "_cli.py").write_text(CLI.read_text(encoding="utf-8"), encoding="utf-8")
    return root


def build_corpus(
    root: Path,
    *,
    skills: tuple[str, ...] = ("review-exchange",),
    declared: Mapping[str, str] | None = None,
    tree_version: str = "0.6.0",
    manifest: bool = True,
) -> Path:
    """Build one temporary corpus with rewritten declared versions."""
    write_cli(root)
    if manifest:
        (root / "_plugin.json").write_text(
            json.dumps({"version": tree_version}) + "\n", encoding="utf-8"
        )
    versions = dict(declared or {})
    for skill in skills:
        scripts = root / skill / "scripts"
        scripts.mkdir(parents=True)
        for script in sorted((ROOT / "skills" / skill / "scripts").glob("*.py")):
            text = script.read_text(encoding="utf-8")
            declared_match = DECLARED_PATTERN.search(text)
            if declared_match is not None:
                text = text.replace(
                    declared_match.group(0),
                    "CORPUS_VERSION: Final[str] = "
                    f'"{versions.get(script.name, "0.6.0")}"',
                )
            (scripts / script.name).write_text(text, encoding="utf-8")
    return root


def synthetic_peer(path: Path, declared: str | None) -> ModuleType:
    """Return one module object that stands for a loaded helper copy."""
    peer = ModuleType(f"synthetic_peer_{path.name}")
    peer.__file__ = str(path)
    if declared is not None:
        peer.CORPUS_VERSION = declared  # type: ignore[attr-defined]
    return peer


def helper_environment(tmp_path: Path) -> dict[str, str]:
    """Return one clean environment that cannot shadow helper resolution."""
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("PYTHON")
    }
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir(parents=True, exist_ok=True)
    environment["PYTHONPATH"] = str(unrelated)
    return environment


def run_helper(
    tmp_path: Path, script: Path, *arguments: str, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run one helper from a temporary corpus."""
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        cwd=tmp_path,
        env=helper_environment(tmp_path),
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def snapshot(comments: list[dict[str, Any]]) -> dict[str, Any]:
    """Return one minimal issue snapshot."""
    return {
        "schema_id": "athena.issue-exchange.snapshot",
        "schema_version": 1,
        "target": {
            "provider": "github",
            "host": "github.com",
            "repository": "owner/repository",
            "issue_id": "I_kwDO7",
            "number": 210,
            "url": "https://github.com/owner/repository/issues/210",
        },
        "actor": {"id": "U_athena", "login": "reviewer"},
        "issue": {
            "state": "open",
            "title": "Bound the review exchange",
            "body": "Implement a bounded protocol.",
            "acceptance_criteria": [],
        },
        "comments": comments,
        "comments_complete": True,
    }


def comment(comment_id: str, body: str) -> dict[str, Any]:
    """Return one authenticated issue comment."""
    return {
        "id": comment_id,
        "url": (
            f"https://github.com/owner/repository/issues/210#issuecomment-{comment_id}"
        ),
        "author": {
            "id": "U_athena",
            "login": "reviewer",
            "is_authority": False,
        },
        "body": body,
    }


def unsupported_carrier_body(exchange: Any, visible: str) -> str:
    """Render one carrier that carries an unsupported envelope schema version."""
    envelope = {
        "schema_id": exchange.STATE_SCHEMA_ID,
        "schema_version": 7,
        "state": {},
        "state_sha256": exchange.sha256_json({}),
    }
    marker = (
        "<!-- HomericIntelligence:review-exchange:v1 "
        f"kind=state sha256={envelope['state_sha256']} -->"
    )
    encoded = exchange.canonical_json(envelope)
    return f"{visible}\n\n{marker}\n```json\n{encoded}\n```\n"


def test_corpus_root_uses_the_nearest_cli_ancestor(tmp_path: Path) -> None:
    """The nearest ancestor directory with the shared CLI file is the root."""
    root = write_cli(tmp_path / "corpus")
    helper = root / "review-exchange" / "scripts" / "review_exchange.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("", encoding="utf-8")
    assert _cli.corpus_root(helper) == root.resolve()


def test_corpus_root_returns_none_outside_a_corpus(tmp_path: Path) -> None:
    """A helper without a CLI anchor directory has no corpus root."""
    helper = tmp_path / "loose" / "helper.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("", encoding="utf-8")
    assert _cli.corpus_root(helper) is None


def test_corpus_version_prefers_the_generated_plugin_metadata(tmp_path: Path) -> None:
    """The generated corpus metadata wins over an adjacent host manifest."""
    root = tmp_path / "skills"
    write_cli(root)
    (root / "_plugin.json").write_text('{"version": "9.9.9"}\n', encoding="utf-8")
    manifest = tmp_path / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text('{"version": "1.0.0"}\n', encoding="utf-8")
    helper = root / "review-exchange" / "scripts" / "review_exchange.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("", encoding="utf-8")
    with patch.object(_cli, "PLUGIN_ROOT", tmp_path):
        assert _cli.corpus_version(helper) == "9.9.9"


def test_corpus_version_falls_back_to_the_host_manifest(tmp_path: Path) -> None:
    """A source corpus without generated metadata reads the host manifest."""
    root = tmp_path / "skills"
    write_cli(root)
    manifest = tmp_path / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text('{"version": "1.2.3"}\n', encoding="utf-8")
    helper = root / "review-exchange" / "scripts" / "review_exchange.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("", encoding="utf-8")
    with patch.object(_cli, "PLUGIN_ROOT", tmp_path):
        assert _cli.corpus_version(helper) == "1.2.3"


@pytest.mark.parametrize(
    "manifest",
    [
        pytest.param(None, id="absent"),
        pytest.param("[]\n", id="not-an-object"),
        pytest.param("invalid\n", id="not-json"),
        pytest.param('{"version": null}\n', id="no-version"),
        pytest.param('{"version": 7}\n', id="not-text"),
        pytest.param('{"version": "  "}\n', id="blank-version"),
    ],
)
def test_corpus_version_returns_none_when_no_manifest_is_reachable(
    tmp_path: Path, manifest: str | None
) -> None:
    """An unusable manifest yields None instead of a raised error."""
    root = write_cli(tmp_path / "installed")
    if manifest is not None:
        (root / "_plugin.json").write_text(manifest, encoding="utf-8")
    helper = root / "review-exchange" / "scripts" / "review_exchange.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("", encoding="utf-8")
    assert _cli.corpus_version(helper) is None


def test_corpus_version_reads_the_manifest_on_every_call(tmp_path: Path) -> None:
    """No call caches a manifest value, so a re-sync is visible at once."""
    root = write_cli(tmp_path / "installed")
    metadata = root / "_plugin.json"
    metadata.write_text('{"version": "1.0.0"}\n', encoding="utf-8")
    helper = root / "review-exchange" / "scripts" / "review_exchange.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("", encoding="utf-8")
    assert _cli.corpus_version(helper) == "1.0.0"
    metadata.write_text('{"version": "2.0.0"}\n', encoding="utf-8")
    assert _cli.corpus_version(helper) == "2.0.0"


def test_plugin_version_keeps_its_type_error_contract(tmp_path: Path) -> None:
    """The plugin version reports the shipped version and keeps its error."""
    assert (
        _cli.plugin_version()
        == json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))[
            "version"
        ]
    )
    with (
        patch.object(_cli, "PLUGIN_ROOT", tmp_path / "empty"),
        pytest.raises(TypeError),
    ):
        _cli.plugin_version()


def test_corpus_relative_path_is_root_relative(tmp_path: Path) -> None:
    """A corpus path never exposes the corpus root itself."""
    root = write_cli(tmp_path / "installed")
    helper = root / "review-exchange" / "scripts" / "review_exchange.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("", encoding="utf-8")
    assert _cli.corpus_relative_path(helper) == (
        "review-exchange/scripts/review_exchange.py"
    )
    loose = tmp_path / "loose.py"
    loose.write_text("", encoding="utf-8")
    assert _cli.corpus_relative_path(loose) == "loose.py"


def test_module_identity_reports_the_declared_corpus_version() -> None:
    """One loaded helper reports its relative path and both versions."""
    exchange = load_module(REVIEW_SCRIPT, "corpus_identity_review_exchange")
    assert exchange.module_identity(exchange) == {
        "path": "review-exchange/scripts/review_exchange.py",
        "declared_corpus_version": "0.6.0",
        "tree_corpus_version": _cli.plugin_version(),
    }


def test_module_identity_marks_a_helper_without_a_declared_version() -> None:
    """A helper without the compiled constant reports the literal none."""
    exchange = load_module(REVIEW_SCRIPT, "corpus_identity_missing_declaration")
    peer = synthetic_peer(REVIEW_SCRIPT, None)
    assert exchange.module_identity(peer)["declared_corpus_version"] == "none"


def test_verify_corpus_accepts_two_helpers_of_one_declared_version() -> None:
    """Two coherent helpers of one declared version pass the guard."""
    exchange = load_module(REVIEW_SCRIPT, "corpus_identity_accept_pair")
    peer = load_module(ISSUE_SCRIPT, "corpus_identity_accept_peer")
    verified = exchange.verify_corpus(peer)
    assert verified["peer"] == "review-exchange/scripts/issue_exchange.py"
    assert verified["peer_corpus_version"] == exchange.CORPUS_VERSION
    assert verified["review_exchange_tree_corpus_version"] == _cli.plugin_version()


def test_verify_corpus_rejects_a_different_declared_version() -> None:
    """A stale sibling declaration names both copies and both values."""
    exchange = load_module(REVIEW_SCRIPT, "corpus_identity_reject_skew")
    peer = synthetic_peer(
        ROOT / "skills/review-exchange/scripts/issue_exchange.py", "0.5.3"
    )
    with pytest.raises(exchange.OperationalError) as failure:
        exchange.verify_corpus(peer)
    message = str(failure.value)
    assert "mixed" in message
    assert "0.6.0" in message
    assert "0.5.3" in message
    assert "issue_exchange.py" in message
    assert REMEDY in message


def test_verify_corpus_rejects_a_helper_without_a_declared_version() -> None:
    """A peer without the compiled constant has its own named sentence."""
    exchange = load_module(REVIEW_SCRIPT, "corpus_identity_reject_undeclared")
    peer = synthetic_peer(ROOT / "skills/pr-review/scripts/deliver_go.py", None)
    with pytest.raises(exchange.OperationalError) as failure:
        exchange.verify_corpus(peer)
    assert "declares no corpus version" in str(failure.value)
    assert "0.6.0" not in str(failure.value)
    assert REMEDY in str(failure.value)


def test_verify_corpus_rejects_an_unreachable_manifest(tmp_path: Path) -> None:
    """A corpus without readable version metadata is refused by name."""
    exchange = load_module(REVIEW_SCRIPT, "corpus_identity_reject_unreadable")
    root = build_corpus(tmp_path / "stale", manifest=False)
    peer = synthetic_peer(root / "review-exchange/scripts/issue_exchange.py", "0.6.0")
    with pytest.raises(exchange.OperationalError) as failure:
        exchange.verify_corpus(peer)
    message = str(failure.value)
    assert "manifest cannot be read" in message
    assert REMEDY in message


def test_verify_corpus_accepts_a_manifest_that_differs_from_the_declared_version(
    tmp_path: Path,
) -> None:
    """One tree may carry a version that a helper was not written against."""
    exchange = load_module(REVIEW_SCRIPT, "corpus_identity_accept_manifest_skew")
    root = build_corpus(tmp_path / "installed", tree_version="1.2.3-rc.1+build.42")
    peer = synthetic_peer(root / "review-exchange/scripts/issue_exchange.py", "0.6.0")
    verified = exchange.verify_corpus(peer)
    assert verified["peer_tree_corpus_version"] == "1.2.3-rc.1+build.42"
    assert verified["peer_corpus_version"] == exchange.CORPUS_VERSION


def test_issue_exchange_exits_two_on_a_stale_sibling_declared_version(
    tmp_path: Path,
) -> None:
    """A stale sibling refusal stops the exchange with the remedy text."""
    root = build_corpus(tmp_path / "mixed", declared={"review_exchange.py": "0.5.3"})
    script = root / "review-exchange/scripts/issue_exchange.py"
    result = run_helper(
        tmp_path, script, "inspect", "-", input_text=json.dumps(snapshot([]))
    )
    assert result.returncode == 2, result.stderr
    assert "mixed" in result.stderr
    assert "0.5.3" in result.stderr
    assert "0.6.0" in result.stderr
    assert REMEDY in result.stderr
    assert "usage:" not in result.stderr
    assert "Traceback" not in result.stderr


def test_issue_exchange_exits_two_on_an_unreachable_manifest(tmp_path: Path) -> None:
    """An unreadable corpus manifest refuses before any transition."""
    root = build_corpus(tmp_path / "unreadable", manifest=False)
    script = root / "review-exchange/scripts/issue_exchange.py"
    result = run_helper(
        tmp_path, script, "inspect", "-", input_text=json.dumps(snapshot([]))
    )
    assert result.returncode == 2, result.stderr
    assert "manifest cannot be read" in result.stderr
    assert REMEDY in result.stderr
    assert "usage:" not in result.stderr


def delivery_arguments() -> tuple[str, ...]:
    """Return one complete delivery argument vector."""
    return (
        "--target-repository",
        "owner/repository",
        "7",
        "--expected-pr-url",
        "https://github.com/owner/repository/pull/7",
        "--base-oid",
        HEX,
        "--head-oid",
        HEX,
        "--prepare-manifest",
    )


def test_deliver_go_exits_two_on_a_stale_sibling_declared_version(
    tmp_path: Path,
) -> None:
    """The delivery helper refuses a mixed corpus before it binds a forge."""
    root = build_corpus(
        tmp_path / "mixed",
        skills=("pr-review",),
        declared={"deliver_go.py": "0.5.3"},
    )
    build_corpus(root, skills=("review-exchange",))
    script = root / "pr-review/scripts/deliver_go.py"
    result = run_helper(tmp_path, script, *delivery_arguments())
    assert result.returncode == 2, result.stderr
    assert "mixed" in result.stderr
    assert REMEDY in result.stderr
    assert "usage:" not in result.stderr


def test_deliver_go_exits_one_on_a_delivery_failure(tmp_path: Path) -> None:
    """A delivery precondition failure keeps the existing exit code one."""
    root = build_corpus(
        tmp_path / "coherent",
        skills=("pr-review", "review-exchange"),
    )
    script = root / "pr-review/scripts/deliver_go.py"
    result = run_helper(
        tmp_path,
        script,
        *(
            "--target-repository",
            "owner/repository",
            "7",
            "--expected-pr-url",
            "https://github.com/owner/repository/pull/7",
            "--base-oid",
            HEX,
            "--head-oid",
            HEX,
            "--response-manifest",
            str(tmp_path / "absent-manifest.json"),
        ),
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "response manifest" in result.stderr
    assert REMEDY not in result.stderr


def test_malformed_carrier_diagnostic_names_the_comment_and_both_helpers() -> None:
    """A malformed carrier names the failing comment and both loaded helpers."""
    adapter = load_module(ISSUE_SCRIPT, "corpus_identity_diagnostic_adapter")
    exchange = adapter.review_exchange
    body = unsupported_carrier_body(exchange, f"{REVIEW_MARKER}\nstate:review-go")
    inspected = adapter.inspect_snapshot(snapshot([comment("6067660928", body)]))
    assert inspected["status"] == "withheld"
    assert inspected["next_action"] == "human_decision"
    diagnostic = inspected["diagnostics"][0]
    assert diagnostic["code"] == "malformed_carrier"
    assert diagnostic["message"] == ("The envelope schema version is not supported.")
    location = diagnostic["location"]
    assert location["comment_id"] == "6067660928"
    assert location["review_exchange"]["path"] == (
        "review-exchange/scripts/review_exchange.py"
    )
    assert location["issue_exchange"]["path"] == (
        "review-exchange/scripts/issue_exchange.py"
    )
    assert location["review_exchange"]["declared_corpus_version"] == "0.6.0"
    assert location["issue_exchange"]["declared_corpus_version"] == "0.6.0"


def test_diagnostic_location_never_publishes_an_absolute_path() -> None:
    """No operator home directory reaches a published carrier diagnostic."""
    adapter = load_module(ISSUE_SCRIPT, "corpus_identity_diagnostic_paths")
    exchange = adapter.review_exchange
    body = unsupported_carrier_body(exchange, f"{REVIEW_MARKER}\nstate:review-go")
    inspected = adapter.inspect_snapshot(snapshot([comment("1", body)]))
    location = copy.deepcopy(inspected["diagnostics"][0]["location"])
    published = json.dumps(location, sort_keys=True)
    assert str(Path.home()) not in published
    for identity in ("review_exchange", "issue_exchange"):
        assert not Path(location[identity]["path"]).is_absolute()
