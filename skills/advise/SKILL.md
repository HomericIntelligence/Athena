---
name: advise
description: Search the required Mnemosyne knowledge repository before planning or implementation. Resolves HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER, a verified fork in the current repository owner, or HomericIntelligence/Mnemosyne, and fails if the backend cannot be prepared at ~/.agent_brain/knowledge.
argument-hint: <task description>
allowed-tools: [Read, Bash, Grep, Glob]
---

# Advise

Search durable knowledge before unfamiliar work. Mnemosyne is mandatory; never silently continue
without it.

## Resolve the knowledge repository

Requirements: authenticated `gh`, `git`, and network access.

Resolve the owner in this order:

1. If `HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER` is non-empty, use it. If that repository cannot be
   read, fail; an explicit override never falls back.
2. Determine the current repository owner with `gh repo view --json owner --jq .owner.login`. If
   `<current-owner>/Mnemosyne` exists and GitHub reports that it is a fork whose
   `parent.full_name` is `HomericIntelligence/Mnemosyne`, use it.
3. Otherwise use `HomericIntelligence/Mnemosyne`.

The canonical checkout is `$HOME/.agent_brain/knowledge`. Create `$HOME/.agent_brain` when needed.
If the checkout does not exist, clone the resolved repository there. If it exists, require its
`origin` to match the resolved repository, fetch `origin`, determine the remote default branch, and
fast-forward that branch. Never overwrite local changes or silently retarget an existing checkout.

Fail with the exact failed prerequisite, repository, or checkout mismatch when resolution,
authentication, clone, fetch, or fast-forward fails.

## Search contract

- Corpus: `skills/*.md` directly under the checkout.
- Exclude `*.notes.md`; treat matching `.history` files as provenance.
- Search names, descriptions, categories, tags, triggers, failed attempts, and results.
- Select at most five relevant entries, read each completely, and report its version and
  verification level.
- Prefer newer, better-verified guidance and expose contradictions and failed approaches.

## Consolidation rules

- Prefer one canonical knowledge entry per user intent.
- Search history before recommending a name that may have been consolidated.
- Athena repository reviews use `repo-review`; PR reviews use `pr-review`.
- Quick/default review depth is a mode, not a separate skill.
- Recommend `learn` only for a new trigger, corrected command, parameter, failure mode, or verified
  workflow.

## Output

Return the resolved `owner/Mnemosyne` repository and checkout revision, then a table of entry,
version, verification, and relevance. Follow with what worked, what failed, contradictions, and
copy-ready parameters. Clearly label unverified guidance.
