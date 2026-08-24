# Contributing to Athena

Athena is a plugin-only distribution. Contributions change canonical skills, host manifests,
documentation, policies, validation scripts, or release automation—not a Python package.

Read [`AGENTS.md`](AGENTS.md) and the local [`development policy`](docs/policies/development.md)
before changing the repository.

## Environment setup

Prerequisites are Git, uv, Just, and Python 3.13 for repository validation only.

```bash
git clone https://github.com/HomericIntelligence/Athena
cd Athena
just bootstrap
just all
```

`just all` validates skills and manifests, runs executable unit tests, enforces at least 80% branch
coverage for every repository and skill-local executable script, runs Ruff and strict mypy over the
same tooling, lints public documentation and workflows, and builds a deterministic plugin archive
with a SHA-256 checksum. It never builds Python distribution artifacts.

## Add or change a skill

1. File or identify a tracking issue with example invocations and an output contract.
2. Create a short-lived branch from `main`.
3. Edit `skills/<name>/SKILL.md`; do not create host-specific copies or marketplace entries.
4. Put target-repository-specific examples in `references/`, keeping the executable workflow
   portable.
5. Apply the [`AGENTS.md` principle-routing rule](AGENTS.md#authoring-a-skill) against the canonical
   [`engineering principles catalog`](docs/principles/README.md).
6. Run `just all`.
7. Commit with a signed, DCO-attested Conventional Commit.
8. Open a PR. Include `Closes #N` on its own line when a tracking issue exists.

Do not enable auto-merge or merge without explicit maintainer authority.

## Required dependency changes

Mnemosyne and Hephaestus are Athena's only hard repository dependencies. Changes to their owner
resolution, fork verification, checkout paths, or failure behavior modify a trust boundary and
require focused maintainer review and validator coverage.

## Release process

After required checks pass, a maintainer creates a signed `vX.Y.Z` tag. The release workflow
revalidates the repository, builds a portable plugin archive, and publishes a GitHub release. No
Python wheel or source distribution is produced.

## Rejection criteria

Pull requests are rejected when they introduce duplicated skill trees, optionalize the knowledge
backend, silently fall back from an invalid dependency override, fabricate evidence, bypass checks,
weaken permissions, or reintroduce a Python distribution.
