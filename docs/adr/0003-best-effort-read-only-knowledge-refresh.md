# ADR 0003: Best-effort refresh for read-only Mnemosyne access

**Status:** Accepted

**Supersedes:** The read-only refresh rule in
[ADR 0002](0002-local-first-knowledge-retrieval.md).

## Context

Read-only Mnemosyne use needs a trusted local answer even when `gh`, authentication, or network
access is not available. A validated local checkout already gives a usable commit and a trust
basis. Requiring a fresh remote refresh before read-only work blocks unrelated tasks.

## Decision

For read-only Mnemosyne access:

- Validate the local checkout first.
- Bind the read path to the local `HEAD`.
- Report the checkout, the revision, the trust basis, and the freshness limit.
- Try a refresh only when `gh`, authentication, and network access are available.
- If the refresh cannot run or fails, keep the validated local revision and report the limit.
- Keep durable writes fail closed. Write workflows still require valid identity, clean state, and a
  successful refresh.

## Consequences

- Advice can use a trusted local checkout when `gh` is missing or unusable.
- Read-only results must state when freshness was not verified or updated.
- Write workflows still stop on invalid identity, bad auth, fetch failures, or dirty state.
- ADR 0002 still owns the broader repository-resolution contract. This ADR updates the read-only
  branch only.
