# Contributing to Athena

Athena is a plugin-only distribution. Contributions change canonical skills, host manifests,
documentation, policies, validation scripts, or release automation—not a Python package.

Read [`AGENTS.md`](AGENTS.md) and the local [`development policy`](docs/policies/development.md)
before changing the repository.

## Add or change a skill

1. File or identify a tracking issue with example invocations and an output contract.
2. Create a short-lived branch from `main`.
3. Edit `skills/<name>/SKILL.md`; do not create host-specific copies or marketplace entries.
4. Put target-repository-specific examples in `references/`, keeping the executable workflow
   portable.
5. Run `just all`.
6. Commit with a signed, DCO-attested Conventional Commit.
7. Open a PR. Include `Closes #N` on its own line when a tracking issue exists.

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
