# ADR 0002: Local-first knowledge retrieval

**Status:** Accepted

**Supersedes:** The Mnemosyne hard-dependency classification and the fail-closed
knowledge-detection consequence in [ADR 0001](0001-plugin-distro-scope-policy.md). ADR 0001
continues to define the plugin-only distribution boundary and the two repository locations.

## Context

Athena can use Mnemosyne to add durable guidance to a primary task. Earlier policy required current
remote identity, authentication, checkout synchronization, and revalidation before most advice.
Thus, a network, authentication, freshness, or helper failure could stop unrelated local work.

An installed Athena plugin contains the skill instructions and the bounded selector that apply to
that plugin version. Read-only guidance does not change Mnemosyne or another system. Requiring the
newest remote repository for this read path couples plugin usability to external state without a
corresponding mutation risk.

The `learn` skill has a second usability problem. A broad generalization rule can reject a lesson
only because its source is specific. A specific case can contain a new constraint, decision branch,
failure mode, command, or parameter even when a general entry already exists.

## Decision

Use local-first, best-effort behavior for all read-only Mnemosyne access:

- Use an available local checkout without a clone, fetch, fast-forward, or remote trust check.
- Bind guidance to the local commit identifier and report freshness and verification limits.
- Do not require the installed Athena revision and the Mnemosyne revision to be the newest versions
  or to have matching versions.
- If the local checkout or primary selector is unavailable, stop only knowledge retrieval. Continue
  the primary task. A bounded direct-file fallback can replace the selector.
- Treat remote pull-request discovery as optional during read-only work.

Keep fail-closed behavior at a mutation or execution boundary:

- Before a durable Mnemosyne write, resolve the repository, synchronize the delivery base, inspect
  related open pull requests, and validate the proposed artifact set.
- Before Athena executes Hephaestus automation, complete its repository trust and revision checks.
- Keep privacy, secret, allowed-path, isolated-worktree, exact-PR-identity, and evidence controls.

For learning, assess the decision value of a specific case. Amend a general entry when the case adds
a new trigger, constraint, branch, failure mode, command, parameter, or necessary example. Reject it
as already covered only when the rule and existing examples produce the same decision.

This decision applies [P006 — POLA — Principle of Least Astonishment](../principles/README.md#p006),
[P009 — General Mechanisms Over Special Cases](../principles/README.md#p009),
[P013 — AHA — Avoid Hasty Abstractions](../principles/README.md#p013), and
[P036 — Graceful Degradation](../principles/README.md#p036). It keeps
[P035 — Fail Secure / Fail Closed](../principles/README.md#p035) at boundaries that can change or
execute external state.

## Consequences

- Advice can use an older local knowledge revision and must identify it as best effort.
- A missing knowledge checkout no longer blocks the primary task.
- `learn` can classify a candidate without local or remote knowledge access. It cannot publish until
  it completes duplicate, privacy, repository, and delivery checks.
- Installed plugin versions remain usable when a repository cannot update.
- Read-only results can omit remote provenance. The output must state this limit.
- Mnemosyne writes and Hephaestus execution keep their strict trust boundaries.
