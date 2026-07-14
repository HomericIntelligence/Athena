# Required-check policy

Athena uses `.github/workflows/_required.yml` as the canonical merge gate. All Actions are pinned to
immutable commits with readable version comments and have minimum permissions and timeouts.

## Canonical contexts

- `forbid-suppressions`: rejects silent-failure workarounds and `continue-on-error: true`.
- `validate`: validates every skill and host manifest and runs validator tests.
- `markdownlint`: validates public documentation.
- `workflow-schema`: validates GitHub workflow syntax.
- `justfile-check`: ensures documented task entry points parse.
- `security/secrets-scan`: scans the complete Git history for secrets.
- `package`: builds and inspects the portable plugin archive; no Python artifacts are produced.
- `pr-policy`: on pull requests, enforces issue linkage when applicable, signed commits, DCO
  sign-offs, and Conventional Commit subjects.
- `required-checks-gate`: depends on every gating job and fails if any is not successful.

New gating jobs must be added to `required-checks-gate`. Advisory jobs must never be represented as
required. Branch rules should require `required-checks-gate` after the workflow has run on `main`.

Tag releases rerun validation, build the same portable archive contract, and publish a GitHub
release. A release workflow never manufactures an artifact that did not pass the required checks.
