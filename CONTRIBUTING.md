# Contributing to Athena

Athena is a plugin-only distribution. Contributions can change canonical skills, host manifests,
documentation, policies, validation scripts, or release automation. They do not change a Python
package.

Before you change the repository:

1. Read [`AGENTS.md`](AGENTS.md).
2. Read the [`development policy`](docs/policies/development.md).
3. Follow the [ASD-STE100 technical-English policy](skills/TECHNICAL_ENGLISH.md) for English technical
   prose.

## Environment setup

Install Git, uv, Just, and Python 3.13. Athena uses these tools only for repository validation.

```bash
git clone https://github.com/HomericIntelligence/Athena
cd Athena
just bootstrap
just all
```

`just all` does these checks:

- It validates skills and manifests.
- It runs executable unit tests.
- It requires at least 80% branch coverage for each executable repository script and skill-local
  script.
- It runs Ruff and strict mypy on the same tools.
- It lints public documents and workflows.
- It builds a deterministic plugin archive with a SHA-256 checksum.

It does not build Python distribution artifacts.

## Add or change a skill

1. File or identify a tracking issue with example invocations and an output contract.
2. Create a short-lived branch from `main`.
3. Edit `skills/<name>/SKILL.md`.
4. Do not create host-specific copies or marketplace entries.
5. Put target-repository-specific examples in `references/`.
6. Keep the executable workflow portable.
7. Apply the [`AGENTS.md` principle-routing rule](AGENTS.md#authoring-a-skill) against the canonical
   [`engineering principles catalog`](docs/principles/README.md).
8. Apply the [ASD-STE100 technical-English policy](skills/TECHNICAL_ENGLISH.md) to all English
   technical prose.
9. Run `just all`.
10. Commit with a signed Conventional Commit that includes a Developer Certificate of Origin (DCO)
   attestation.
11. Open a pull request.
12. If a tracking issue exists, include `Closes #N` on its own line.

Do not enable auto-merge or merge without explicit maintainer authority.

## Required dependency changes

Mnemosyne and Hephaestus are Athena's only required repositories. A change to owner resolution,
fork verification, checkout paths, or failure behavior changes a trust boundary. This change
requires focused maintainer review and validator coverage.

## Release process

After required checks pass, a maintainer creates a signed `vX.Y.Z` tag. The release workflow
revalidates the repository, builds a portable plugin archive, and publishes a GitHub release. Both
publish jobs use the protected `release` environment. A maintainer must approve the environment
deployment before GitHub or npm publication starts. No Python wheel or source distribution is
produced.

Before the first release, a repository administrator must create the `release` environment in
Settings > Environments. Add at least one required reviewer and restrict deployment to the
repository's release tags (for example, `v*`). Keep the environment name exactly `release`.

If a published release is defective, use this rollback procedure:

1. Delete the GitHub release and its assets. Keep the tag for the next step:
   `gh release delete vX.Y.Z --cleanup-tag=false`.
2. Invalidate the published version by deleting the remote tag:
   `git push origin :refs/tags/vX.Y.Z`. Delete the matching local tag with `git tag -d vX.Y.Z`.
   Never re-create a version after its assets were published publicly.
3. Fix the defect on `main` through the normal pull request and merge queue process.
4. Create the next patch version as a fresh signed annotated tag on the fixed, queue-merged
   commit, then run the full release gate. For example: `vX.Y.(Z+1)`.

npm does not provide a safe, general unpublish path after its short unpublish window. Deprecate the
published package version, then publish the next patch version:
`npm deprecate athena-opencode@X.Y.Z "Defective release; use X.Y.(Z+1)"`.

## Rejection criteria

Athena rejects a pull request that does one or more of these actions:

- It introduces a duplicate skill tree.
- It makes the knowledge backend optional.
- It silently uses a fallback after an invalid dependency override.
- It fabricates evidence.
- It bypasses checks.
- It weakens permissions.
- It adds a Python distribution again.
