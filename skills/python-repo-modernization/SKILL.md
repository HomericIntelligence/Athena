---
name: python-repo-modernization
description: Modernize a Python repository using required Hephaestus automation as a reference. Resolves HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER, a verified fork in the current repository owner, or HomericIntelligence/Hephaestus at ~/.agent_brain/automation and fails when unavailable.
argument-hint: <path to Python repository>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# Python repository modernization

Use this for a Python repository with mixed legacy and modern practices. Modernization follows the
target's product requirements; it is not a mechanical conversion to one package layout.

## Required reference

Resolve Hephaestus using explicit `HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER`, a GitHub-verified fork
in the current repository owner, or `HomericIntelligence/Hephaestus`. Prepare it at
`$HOME/.agent_brain/automation` under
[`docs/dependency-resolution.md`](../../docs/dependency-resolution.md). Failure is blocking.

Use the resolved checkout to study current policy, typing, testing, CI, security, and release
patterns. Substitute the target repository's package name, source layout, commands, and publication
model everywhere.

## Workflow

1. Establish a green or honestly documented baseline: imports, tests, coverage, lint, typing,
   build, installed-artifact smoke test, dependency audit, and workflow state.
2. Read public API and compatibility requirements before moving modules or removing shims.
3. Fix correctness and circular-import issues with regression tests first.
4. Select flat or `src/` layout based on the target's import and packaging needs; do not impose the
   reference layout.
5. Align tests with behavioral boundaries. Require focused unit/error tests and integration or
   installed-artifact tests where they catch distinct failures.
6. Centralize tool configuration and commit the authoritative dependency lock.
7. Add typed-package metadata only when the package ships inline types.
8. Add fail-fast pre-commit and required GitHub checks using `github-actions-python-cicd`.
9. Build the actual release artifacts, inspect contents, install them outside the checkout, and
   verify public imports/commands.
10. Document supported versions, installation, upgrades, compatibility, release, and rollback.

## Guardrails

- Preserve public behavior unless a breaking change and migration are explicitly approved.
- Do not hide failing tests, lower coverage merely to pass, or exclude hard modules without tested
  justification.
- Do not mix environment managers over one site-packages tree.
- Never claim PyPI or another registry publication without a real authenticated publish result.

## Output

Return the resolved reference SHA, baseline, modernization decisions, compatibility impact, files
changed, exact gate results, artifact inspection/install evidence, and remaining release actions.
