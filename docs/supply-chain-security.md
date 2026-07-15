# Supply-chain security

Athena publishes two checksummed SPDX 2.3 software bills of materials with each plugin archive:

- `athena-plugin-<version>.spdx.json` describes every regular file in the portable archive, the
  required `python`, `git`, and `gh` commands, and the dynamically resolved Mnemosyne and Hephaestus
  repositories.
- `athena-build-linux-64-<version>.spdx.json` describes the locked packages installed in the
  authoritative `ubuntu-24.04`/`linux-64` build environment, Pixi, and the immutable GitHub Actions
  used by the package job.

Host capabilities, the runner operating system, and commands used only in examples are outside the
dependency scope. Athena remains a plugin distribution and does not add a Python package or runtime
dependency for SBOM generation.

The package job generates both documents with the locked Syft version, replaces volatile timestamps
and namespaces with commit- and content-derived values, sorts the SPDX content, verifies complete
archive-file coverage, and emits SHA-256 checksum files. Native Syft JSON is retained only as an
internal CI artifact because it preserves the package metadata Grype needs; it is not a release
asset.

## Vulnerability policy

The required `security/dependency-scan` job scans the native Linux build-environment inventory with
the locked Grype version. Scanner, database, configuration, or report failures block the gate. The
database must pass its hash check, be no more than 120 hours old, and complete an update check.

Fixable Critical and High findings block the gate. Unfixed Critical and High findings and all lower
severities remain visible in the retained full JSON report but are non-blocking. Conda vulnerability
matching relies on cross-ecosystem identifiers and can be incomplete; the scheduled weekly run
keeps the same policy visible between repository changes.

Exceptions in `security/vulnerability-exceptions.yaml` must identify one vulnerability, package,
installed version, and severity, plus a reason, owner, GitHub issue, and expiry date. Critical
exceptions may last at most 7 days and High exceptions at most 30 days. Broad, malformed, expired,
or version-mismatched exceptions fail closed.

Run `just sbom` on Linux after installing the locked default and security Pixi environments; the
generator fails on other hosts rather than mislabeling their environment as the authoritative
`linux-64` build. Run `just sca` to scan the resulting internal inventory with the current
vulnerability database. The latter is an explicit network-backed security operation and is
therefore not part of `just all`.
