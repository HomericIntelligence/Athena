---
name: create-reusable-utilities
description: Port utilities into required Hephaestus automation. Resolves HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER, a canonically forked repository in the current Organization when the viewer has push/maintain/admin permission, or HomericIntelligence/Hephaestus at ~/.agent_brain/automation and fails when unavailable.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# Create reusable utilities

Use this when project-local automation has a demonstrated cross-project use case and belongs in the
shared Hephaestus automation repository.

## Required repository

Resolve Hephaestus in this order:

1. Explicit `HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER`.
2. A GitHub-verified `<current-repository-owner>/Hephaestus` fork when the current owner is an
   Organization, the viewer has push/maintain/admin permission on the current repository, and its
   `parent.full_name` is `HomericIntelligence/Hephaestus`. Modified organization fork content is
   allowed after all gates pass.
3. `HomericIntelligence/Hephaestus`.

Prepare it at `$HOME/.agent_brain/automation` under
[`docs/dependency-resolution.md`](../../docs/dependency-resolution.md). An invalid override,
identity mismatch, authentication failure, or checkout/update failure is blocking.
Report the exact repository, SHA, and trust basis. For an automatic fork, immediately before use
reverify Organization ownership, viewer permission, `parent.full_name`, repository identity,
default branch, tip SHA, and checkout SHA; any mismatch is blocking.

## External-write authority checkpoint

A direct user request to port a utility into the resolved Hephaestus repository authorizes the
declared branch, edit, commit, push, and PR workflow. An indirect recommendation or invocation does
not. Before creating mutable state, show the resolved repository/SHA/trust basis, proposed branch,
owned files, validation, and PR target, then obtain explicit approval. Read-only overlap analysis
never authorizes a later write.

## Workflow

1. Read the source utility, its callers, tests, configuration, error behavior, and license.
2. Search the resolved Hephaestus checkout for equivalent or overlapping behavior. Extend an
   existing abstraction instead of creating a duplicate.
3. Separate reusable behavior from source-repository policy, paths, global state, and output.
4. Design a typed programmatic interface first. Make filesystem, environment, clock, network, and
   process dependencies injectable where useful.
5. Follow the resolved checkout's current package layout and repository instructions; never assume
   example paths from a prior version.
6. Write failing behavior and error-path tests in the resolved repository before implementation.
7. Add a thin CLI only when a real command-line consumer exists. Keep parsing and presentation out
   of the reusable core.
8. Run Hephaestus's repository-defined validation and focused/full tests.
9. Deliver the Hephaestus change through its signed, DCO-attested PR workflow. Do not edit or pin
   another repository as part of the same unapproved operation.

## Acceptance criteria

- No source-repository names, paths, or policy remain in the reusable interface.
- Existing behavior and failures are covered by tests.
- Public types and errors are documented.
- License and attribution are compatible and preserved.
- The source repository migration is a separate, explicit follow-up after the shared change lands.

## Output

Report the resolved Hephaestus repository/SHA, overlap analysis, interface decision, files changed,
tests and gates run, compatibility/migration notes, and PR URL when authorized.
