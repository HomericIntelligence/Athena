#!/usr/bin/env python3
"""Export redacted agent rollouts after `/athena:learn` and remove the raw session.

A session qualifies when its last real user prompt is the learn command and the
session is idle. The export is redacted, written atomically, and verified. Only
then does `--remove` delete a Claude Code or Codex session. opencode is export-only.
"""

from __future__ import annotations

import getpass
import hashlib
import importlib.util
import json
import os
import pwd
import re
import shutil
import socket
import sqlite3
import stat
import sys
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import closing, suppress
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING or __package__ not in {None, ""}:
    from skills._cli import argument_parser
else:
    _cli_path = Path(__file__).resolve().parents[2] / "_cli.py"
    _cli_spec = importlib.util.spec_from_file_location(
        "athena_installed_cli", _cli_path
    )
    if _cli_spec is None or _cli_spec.loader is None:
        raise RuntimeError(
            f"The installed Athena CLI helper is unavailable: '{_cli_path}'."
        )
    _cli = importlib.util.module_from_spec(_cli_spec)
    _cli_spec.loader.exec_module(_cli)
    argument_parser = _cli.argument_parser

MANIFEST_SCHEMA_VERSION = 1
MANIFEST_NAME = "_manifest.jsonl"
AGENTS = ("claude", "codex", "opencode")
CLAUDE_DROP_TYPES = {
    "api-request-blob",
    "file-history-snapshot",
    "file-history-delta",
}
LEARN_COMMAND = "/athena:learn"
CLAUDE_LEARN_RE = re.compile(
    r"\A\s*(?:<command-message>[^<]*</command-message>\s*)?"
    rf"<command-name>{re.escape(LEARN_COMMAND)}</command-name>"
)
CODEX_LEARN_PREFIXES = ("$athena:learn", LEARN_COMMAND)
OPENCODE_LEARN_PREFIX = "@learn"

SENSITIVE_KEY_EXACT = {
    "account_number",
    "address",
    "api_key",
    "apikey",
    "authorization",
    "birth_date",
    "birthdate",
    "card_number",
    "client_secret",
    "cookie",
    "cvc",
    "cvv",
    "display_name",
    "dob",
    "email",
    "email_address",
    "family_name",
    "first_name",
    "full_name",
    "given_name",
    "iban",
    "id_token",
    "last_name",
    "legal_name",
    "login",
    "mail",
    "name_on_card",
    "passport",
    "passphrase",
    "password",
    "phone",
    "phone_number",
    "postal_code",
    "preferred_name",
    "private_key",
    "refresh_token",
    "routing_number",
    "secret",
    "session_cookie",
    "social_security_number",
    "ssn",
    "street",
    "street_address",
    "token",
    "user_email",
    "user_name",
    "username",
    "zip",
    "zip_code",
}
SENSITIVE_KEY_CONTAINS = (
    "access_token",
    "api_key",
    "apikey",
    "auth_header",
    "authorization",
    "bearer_token",
    "client_secret",
    "credential",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "session_token",
    "ssh_key",
)
PLACEHOLDER_BY_KEY_FRAGMENT = (
    ("api_key", "[REDACTED:API_KEY]"),
    ("apikey", "[REDACTED:API_KEY]"),
    ("token", "[REDACTED:TOKEN]"),
    ("secret", "[REDACTED:SECRET]"),
    ("password", "[REDACTED:PASSWORD]"),
    ("email", "[REDACTED:EMAIL]"),
    ("mail", "[REDACTED:EMAIL]"),
    ("phone", "[REDACTED:PHONE]"),
    ("address", "[REDACTED:ADDRESS]"),
    ("street", "[REDACTED:ADDRESS]"),
    ("postal", "[REDACTED:ADDRESS]"),
    ("zip", "[REDACTED:ADDRESS]"),
    ("login", "[REDACTED:USERNAME]"),
    ("username", "[REDACTED:USERNAME]"),
    ("user_name", "[REDACTED:USERNAME]"),
    ("name", "[REDACTED:NAME]"),
    ("ssn", "[REDACTED:SSN]"),
    ("social_security", "[REDACTED:SSN]"),
    ("card", "[REDACTED:PAYMENT_CARD]"),
    ("cvv", "[REDACTED:PAYMENT_CARD]"),
    ("cvc", "[REDACTED:PAYMENT_CARD]"),
    ("iban", "[REDACTED:BANK_ACCOUNT]"),
    ("routing", "[REDACTED:BANK_ACCOUNT]"),
    ("account_number", "[REDACTED:BANK_ACCOUNT]"),
    ("passport", "[REDACTED:GOVERNMENT_ID]"),
    ("dob", "[REDACTED:BIRTH_DATE]"),
    ("birth", "[REDACTED:BIRTH_DATE]"),
)

