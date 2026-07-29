---
name: advise
description: Search the required Mnemosyne knowledge repository before planning or implementation. Uses Athena's canonical dependency-resolution contract and fails if the backend cannot be prepared at ~/.agent_brain/knowledge.
argument-hint: <task description>
allowed-tools: [Read, Bash, Grep, Glob]
---

# Advise

Search durable knowledge before unfamiliar work. Mnemosyne is mandatory; never silently continue
without it.

## Prepare the knowledge repository

With authenticated `gh`, `git`, and network access, prepare Mnemosyne at
`$HOME/.agent_brain/knowledge` by following the canonical
[`dependency-resolution` contract](../../docs/dependency-resolution.md) exactly. Do not summarize or
override its owner precedence, trust gates, checkout rules, or revalidation requirements here.
Report the exact repository, commit SHA, and trust basis. Any resolution, authentication, checkout,
update, or revalidation failure is blocking.

## Planning-mode hard gate

When the host is in planning mode, complete the dependency-resolution sync
before searching, framing options, drafting a plan, or relying on remembered
knowledge. In order: resolve the trusted repository, verify the checkout and
clean origin, fetch and fast-forward it, revalidate automatic-fork trust when
applicable, and bind retrieval to the resulting immutable SHA.

Do not present a partial plan while that sequence is incomplete. A stale tree,
failed fetch, authentication problem, dirty checkout, or failed revalidation is
a planning blocker. Report the failed step and stop; never substitute cached,
local, or similarly named guidance for the required Mnemosyne tree.

## Search contract

- Corpus: `skills/*.md` directly under the checkout.
- Exclude `*.notes.md`; use Git and pull-request history as provenance.
- Search names, descriptions, categories, tags, triggers, failed attempts, and results.
- Select at most five relevant entries, read each completely, and report its version and
  verification level.
- Rank entries by the task's intended outcome, constraints, and failure mode before title or wording
  similarity. For every selected entry, state both the concrete relevance and the boundary where it
  does not apply.
- Prefer newer, better-verified guidance and expose contradictions and failed approaches.
- Query open Mnemosyne pull requests by matched skill path and candidate title. Report an open
  amendment with its branch and URL so a later Learn invocation can stack or stop instead of opening
  a conflicting pull request.

## Consolidation rules

- Prefer one canonical knowledge entry per user intent.
- Search Git history before recommending a name that may have been consolidated.
- Treat a user intent as its trigger/context plus desired outcome, rather than the wording of a
  session summary. Recommend a new entry only when that intent is materially distinct.
- Athena repository reviews use `repo-review`; PR reviews use `pr-review`.
- Quick/default review depth is a mode, not a separate skill.
- Recommend `learn` only for a new trigger, corrected command, parameter, failure mode, or verified
  workflow.

## Output

Return the resolved `owner/Mnemosyne` repository and checkout revision, then a table of entry,
version, verification, relevance, and non-relevance boundary. Follow with what worked, what failed,
contradictions, and copy-ready parameters. Clearly label unverified guidance and explicitly say when
no applicable durable guidance was found.
