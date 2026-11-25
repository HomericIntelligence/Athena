---
name: rollout-export
license: BSD-3-Clause
description: Export a redacted copy of finished Claude Code, Codex, or opencode sessions that end with the learn command, then remove the raw Claude Code or Codex session. Use it after `/athena:learn` work is complete. Python 3.12 or later is required. If a check fails, the helper keeps the raw session.
argument-hint: "<optional: --export | --remove>"
allowed-tools: [Bash, Read]
---

# Export rollouts

Use this skill to keep one redacted copy of a finished session in `~/.agent_brain/rollouts/`.
After the copy passes verification, `--remove` deletes the raw Claude Code or Codex session.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to
all prose that it produces.

Use the [autonomous workflow policy](../../docs/policies/autonomous-workflows.md) for authority,
recovery, resources, validation, and delivery.

## When a session qualifies

A session qualifies when both rules are true:

- Its last real user prompt is the learn command (`/athena:learn`, `$athena:learn`, or
  `@learn`). A tool result, an injected skill message, and a sub-agent message are not user
  prompts. A later user prompt means the session does not qualify.
- No file of the session changed in the last `--min-idle-minutes` minutes (default 30).

An unknown record shape is not a match. The helper then keeps the session.

## Inputs

- `--claude-dir`, `--codex-dir`, `--opencode-db`: session locations. The defaults are the
  standard locations in the home directory.
- `--output-dir`: export location. The default is `~/.agent_brain/rollouts`.
- `--agent`: limit the run to `claude`, `codex`, or `opencode`. Use it more than once if needed.
- `--redact-literal` and `--extra-redaction`: extra text or regular expressions to redact.
- `--export`: write redacted copies. Do not delete.
- `--remove`: write redacted copies and delete each verified Claude Code or Codex session.
- `--clobber`: replace an existing copy that differs from the new export.

## Workflow

1. Run the helper with no mode flag. This is a dry run. It prints each qualifying session and
   what the next run would do.

   ```bash
   python3 "<installed-skill-directory>/scripts/export_rollouts.py"
   ```

2. Read the report. Add `--redact-literal` for each internal name that the built-in rules miss.
3. Run again with `--export`. Open one exported file and read it.
4. Run again with `--remove` only when the copy is acceptable. The raw session is not backed up.

For each session, the helper does these steps in order:

1. Write the redacted copy to a temporary file.
2. Verify it: the record count equals a fresh parse of the raw source, a second redaction pass
   changes nothing, and no known sensitive text remains (user name, host name, home path, and
   each `--redact-literal` value).
3. Refuse to replace an existing copy that the new copy does not extend.
4. Move the copy into place atomically and record it in `_manifest.jsonl`.
5. With `--remove`: check that the session did not change after the export. Delete only real
   paths under the agent's session directory. Never follow a symbolic link.

opencode sessions are export-only. The helper opens the database read-only.

## Failure behavior

- A failed check blocks the delete for that session. The helper continues with other sessions.
  It exits with status 1 when a session is blocked.
- A failed Codex index rewrite after a delete is reported. It does not restore the session.
- Redaction can miss an unknown secret format. Read an export before you use `--remove`.

## Failed approaches

- Do not require the learn command to be the last record. The skill expansion and the reply
  always follow it, so no session matches.
- Do not search the raw text for the command. Other records quote it.

## Output contract

One line for each qualifying session: agent, output name, and status. The copies and
`_manifest.jsonl` are in the output directory.
