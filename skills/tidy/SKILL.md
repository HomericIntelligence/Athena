---
name: tidy
license: BSD-3-Clause
description: Delegate repository branch and worktree cleanup to the dependency-locked Hephaestus tidy command. Use for tidy, cleanup, or rebase requests; fail closed when the trusted automation checkout or required execution capability cannot be prepared.
argument-hint: "<optional: hephaestus-tidy arguments>"
allowed-tools: [Bash, Read]
---

# Tidy through Hephaestus

Use this when the user asks to tidy, clean up, or rebase a repository's local branches or
worktrees. Athena prepares the trusted automation dependency and delegates the complete operation;
`hephaestus-tidy` owns discovery, preservation rules, prompts, rebases, removal safeguards, output,
and the final exit status.

Apply the [ASD-STE100 writing policy](../../docs/technical-english.md) to this skill and to all prose
that it produces.

## Engineering principles

Use the [canonical engineering-principles catalog](../../docs/principles/README.md) through these
workflow-specific rules:

- [P010 — Scope Fidelity](../../docs/principles/README.md#p010): delegate only the requested tidy,
  cleanup, or rebase operation and do not add a second Athena cleanup policy.
- [P031 — Propagate Rather Than Swallow](../../docs/principles/README.md#p031): preserve the delegated
  command's output, signals, and nonzero result instead of masking or retrying a failure.
- [P035 — Fail Secure / Fail Closed](../../docs/principles/README.md#p035): stop when dependency
  identity, revision binding, checkout cleanliness, or a required capability cannot be established.
- [P050 — Least Privilege](../../docs/principles/README.md#p050): use only the resolved dependency,
  target repository, capabilities, and arguments required by this invocation.
- [P058 — Bounded Agent Authority](../../docs/principles/README.md#p058): forwarding arguments does
  not widen the user's requested scope, destinations, credentials, or mutation authority.
- [P061 — Separate Decision from High-Impact Execution](../../docs/principles/README.md#p061): bind
  the dependency, target, authority, and exact command vector before starting delegated execution.
- [P062 — Human Approval for Irreversible or High-Risk Actions](../../docs/principles/README.md#p062):
  preserve existing authorization for scoped constructive work without redundant prompts, while
  leaving destructive or otherwise ungranted irreversible actions behind action-bound approval.
- [P083 — Irreversible Actions Last](../../docs/principles/README.md#p083): finish dependency and
  command validation before handing control to an operation that may cross a point of no return.

## Inputs

Keep the target repository as the current working directory. Treat every argument supplied to this
skill as a `hephaestus-tidy` argument and forward it unchanged. When the user wants a preview,
forward `--dry-run`; do not reinterpret it or add it implicitly.

Treat arguments as opaque, untrusted CLI data under
[P053 — Validate at Trust Boundaries](../../docs/principles/README.md#p053). Preserve their argument
boundaries; Hephaestus's parser is the nearest responsible validation boundary.

## Workflow

1. Prepare Hephaestus at `$HOME/.agent_brain/automation` under the canonical
   [`dependency-resolution` contract](../../docs/dependency-resolution.md). Report the resolved
   repository, commit SHA, and trust basis. Resolution, authentication, checkout, update,
   cleanliness, identity, revision-binding, or automatic-fork revalidation failure is blocking.
2. Keep the target repository as the current working directory. Resolve `scripts/run_tidy.py`
   against this installed skill directory and invoke that absolute helper path with the resolved
   automation checkout as its first internal operand, followed by every user argument in its
   original order and form.
3. The helper replaces itself with this dependency-locked command vector:

   ```text
   uv run --project <resolved-automation-checkout> --locked hephaestus-tidy <user-arguments>
   ```

4. Leave stdin, stdout, and stderr attached. Do not capture, pipe, summarize in place of, answer,
   retry, or otherwise mediate the command. The user answers any interactive prompt emitted by
   Hephaestus.

Athena performs no worktree audit, candidate classification, removal, prompt, branch rebase, or
cleanup safety decision of its own. It never substitutes a `hephaestus-tidy` executable found on
`PATH` for the dependency-locked command.

Delegation neither withdraws already granted authority for scoped constructive actions nor creates
new authority. Keep Hephaestus's prompts attached, and never use delegation to bypass action-bound
approval for destructive or otherwise ungranted irreversible operations.

## Dependency and capability failures

Authenticated `gh`, Git, and network access are required by dependency preparation. Python 3 and
`uv` are required to start the locked command. On any missing capability or nonzero command result,
return the failure unchanged and stop. Do not fall back to a stale checkout, a similarly named
repository, an ambient executable, or a second cleanup implementation.

## Failed approaches

- Auditing and removing worktrees in Athena duplicated Hephaestus policy and produced a second set
  of destructive-action prompts.
- Invoking an ambient `hephaestus-tidy` could bypass the resolved repository and its lockfile.
- Parsing, normalizing, or reconstructing user arguments changed the delegated CLI contract.
- Capturing or piping the process could alter interactive behavior, output, signals, or exit status.

## Output

Before execution, report the resolved Hephaestus repository, commit SHA, and trust basis. After
that, preserve the delegated command's output and terminal result without adding Athena-specific
worktree classifications or cleanup conclusions.

## Attribution

The cleanup implementation and safeguards are owned by
[`HomericIntelligence/Hephaestus`](https://github.com/HomericIntelligence/Hephaestus). Athena owns
only dependency preparation and the tested transport adapter.
