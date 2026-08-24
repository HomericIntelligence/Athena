# Supply-chain security

Athena publishes two checksummed SPDX 2.3 software bills of materials with each plugin archive:

- `athena-plugin-<version>.spdx.json` describes every regular file in the portable archive, the
  required `python`, `git`, and `gh` commands, and the dynamically resolved Mnemosyne and Hephaestus
  repositories.
- `athena-build-linux-64-<version>.spdx.json` describes the locked packages installed in the
  authoritative `ubuntu-24.04`/`linux-64` build environment, uv, and the immutable GitHub Actions
  used by the package job.

The locked coding-agent runtime comes from the official released `@earendil-works/pi-coding-agent`
npm artifact, pinned with an integrity hash in `ci/pi-runtime/package-lock.json` and scanned from
its shipped `npm-shrinkwrap.json`. This replaces the temporary source-commit build pin retired by
[Issue #63](https://github.com/HomericIntelligence/Athena/issues/63). The package job scans both
dependency contracts after validating the coding-harness package and
retains the native inventories for Grype. It does not scan example lockfiles or build-time compiler
binaries, which are outside the installed runtime surface. These are CI evidence rather than release
assets, and Athena never bundles those third-party packages. [Issue #74](https://github.com/HomericIntelligence/Athena/issues/74)
tracks restoring a broader source inventory when the upstream runtime remediates those excluded
inputs.

Host capabilities, the runner operating system, and commands used only in examples are outside the
dependency scope. Athena remains a plugin distribution and does not add a Python package or runtime
dependency for SBOM generation.

The package job generates both documents with the locked Syft version, replaces volatile timestamps
and namespaces with commit- and content-derived values, sorts the SPDX content, verifies complete
archive-file coverage, and emits SHA-256 checksum files. Native Syft JSON is retained only as an
internal CI artifact because it preserves the package metadata Grype needs; it is not a release
asset. The build SPDX preserves Syft's package-to-file evidence and unambiguous dependency
relationships. When multiple installed packages share a name, Athena omits Syft's nondeterministic
dependency guess for that name instead of publishing an arbitrary version relationship; every
installed package remains represented as a build-environment dependency.

## Vulnerability policy

The required `security/dependency-scan` job scans both native inventories—the Linux build environment
and the isolated coding-harness runtime—with the locked Grype version. Scanner, database, configuration, or
report failures block the gate. The database must pass its hash check, be no more than 120 hours old,
and complete an update check.

Fixable Critical and High findings block the gate. Unfixed Critical and High findings and all lower
severities remain visible in the retained full JSON report but are non-blocking. Vulnerability
matching relies on cross-ecosystem identifiers and can be incomplete; the scheduled weekly run
keeps the same policy visible between repository changes.

Exceptions in `security/vulnerability-exceptions.yaml` must identify one vulnerability, package,
installed version, and severity, plus a reason, owner, open Athena GitHub issue, approval date, and
expiry date. The scan verifies the linked issue through GitHub and fails closed when it is missing,
inaccessible, closed, or outside Athena. Critical exceptions may last at most 7 days from approval
and High exceptions at most 30 days from approval. Broad, malformed, expired, future-approved, or
version-mismatched exceptions fail closed. Extending an exception requires a new recorded approval
rather than moving its expiry relative to the current scan date.

Run `just sbom` on Linux after `uv sync --locked` and installing the CI-pinned Syft binary on
`PATH`; the generator fails on other hosts rather than mislabeling their environment as the
authoritative `linux-64` build. Run `just sca` after installing the CI-pinned Grype binary on
`PATH` to scan the resulting internal inventory with the current vulnerability database. The
latter is an explicit network-backed security operation and is therefore not part of `just all`.
