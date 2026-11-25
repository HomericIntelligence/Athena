"""Behavior tests for the rollout export helper.

The tests use temporary session trees. They check the redaction contract, the
learn-prompt rule for each agent, and the safety rules around deletion.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "rollout-export" / "scripts" / "export_rollouts.py"


def load_export() -> ModuleType:
    """Load the helper as an installed, package-less script."""
    spec = importlib.util.spec_from_file_location("rollout_export_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"The helper cannot load: '{SCRIPT}'.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


export = load_export()

# Built at run time so that no secret-shaped literal sits in the source.
FIXTURE_SECRET = "abcdefgh" + "12345678"
LEARN_CLAUDE = (
    "<command-message>athena:learn</command-message>\n"
    "<command-name>/athena:learn</command-name>"
)


@pytest.fixture(autouse=True)
def fixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        export.Redactor, "environment_literals", staticmethod(lambda: ["tester9"])
    )


def write_jsonl(path: Path, records: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def user(content: Any, **extra: Any) -> dict[str, Any]:
    return {"type": "user", "message": {"role": "user", "content": content}, **extra}


def claude_learn_session(claude: Path, session_id: str = "s1") -> Path:
    path = claude / "projects" / "proj" / f"{session_id}.jsonl"
    write_jsonl(
        path,
        [
            user("fix the bug, mail me at jane@example.com"),
            user(LEARN_CLAUDE),
            user([{"type": "text", "text": "Base directory"}], isMeta=True),
            {"type": "assistant", "message": {"role": "assistant", "content": "ok"}},
            {"type": "api-request-blob", "blob": "x" * 50},
            {"type": "cost-state", "sessionId": session_id},
        ],
    )
    side = claude / "projects" / "proj" / session_id / "subagents"
    write_jsonl(side / "agent-1.jsonl", [user("sub work path /home/tester9/x")])
    tool = claude / "projects" / "proj" / session_id / "tool-results" / "r.txt"
    tool.parent.mkdir(parents=True, exist_ok=True)
    tool.write_text("token=" + FIXTURE_SECRET, encoding="utf-8")
    return path


def run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    *flags: str,
) -> tuple[int, str]:
    arguments = [
        "export_rollouts.py",
        "--claude-dir", str(tmp_path / "claude"),
        "--codex-dir", str(tmp_path / "codex"),
        "--opencode-db", str(tmp_path / "opencode.db"),
        "--output-dir", str(tmp_path / "out"),
        "--min-idle-minutes", "0",
        *flags,
    ]  # fmt: skip
    monkeypatch.setattr(sys, "argv", arguments)
    code = export.main()
    return code, capsys.readouterr().out


def exports(tmp_path: Path, agent: str) -> list[Path]:
    return sorted((tmp_path / "out" / agent).glob("*.jsonl"))


# --- redaction ---------------------------------------------------------------


def test_redaction_removes_secrets_and_is_idempotent() -> None:
    redactor = export.Redactor()
    record = {
        "text": "mail jane@example.com key "
        + "sk-"
        + "abcdefghijklmnop1234"
        + " card 4111 1111 1111 1111",
        "path": "/home/tester9/work and tester9 again",
        "password": "hunter2",
        "content": [{"type": "image", "source": {"data": "AAAA" * 100}}],
    }
    result = redactor.redact(record)
    flat = json.dumps(result)
    for leaked in ("jane@example.com", "sk-abc", "4111", "hunter2", "tester9", "AAAA"):
        assert leaked not in flat
    assert export.Redactor().redact(result) == result


def test_short_literal_redaction_respects_word_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        export.Redactor, "environment_literals", staticmethod(lambda: ["bob"])
    )
    redactor = export.Redactor()
    assert redactor.redact_text("bob and bobcat") == "[REDACTED:USER] and bobcat"


# --- learn-prompt rule -------------------------------------------------------


def test_claude_last_prompt_rules() -> None:
    learn = user(LEARN_CLAUDE)
    meta = user([{"type": "text", "text": "skill"}], isMeta=True)
    reply = {"type": "assistant", "message": {"content": "done"}}
    later = user("one more thing")
    tool_result = user([{"type": "tool_result", "content": "x"}])
    sidechain = user("agent chatter", isSidechain=True)
    quoted = user("please explain " + LEARN_CLAUDE.replace("<", "&lt;"))
    assert export.is_learn_prompt(
        "claude",
        export.claude_last_prompt([learn, meta, reply, tool_result, sidechain]),
    )
    assert not export.is_learn_prompt(
        "claude", export.claude_last_prompt([learn, meta, reply, later])
    )
    assert not export.is_learn_prompt(
        "claude", export.claude_last_prompt([learn, quoted])
    )
    assert export.claude_last_prompt([{"type": "cost-state"}]) is None
    prefixed = user("see this: " + LEARN_CLAUDE)
    assert not export.is_learn_prompt("claude", export.claude_last_prompt([prefixed]))


def test_codex_last_prompt_rules() -> None:
    def message(text: str) -> dict[str, Any]:
        return {
            "type": "event_msg",
            "payload": {"type": "user_message", "message": text},
        }

    def item(text: str) -> dict[str, Any]:
        content = [{"type": "input_text", "text": text}]
        return {
            "type": "response_item",
            "payload": {"type": "message", "role": "user", "content": content},
        }

    injected = item("<skill>\n<name>athena:learn</name>")
    assert export.is_learn_prompt(
        "codex", export.codex_last_prompt([message("$athena:learn x"), injected])
    )
    assert not export.is_learn_prompt(
        "codex", export.codex_last_prompt([message("$athena:learn"), message("next")])
    )
    assert export.is_learn_prompt(
        "codex",
        export.codex_last_prompt(
            [item("$athena:learn"), injected, item("# AGENTS.md rules")]
        ),
    )
    assert not export.is_learn_prompt(
        "codex",
        export.codex_last_prompt([item("$athena:learn"), item("<unknown_shape>")]),
    )


def test_opencode_last_prompt_rules() -> None:
    learn = ("user", {"text": "@learn notes", "skills": [{"name": "learn"}]})
    other = ("user", {"text": "@learn", "skills": []})
    idle = ("idle", {"outcome": "done"})
    assert export.is_learn_prompt(
        "opencode", export.opencode_last_prompt([learn, idle])
    )
    assert not export.is_learn_prompt(
        "opencode", export.opencode_last_prompt([other, idle])
    )
    assert not export.is_learn_prompt("unknown", "anything")
    assert not export.is_learn_prompt("claude", None)


# --- pipeline ----------------------------------------------------------------


def test_dry_run_writes_and_deletes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = claude_learn_session(tmp_path / "claude")
    code, output = run(monkeypatch, capsys, tmp_path)
    assert code == 0
    assert "would-export" in output
    assert source.exists()
    assert not (tmp_path / "out" / "claude").exists()


def test_export_only_keeps_the_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = claude_learn_session(tmp_path / "claude")
    code, _ = run(monkeypatch, capsys, tmp_path, "--export")
    assert code == 0
    assert source.exists()
    (exported,) = exports(tmp_path, "claude")
    text = exported.read_text(encoding="utf-8")
    for leaked in ("jane@example.com", "tester9", FIXTURE_SECRET, "x" * 50):
        assert leaked not in text
    assert "api-request-blob" not in text
    assert "subagents/agent-1.jsonl" in text


def test_remove_deletes_session_after_verified_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = claude_learn_session(tmp_path / "claude")
    code, output = run(monkeypatch, capsys, tmp_path, "--remove")
    assert code == 0
    assert "deleted" in output
    assert not source.exists()
    assert not source.with_suffix("").exists()
    assert len(exports(tmp_path, "claude")) == 1
    manifest = (tmp_path / "out" / export.MANIFEST_NAME).read_text(encoding="utf-8")
    assert json.loads(manifest.splitlines()[0])["deleted_paths"]


def test_not_learn_and_active_sessions_are_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    other = tmp_path / "claude" / "projects" / "proj" / "plain.jsonl"
    write_jsonl(other, [user("just work")])
    active = claude_learn_session(tmp_path / "claude", "live")
    code, output = run(
        monkeypatch, capsys, tmp_path, "--remove", "--min-idle-minutes", "60"
    )
    assert code == 0
    assert "skip-active" in output
    assert other.exists()
    assert active.exists()


def test_failed_verify_blocks_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = claude_learn_session(tmp_path / "claude")
    monkeypatch.setattr(export, "verify_export", lambda *_a, **_k: "forced failure")
    code, output = run(monkeypatch, capsys, tmp_path, "--remove")
    assert code == 1
    assert "blocked: forced failure" in output
    assert source.exists()
    assert not exports(tmp_path, "claude")


def test_verify_detects_count_mismatch_and_leak(tmp_path: Path) -> None:
    path = tmp_path / "out.jsonl"
    write_jsonl(path, [{"a": 1}, {"b": "clean text"}])
    redactor = export.Redactor()
    assert "count" in export.verify_export(path, 5, redactor, [])
    assert "leak" in export.verify_export(path, 2, redactor, ["clean"])
    assert export.verify_export(path, 2, redactor, []) is None
    write_jsonl(path, [{"b": "tester9 here"}])
    assert "second" in export.verify_export(path, 1, redactor, [])
    path.write_bytes(b"\xff\xfe not json")
    assert export.verify_export(path, 1, redactor, []) is not None


def test_session_changed_after_export_is_not_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = claude_learn_session(tmp_path / "claude")
    real = export.write_export

    def write_then_append(session: Any, redactor: Any, temp: Path) -> int:
        count: int = real(session, redactor, temp)
        with source.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(user("late line")) + "\n")
        return count

    monkeypatch.setattr(export, "write_export", write_then_append)
    monkeypatch.setattr(
        export, "expected_record_count", lambda s: sum(1 for _ in s.records()) - 1
    )
    _, output = run(monkeypatch, capsys, tmp_path, "--remove")
    assert source.exists()
    assert "blocked" in output or "delete skipped" in output


def test_symlink_in_session_tree_blocks_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = claude_learn_session(tmp_path / "claude")
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    os.symlink(outside, source.with_suffix("") / "tool-results" / "link.txt")
    _, output = run(monkeypatch, capsys, tmp_path, "--remove")
    assert "unsafe path" in output
    assert source.exists()
    assert outside.exists()


def test_overwrite_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_learn_session(tmp_path / "claude")
    run(monkeypatch, capsys, tmp_path, "--export")
    (exported,) = exports(tmp_path, "claude")
    good = exported.read_text(encoding="utf-8")

    exported.write_text('{"different":1}\n' + good, encoding="utf-8")
    _, output = run(monkeypatch, capsys, tmp_path, "--export")
    assert "diverges" in output
    assert exported.read_text(encoding="utf-8").startswith('{"different"')

    run(monkeypatch, capsys, tmp_path, "--export", "--clobber")
    assert exported.read_text(encoding="utf-8") == good

    exported.write_bytes(b"\xff\xfe\x00 garbage")
    run(monkeypatch, capsys, tmp_path, "--export")
    assert exported.read_text(encoding="utf-8") == good


def test_codex_remove_drops_exact_session_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    codex = tmp_path / "codex"
    rollout = codex / "sessions" / "2026" / "11" / "25" / "rollout-1-abc.jsonl"
    write_jsonl(
        rollout,
        [
            {"type": "session_meta", "payload": {"id": "abc"}},
            {
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "$athena:learn"},
            },
            {"type": "event_msg", "payload": {"type": "task_complete"}},
        ],
    )
    write_jsonl(
        codex / "history.jsonl",
        [{"session_id": "abc", "text": "x"}, {"session_id": "abcd", "text": "y"}],
    )
    write_jsonl(codex / "session_index.jsonl", [{"id": "abc"}, {"id": "other"}])
    code, output = run(monkeypatch, capsys, tmp_path, "--remove")
    assert code == 0
    assert "deleted" in output
    assert not rollout.exists()
    assert "abcd" in (codex / "history.jsonl").read_text(encoding="utf-8")
    assert '"abc"' not in (codex / "history.jsonl").read_text(encoding="utf-8")
    assert "other" in (codex / "session_index.jsonl").read_text(encoding="utf-8")
    assert len(exports(tmp_path, "codex")) == 1


def test_opencode_export_is_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    database = tmp_path / "opencode.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        "create table session_v2 (id text, parent_id text, time_updated integer);"
        "create table session_message (session_id text, type text, seq integer, data text);"
    )
    connection.execute("insert into session_v2 values ('ses_1', null, 1)")
    connection.execute("insert into session_v2 values ('ses_2', 'ses_1', 1)")
    rows = [
        (
            "ses_1",
            "user",
            1,
            json.dumps({"text": "@learn", "skills": [{"name": "learn"}]}),
        ),
        ("ses_1", "idle", 2, json.dumps({"outcome": "done"})),
        ("ses_2", "user", 1, json.dumps({"text": "child mail a@b.io"})),
    ]
    connection.executemany("insert into session_message values (?,?,?,?)", rows)
    connection.commit()
    connection.close()
    before = database.read_bytes()
    code, output = run(monkeypatch, capsys, tmp_path, "--remove")
    assert code == 0
    assert "no delete" in output
    assert database.read_bytes() == before
    (exported,) = exports(tmp_path, "opencode")
    text = exported.read_text(encoding="utf-8")
    assert "ses_2" in text
    assert "a@b.io" not in text


def test_new_file_after_discovery_blocks_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = claude_learn_session(tmp_path / "claude")
    late = source.with_suffix("") / "tool-results" / "late.txt"
    real = export.write_export

    def write_then_add(session: Any, redactor: Any, temp: Path) -> int:
        count: int = real(session, redactor, temp)
        late.write_text("late output", encoding="utf-8")
        return count

    monkeypatch.setattr(export, "write_export", write_then_add)
    code, output = run(monkeypatch, capsys, tmp_path, "--remove")
    assert code == 1
    assert "blocked" in output
    assert source.exists()
    assert late.exists()


def test_read_error_blocks_one_session_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    first = claude_learn_session(tmp_path / "claude", "s1")
    second = claude_learn_session(tmp_path / "claude", "s2")
    real = export.write_export

    def fail_first(session: Any, redactor: Any, temp: Path) -> int:
        if session.session_id == "s1":
            raise FileNotFoundError("vanished")
        count: int = real(session, redactor, temp)
        return count

    monkeypatch.setattr(export, "write_export", fail_first)
    code, output = run(monkeypatch, capsys, tmp_path, "--remove")
    assert code == 1
    assert first.exists()
    assert not second.exists()
    assert output.count("blocked") == 1


def test_file_removed_before_export_skips_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = claude_learn_session(tmp_path / "claude")
    real = export.write_export

    def vanish(session: Any, redactor: Any, temp: Path) -> int:
        (source.with_suffix("") / "tool-results" / "r.txt").unlink()
        count: int = real(session, redactor, temp)
        return count

    monkeypatch.setattr(export, "write_export", vanish)
    _, output = run(monkeypatch, capsys, tmp_path, "--remove")
    assert "delete skipped" in output
    assert source.exists()


def test_exports_and_manifest_are_private_and_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = claude_learn_session(tmp_path / "claude")
    run(monkeypatch, capsys, tmp_path, "--remove")
    (exported,) = exports(tmp_path, "claude")
    manifest = tmp_path / "out" / export.MANIFEST_NAME
    assert exported.stat().st_mode & 0o777 == 0o600
    assert manifest.stat().st_mode & 0o777 == 0o600
    row = json.loads(manifest.read_text(encoding="utf-8").splitlines()[0])
    assert row["redactions"] > 0
    assert row["source_size"] > 0
    assert str(source) in row["deleted_paths"]


def test_codex_index_rewrite_keeps_mode_and_skips_when_no_match(tmp_path: Path) -> None:
    index = tmp_path / "history.jsonl"
    write_jsonl(index, [{"session_id": "abc"}, {"session_id": "other"}])
    index.chmod(0o600)
    export.drop_index_entries(index, "session_id", "abc")
    assert index.stat().st_mode & 0o777 == 0o600
    assert "abc" not in index.read_text(encoding="utf-8")
    stamp = index.stat().st_mtime_ns
    export.drop_index_entries(index, "session_id", "missing")
    assert index.stat().st_mtime_ns == stamp
