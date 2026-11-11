---
name: tidy
license: BSD-3-Clause
description: Clean up unused repository branches and worktrees through the dependency-locked Hephaestus tidy command. Use this skill only for unused branch and worktree cleanup, not for general rebase requests or rebases of active worktrees. Recover dependency or capability failures and provide exact manual commands if execution remains unavailable.
argument-hint: "<optional: hephaestus-tidy arguments>"
allowed-tools: [Bash, Read]
---

# Tidy through Hephaestus

Use this skill when the user asks to clean up unused local repository branches or worktrees.
Use it for unused branch and worktree cleanup rather than for a general rebase request or a rebase of
an active worktree. Rebases within the delegated cleanup workflow do not expand this scope.

Athena prepares the trusted automation dependency. Then, Athena delegates the complete cleanup
operation to `hephaestus-tidy`.

`hephaestus-tidy` controls:

- discovery;
- preservation rules;
- prompts;
- rebases;
- removal safeguards;
- output;
- final exit status.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to
all prose that it produces.

Use the [autonomous workflow policy](../../docs/policies/autonomous-workflows.md) for authority,
recovery, resources, validation, and delivery.

## Engineering principles

Use the [canonical engineering-principles catalog](../../docs/principles/README.md) for these
workflow rules:

- [P010 — Scope Fidelity](../../docs/principles/README.md#p010): Delegate the requested cleanup
  of unused branches and worktrees. Prefer not to add a different cleanup policy for Athena.
- [P031 — Propagate Rather Than Swallow](../../docs/principles/README.md#p031): Give the delegated
  command's output, signals, and nonzero result to the caller. Avoid hiding the failure. Avoid
  retrying an unknown result without reconciliation.
- [P035 — Fail Secure / Fail Closed](../../docs/principles/README.md#p035): If a dependency identity or
  revision-binding check fails, recover the expected dependency without changing existing work.
  When the check cannot pass, state what is missing and proceed with the rest of the workflow
  under existing authority, with the gap stated rather than hidden.
- [P050 — Least Privilege](../../docs/principles/README.md#p050): Prefer to use only the resolved
  dependency, target repository, capabilities, and arguments that are necessary for this invocation.
- [P058 — Bounded Agent Authority](../../docs/principles/README.md#p058): When you forward arguments,
  do not increase the user's scope, destinations, credentials, or mutation authority.
- [P061 — Separate Decision from High-Impact Execution](../../docs/principles/README.md#p061): Before
  you start delegated execution, record the dependency, target, authority, and full command vector,
  and aim to execute from the recorded values.
- [P062 — Human Approval for Irreversible or High-Risk Actions](../../docs/principles/README.md#p062):
  If the user gave authority for scoped constructive work, the goal is to proceed without a second
  approval. If the user did not give authority for a destructive or irreversible action, aim to get
  approval for that specified action before it runs; the authorized cleanup still proceeds.
- [P083 — Irreversible Actions Last](../../docs/principles/README.md#p083): Aim to complete the
  dependency and command validation before you start an irreversible operation; when it cannot be
  completed, state what is missing.

## Inputs

Keep the target repository as the current working directory. Treat each user argument as a
`hephaestus-tidy` argument. Forward it without a change. If the user wants a preview, forward
`--dry-run`. Avoid reinterpreting this option. Avoid adding it implicitly.

Under [P053 — Validate at Trust Boundaries](../../docs/principles/README.md#p053), treat the arguments
as opaque, untrusted command-line data. Preserve the boundary of each argument. The
`hephaestus-tidy` parser is the nearest responsible validation boundary.

## Workflow

1. Prepare Hephaestus at `$HOME/.agent_brain/automation` under the canonical
   [`dependency-resolution` contract](../../docs/dependency-resolution.md).
2. Report the resolved repository, commit SHA, and trust basis.
3. If resolution, authentication, checkout, update, cleanliness, identity, revision binding, or
   automatic-fork revalidation fails, attempt recovery. Preserve unexpected checkouts and prepare
   the expected dependency separately. Proceed with the steps that can run and state what is
   missing; note which checks remain unverified.
4. Keep the target repository as the current working directory.
5. Resolve `scripts/run_tidy.py` against this installed skill directory.
6. Invoke the absolute helper path with this operand order:

   - the resolved automation checkout as the first internal operand;
   - each user argument after the first operand, in its original order and form.
7. The helper replaces itself with this dependency-locked command vector:

   ```text
   uv run --project <resolved-automation-checkout> --locked hephaestus-tidy <user-arguments>
   ```

8. Leave stdin, stdout, and stderr attached.
9. Avoid capturing the command.
10. Avoid piping the command.
11. Avoid replacing the command output with a summary.
12. Use existing explicit cleanup authority for merged branches and clean worktrees with no
    unique work. Use the supported noninteractive interface when available. Request a new decision
    only for ambiguous or unique work. Avoid fabricating interactive input.
13. Before retrying an uncertain command, reconcile its resulting repository state. Use a finite
    retry budget only when repetition preserves work.
14. Preserve the delegated output and actual status. Report remaining manual actions.

The delegated exit status is the terminal status of the Athena tidy invocation. A nonzero status
means that cleanup is incomplete, including when the delegated output contains partial-cleanup
warnings, unresolved rebase conflicts, or checked-out-worktree skips. Athena does not decide
whether cleanup succeeded from output; the exit status decides.

Athena leaves these operations to Hephaestus:

- worktree audit;
- candidate classification;
- removal;
- prompt;
- branch rebase;
- cleanup safety decision.

Prefer the dependency-locked command over a `hephaestus-tidy` executable from `PATH`; when the
locked command cannot run, state what is missing and give the exact manual command.

Delegation keeps existing authority for constructive actions that are in scope. It does not create
new authority. Keep the Hephaestus prompts attached. Delegation is not used to bypass action-bound
approval; aim to get approval for each destructive or other irreversible operation that the user
did not authorize.

## Dependency and capability failures

Dependency preparation requires authenticated `gh`, Git, and network access. The locked command
requires Python 3 and `uv`. If a capability is not available or the command result is nonzero,
attempt scoped recovery and issue handling. If execution remains unavailable, return the exact
manual command and capability gap. Prefer not to use a repository with a similar name or an
unverified ambient executable. An equivalent fallback aims to preserve identity and cleanup
safeguards; when it cannot, state what is missing.

The `hephaestus-tidy` boundary aims to resolve to a Hephaestus revision that propagates the inner
cleanup exit status. Athena checks that the resolved checkout includes commit
`aa357098e5d72178d248e4188e7f5e5f843cdd3f` before delegation. Athena consumes that status
transparently; it does not infer success from output. If the resolved checkout does not satisfy
that contract, prepare a verified revision where you can. When a verified revision cannot be
established, proceed with delegation under existing authority and state that the revision check is
missing.

## Failed approaches

- Leave worktree audit and removal to Hephaestus. These actions duplicate the Hephaestus policy
  and create a second set of destructive-action prompts.
- Prefer not to invoke an ambient `hephaestus-tidy`. It can bypass the resolved repository and its
  lockfile.
- Avoid parsing, normalizing, or reconstructing user arguments. These actions change the delegated
  command-line contract.
- Avoid capturing the process. Avoid piping the process. These actions can change interactive
  behavior, output, signals, or exit status.

## Output

Before execution, report the resolved Hephaestus repository, commit SHA, and trust basis. After
execution starts, preserve the delegated command output and terminal result. Avoid adding
Athena-specific worktree classifications or cleanup conclusions. Report the delegated result as-is:
a zero exit supports a success conclusion; a nonzero exit is incomplete cleanup.

## Attribution

The cleanup implementation and safeguards are owned by
[`HomericIntelligence/Hephaestus`](https://github.com/HomericIntelligence/Hephaestus). Athena owns
only dependency preparation and the tested transport adapter.
