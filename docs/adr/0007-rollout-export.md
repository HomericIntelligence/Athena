# ADR 0007: Rollout export after the learn command

**Status:** Proposed

## Context

Agent session logs hold PII and secrets. After a session ends with `/athena:learn`, the owner
wants one redacted copy in `~/.agent_brain/rollouts/` and no raw copy. Issue #431 tracks the work.

The learn command is never the last record of a session. The skill expansion and the assistant
reply follow it. Other records also quote the command text.

## Decision

Athena adds the `rollout-export` skill and the helper `export_rollouts.py`.

- A session qualifies when its last real user prompt is the learn command and no file of the
  session changed within the idle window. Unknown record shapes do not match.
- The helper writes a redacted copy, verifies it, and only then deletes the raw Claude Code or
  Codex session. A dry run is the default. `--remove` is required to delete.
- The delete step re-checks the session before it runs. It deletes only real paths under the
  agent's session directory, and it never follows a symbolic link.
- An existing copy is replaced only when the new export extends it, or when `--clobber` is given.
- opencode is export-only. Deleting rows from its live database is out of scope for this decision.

## Consequences

- The redacted copy is the only retained copy. Redaction can miss an unknown secret format.
- A session that continues after the learn command is kept.
- A follow-up decision must cover opencode row deletion and the global prompt indexes of
  Claude Code.