TEXT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED:PRIVATE_KEY]",
    ),
    (
        re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@"),
        r"\1[REDACTED:CREDENTIALS]@",
    ),
    (
        re.compile(
            r"(?i)\b(authorization\s*[:=]\s*)(?:bearer|basic)?\s*[A-Za-z0-9._~+/=-]{8,}"
        ),
        r"\1[REDACTED:TOKEN]",
    ),
    (
        re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
        r"\1 [REDACTED:TOKEN]",
    ),
    (
        re.compile(r"\bsk-(?:proj|svcacct)?-?[A-Za-z0-9_\-]{16,}\b"),
        "[REDACTED:API_KEY]",
    ),
    (
        re.compile(r"\b(?:rk|sk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b"),
        "[REDACTED:API_KEY]",
    ),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[REDACTED:GITHUB_TOKEN]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "[REDACTED:GITHUB_TOKEN]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "[REDACTED:SLACK_TOKEN]"),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{30,}\b"), "[REDACTED:GOOGLE_API_KEY]"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[REDACTED:AWS_ACCESS_KEY]"),
    (re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"), "[REDACTED:HUGGINGFACE_TOKEN]"),
    (
        re.compile(
            r"(?i)\b((?:[A-Z0-9][A-Z0-9_-]*[_-])?"
            r"(?:api[_-]?key|token|secret|password|passwd|pwd|client[_-]?secret)"
            r"\s*[:=]\s*)[\"']?[A-Za-z0-9._~+/=:@%\-]{8,}[\"']?"
        ),
        r"\1[REDACTED:SECRET]",
    ),
    (
        re.compile(
            r"(?x)(?<![A-Za-z0-9+/=_-])"
            r"(?=[A-Za-z0-9+/=_-]{24,}(?![A-Za-z0-9+/=_-]))"
            r"(?=[A-Za-z0-9+/=_-]*[A-Z])"
            r"(?=[A-Za-z0-9+/=_-]*[a-z])"
            r"(?=[A-Za-z0-9+/=_-]*\d)"
            r"[A-Za-z0-9+/=_-]{24,}"
            r"(?![A-Za-z0-9+/=_-])"
        ),
        "[REDACTED:OPAQUE_TOKEN]",
    ),
    (
        re.compile(r"(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b"),
        "[REDACTED:EMAIL]",
    ),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED:SSN]"),
    (
        re.compile(
            r"(?x)(?<!\w)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}"
            r"(?:\s*(?:x|ext\.?)\s*\d{1,6})?(?!\w)"
        ),
        "[REDACTED:PHONE]",
    ),
    (
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
        ),
        "[REDACTED:IP_ADDRESS]",
    ),
    (
        re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}\b"),
        "[REDACTED:IP_ADDRESS]",
    ),
    (
        re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"),
        "[REDACTED:MAC_ADDRESS]",
    ),
    (
        re.compile(r"(?P<prefix>/(?:Users|home)/)[^/\s'\"`]+"),
        r"\g<prefix>[REDACTED:USER]",
    ),
    (
        re.compile(r"(?i)\b(?P<prefix>[A-Z]:\\Users\\)[^\\/\s'\"`]+"),
        r"\g<prefix>[REDACTED:USER]",
    ),
)
CARD_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
IMAGE_BLOCK_TYPES = {"image", "input_image"}


def normalize_key(key: str) -> str:
    split_camel = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return re.sub(r"[^a-z0-9]+", "_", split_camel.lower()).strip("_")


def is_sensitive_key(key: str) -> bool:
    normalized = normalize_key(key)
    if normalized in SENSITIVE_KEY_EXACT:
        return True
    return any(fragment in normalized for fragment in SENSITIVE_KEY_CONTAINS)


