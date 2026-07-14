---
name: create-reusable-utilities
description: Port utilities into required Hephaestus automation. Resolves HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER, a verified fork in the current repository owner, or HomericIntelligence/Hephaestus at ~/.agent_brain/automation and fails when unavailable.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# Create reusable utilities

Use this when project-local automation has a demonstrated cross-project use case and belongs in the
shared Hephaestus automation repository.

## Required repository

Resolve Hephaestus in this order:

1. Explicit `HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER`.
2. A GitHub-verified `<current-repository-owner>/Hephaestus` fork whose parent is
   `HomericIntelligence/Hephaestus`.
3. `HomericIntelligence/Hephaestus`.

Prepare it at `$HOME/.agent_brain/automation` under
[`docs/dependency-resolution.md`](../../docs/dependency-resolution.md). An invalid override,
identity mismatch, authentication failure, or checkout/update failure is blocking.

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
