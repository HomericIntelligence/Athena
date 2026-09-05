---
name: tidy
license: BSD-3-Clause
description: Delegate repository branch and worktree cleanup to the dependency-locked Hephaestus tidy command. Use this skill for a tidy, cleanup, or rebase request. Stop if the trusted automation checkout or a required execution capability cannot be prepared.
argument-hint: "<optional: hephaestus-tidy arguments>"
allowed-tools: [Bash, Read]
---

# Tidy through Hephaestus

Use this skill when the user asks to tidy, clean up, or rebase local repository branches or
worktrees. Athena prepares the trusted automation dependency. Then, Athena delegates the complete
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

## Engineering principles

Use the [canonical engineering-principles catalog](../../docs/principles/README.md) for these
workflow rules:

- [P010 — Scope Fidelity](../../docs/principles/README.md#p010): Delegate only the requested tidy,
  cleanup, or rebase operation. Do not add a different cleanup policy for Athena.
- [P031 — Propagate Rather Than Swallow](../../docs/principles/README.md#p031): Give the delegated
  command's output, signals, and nonzero result to the caller. Do not hide the failure. Do not
  automatically retry it.
- [P035 — Fail Secure / Fail Closed](../../docs/principles/README.md#p035): If a dependency identity or
  revision-binding check is not satisfactory, stop. If the checkout is not clean, stop. If a
  necessary capability is not available, stop.
- [P050 — Least Privilege](../../docs/principles/README.md#p050): Use only the resolved dependency,
  target repository, capabilities, and arguments that are necessary for this invocation.
- [P058 — Bounded Agent Authority](../../docs/principles/README.md#p058): When you forward arguments,
  do not increase the user's scope, destinations, credentials, or mutation authority.
- [P061 — Separate Decision from High-Impact Execution](../../docs/principles/README.md#p061): Before
  you start delegated execution, record the dependency, target, authority, and full command vector.
  Validate the record. During execution, use only the recorded values.
- [P062 — Human Approval for Irreversible or High-Risk Actions](../../docs/principles/README.md#p062):
  If the user gave authority for scoped constructive work, do not request a second approval. If the
  user did not give authority for a destructive or irreversible action, request approval for that
  specified action.
- [P083 — Irreversible Actions Last](../../docs/principles/README.md#p083): Before you start an
  irreversible operation, complete the dependency and command validation.

## Inputs

Keep the target repository as the current working directory. Treat each user argument as a
`hephaestus-tidy` argument. Forward it without a change. If the user wants a preview, forward
`--dry-run`. Do not reinterpret this option. Do not add it implicitly.

Under [P053 — Validate at Trust Boundaries](../../docs/principles/README.md#p053), treat the arguments
as opaque, untrusted command-line data. Preserve the boundary of each argument. The
`hephaestus-tidy` parser is the nearest responsible validation boundary.

## Workflow

1. Prepare Hephaestus at `$HOME/.agent_brain/automation` under the canonical
   [`dependency-resolution` contract](../../docs/dependency-resolution.md).
2. Report the resolved repository, commit SHA, and trust basis.
3. If resolution, authentication, checkout, update, cleanliness, identity, revision binding, or
   automatic-fork revalidation fails, stop.
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
9. Do not capture the command.
10. Do not pipe the command.
11. Do not replace the command output with a summary.
12. Do not answer an interactive prompt from Hephaestus. The user answers each prompt.
13. Do not retry the command.
14. Do not otherwise mediate it.

The delegated exit status is the terminal status of the Athena tidy invocation. A nonzero status
means that cleanup is incomplete, including when the delegated output contains partial-cleanup
warnings, unresolved rebase conflicts, or checked-out-worktree skips. Athena does not inspect or
interpret delegated output to decide whether cleanup succeeded.

Athena does not do these operations:

- worktree audit;
- candidate classification;
- removal;
- prompt;
- branch rebase;
- cleanup safety decision.

Do not replace the dependency-locked command with a `hephaestus-tidy` executable from `PATH`.

Delegation keeps existing authority for constructive actions that are in scope. It does not create
new authority. Keep the Hephaestus prompts attached. Do not use delegation to bypass action-bound
approval. This restriction applies to each destructive or other irreversible operation that the user
did not authorize.

## Dependency and capability failures

Dependency preparation requires authenticated `gh`, Git, and network access. The locked command
requires Python 3 and `uv`. If a capability is not available or the command result is nonzero,
return the failure without a change. In that case, stop. Do not use a stale checkout, a repository with a
similar name, an ambient executable, or a second cleanup implementation.

The `hephaestus-tidy` boundary must resolve to a Hephaestus revision that propagates the inner
cleanup exit status. Athena consumes that status transparently; it does not infer success from
output. If the resolved checkout does not satisfy that contract, stop.

## Failed approaches

- Do not audit worktrees in Athena. Do not remove worktrees in Athena. These actions duplicate the
  Hephaestus policy and create a second set of destructive-action prompts.
- Do not invoke an ambient `hephaestus-tidy`. It can bypass the resolved repository and its lockfile.
- Do not parse user arguments. Do not normalize user arguments. Do not reconstruct user arguments.
  These actions change the delegated command-line contract.
- Do not capture the process. Do not pipe the process. These actions can change interactive behavior,
  output, signals, or exit status.

## Output

Before execution, report the resolved Hephaestus repository, commit SHA, and trust basis. After
execution starts, preserve the delegated command output and terminal result. Do not add
Athena-specific worktree classifications or cleanup conclusions. Report the delegated result as-is:
success conclusions require a zero exit, and a nonzero exit is incomplete cleanup.

## Attribution

The cleanup implementation and safeguards are owned by
[`HomericIntelligence/Hephaestus`](https://github.com/HomericIntelligence/Hephaestus). Athena owns
only dependency preparation and the tested transport adapter.