def placeholder_for_key(key: str) -> str:
    normalized = normalize_key(key)
    for fragment, placeholder in PLACEHOLDER_BY_KEY_FRAGMENT:
        if fragment in normalized:
            return placeholder
    return "[REDACTED:SECRET]"


def luhn_is_valid(digits: str) -> bool:
    total = 0
    double = False
    for char in reversed(digits):
        number = ord(char) - ord("0")
        if double:
            number *= 2
            if number > 9:
                number -= 9
        total += number
        double = not double
    return total % 10 == 0


def looks_like_payment_card(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    return luhn_is_valid(digits)


def literal_pattern(literal: str) -> re.Pattern[str]:
    """Match a sensitive literal. A short literal must be a whole word."""
    escaped = re.escape(literal)
    if len(literal) >= 6:
        return re.compile(escaped, re.IGNORECASE)
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


@dataclass
class Redactor:
    """Redact secrets and PII recursively in JSON values."""

    extra_patterns: list[re.Pattern[str]] = field(default_factory=list)
    literals: list[str] = field(default_factory=list)
    replacements: int = 0
    _patterns: list[tuple[re.Pattern[str], str]] = field(
        default_factory=list, init=False
    )

    def __post_init__(self) -> None:
        patterns = list(TEXT_PATTERNS)
        patterns.extend(
            (pattern, "[REDACTED:EXTRA]") for pattern in self.extra_patterns
        )
        patterns.extend(
            (re.compile(re.escape(text)), "[REDACTED:LITERAL]")
            for text in self.literals
            if text
        )
        for text in self.environment_literals():
            patterns.append((literal_pattern(text), "[REDACTED:USER]"))
        self._patterns = patterns

    @staticmethod
    def environment_literals() -> list[str]:
        """Return the account name, host name, and home path of the current account.

        The environment variable behind `getpass.getuser` can differ from the real
        account, so the passwd name and the home directory name are included too.
        """
        found = [
            getpass.getuser(),
            socket.gethostname(),
            str(Path.home()),
            Path.home().name,
        ]
        found.append(socket.gethostname().split(".")[0])
        # An account without a passwd entry is normal in a container. Skip the name.
        with suppress(KeyError, OSError):
            found.append(pwd.getpwuid(os.getuid()).pw_name)
        return sorted({text for text in found if len(text) >= 3}, key=len, reverse=True)

    def redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            if value.get("type") in IMAGE_BLOCK_TYPES:
                self.replacements += 1
                return {"type": value["type"], "data": "[REDACTED:IMAGE]"}
            result: dict[str, Any] = {}
            for key, child in value.items():
                safe_key = self.redact_text(str(key))
                if is_sensitive_key(str(key)):
                    result[safe_key] = placeholder_for_key(str(key))
                    self.replacements += 1
                else:
                    result[safe_key] = self.redact(child)
            return result
        if isinstance(value, (list, tuple)):
            return [self.redact(child) for child in value]
        if isinstance(value, str):
            return self.redact_text(value)
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and looks_like_payment_card(str(value))
        ):
            self.replacements += 1
            return "[REDACTED:PAYMENT_CARD]"
        return value

    def redact_text(self, text: str) -> str:
        for pattern, replacement in self._patterns:
            text, count = pattern.subn(replacement, text)
            self.replacements += count

        def replace_card(match: re.Match[str]) -> str:
            if looks_like_payment_card(match.group(0)):
                self.replacements += 1
                return "[REDACTED:PAYMENT_CARD]"
            return match.group(0)

        return CARD_CANDIDATE_RE.sub(replace_card, text)


def _json_lines(path: Path) -> Iterator[Any]:
    """Yield each parsed JSON line. An invalid line is kept as a raw record."""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError:
                yield {"_export_parse_error": True, "raw": stripped}


@dataclass
class Session:
    """One qualifying session and the files that belong to it."""

    agent: str
    session_id: str
    list_files: Callable[[], list[Path]]
    records: Callable[[], Iterator[Any]]
    last_prompt: str | None
    tracked: bool = True
    delete_roots: list[Path] = field(default_factory=list)
    delete_paths: list[Path] = field(default_factory=list)
    activity_ns: Callable[[], int] = field(default=lambda: 0)

    def fingerprint(self) -> tuple[int, int]:
        """Return the newest mtime and total size of all files in the session.

        The file list is read again on each call, so a file that appears later
        changes the fingerprint.
        """
        newest = 0
        total = 0
        for path in self.list_files():
            stat = path.stat()
            newest = max(newest, stat.st_mtime_ns)
            total += stat.st_size
        return newest, total


