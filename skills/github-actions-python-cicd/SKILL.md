---
name: github-actions-python-cicd
description: Set up Python GitHub Actions using required Hephaestus automation as the reference. Resolves HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER, a verified fork in the current repository owner, or HomericIntelligence/Hephaestus at ~/.agent_brain/automation and fails when unavailable.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# GitHub Actions for Python

Use this to create or repair required checks and tag releases in a Python repository. The target
repository remains authoritative for its languages, package layout, commands, and release channel.

## Required reference

Resolve Hephaestus through explicit `HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER`, a GitHub-verified fork
in the current repository owner, or `HomericIntelligence/Hephaestus`, in that order. Prepare it at
`$HOME/.agent_brain/automation` under
[`docs/dependency-resolution.md`](../../docs/dependency-resolution.md). Failure is blocking.

Read the resolved checkout's current `_required.yml`, release workflow, `.github/CODEOWNERS`, and
local policies. Treat them as control-pattern guidance, not copy-ready package commands.

## Discover the target contract

Read `AGENTS.md`, manifests, lockfiles, task runners, existing workflows, supported Python
classifiers, test layout, release documentation, GitHub Actions settings, and rulesets. Determine:

- Bootstrap and locked-install command.
- Formatting, lint, typing, unit/integration, build, install-smoke, and security commands.
- Supported runners/Python matrix.
- Artifact and publication channel.
- Required PR policy and branch-protection contexts.

Ask when these sources conflict; never substitute Hephaestus package paths.

## Required workflow design

1. Use `.github/workflows/_required.yml` as the canonical merge gate.
2. Pin third-party Actions to immutable commits with readable version comments.
3. Set least-privilege permissions, timeouts, and concurrency cancellation.
4. Fail closed: no `continue-on-error`, swallowed exit codes, or advisory replacement for a gate.
5. Separate meaningful jobs such as lint, tests, build/package, install smoke, dependency/security
   scans, workflow schema, version/lock sync, and PR policy.
6. Fan every gating job into `required-checks-gate` with `if: always()` and explicit result checks.
7. Use a tag-only release workflow that reruns the release contract and publishes only validated
   artifacts.
8. Put `CODEOWNERS` at `.github/CODEOWNERS` and cover workflows, package metadata, source, tests,
   scripts, and policy files.
9. Verify workflows against the GitHub schema and inspect live Actions/ruleset configuration.

## Output

Report the resolved reference SHA, discovered target contract, jobs and contexts created, pin and
permission choices, commands run, live settings still requiring operator action, and rollback.
