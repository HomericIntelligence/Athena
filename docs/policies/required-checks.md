# Required-check policy

Athena uses `.github/workflows/_required.yml` as the canonical merge gate. All Actions are pinned to
immutable commits with readable version comments and have minimum permissions and timeouts.

## Canonical contexts

- `forbid-suppressions`: rejects silent-failure workarounds and `continue-on-error: true`.
- `validate`: validates every skill and host manifest, runs executable-script unit tests with an 80%
  per-script branch-coverage floor, and enforces Ruff, formatting, and strict mypy over repository
  and skill-local scripts.
- `markdownlint`: validates public documentation and the shipped `skills/**/*.md` product corpus.
- `workflow-schema`: validates GitHub workflow syntax.
- `justfile-check`: ensures documented task entry points parse.
- `security/secrets-scan`: scans the complete Git history for secrets.
- `package`: builds and inspects a deterministic portable plugin archive, rejects unsafe,
  generated-Python, misplaced-Python, and credential-like members, ignores Python cache directories,
  permits tested helpers in skill-local script directories plus the shared `skills/_cli.py` factory,
  emits a SHA-256 checksum, and generates checksummed plugin and Linux build-environment SPDX 2.3
  SBOMs plus the internal native Syft inventory used for vulnerability analysis.
- `security/dependency-scan`: scans the internal inventory with a locked Grype version and current,
  hash-validated database; blocks fixable Critical and High findings unless covered by a narrow,
  owned, linked, unexpired exception whose Athena issue is still open; and retains the full JSON
  report.
- `pr-policy`: on pull requests, enforces issue linkage when applicable, signed commits, DCO
  sign-offs, and Conventional Commit subjects.
- `required-checks-gate`: depends on every gating job and fails if any is not successful.

New gating jobs must be added to `required-checks-gate`. Advisory jobs must never be represented as
required. The tracked and live main ruleset require `required-checks-gate` to pass against the
current `main` base before merge.

The required workflow also runs weekly so dependency findings are refreshed between changes. Tag
releases require a GitHub-verified signed annotated SemVer tag whose version matches every host
manifest and whose target is reachable from protected `main`. They invoke the complete required
workflow, verify the exact six-file archive/SBOM set and its three checksum pairs, parse both SPDX
identities, and publish those already-gated files only after the aggregate gate succeeds. A release
workflow never manufactures an artifact that did not pass the required checks.