def is_learn_prompt(agent: str, prompt: str | None) -> bool:
    """Return True only for a known learn-command shape. Unknown shapes fail closed."""
    if prompt is None:
        return False
    if agent == "claude":
        return CLAUDE_LEARN_RE.match(prompt) is not None
    if agent == "codex":
        return prompt.lstrip().startswith(CODEX_LEARN_PREFIXES)
    if agent == "opencode":
        return prompt.lstrip().startswith(OPENCODE_LEARN_PREFIX)
    return False


def claude_last_prompt(records: Iterable[Any]) -> str | None:
    """Return the text of the last real user prompt in a Claude Code transcript."""
    last: str | None = None
    for record in records:
        if not isinstance(record, dict) or record.get("type") != "user":
            continue
        if record.get("isSidechain") or record.get("isMeta"):
            continue
        message = record.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            last = content
        elif isinstance(content, list):
            blocks = [b for b in content if isinstance(b, dict)]
            if any(b.get("type") == "tool_result" for b in blocks):
                continue
            last = "\n".join(
                str(b.get("text", "")) for b in blocks if b.get("type") == "text"
            )
    return last


CODEX_INJECTED_PREFIXES = (
    "<environment_context>",
    "<user_instructions>",
    "<skill>",
    "# AGENTS.md",
    "The following is the Codex agent history",
)


def codex_last_prompt(records: Iterable[Any]) -> str | None:
    """Return the text of the last real user prompt in a Codex rollout.

    A prompt is an `event_msg/user_message` or a user `response_item` message.
    Only known injected context messages are skipped. An unknown shape counts as a
    prompt, so the session is kept.
    """
    last: str | None = None
    for record in records:
        if not isinstance(record, dict):
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        if record.get("type") == "event_msg" and payload.get("type") == "user_message":
            message = payload.get("message")
            if isinstance(message, str):
                last = message
        elif (
            record.get("type") == "response_item"
            and payload.get("type") == "message"
            and payload.get("role") == "user"
        ):
            content = payload.get("content")
            blocks = (
                [b for b in content if isinstance(b, dict)]
                if isinstance(content, list)
                else []
            )
            text = "\n".join(str(b.get("text", "")) for b in blocks)
            if not text.lstrip().startswith(CODEX_INJECTED_PREFIXES):
                last = text
    return last


def opencode_last_prompt(rows: Iterable[tuple[str, Any]]) -> str | None:
    """Return the text of the last `user` row. Rows are `(type, data)` by `seq`."""
    last: str | None = None
    for row_type, data in rows:
        if row_type == "user" and isinstance(data, dict):
            text = data.get("text")
            skills = data.get("skills")
            names = (
                {s.get("name") for s in skills if isinstance(s, dict)}
                if isinstance(skills, list)
                else set()
            )
            last = text if isinstance(text, str) and "learn" in names else None
    return last


def claude_sessions(claude_dir: Path) -> Iterator[Session]:
    for path in sorted((claude_dir / "projects").glob("*/*.jsonl")):
        if path.is_symlink():
            continue
        session_dir = path.with_suffix("")

        def listing(main: Path = path, root: Path = session_dir) -> list[Path]:
            if not root.is_dir():
                return [main]
            return [main, *sorted(p for p in root.rglob("*") if p.is_file())]

        def records(
            main: Path = path,
            root: Path = session_dir,
            files: Callable[[], list[Path]] = listing,
        ) -> Iterator[Any]:
            for record in _json_lines(main):
                if isinstance(record, dict) and record.get("type") in CLAUDE_DROP_TYPES:
                    continue
                yield record
            for extra_path in files()[1:]:
                source = extra_path.relative_to(root).as_posix()
                if extra_path.suffix == ".jsonl":
                    for record in _json_lines(extra_path):
                        yield {"_source": source, "record": record}
                else:
                    text = extra_path.read_text(encoding="utf-8", errors="replace")
                    yield {"_source": source, "content": text}

        try:
            last_prompt = claude_last_prompt(_json_lines(path))
        except OSError:
            continue
        yield Session(
            agent="claude",
            session_id=path.stem,
            list_files=listing,
            records=records,
            last_prompt=last_prompt,
            delete_roots=[claude_dir / "projects"],
            delete_paths=[path, *([session_dir] if session_dir.is_dir() else [])],
        )


