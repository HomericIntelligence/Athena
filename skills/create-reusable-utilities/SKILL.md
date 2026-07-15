---
name: create-reusable-utilities
description: Port utilities into required Hephaestus automation. Uses Athena's canonical dependency-resolution contract and fails if ~/.agent_brain/automation cannot be prepared.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# Create reusable utilities

Use this when project-local automation has a demonstrated cross-project use case and belongs in the
shared Hephaestus automation repository.

## Required repository

Prepare Hephaestus at `$HOME/.agent_brain/automation` by following the canonical
[`dependency-resolution` contract](../../docs/dependency-resolution.md) exactly. Do not restate its
owner precedence, trust gates, checkout rules, or revalidation requirements in this skill. Report
the exact repository, commit SHA, and trust basis. Any preparation or revalidation failure is
blocking.

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
