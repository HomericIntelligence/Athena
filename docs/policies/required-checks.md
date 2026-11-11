# Required-check policy

Apply the [ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md) to all English
technical prose in this document.

Athena runs `.github/workflows/_required.yml` as its check workflow. Each GitHub Action has an
immutable commit pin and a readable version comment. Each action also carries minimum permissions
and a timeout.

This document describes what those checks look at and what the jobs report. The jobs are
instrumentation for the repository; they are not a verdict on a change, and nothing here promises
merge or release readiness.

## What the checks report

- `agent-contract / validate-agent-contract` checks root `AGENTS.md` and `CLAUDE.md` against the
  canonical Athena principles catalog. The reusable workflow has read-only permission. It accepts
  no input and no secret.
- `forbid-suppressions` reports silent-failure workarounds. `continue-on-error: true` also shows
  up there.
- `validate` reports:

  - each skill and host manifest;
  - the fast unit-test tier on pull requests, pushes, merge groups, scheduled runs, and manual
    runs;
  - for a release, all unit tests for executable scripts;
  - for a release, at least 80% branch coverage for each repository script and skill-local
    executable script;
  - Ruff, formatting, and strict mypy on repository scripts and skill-local scripts.

  Pre-commit does not run pytest. A pull request can be published with pending validation, and
  pending, failed, and unavailable checks are reported accurately. A focused run of the new or
  changed tests on a local or hosted runner complements those tiers.

- `markdownlint` covers public documents and the shipped `skills/**/*.md` product corpus. It does
  not verify ASD-STE100 conformance. Prose review happens under the
  [ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md).
- `workflow-schema` validates GitHub workflow syntax.
- `justfile-check` verifies that documented task entry points parse.
- `security/secrets-scan` scans the complete Git history for secrets.
- `package` builds and inspects a deterministic portable plugin archive:

  - it rejects members that look unsafe, generated Python members, misplaced Python members, and
    members that look like credentials;
  - it ignores Python cache directories;
  - it permits tested helpers in skill-local script directories;
  - it permits the shared `skills/_cli.py` factory;
  - it emits a SHA-256 checksum;
  - it generates checksummed plugin and Linux build-environment Software Package Data Exchange
    (SPDX) 2.3 software bills of materials (SBOMs);
  - it generates native Syft inventories for the build environment and the locked, isolated
    coding-harness runtime.

- `security/dependency-scan` does these things:

  - it scans both internal inventories with a locked Grype version;
  - it uses a current database that passed hash validation;
  - it reports and fails on fixable Critical and High findings unless a valid exception covers the
    finding;
  - a valid exception is narrow, owned, linked, and not expired;
  - the linked Athena issue is open;
  - it retains the full JavaScript Object Notation (JSON) reports.