def codex_sessions(codex_dir: Path) -> Iterator[Session]:
    for path in sorted((codex_dir / "sessions").glob("*/*/*/rollout-*.jsonl")):
        if path.is_symlink():
            continue
        session_id = ""
        try:
            for record in _json_lines(path):
                if isinstance(record, dict) and record.get("type") == "session_meta":
                    payload = record.get("payload")
                    if isinstance(payload, dict) and isinstance(payload.get("id"), str):
                        session_id = payload["id"]
                        break
            last_prompt = codex_last_prompt(_json_lines(path))
        except OSError:
            continue
        if not session_id:
            continue
        yield Session(
            agent="codex",
            session_id=session_id,
            list_files=partial(list, [path]),
            records=partial(_json_lines, path),
            last_prompt=last_prompt,
            delete_roots=[codex_dir / "sessions"],
            delete_paths=[path],
        )


def opencode_sessions(database: Path) -> Iterator[Session]:
    if not database.is_file():
        return
    uri = f"file:{database}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        roots = connection.execute(
            "select id, time_updated from session_v2 where parent_id is null"
        ).fetchall()
        for (session_id,) in (row[:1] for row in roots):
            family = [session_id] + [
                row[0]
                for row in connection.execute(
                    "select id from session_v2 where parent_id = ?", (session_id,)
                )
            ]

            def messages(ids: list[str] = family) -> list[tuple[str, int, str, Any]]:
                found: list[tuple[str, int, str, Any]] = []
                with closing(sqlite3.connect(uri, uri=True)) as reader:
                    for sid in ids:
                        for row_type, seq, data in reader.execute(
                            "select type, seq, data from session_message "
                            "where session_id = ? order by seq",
                            (sid,),
                        ):
                            try:
                                parsed: Any = json.loads(data)
                            except (TypeError, json.JSONDecodeError):
                                parsed = {"_export_parse_error": True}
                            found.append((sid, seq, row_type, parsed))
                return found

            own = messages([session_id])
            updated = max(
                (
                    int(row[0] or 0)
                    for row in connection.execute(
                        f"select time_updated from session_v2 where id in "
                        f"({','.join('?' * len(family))})",
                        family,
                    )
                ),
                default=0,
            )
            nanoseconds = updated * (1_000_000 if updated > 10**11 else 1_000_000_000)

            def records(
                load: Callable[[], list[tuple[str, int, str, Any]]] = messages,
            ) -> Iterator[Any]:
                for sid, seq, row_type, data in load():
                    yield {"_session": sid, "seq": seq, "type": row_type, "data": data}

            def activity(value: int = nanoseconds) -> int:
                return value

            yield Session(
                agent="opencode",
                session_id=str(session_id),
                list_files=list,
                tracked=False,
                records=records,
                last_prompt=opencode_last_prompt((t, d) for _s, _q, t, d in own),
                activity_ns=activity,
            )
    finally:
        connection.close()


def session_activity_ns(session: Session) -> int:
    if session.tracked:
        return session.fingerprint()[0]
    return session.activity_ns()


def output_path(output_dir: Path, session: Session) -> Path:
    digest = hashlib.sha256(
        f"{session.agent}:{session.session_id}".encode()
    ).hexdigest()
    return output_dir / session.agent / f"{digest[:16]}.jsonl"


def write_export(session: Session, redactor: Redactor, temp: Path) -> int:
    """Write the redacted records to `temp` and return the record count."""
    count = 0
    temp.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with temp.open("w", encoding="utf-8") as handle:
        for record in session.records():
            handle.write(
                json.dumps(
                    redactor.redact(record), ensure_ascii=False, separators=(",", ":")
                )
            )
            handle.write("\n")
            count += 1
    os.chmod(temp, 0o600)
    return count


def expected_record_count(session: Session) -> int:
    """Count the exportable records with a fresh parse of the raw source."""
    return sum(1 for _ in session.records())


