# Required-check policy

Apply the [ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md) to all English technical
prose in this document.

Athena uses `.github/workflows/_required.yml` as the canonical merge gate. Each GitHub Action has an
immutable commit pin and a readable version comment. Each action also has minimum permissions and a
timeout.

## Canonical contexts

- `agent-contract / validate-agent-contract` checks root `AGENTS.md` and `CLAUDE.md` against the
  canonical Athena principles catalog. The reusable workflow has read-only permission. It accepts
  no input and no secret.
- `forbid-suppressions` rejects silent-failure workarounds. It also rejects
  `continue-on-error: true`.
- `validate` does these checks:

  - It validates each skill and host manifest.
  - It runs unit tests for executable scripts.
  - It requires at least 80% branch coverage for each repository script and skill-local executable
    script.
  - It enforces Ruff, formatting, and strict mypy on repository scripts and skill-local scripts.

- `markdownlint` validates public documents and the shipped `skills/**/*.md` product corpus. It does
  not verify ASD-STE100 conformance. Review applicable prose under the
  [ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md).
- `workflow-schema` validates GitHub workflow syntax.
- `justfile-check` makes sure that documented task entry points parse.
- `security/secrets-scan` scans the complete Git history for secrets.
- `package` does these actions:

  - It builds and inspects a deterministic portable plugin archive.
  - It rejects unsafe members, generated Python members, misplaced Python members, and members that
    look like credentials.
  - It ignores Python cache directories.
  - It permits tested helpers in skill-local script directories.
  - It permits the shared `skills/_cli.py` factory.
  - It emits a SHA-256 checksum.
  - It generates checksummed plugin and Linux build-environment Software Package Data Exchange
    (SPDX) 2.3 software bills of materials (SBOMs).
  - It generates native Syft inventories for the build environment and the locked, isolated
    coding-harness runtime.

- `security/dependency-scan` does these actions:

  - It scans both internal inventories with a locked Grype version.
  - It uses a current database that passed hash validation.
  - It blocks fixable Critical and High findings unless a valid exception covers the finding.
  - A valid exception must be narrow, owned, linked, and not expired.
  - The linked Athena issue must be open.
  - It retains the full JavaScript Object Notation (JSON) reports.

- `security/pi-upstream-inventory-watch` is the single intentional advisory job. It runs on the
  weekly schedule or by manual dispatch, and scans the full upstream Pi source tree. It must not join
  `required-checks-gate` while upstream-only findings can fail the scan.

- On pull requests, `pr-policy` enforces these requirements:

  - applicable issue linkage;
  - signed commits;
  - Developer Certificate of Origin (DCO) sign-offs; and
  - Conventional Commit subjects.

- `required-checks-gate` depends on each gating job. It fails if a gating job is not successful.

Add each new gating job to `required-checks-gate`. Never represent an advisory job as required. The
tracked `main` ruleset and the live `main` ruleset require `required-checks-gate` to pass against the
current `main` base before merge.

Athena calls `.github/workflows/_agent-contract.yml` from its required and release workflows. The
workflow checks out the caller revision. The called Athena revision supplies the validator and
catalog. The validator reads only the caller's root `AGENTS.md` and `CLAUDE.md` files.

A consumer uses this job after issue #163 publishes and protects the version tag:

```yaml
jobs:
  agent-contract:
    name: agent-contract
    permissions:
      contents: read
    uses: >-
      HomericIntelligence/Athena/.github/workflows/_agent-contract.yml@agent-contract-v1.0.0
```

This call emits the `agent-contract / validate-agent-contract` check. Add the caller job to the
repository's aggregate required gate.
Release publication is also gated by the protected `release` environment, which requires maintainer
approval. The release workflow reads that environment configuration before publication and fails if
the required reviewers or the `v*` tag policy are missing. See [`CONTRIBUTING.md`](../../CONTRIBUTING.md)
for the rollback and re-release procedure.

The required workflow handles the `merge_group` `checks_requested` event. It also handles these entry
points:

- pull request;
- push;
- reusable workflow; and
- scheduled run.

The concurrency key includes the event type. Thus, a scheduled or reusable run cannot cancel a
pull-request, merge-group, or push run for the same revision. Manual dispatch runs the workflow
entry points as configured. The advisory Pi watch is the only job that runs exclusively for manual
dispatch or the weekly schedule.

The tracked `main` ruleset records this staged merge-queue policy:

- Use squash merges.
- Use all-green grouping.
- Permit a maximum of 10 builds in each group.
- Permit a maximum of 5 merged entries in each group.
- Require a minimum of 1 entry.
- Require a minimum wait of 5 minutes.
- Use a check timeout of 60 minutes.

The repository records only that the queue is ready. Application or activation of this policy on
GitHub is a separate rollout action. That action requires explicit authority after review and merge
of this change.

The required workflow also runs each week. Thus, dependency findings are refreshed between changes.

Tag releases require a GitHub-verified, signed, annotated Semantic Versioning (SemVer) tag. Its
version must agree with each host manifest. Its target must be reachable from protected `main`.
Release jobs then do these actions:

1. They invoke the complete required workflow.
2. They verify the exact six-file archive and SBOM set.
3. They verify the three checksum pairs in that set.
4. They parse both SPDX identities.
5. They publish only the files that passed the aggregate gate.

A release workflow never creates an artifact that did not pass the required checks.

[Issue #163](https://github.com/HomericIntelligence/Athena/issues/163) owns the protected
`agent-contract-v*` release and its live tag ruleset. Consumers must not use an agent-contract
version until that release protects the tag from deletion and retargeting.
