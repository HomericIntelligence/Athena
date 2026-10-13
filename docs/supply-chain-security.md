# Supply-chain security

Apply the [ASD-STE100 technical-English policy](../skills/TECHNICAL_ENGLISH.md) to all English technical prose
in this document.

Athena publishes two checksummed Software Package Data Exchange (SPDX) 2.3 software bills of
materials (SBOMs) with each plugin archive:

- `athena-plugin-<version>.spdx.json` describes each regular file in the portable archive. It also
  describes these dependencies:

  - the required `python` and `git` commands and the GitHub CLI (`gh`); and
  - the dynamically resolved Mnemosyne and Hephaestus repositories.

- `athena-build-linux-64-<version>.spdx.json` describes these build inputs:

  - the locked packages installed in the authoritative `ubuntu-24.04` and `linux-64` build
    environment;
  - uv; and
  - the immutable GitHub Actions that the package job uses.

The locked coding-agent runtime comes from the official released
`@earendil-works/pi-coding-agent` npm artifact. An integrity hash in
`ci/pi-runtime/package-lock.json` pins the artifact. Athena scans its shipped
`npm-shrinkwrap.json`.

[Issue #63](https://github.com/HomericIntelligence/Athena/issues/63) retired the temporary
source-commit build pin. The locked runtime replaces that pin. The package job first validates the
coding-harness package. It then scans both dependency contracts. The job retains the native
inventories for Grype.

[Issue #74](https://github.com/HomericIntelligence/Athena/issues/74) tracks the restoration of the
full Pi source inventory. The job does not scan example lockfiles or build-time compiler binaries.
These items are not in the installed runtime surface. The native inventories are continuous
integration (CI) evidence and not release assets. Athena never includes those third-party packages
in its archive.
The advisory `security/pi-upstream-inventory-watch` job scans the full upstream Pi source tree each
week with the same Syft and Grype policy. It keeps a separate record for upstream inventory
evidence for tracking only. It does not change `required-checks-gate` or the shipped dependency
contract. A failure of this job means upstream still ships an unremediated non-runtime dependency.
Its first successful run gives the automated signal that restoration is permitted.

Host capabilities, the runner operating system, and commands used only in examples are outside the
dependency scope. Athena remains a plugin distribution. It does not add a Python package or runtime
dependency for SBOM generation.

The package job uses the locked Syft version to generate both documents. It then does these actions:

- It replaces volatile timestamps and namespaces with values derived from the commit and content.
- It sorts the SPDX content.
- It verifies complete coverage of archive files.
- It emits SHA-256 checksum files.

The job retains native Syft JavaScript Object Notation (JSON) only as an internal CI artifact. This
format keeps the package metadata that Grype requires. It is not a release asset. The build SPDX
keeps the Syft evidence that links packages to files. It also keeps unambiguous dependency
relationships.

Multiple installed packages can have the same name. In this condition, Athena omits the
nondeterministic Syft dependency guess for that name. It does not publish an arbitrary version
relationship. Each installed package remains a build-environment dependency.

## Restoring the full Pi source inventory

Restoration stays dormant until each step below is permitted. The pull request that restores the
full inventory closes [Issue #74](https://github.com/HomericIntelligence/Athena/issues/74).

1. Confirm that a `security/pi-upstream-inventory-watch` run against upstream `main` is
   successful. A red run means upstream still ships a vulnerable non-runtime dependency.
2. Update the pinned `@earendil-works/pi-coding-agent` version in `ci/pi-runtime/package-lock.json`
   to a released upstream artifact that contains the remediated files.
3. In the `package` job, replace the coding-agent shrinkwrap scan in
   `.github/workflows/_required.yml` with a Syft scan of the full Pi source root. Keep the
   `syft-pi-subagents.json` inventory of the isolated runtime.
4. Update the workflow assertions in `tests/unit/test_supply_chain.py` for the new scan target and
   inventory name.
5. Remove the `security/pi-upstream-inventory-watch` job, the `workflow_dispatch` trigger that only
   it needs, and the advisory record in `docs/policies/required-checks.md`.

The restored required scan must pass with zero new entries in
`security/vulnerability-exceptions.yaml`. Do not lower a scanner threshold, suppress a finding, or
add a broad ignore. A residual finding goes through the narrow exception policy only.

## Vulnerability policy

The required `security/dependency-scan` job scans both native inventories:

- the Linux build environment; and
- the isolated coding-harness runtime.

It uses the locked Grype version. A scanner, database, configuration, or report failure blocks the
gate. The database must meet these requirements:

- Its hash check passes.
- It is not more than 120 hours old.
- It completes an update check.

Fixable Critical and High findings block the gate. Unfixed Critical and High findings remain in the
retained full JSON report. All lower-severity findings also remain in that report. These findings do
not block the gate.

Vulnerability matching uses identifiers from different ecosystems. Thus, the matches can be
incomplete. The scheduled weekly run keeps the same policy visible between repository changes.

Each entry in `security/vulnerability-exceptions.yaml` must identify these values:

- one vulnerability;
- one package;
- one installed version;
- one severity;
- a reason;
- an owner;
- an open Athena GitHub issue;
- an approval date; and
- an expiry date.

The scan verifies the linked issue through GitHub. It fails closed if the issue is missing,
inaccessible, closed, or outside Athena. A Critical exception can last for a maximum of 7 days from
approval. A High exception can last for a maximum of 30 days from approval.

The linked issue must stay open for the whole lifetime of the exception. Close the linked issue only
when its entries leave `security/vulnerability-exceptions.yaml`. Do not add a `Closes` line to a pull
request that edits that file, because it closes the tracking issue of the entries it writes.

The scan fails closed for these exception conditions:

- broad scope;
- malformed content;
- an expired date;
- a future approval date; or
- an installed version that does not agree with the exception.

To extend an exception, get a new recorded approval. Do not move its expiry relative to the current
scan date.

To run `just sbom`, use these steps:

1. Use Linux.
2. Run `uv sync --locked`.
3. Install the CI-pinned Syft binary on `PATH`.
4. Run `just sbom`.

On other hosts, the generator stops. Thus, it does not incorrectly label another environment as the
authoritative `linux-64` build.

To run software composition analysis (SCA) with `just sca`, use these steps:

1. Install the CI-pinned Grype binary on `PATH`.
2. Make sure that the vulnerability database is current.
3. Run `just sca` to scan the resultant internal inventory.

The `just sca` command is an explicit network-backed security operation. Thus, it is not part of
`just all`.
