# Required-check policy

Athena uses `.github/workflows/_required.yml` as the canonical merge gate. All Actions are pinned to
immutable commits with readable version comments and have minimum permissions and timeouts.

## Canonical contexts

- `forbid-suppressions`: rejects silent-failure workarounds and `continue-on-error: true`.
- `validate`: validates every skill and host manifest, runs executable-script unit tests with an 80%
  repository-tooling branch-coverage floor, and enforces Ruff, formatting, and strict mypy over
  repository and skill-local scripts.
- `markdownlint`: validates public documentation.
- `workflow-schema`: validates GitHub workflow syntax.
- `justfile-check`: ensures documented task entry points parse.
- `security/secrets-scan`: scans the complete Git history for secrets.
- `package`: builds and inspects a deterministic portable plugin archive, rejects unsafe,
  generated-Python, misplaced-Python, and credential-like members, permits tested helpers only in
  skill-local script directories, and emits a SHA-256 checksum.
- `pr-policy`: on pull requests, enforces issue linkage when applicable, signed commits, DCO
  sign-offs, and Conventional Commit subjects.
- `required-checks-gate`: depends on every gating job and fails if any is not successful.

New gating jobs must be added to `required-checks-gate`. Advisory jobs must never be represented as
required. Branch rules should require `required-checks-gate` after the workflow has run on `main`.

Tag releases require a GitHub-verified signed annotated SemVer tag whose version matches every host
manifest and whose target is reachable from protected `main`. They invoke the complete required
workflow, verify the downloaded archive checksum, and publish the archive and checksum only after
the aggregate gate succeeds. A release workflow never manufactures an artifact that did not pass
the required checks.
