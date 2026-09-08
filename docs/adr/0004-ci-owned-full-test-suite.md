# ADR 0004: CI/CD-owned pytest execution

**Status:** Proposed

## Context

Athena has a fast pytest tier for pull requests and a complete pytest tier with coverage for nightly
and release workflows. Pre-commit also ran the fast tier through `just test-fast`. Thus, a commit
repeated the test tier that the protected pull-request workflow already owns.

New tests still need local evidence before review. A focused run gives fast evidence that a new or
changed test is selected and passes. It does not prove that the complete repository suite passes.

## Decision

- Remove all pytest tiers from pre-commit.
- Keep the remaining pre-commit validation hooks.
- Keep the fast pytest tier in required pull-request CI.
- Keep the complete pytest suite and coverage policy in nightly and release workflows.
- Make CI/CD workflows the only automatic executors of pytest tiers.
- Before a contributor creates a pull request, require a focused local run of each new or changed
  test. The contributor must confirm that the command selects that test and that the test passes.
- Keep `just test` and `just all` available for optional local use.
- Do not use focused local validation as a replacement for required CI.

## Consequences

- Commits do not wait for a pytest tier.
- Pull requests cannot use pre-commit as pytest evidence.
- Pull-request CI detects fast-tier failures. Nightly and release workflows detect failures in the
  complete suite and repository coverage policy.
- Contributors must validate new or changed tests before they create a pull request.
- The pull-request checklist records the focused local validation requirement.

## Alternatives considered

### Keep the fast tier in pre-commit and pull-request CI

This option gives an earlier fast-tier result, but it repeats the required CI gate on each commit.

### Remove all local test validation

This option makes CI the first executor of new tests. It does not give pre-review evidence that a
new test is selected or can pass, so Athena does not select it.