def existing_is_prefix(existing: Path, staged: Path) -> bool | None:
    """Return True when `existing` is a non-shrinking prefix of `staged`.

    Return None when the existing file cannot be read. That file is replaceable.
    """
    try:
        with (
            existing.open("r", encoding="utf-8") as old,
            staged.open("r", encoding="utf-8") as new,
        ):
            for old_line in old:
                if new.readline() != old_line:
                    return False
    except (OSError, UnicodeDecodeError):
        return None
    return True


def verify_export(
    path: Path, expected: int, redactor: Redactor, leaks: list[str]
) -> str | None:
    """Return a failure reason, or None when the export passes the gate."""
    found = [literal_pattern(text) for text in leaks if len(text) >= 3]
    count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                count += 1
                if redactor.redact(record) != record:
                    return "second redaction pass changed the export"
                if any(pattern.search(line) for pattern in found):
                    return "leak scan found a sensitive literal"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return f"export cannot be read back: {error}"
    if count != expected:
        return f"record count {count} differs from raw source count {expected}"
    return None


def read_manifest(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["source_id"]] = row
    return rows


def write_manifest(path: Path, rows: dict[str, dict[str, Any]]) -> None:
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        for key in sorted(rows):
            handle.write(json.dumps(rows[key], separators=(",", ":")))
            handle.write("\n")
    os.chmod(temp, 0o600)
    os.replace(temp, path)


def path_is_safe_to_delete(path: Path, roots: list[Path]) -> bool:
    """Allow only real paths under an expected root. Refuse any symlink."""
    if path.is_symlink():
        return False
    resolved = path.resolve()
    if not any(resolved.is_relative_to(root.resolve()) for root in roots):
        return False
    if path.is_dir():
        return not any(child.is_symlink() for child in path.rglob("*"))
    return True


def drop_index_entries(path: Path, key: str, session_id: str) -> None:
    """Rewrite a JSONL index without the entries for `session_id` (exact match).

    Keep the file mode. Skip the rewrite when no entry matches. Stop without a
    change when a live writer appended during the rewrite.
    """
    if not path.is_file():
        return
    before = path.stat()
    kept: list[str] = []
    dropped = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            kept.append(line)
            continue
        if isinstance(row, dict) and row.get(key) == session_id:
            dropped += 1
            continue
        kept.append(line)
    if not dropped:
        return
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
    os.chmod(temp, stat.S_IMODE(before.st_mode))
    after = path.stat()
    if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
        temp.unlink(missing_ok=True)
        raise OSError("the index changed during the rewrite")
    os.replace(temp, path)


def delete_session(session: Session, codex_dir: Path) -> None:
    for path in session.delete_paths:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    if session.agent == "codex":
        for name, key in (
            ("history.jsonl", "session_id"),
            ("session_index.jsonl", "id"),
        ):
            try:
                drop_index_entries(codex_dir / name, key, session.session_id)
            except OSError as error:
                print(
                    f"warning: index rewrite failed for {name}: {error}",
                    file=sys.stderr,
                )


@dataclass
class Options:
    output_dir: Path
    codex_dir: Path
    export: bool
    remove: bool
    clobber: bool
    min_idle_ns: int
    redactor: Redactor
    leaks: list[str]


def process_session(
    session: Session, options: Options, manifest: dict[str, dict[str, Any]]
) -> str:
    """Run one session through the pipeline and return a one-line status."""
    if not is_learn_prompt(session.agent, session.last_prompt):
        return "skip-not-learn"
    if time.time_ns() - session_activity_ns(session) < options.min_idle_ns:
        return "skip-active"
    destination = output_path(options.output_dir, session)
    source_id = destination.stem
    snapshot = session.fingerprint() if session.tracked else None
    temp = destination.with_suffix(".tmp")
    try:
        before = options.redactor.replacements
        written = write_export(session, options.redactor, temp)
        redactions = options.redactor.replacements - before
        expected = expected_record_count(session)
        failure = verify_export(temp, expected, options.redactor, options.leaks)
        if failure is None and written != expected:
            failure = "record count changed during the export"
        if failure is not None:
            return f"blocked: {failure}"
        if (
            destination.exists()
            and not options.clobber
            and existing_is_prefix(destination, temp) is False
        ):
            return "blocked: existing rollout diverges from the new export"
        os.replace(temp, destination)
    finally:
        temp.unlink(missing_ok=True)
    deletable = session.agent != "opencode"
    row = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "agent": session.agent,
        "source_id": source_id,
        "records": written,
        "redactions": redactions,
        "source_size": snapshot[1] if snapshot else None,
        "source_mtime_ns": snapshot[0] if snapshot else None,
        "output_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "deleted_paths": [],
    }
    if not options.remove or not deletable:
        manifest[source_id] = row
        return "exported" if deletable else "exported (opencode: no delete)"
    if snapshot is not None and session.fingerprint() != snapshot:
        manifest[source_id] = row
        return "exported; delete skipped: session changed after export"
    unsafe = [
        p
        for p in session.delete_paths
        if not path_is_safe_to_delete(p, session.delete_roots)
    ]
    if unsafe:
        manifest[source_id] = row
        return "exported; delete skipped: unsafe path"
    row["deleted_paths"] = [str(p) for p in session.delete_paths]
    manifest[source_id] = row
    write_manifest(options.output_dir / MANIFEST_NAME, manifest)
    delete_session(session, options.codex_dir)
    return "exported; deleted"


