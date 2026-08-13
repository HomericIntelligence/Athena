---
name: advise
description: Retrieve trusted Mnemosyne guidance before unfamiliar planning or implementation. In planning mode, use the checked-out knowledge tree as a best effort without requiring upstream synchronization; report its revision and any trust or freshness limits.
argument-hint: <task description>
allowed-tools: [Read, Bash, Grep, Glob]
---

# Advise

Why: decisions are only as reliable as the current, trusted knowledge behind them.

## Required knowledge gate

Prepare Mnemosyne at `$HOME/.agent_brain/knowledge` under the canonical
[`dependency-resolution` contract](../../docs/dependency-resolution.md). Report the resolved
repository, commit SHA, and trust basis. Outside planning mode, resolution, authentication,
checkout, update, or revalidation failure blocks this skill.

**Planning mode:** before searching, framing options, drafting a plan, or relying on remembered
guidance, inspect the existing knowledge checkout and bind retrieval to its current `HEAD` when
available. Do not require upstream resolution, fetch, fast-forward, or automatic-fork
revalidation. Use the checked-out content as a best effort, and report its repository, current
commit SHA, origin/trust status, and any freshness or verification limitation. A missing checkout
or failed inspection is a limitation to report, not a reason to stop the primary plan; return an
explicit `no applicable durable guidance` result and do not continue retrieval as if knowledge were
available. Never substitute a different repository or silently treat local content as current or
trusted.

## Retrieve

- Search only flat `skills/*.md`; exclude `*.notes.md`; search names, descriptions, categories, tags,
  triggers, failed attempts, and results; and use Git and PR history as provenance.
- Rank by intended outcome, constraints, and failure mode before title or wording. Read at most five
  selected entries completely, preferring newer and better-verified guidance.
- For each result, state its version, verification, concrete relevance, non-relevance boundary,
  contradictions, and failed approaches; clearly label unverified guidance.
- Surface potentially matching open Mnemosyne PRs by candidate artifact or title and report their
  branch and URL. This is a retrieval hint, not duplicate clearance: `learn` must inspect the changed
  content of every open PR semantically before any write.

## Recommend

Treat intent as trigger/context plus desired outcome, not session wording, names, or issue numbers.
Prefer one canonical entry per intent; search history before proposing a name that may have been
consolidated. Route repository audits to `repo-review`, PR audits to `pr-review`, and vary review
depth by mode. Recommend `learn` only for a verified new trigger, corrected command or parameter,
failure mode, or workflow.

## Output

Return the resolved `owner/Mnemosyne` revision, the bound local checkout `HEAD`, or an explicit
no-local-guidance status, together with a table of entry, version, verification, relevance, and
boundary. Include contradictions, what worked or failed, copy-ready parameters, and clearly label
best-effort or unverified guidance.
