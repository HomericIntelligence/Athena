# Contributing to Athena

Athena is a plugin-only distribution. Contributions can change canonical skills, host manifests,
documentation, policies, validation scripts, or release automation. They do not change a Python
package.

Before you change the repository, read [`AGENTS.md`](AGENTS.md), the
[`development policy`](docs/policies/development.md), and the
[ASD-STE100 writing policy](docs/technical-english.md).

## Environment setup

Install Git, uv, Just, and Python 3.13. Athena uses these tools only for repository validation.

```bash
git clone https://github.com/HomericIntelligence/Athena
cd Athena
just bootstrap
just all
```

`just all` validates skills and manifests. It runs executable unit tests and requires at least 80%
branch coverage for each executable repository script and skill-local script. It runs Ruff and strict
mypy on the same tools. It lints public documentation and workflows. It also builds a deterministic
plugin archive with a SHA-256 checksum. It does not build Python distribution artifacts.

## Add or change a skill

1. File or identify a tracking issue with example invocations and an output contract.
2. Create a short-lived branch from `main`.
3. Edit `skills/<name>/SKILL.md`; do not create host-specific copies or marketplace entries.
4. Put target-repository-specific examples in `references/`, keeping the executable workflow
   portable.
5. Apply the [`AGENTS.md` principle-routing rule](AGENTS.md#authoring-a-skill) against the canonical
   [`engineering principles catalog`](docs/principles/README.md).
6. Apply the [ASD-STE100 writing policy](docs/technical-english.md) to all applicable prose.
7. Run `just all`.
8. Commit with a signed, DCO-attested Conventional Commit.
9. Open a PR. Include `Closes #N` on its own line when a tracking issue exists.

Do not enable auto-merge or merge without explicit maintainer authority.

## Required dependency changes

Mnemosyne and Hephaestus are Athena's only required repositories. A change to owner resolution,
fork verification, checkout paths, or failure behavior changes a trust boundary. This change
requires focused maintainer review and validator coverage.

## Release process

After required checks pass, a maintainer creates a signed `vX.Y.Z` tag. The release workflow
revalidates the repository, builds a portable plugin archive, and publishes a GitHub release. No
Python wheel or source distribution is produced.

## Rejection criteria

Pull requests are rejected when they introduce duplicated skill trees, optionalize the knowledge
backend, silently fall back from an invalid dependency override, fabricate evidence, bypass checks,
weaken permissions, or reintroduce a Python distribution.
