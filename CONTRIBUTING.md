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
revalidates the repository, builds a portable plugin archive, and publishes a GitHub release. No
Python wheel or source distribution is produced.

## Definition of done

A change is done when:

- `just all` passes locally.
- Each completion claim has runnable evidence that follows the
  [evidence integrity policy](docs/policies/evidence-integrity.md).
- Documentation and skill frontmatter follow `AGENTS.md` and the
  [development policy](docs/policies/development.md).
- Commits are signed Conventional Commits with a Developer Certificate of Origin (DCO)
  attestation.
- The pull request passes the current-head [required checks](docs/policies/required-checks.md).

## Rejection criteria

Athena rejects a pull request that does one or more of these actions:

- It introduces a duplicate skill tree.
- It makes the knowledge backend optional.
- It silently uses a fallback after an invalid dependency override.
- It fabricates evidence.
- It bypasses checks.
- It weakens permissions.
- It adds a Python distribution again.