def safe_process(
    session: Session, options: Options, manifest: dict[str, dict[str, Any]]
) -> str:
    """Run `process_session`. A failure blocks this session and nothing else."""
    try:
        return process_session(session, options, manifest)
    except (OSError, sqlite3.Error, ValueError) as error:
        return f"blocked: {type(error).__name__}: {error}"


def main() -> int:
    parser = argument_parser(description=__doc__)
    home = Path.home()
    parser.add_argument("--claude-dir", type=Path, default=home / ".claude")
    parser.add_argument("--codex-dir", type=Path, default=home / ".codex")
    parser.add_argument(
        "--opencode-db",
        type=Path,
        default=home / ".local" / "share" / "opencode" / "opencode.db",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=home / ".agent_brain" / "rollouts"
    )
    parser.add_argument("--agent", action="append", choices=AGENTS, default=[])
    parser.add_argument("--min-idle-minutes", type=int, default=30)
    parser.add_argument("--redact-literal", action="append", default=[])
    parser.add_argument("--extra-redaction", action="append", default=[])
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--clobber", action="store_true")
    arguments = parser.parse_args()

    try:
        extra = [re.compile(text) for text in arguments.extra_redaction]
    except re.error as error:
        print(f"error: invalid regex: {error}", file=sys.stderr)
        return 2
    redactor = Redactor(extra_patterns=extra, literals=arguments.redact_literal)
    options = Options(
        output_dir=arguments.output_dir.expanduser().resolve(),
        codex_dir=arguments.codex_dir.expanduser().resolve(),
        export=arguments.export,
        remove=arguments.remove,
        clobber=arguments.clobber,
        min_idle_ns=max(arguments.min_idle_minutes, 0) * 60 * 1_000_000_000,
        redactor=redactor,
        leaks=[*Redactor.environment_literals(), *arguments.redact_literal],
    )
    wanted = set(arguments.agent) or set(AGENTS)
    sources: list[Iterator[Session]] = []
    if "claude" in wanted:
        sources.append(claude_sessions(arguments.claude_dir.expanduser().resolve()))
    if "codex" in wanted:
        sources.append(codex_sessions(options.codex_dir))
    if "opencode" in wanted:
        sources.append(opencode_sessions(arguments.opencode_db.expanduser().resolve()))

    manifest_path = options.output_dir / MANIFEST_NAME
    options.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        manifest = read_manifest(manifest_path)
    except (OSError, ValueError, KeyError) as error:
        print(f"error: manifest cannot be read: {error}", file=sys.stderr)
        return 2

    failures = 0
    for source in sources:
        for session in source:
            if not is_learn_prompt(session.agent, session.last_prompt):
                continue
            if options.export or options.remove:
                status = safe_process(session, options, manifest)
            else:
                try:
                    idle = (
                        time.time_ns() - session_activity_ns(session)
                        >= options.min_idle_ns
                    )
                    status = "would-export" if idle else "skip-active"
                    if idle and session.agent != "opencode":
                        status += "; would-delete with --remove"
                except OSError as error:
                    status = f"blocked: {type(error).__name__}: {error}"
            digest = output_path(options.output_dir, session).stem
            print(f"{session.agent}\t{digest}\t{status}")
            if status.startswith("blocked"):
                failures += 1
    if options.export or options.remove:
        write_manifest(manifest_path, manifest)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