- `security/pi-upstream-inventory-watch` is the single advisory job. It runs on the weekly schedule
  or by manual dispatch. A manual dispatch also runs the other jobs. The job scans the full
  upstream Pi source tree. It records upstream inventory evidence for tracking only and stays out
  of `required-checks-gate` while upstream-only findings can fail the scan. It tracks
  [Issue #74](https://github.com/HomericIntelligence/Athena/issues/74). Athena retires it when the
  full Pi source inventory is restored into the gate.

- On pull requests, `pr-policy` checks these items:

  - applicable issue linkage;
  - signed commits;
  - Developer Certificate of Origin (DCO) sign-offs; and
  - Conventional Commit subjects.

- `required-checks-gate` depends on each gating job and fails when a gating job fails.

A new gating job is usually added to `required-checks-gate`. Advisory jobs are presented as
advisory, not as required. The tracked `main` ruleset uses the GitHub merge queue for normal
target integration and merge-group validation.

A branch that is behind `main` but has no reported merge conflict does not gain anything from an
agent rebase. Target movement does not invalidate review of unchanged candidate content. The merge
queue owns normal target integration and merge-group validation.

## Test tiers

The `nightly` pytest marker identifies integration-heavy tests. These tests use Git repositories,
installed package trees, or many subprocesses. The fast tier uses `not nightly`. New tests start in
the fast tier; an author can add the `nightly` marker for integration-heavy tests.

Pull-request continuous integration (CI) runs the fast test tier. Pre-commit does not run pytest.
The full test suite runs each day at 09:17 Coordinated Universal Time (UTC). The nightly workflow
also supports a manual run. It does not join `required-checks-gate`.

A release calls the required workflow with `full-tests: true`. Thus, a release runs the full test
suite and the coverage policy for the exact release revision.

The initial tier selection used these runtime classification criteria:

- Evaluate a pre-commit hook or pull-request job only when its representative runtime is at least
  one minute.
- Keep approximately 10% of the current test runtime in the fast tier.
- Put approximately 90% of the current test runtime in the nightly tier.

These percentages are selection guidance. They are not execution time limits. The repository does
not fail a test tier because its runtime ratio changes. Sub-minute validation, static-analysis,
documentation, workflow, policy, package, and security jobs stay unchanged.

## The agent-contract job

Athena calls `.github/workflows/_agent-contract.yml` from its required and release workflows. The
workflow checks out the caller revision. The called Athena revision supplies the validator and
catalog. The validator reads only the caller's root `AGENTS.md` and `CLAUDE.md` files.

A consumer calls this job this way:

```yaml
jobs:
  agent-contract:
    name: agent-contract
    permissions:
      contents: read
    uses: >-
      HomericIntelligence/Athena/.github/workflows/_agent-contract.yml@agent-contract-v1.0.0
```

This call emits the `agent-contract / validate-agent-contract` check. Adding the caller job to a
repository's aggregate checks is the documented pattern.

Release publication goes through the protected `release` environment, whose configuration covers
maintainer reviewers and tag policies for `v*` and `agent-contract-v*` (both type `tag`). The
release workflow reads the environment configuration before publication. See
[`CONTRIBUTING.md`](../../CONTRIBUTING.md) for the rollback and re-release procedure.

The required workflow handles the `merge_group` `checks_requested` event. It also handles these
entry points:

- pull request;
- push;
- reusable workflow; and
- scheduled run.

The concurrency key includes the event type. Thus, a scheduled or reusable run does not cancel a
pull-request, merge-group, or push run for the same revision. Manual dispatch runs the workflow
entry points as configured. The advisory Pi watch is the only job that runs exclusively for
manual dispatch or the weekly schedule.

The tracked `main` ruleset records this staged merge-queue policy. This block mirrors these
parameters. The tracked ruleset stays in step with this block, and changes land in both places
together:

<!-- athena:merge-queue-parameters -->
```json
{
  "check_response_timeout_minutes": 180,
  "grouping_strategy": "HEADGREEN",
  "max_entries_to_build": 10,
  "max_entries_to_merge": 5,
  "merge_method": "SQUASH",
  "min_entries_to_merge": 1,
  "min_entries_to_merge_wait_minutes": 5
}
```

The required workflow also runs each week. Thus, dependency findings are refreshed between
changes.

## Tag releases

Tag releases use a signed, annotated Semantic Versioning (SemVer) tag. Its
version agrees with each host manifest. Its target is reachable from protected `main`. Release
jobs do these things:

1. They invoke the complete required workflow.
2. They verify the exact six-file archive and SBOM set.
3. They verify the three checksum pairs in that set.
4. They parse both SPDX identities.
5. They publish the files from that run.

[Issue #163](https://github.com/HomericIntelligence/Athena/issues/163) owns the protected
`agent-contract-v*` release and its live tag ruleset.

The tracked `.github/rulesets/homeric-agent-contract-tags.json` policy targets only
`refs/tags/agent-contract-v*`. It blocks tag update and deletion, and it permits the first tag
creation. The live ruleset matches the tracked policy before tag creation. The protected
`release` environment holds `AGENT_CONTRACT_RULESET_PROOF_TOKEN`, a fine-grained token for this
repository with Administration permission set to read-only. Only the live ruleset readback step
uses this token. The default Actions token does not surface the ruleset's detailed response and
cannot show a no-bypass configuration.

The `agent-contract-v*` release path is separate from the package `v*` release path. It invokes
the agent-contract provider and the complete required workflow. It does not publish plugin
archives or npm packages. Its GitHub Release body is the release record. The record contains the
tag object SHA, commit SHA, catalog SHA-256, required workflow run URLs, live ruleset readback,
tagged URL results, and the update and deletion rejection evidence. Use the
[`agent-contract-v1.0.0` release runbook](../runbooks/agent-contract-v1.0.0-release.md) for the
operation and recovery steps.
